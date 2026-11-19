"""Explicit, bounded dependency probes; no credentials in diagnostic results."""

import shutil

import httpx
from sqlalchemy import select

from devmind.config import Config
from devmind.database import Repository, runs
from devmind.operations import execute, git


def inspect(config: Config, repository: Repository, execution: bool = True) -> dict:
    checks = {}
    try:
        repository.check_schema()
        with repository.engine.connect() as conn:
            conn.execute(select(runs.c.id).limit(1))
        checks["database"] = {"ready": True}
    except Exception:
        checks["database"] = {"ready": False, "reason": "Database/schema unavailable"}
    checks["console"] = {
        "ready": all(
            (config.web / f).is_file() for f in ("index.html", "app.js", "style.css")
        )
    }
    if execution:
        checks["projects"] = {"ready": bool(config.projects)}
        for project in config.projects:
            try:
                git(project.checkout, ["rev-parse", "--verify", "HEAD^{commit}"])
                checks["repository:" + project.key] = {"ready": True}
            except Exception:
                checks["repository:" + project.key] = {"ready": False}
        available = shutil.which("docker") is not None
        if available:
            outcome, _ = execute(["docker", "info"], deadline=5, limit=65536)
            available = not (outcome.code or outcome.timeout or outcome.overflow)
        checks["docker"] = {"ready": available}
        for name in sorted({p.image for p in config.projects}):
            ready = False
            if available:
                outcome, _ = execute(
                    ["docker", "image", "inspect", name], deadline=5, limit=65536
                )
                ready = not (outcome.code or outcome.timeout or outcome.overflow)
            checks["image:" + name] = {"ready": ready}
        ready = False
        if config.model:
            headers = (
                {"Authorization": "Bearer " + config.model_key}
                if config.model_key
                else {}
            )
            try:
                with httpx.Client(timeout=5, trust_env=False) as client:
                    with client.stream(
                        "GET", config.model_url.rstrip("/") + "/models", headers=headers
                    ) as response:
                        ready = response.status_code == 200
            except httpx.HTTPError:
                pass
        checks["model"] = {
            "ready": ready,
            "note": "Catalog reachability only; run a completion to verify inference",
        }
    return {"ready": all(c["ready"] for c in checks.values()), "checks": checks}
