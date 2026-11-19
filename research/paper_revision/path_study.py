"""Reproducible path-oracle comparison; a new study, not v2 data reconstruction."""

import argparse
import hashlib
import json
import random
from pathlib import Path, PurePosixPath

from devmind.operations import safe_name

TOKENS = [
    "a",
    "file.py",
    "..",
    ".",
    "/",
    "\\",
    "\0",
    ".git",
    ".GIT",
    ".Git",
    "é",
    " ",
    "-",
    "_",
    "tests",
    "config",
    "0",
    "x",
    "//",
    "",
]


def baseline(name: str) -> None:
    """Exact pre-fix predicate retained solely as the historical comparison."""
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or str(path) != name
        or "\\" in name
        or "\0" in name
        or any(p.casefold() in {"..", ".git"} for p in path.parts)
    ):
        raise ValueError("Invalid repository-relative path")


def oracle(name: str) -> bool:
    # String-component specification independent of pathlib canonicalization.
    return (
        bool(name)
        and "\\" not in name
        and "\0" not in name
        and all(
            part not in {"", ".", ".."} and part.casefold() != ".git"
            for part in name.split("/")
        )
    )


def accepts(function, name: str) -> bool:
    try:
        function(name)
        return True
    except ValueError:
        return False


def study(output: Path, seed: int = 20261119, count: int = 20000) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    rng = random.Random(seed)
    rows = []
    for _ in range(count):
        name = "".join(rng.choice(TOKENS) for _ in range(rng.randrange(7)))
        rows.append(
            {
                "name": name,
                "oracle": oracle(name),
                "before": accepts(baseline, name),
                "after": accepts(safe_name, name),
            }
        )
    corpus = output / "corpus.jsonl"
    corpus.write_text("".join(json.dumps(row) + "\n" for row in rows))
    summary = {
        "seed": seed,
        "count": count,
        "tokens": TOKENS,
        "corpus_sha256": hashlib.sha256(corpus.read_bytes()).hexdigest(),
        "scope": "New deterministic corpus; do not compare counts with v2 "
        "as identical inputs",
    }
    for label in ("before", "after"):
        summary[label] = {
            "accepted": sum(r[label] for r in rows),
            "false_accepts": sum(r[label] and not r["oracle"] for r in rows),
            "false_rejects": sum(not r[label] and r["oracle"] for r in rows),
            "disagreement_values": sorted(
                {r["name"] for r in rows if r[label] != r["oracle"]}
            ),
        }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(study(args.output), indent=2))
