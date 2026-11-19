"""Transactional run state, fenced work ownership, event history and review."""

import hashlib
import json
import time
import uuid

from sqlalchemy import (
    JSON,
    Column,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
    insert,
    inspect,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError

from devmind.contracts import RunRequest

metadata = MetaData()
SCHEMA_VERSION = 1
schema_version = Table(
    "schema_version",
    metadata,
    Column("singleton", Integer, primary_key=True),
    Column("version", Integer, nullable=False),
)
runs = Table(
    "runs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("request_key", String(128), unique=True, nullable=False),
    Column("fingerprint", String(64), nullable=False),
    Column("request", JSON, nullable=False),
    Column("status", String(24), nullable=False),
    Column("phase", String(24), nullable=False),
    Column("owner", String(36)),
    Column("lease", Float),
    Column("created", Float, nullable=False),
    Column("updated", Float, nullable=False),
    Column("result", JSON),
    Column("review", JSON),
)
events = Table(
    "events",
    metadata,
    Column("sequence", Integer, primary_key=True, autoincrement=True),
    Column("run_id", String(36), ForeignKey("runs.id"), nullable=False),
    Column("at", Float, nullable=False),
    Column("kind", String(40), nullable=False),
    Column("payload", JSON, nullable=False),
)
artifacts = Table(
    "artifacts",
    metadata,
    Column("run_id", String(36), ForeignKey("runs.id"), primary_key=True),
    Column("name", String(40), primary_key=True),
    Column("sha256", String(64), nullable=False),
    Column("content", Text, nullable=False),
)
Index("run_queue", runs.c.status, runs.c.created)
Index("run_events", events.c.run_id, events.c.sequence)
Index("run_leases", runs.c.status, runs.c.lease)


def database_time(conn) -> float:
    """PostgreSQL lease comparisons use one database clock across worker hosts."""
    if conn.dialect.name == "postgresql":
        return float(conn.scalar(select(func.extract("epoch", func.clock_timestamp()))))
    return time.time()


class Rejected(ValueError):
    """A conflicting request or invalid state transition."""


class Repository:
    def __init__(self, url: str):
        self.engine = create_engine(
            url,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False, "timeout": 15}
            if url.startswith("sqlite")
            else {"connect_timeout": 5},
        )

    def initialize(self) -> None:
        """Apply baseline migration; reject unknown versions or incompatible tables."""
        with self.engine.begin() as conn:
            if conn.dialect.name == "postgresql":
                conn.exec_driver_sql("SELECT pg_advisory_xact_lock(7419022)")
            elif conn.dialect.name == "sqlite":
                conn.exec_driver_sql("BEGIN IMMEDIATE")
            inspector = inspect(conn)
            existing = set(inspector.get_table_names())
            if "schema_version" in existing:
                recorded = conn.scalar(select(schema_version.c.version))
                if recorded is not None and recorded != SCHEMA_VERSION:
                    raise RuntimeError("Unsupported database schema version")
            for table in (runs, events, artifacts):
                if table.name in existing:
                    columns = {c["name"] for c in inspector.get_columns(table.name)}
                    if columns != set(table.c.keys()):
                        raise RuntimeError("Incompatible existing database schema")
            metadata.create_all(conn)
            if conn.scalar(select(schema_version.c.version)) is None:
                conn.execute(
                    insert(schema_version).values(singleton=1, version=SCHEMA_VERSION)
                )
        if self.engine.dialect.name == "sqlite":
            with self.engine.connect() as conn:
                conn.exec_driver_sql("PRAGMA journal_mode=WAL")

    def check_schema(self) -> None:
        with self.engine.connect() as conn:
            if conn.scalar(select(schema_version.c.version)) != SCHEMA_VERSION:
                raise RuntimeError("Run devmind init with a compatible release")

    def submit(self, body: RunRequest, key: str, capacity: int) -> tuple[str, bool]:
        data = body.model_dump()
        fingerprint = hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()
        identifier = str(uuid.uuid4())
        try:
            with self.engine.begin() as conn:
                if self.engine.dialect.name == "sqlite":
                    conn.exec_driver_sql("BEGIN IMMEDIATE")
                elif self.engine.dialect.name == "postgresql":
                    conn.exec_driver_sql("SELECT pg_advisory_xact_lock(7419021)")
                existing = (
                    conn.execute(select(runs).where(runs.c.request_key == key))
                    .mappings()
                    .first()
                )
                if existing:
                    if existing["fingerprint"] != fingerprint:
                        raise Rejected(
                            "Idempotency key already belongs to another request"
                        )
                    return existing["id"], False
                pending = conn.scalar(
                    select(func.count())
                    .select_from(runs)
                    .where(runs.c.status.in_(["queued", "active"]))
                )
                if pending >= capacity:
                    raise Rejected("Queue capacity reached")
                now = database_time(conn)
                conn.execute(
                    insert(runs).values(
                        id=identifier,
                        request_key=key,
                        fingerprint=fingerprint,
                        request=data,
                        status="queued",
                        phase="queued",
                        created=now,
                        updated=now,
                    )
                )
                self._event(conn, identifier, "queued", {"title": body.title})
        except IntegrityError:
            # A concurrent identical request won the unique-key race.
            with self.engine.connect() as conn:
                row = (
                    conn.execute(select(runs).where(runs.c.request_key == key))
                    .mappings()
                    .first()
                )
            if row and row["fingerprint"] == fingerprint:
                return row["id"], False
            raise Rejected("Idempotency conflict") from None
        return identifier, True

    @staticmethod
    def _event(conn, identifier: str, kind: str, payload: dict) -> None:
        conn.execute(
            insert(events).values(
                run_id=identifier, at=database_time(conn), kind=kind, payload=payload
            )
        )

    def claim(self, owner: str, seconds: int) -> dict | None:
        with self.engine.begin() as conn:
            now = database_time(conn)
            expired = (
                conn.execute(
                    update(runs)
                    .where(runs.c.status == "active", runs.c.lease < now)
                    .values(
                        status="interrupted",
                        phase="interrupted",
                        owner=None,
                        lease=None,
                        updated=now,
                    )
                    .returning(runs.c.id)
                )
                .scalars()
                .all()
            )
            for expired_id in expired:
                self._event(
                    conn, expired_id, "interrupted", {"reason": "Lease expired"}
                )
            query = (
                select(runs.c.id)
                .where(runs.c.status == "queued")
                .order_by(runs.c.created)
                .limit(1)
            )
            if self.engine.dialect.name == "postgresql":
                query = query.with_for_update(skip_locked=True)
            identifier = conn.scalar(query)
            if not identifier:
                return None
            claimed = conn.execute(
                update(runs)
                .where(runs.c.id == identifier, runs.c.status == "queued")
                .values(
                    status="active",
                    phase="preparing",
                    owner=owner,
                    lease=now + seconds,
                    updated=now,
                )
            )
            if claimed.rowcount != 1:
                return None
            self._event(conn, identifier, "claimed", {"phase": "preparing"})
        return self.get(identifier)

    def get(self, identifier: str) -> dict | None:
        with self.engine.connect() as conn:
            row = (
                conn.execute(select(runs).where(runs.c.id == identifier))
                .mappings()
                .first()
            )
            return dict(row) if row else None

    def listing(self, limit: int = 100) -> list[dict]:
        with self.engine.connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    select(runs).order_by(runs.c.created.desc()).limit(limit)
                ).mappings()
            ]

    def alive(self, identifier: str, owner: str, renew: int = 0) -> bool:
        with self.engine.begin() as conn:
            condition = (
                runs.c.id == identifier,
                runs.c.owner == owner,
                runs.c.status == "active",
                runs.c.lease > database_time(conn),
            )
            if renew:
                return (
                    conn.execute(
                        update(runs)
                        .where(*condition)
                        .values(lease=database_time(conn) + renew)
                    ).rowcount
                    == 1
                )
            return conn.scalar(select(runs.c.id).where(*condition)) is not None

    def emit(
        self,
        identifier: str,
        owner: str,
        kind: str,
        payload: dict,
        phase: str | None = None,
    ) -> bool:
        with self.engine.begin() as conn:
            touched = conn.execute(
                update(runs)
                .where(
                    runs.c.id == identifier,
                    runs.c.owner == owner,
                    runs.c.status == "active",
                    runs.c.lease > database_time(conn),
                )
                .values(
                    updated=database_time(conn), **({"phase": phase} if phase else {})
                )
            )
            if touched.rowcount != 1:
                return False
            self._event(conn, identifier, kind, payload)
            return True

    def complete(
        self, identifier: str, owner: str, status: str, result: dict, patch: str = ""
    ) -> bool:
        if status not in {"review", "failed"}:
            raise ValueError("invalid completion status")
        with self.engine.begin() as conn:
            touched = conn.execute(
                update(runs)
                .where(
                    runs.c.id == identifier,
                    runs.c.owner == owner,
                    runs.c.status == "active",
                    runs.c.lease > database_time(conn),
                )
                .values(
                    status=status,
                    phase=status,
                    result=result,
                    owner=None,
                    lease=None,
                    updated=database_time(conn),
                )
            )
            if touched.rowcount != 1:
                return False
            conn.execute(
                insert(artifacts).values(
                    run_id=identifier,
                    name="patch",
                    sha256=hashlib.sha256(patch.encode()).hexdigest(),
                    content=patch,
                )
            )
            self._event(conn, identifier, status, result)
            return True

    def cancel(self, identifier: str) -> bool:
        with self.engine.begin() as conn:
            result = conn.execute(
                update(runs)
                .where(runs.c.id == identifier, runs.c.status.in_(["queued", "active"]))
                .values(
                    status="cancelled",
                    phase="cancelled",
                    owner=None,
                    lease=None,
                    updated=database_time(conn),
                )
            )
            if result.rowcount:
                self._event(conn, identifier, "cancelled", {})
            return result.rowcount == 1

    def review(self, identifier: str, decision: str, note: str) -> bool:
        if decision not in {"approved", "rejected"}:
            raise ValueError("invalid review decision")
        with self.engine.begin() as conn:
            result = conn.execute(
                update(runs)
                .where(runs.c.id == identifier, runs.c.status == "review")
                .values(
                    status=decision,
                    phase=decision,
                    review={"note": note, "at": database_time(conn)},
                    updated=database_time(conn),
                )
            )
            if result.rowcount:
                self._event(conn, identifier, decision, {"note": note})
            return result.rowcount == 1

    def timeline(
        self, identifier: str, cursor: int = 0, limit: int = 200
    ) -> list[dict]:
        with self.engine.connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    select(events)
                    .where(events.c.run_id == identifier, events.c.sequence > cursor)
                    .order_by(events.c.sequence)
                    .limit(limit)
                ).mappings()
            ]

    def artifact(self, identifier: str, name: str) -> dict | None:
        with self.engine.connect() as conn:
            row = (
                conn.execute(
                    select(artifacts).where(
                        artifacts.c.run_id == identifier, artifacts.c.name == name
                    )
                )
                .mappings()
                .first()
            )
            return dict(row) if row else None
