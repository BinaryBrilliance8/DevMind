"""Generate clearly labelled synthetic DevMind dashboard data."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)

run_id = "demo_sample"

summary = {
    "run_id": run_id,
    "task": "DEMO ONLY: synthetic sample run",
    "exit_status": "Submitted",
    "resolved": True,
    "total_steps": 3,
    "total_cost": 0.012,
    "total_wall_time_seconds": 8.4,
    "api_calls": 3,
    "synthetic": True,
}

steps = [
    {
        "step_index": 1,
        "elapsed_seconds": 2.1,
        "cumulative_cost": 0.004,
        "n_calls_so_far": 1,
        "consecutive_format_errors": 0,
        "last_role": "assistant",
    },
    {
        "step_index": 2,
        "elapsed_seconds": 3.0,
        "cumulative_cost": 0.008,
        "n_calls_so_far": 2,
        "consecutive_format_errors": 0,
        "last_role": "assistant",
    },
    {
        "step_index": 3,
        "elapsed_seconds": 3.3,
        "cumulative_cost": 0.012,
        "n_calls_so_far": 3,
        "consecutive_format_errors": 0,
        "last_role": "assistant",
    },
]

(LOGS / f"{run_id}_summary.json").write_text(
    json.dumps(summary, indent=2), encoding="utf-8"
)
(LOGS / f"{run_id}_steps.json").write_text(
    json.dumps(steps, indent=2), encoding="utf-8"
)

index_path = LOGS / "index.json"
index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else []
index = [row for row in index if row.get("run_id") != run_id]
index.append(summary)
index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")

print("Synthetic demo data created in logs/. No API call was made.")
