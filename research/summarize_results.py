"""Compute explicit-denominator resolution statistics from official report IDs."""

import argparse
import json
import math
from pathlib import Path


def summarize(predictions: list[dict], report: dict) -> dict:
    identifiers = [row["instance_id"] for row in predictions]
    if not identifiers or len(identifiers) != len(set(identifiers)):
        raise ValueError("Predictions must contain unique, nonempty instance IDs")
    if not isinstance(report.get("resolved_ids"), list):
        raise ValueError("Official report must contain a resolved_ids list")
    resolved = set(report["resolved_ids"])
    if not resolved.issubset(identifiers):
        raise ValueError(
            "Report contains resolved IDs absent from this prediction file"
        )
    n, successes = len(identifiers), len(resolved)
    rate, z = successes / n, 1.959963984540054
    denominator = 1 + z * z / n
    center = (rate + z * z / (2 * n)) / denominator
    half = z * math.sqrt(rate * (1 - rate) / n + z * z / (4 * n * n)) / denominator
    return {
        "submitted": n,
        "resolved": successes,
        "resolution_rate": rate,
        "wilson_95": [max(0, center - half), min(1, center + half)],
        "denominator": "all submitted prediction IDs, including empty patches",
        "caveat": "Per-instance interval does not adjust for repository dependence",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("predictions", type=Path)
    parser.add_argument("official_report", type=Path)
    args = parser.parse_args()
    predictions = [
        json.loads(line)
        for line in args.predictions.read_text().splitlines()
        if line.strip()
    ]
    print(
        json.dumps(
            summarize(predictions, json.loads(args.official_report.read_text())),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
