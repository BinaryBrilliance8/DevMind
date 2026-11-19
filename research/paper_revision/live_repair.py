"""Run real-model repairs only through the production Docker/SQL pipeline."""

import argparse
import json
import os
import uuid
from dataclasses import replace
from pathlib import Path

from devmind.config import load
from devmind.contracts import RunRequest
from devmind.database import Repository
from devmind.readiness import inspect
from devmind.runner import Runner


def run(output: Path, database: str, tasks: Path) -> int:
    os.umask(0o077)
    output.mkdir(parents=True, exist_ok=False)
    config = replace(load(), database=database)
    repository = Repository(database)
    try:
        repository.initialize()
        if repository.listing(1):
            raise ValueError(
                "Use a new dedicated evaluation database with no prior runs"
            )
        requests = [
            RunRequest.model_validate(json.loads(line))
            for line in tasks.read_text().splitlines()
            if line.strip()
        ]
        if not requests:
            raise ValueError("No evaluation tasks")
        for request in requests:
            config.project(request.project)
        readiness = inspect(config, repository)
        (output / "preflight.json").write_text(json.dumps(readiness, indent=2) + "\n")
        if not readiness["ready"]:
            print("Execution blocked: inspect preflight.json; no host fallback used")
            return 2
        results = []
        runner = Runner(config, repository)
        for request in requests:
            identifier, _ = repository.submit(
                request, "evaluation-" + uuid.uuid4().hex, config.capacity
            )
            runner.once()
            row = repository.get(identifier)
            events, cursor = [], 0
            while page := repository.timeline(identifier, cursor):
                events.extend(page)
                cursor = page[-1]["sequence"]
            artifact = repository.artifact(identifier, "patch")
            record = {
                "id": identifier,
                "request": request.model_dump(),
                "status": row["status"],
                "result": row["result"],
                "events": events,
                "patch": artifact["content"] if artifact else "",
            }
            (output / f"{identifier}.json").write_text(
                json.dumps(record, indent=2) + "\n"
            )
            results.append({"id": identifier, "status": row["status"]})
        (output / "summary.json").write_text(
            json.dumps(
                {
                    "runs": results,
                    "claim": "Local verification only. Human review and independent "
                    "hidden-test grading remain separate.",
                },
                indent=2,
            )
            + "\n"
        )
        return 0
    finally:
        repository.engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--database", required=True, help="New dedicated SQLAlchemy database URL"
    )
    parser.add_argument("--tasks", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(run(args.output, args.database, args.tasks))
