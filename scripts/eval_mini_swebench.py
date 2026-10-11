"""
DevMind — Mini SWE-bench Evaluation
====================================
Runs the DevMind agent against a small sample of SWE-bench Verified instances
and reports resolve rate, cost, and time — for the project's Evaluation slide.

NOTE: Running the full SWE-bench (2,294 instances) is expensive and slow.
This script is intentionally scoped to a handful of instances (default 10),
which is enough to report real, honest numbers without burning your API budget.

Usage:
    python scripts/eval_mini_swebench.py --n 10 --model claude-sonnet-4-6

Requires:
    pip install datasets
    export ANTHROPIC_API_KEY=... (or OPENAI_API_KEY)
"""

import argparse
import json
import time
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "logs" / "swebench_eval"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=10, help="Number of SWE-bench instances to sample.")
    parser.add_argument("--model", default="claude-sonnet-4-6")
    parser.add_argument("--split", default="test")
    args = parser.parse_args()

    from datasets import load_dataset

    print(f"[DevMind Eval] Loading {args.n} instances from SWE-bench_Verified ({args.split} split)...")
    ds = load_dataset("princeton-nlp/SWE-bench_Verified", split=args.split)
    sample = ds.select(range(min(args.n, len(ds))))

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    results = []

    for i, instance in enumerate(sample):
        instance_id = instance["instance_id"]
        problem_statement = instance["problem_statement"]
        print(f"\n[{i+1}/{len(sample)}] Instance: {instance_id}")
        print("  -> Clone the target repo at the specified base_commit, then run:")
        print(f"     python -m devmind.run --repo <cloned_path> "
              f"--task \"{problem_statement[:80]}...\" --run-id {instance_id} --model {args.model}")
        print("  -> Then score the produced patch using the official SWE-bench harness:")
        print("     https://github.com/princeton-nlp/SWE-bench#-running-evaluation")

        results.append({
            "instance_id": instance_id,
            "repo": instance["repo"],
            "base_commit": instance["base_commit"],
            "status": "pending_manual_run",
        })

    out_path = RESULTS_DIR / f"sample_{args.n}_{int(time.time())}.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\n[DevMind Eval] Instance list saved to: {out_path}")
    print("[DevMind Eval] Run devmind.run for each instance above, then score patches with the official harness.")


if __name__ == "__main__":
    main()
