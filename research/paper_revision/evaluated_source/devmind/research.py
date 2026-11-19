"""Benchmark intake and repository-separated supervised training examples."""

import argparse
import hashlib
import json
from pathlib import Path

from devmind.config import load
from devmind.contracts import RunRequest
from devmind.database import Repository
from devmind.model import initial_messages


def intake(
    path: Path, mapping: dict, repository: Repository, config, experiment: str
) -> list[str]:
    requests = []
    seen = set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row["instance_id"] in seen:
            raise ValueError("Duplicate dataset instance")
        seen.add(row["instance_id"])
        key = mapping[row["repo"]]
        config.project(key)
        # Gold patch, test_patch and all other dataset fields are intentionally omitted.
        requests.append(
            RunRequest(
                project=key,
                title=row["instance_id"],
                issue=row["problem_statement"],
                commit=row["base_commit"],
                benchmark_id=row["instance_id"],
            )
        )
    return [
        repository.submit(
            request,
            hashlib.sha256(
                f"{experiment}:{request.benchmark_id}:{request.commit}".encode()
            ).hexdigest(),
            config.capacity,
        )[0]
        for request in requests
    ]


def supervised_examples(record: dict) -> list[dict]:
    run = record["run"]
    if run["status"] != "approved":
        raise ValueError("Only human-approved trajectories are eligible")
    request, result = run["request"], run["result"]
    policy = {
        "protected": result["protected"],
        "verification_argv": result["test_command"],
        "commit": result["commit"],
    }
    history = initial_messages(request["issue"], policy)
    examples = []
    for event in record["events"]:
        kind, payload = event["kind"], event["payload"]
        if kind == "baseline":
            history.append(
                {
                    "role": "user",
                    "content": "Baseline test evidence: " + json.dumps(payload),
                }
            )
        elif kind == "action":
            target = json.dumps(payload["action"])
            examples.append(
                {
                    "project": request["project"],
                    "run_id": run["id"],
                    "prompt": list(history),
                    "completion": target,
                    "quality": "Human-approved trajectory; step review required",
                }
            )
            history.append({"role": "assistant", "content": target})
        elif kind == "observation":
            history.append(
                {"role": "user", "content": json.dumps(payload["observation"])}
            )
    return examples


def prepare(input_path: Path, output: Path, holdout: set[str]) -> dict:
    if not holdout:
        raise ValueError("Explicit held-out repository keys are required")
    train, validation, seen = [], [], set()
    for line in input_path.read_text().splitlines():
        if not line.strip():
            continue
        for example in supervised_examples(json.loads(line)):
            digest = hashlib.sha256(
                json.dumps(example["prompt"], sort_keys=True).encode()
                + example["completion"].encode()
            ).hexdigest()
            if digest in seen:
                continue
            seen.add(digest)
            (validation if example["project"] in holdout else train).append(example)
    output.mkdir(parents=True, exist_ok=True)
    for name, rows in [("train", train), ("validation", validation)]:
        (output / f"{name}.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows)
        )
        (output / f"{name}.jsonl").chmod(0o600)
    report = {
        "training_examples": len(train),
        "validation_examples": len(validation),
        "holdout_projects": sorted(holdout),
        "source_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="DevMind research-data utilities")
    commands = parser.add_subparsers(dest="command", required=True)
    import_command = commands.add_parser("import-benchmark")
    import_command.add_argument("input", type=Path)
    import_command.add_argument("--mapping", type=Path, required=True)
    import_command.add_argument("--experiment", required=True)
    preparation = commands.add_parser("prepare-training")
    preparation.add_argument("input", type=Path)
    preparation.add_argument("--output", type=Path, required=True)
    preparation.add_argument("--holdout", nargs="+", required=True)
    args = parser.parse_args()
    if args.command == "prepare-training":
        print(json.dumps(prepare(args.input, args.output, set(args.holdout)), indent=2))
    else:
        config = load()
        repository = Repository(config.database)
        print(
            json.dumps(
                intake(
                    args.input,
                    json.loads(args.mapping.read_text()),
                    repository,
                    config,
                    args.experiment,
                )
            )
        )


if __name__ == "__main__":
    main()
