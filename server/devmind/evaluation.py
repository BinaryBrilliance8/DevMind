"""Launch the official SWE-bench harness with a unique, auditable attempt directory."""

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path


def validate_predictions(path: Path) -> list[dict]:
    rows, seen, models = [], set(), set()
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if set(row) != {"instance_id", "model_name_or_path", "model_patch"}:
            raise ValueError("Use canonical SWE-bench prediction fields")
        if not all(isinstance(value, str) for value in row.values()):
            raise ValueError("Prediction values must be strings")
        identifier = row["instance_id"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", identifier):
            raise ValueError("Invalid instance ID")
        model = row["model_name_or_path"]
        if not model or any(c in model for c in "\n\r\0"):
            raise ValueError("Invalid model identifier")
        if identifier in seen:
            raise ValueError("Duplicate instance ID")
        seen.add(identifier)
        models.add(model)
        rows.append(row)
    if not rows or len(models) != 1:
        raise ValueError("Evaluate one model and at least one instance per attempt")
    return rows


def evaluate(predictions: Path, output: Path, dataset: str, workers: int) -> int:
    if workers < 1 or workers > 32:
        raise ValueError("workers must be between 1 and 32")
    rows = validate_predictions(predictions)
    if importlib.util.find_spec("swebench") is None:
        raise RuntimeError("Install the official swebench package in this environment")
    # A new directory prevents stale cached reports from masquerading as new results.
    output.mkdir(parents=True, exist_ok=False)
    output = output.resolve()
    copied = output / "predictions.jsonl"
    copied.write_text("".join(json.dumps(row) + "\n" for row in rows))
    copied.chmod(0o600)
    run_id = "devmind-" + uuid.uuid4().hex
    command = [
        sys.executable,
        "-m",
        "swebench.harness.run_evaluation",
        "--dataset_name",
        dataset,
        "--predictions_path",
        str(copied),
        "--max_workers",
        str(workers),
        "--run_id",
        run_id,
        "--instance_ids",
        *[row["instance_id"] for row in rows],
    ]
    manifest = {
        "run_id": run_id,
        "dataset": dataset,
        "harness_version": importlib.metadata.version("swebench"),
        "prediction_sha256": hashlib.sha256(copied.read_bytes()).hexdigest(),
        "submitted_ids": [row["instance_id"] for row in rows],
        "command": command,
        "status": "running",
        "note": "Inspect official reports; completion is not a resolution score",
    }
    record = output / "evaluation-manifest.json"
    record.write_text(json.dumps(manifest, indent=2) + "\n")
    try:
        # Inherit the terminal for live progress; the harness writes detailed logs.
        completed = subprocess.run(command, cwd=output, check=False)
        manifest.update(
            status="completed" if completed.returncode == 0 else "failed",
            exit_code=completed.returncode,
        )
    except BaseException:
        manifest["status"] = "interrupted"
        raise
    finally:
        record.write_text(json.dumps(manifest, indent=2) + "\n")
    return completed.returncode


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("predictions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset", default="princeton-nlp/SWE-bench_Lite")
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    raise SystemExit(
        evaluate(args.predictions, args.output, args.dataset, args.workers)
    )


if __name__ == "__main__":
    main()
