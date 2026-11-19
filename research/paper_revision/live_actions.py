"""Paired, first-action-only live inference study. Never executes generated code."""

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

from devmind.config import Config
from devmind.contracts import DECISION
from devmind.model import POLICY, Gateway, initial_messages

TASKS = [
    ("cache-1", "Items must expire at the exact TTL boundary, including zero TTL."),
    (
        "cache-2",
        "Fix a TTL cache that returns expired entries at their expiry timestamp.",
    ),
    (
        "cache-3",
        "A cached value survives when clock() equals its deadline. "
        "Correct this boundary.",
    ),
    (
        "text-1",
        "The truncate helper mishandles text whose length equals the output limit.",
    ),
    ("text-2", "Fix text truncation so exact-length strings are returned unchanged."),
    (
        "text-3",
        "A truncation utility appends an ellipsis when no truncation is "
        "needed at equality.",
    ),
    (
        "auth-1",
        "The token verifier accepts unsigned tokens with alg none. Reject "
        "those tokens.",
    ),
    (
        "auth-2",
        "Fix a verifier that trusts tokens which declare the none signing algorithm.",
    ),
    (
        "auth-3",
        "Unsigned authentication tokens are accepted. Require the "
        "permitted signed algorithm.",
    ),
    (
        "orders-1",
        "An order retains earlier reservations when a later item is out of stock.",
    ),
    (
        "orders-2",
        "Fix reservation rollback when a multi-item order cannot reserve every item.",
    ),
    (
        "orders-3",
        "Failed order creation leaks inventory reservations from "
        "preceding order lines.",
    ),
]


def study(output: Path, model: str, url: str) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    config = Config(
        model=model, model_url=url, api_token="local-study-not-an-api-credential-0000"
    )
    config.validate()
    policy = {"protected": ["tests"], "verification_argv": ["python", "-m", "unittest"]}
    summaries = {}
    records = []
    for index, (task_id, issue) in enumerate(TASKS):
        # Alternate order to reduce a fixed warm-cache advantage for either prompt.
        variants = ["aci-v1", "aci-v2"] if index % 2 == 0 else ["aci-v2", "aci-v1"]
        for variant in variants:
            messages = initial_messages(issue, policy)
            if variant == "aci-v1":
                messages[0]["content"] = (
                    POLICY + "\nAction schema:\n" + json.dumps(DECISION.json_schema())
                )
            gateway = Gateway(config)
            record = {
                "task": task_id,
                "variant": variant,
                "messages": messages,
                "schema_valid": False,
                "first_plan": False,
                "plan_gate_refusal": False,
            }
            started = time.monotonic()
            try:
                action = gateway.decide(messages)
                record.update(
                    schema_valid=True,
                    first_plan=action.kind == "plan",
                    plan_gate_refusal=action.kind not in {"plan", "locate", "read"},
                    action=action.model_dump(),
                )
            except ValueError as error:
                record.update(error_type=type(error).__name__, error=str(error))
            except Exception as error:
                record.update(transport_failure=type(error).__name__)
            record.update(
                seconds=time.monotonic() - started,
                tokens=gateway.tokens,
                provider_response=gateway.last_response,
            )
            records.append(record)
            with (output / "responses.jsonl").open("a") as stream:
                stream.write(json.dumps(record) + "\n")
            print(
                task_id,
                variant,
                "schema",
                record["schema_valid"],
                "plan",
                record["first_plan"],
                flush=True,
            )
    for variant in ("aci-v1", "aci-v2"):
        rows = [r for r in records if r["variant"] == variant]
        summaries[variant] = {
            "requests": len(rows),
            "schema_valid": sum(r["schema_valid"] for r in rows),
            "first_plan": sum(r["first_plan"] for r in rows),
            "plan_gate_refusal": sum(r["plan_gate_refusal"] for r in rows),
            "transport_failures": sum("transport_failure" in r for r in rows),
            "mean_seconds": sum(r["seconds"] for r in rows) / len(rows),
            "total_tokens": sum(r["tokens"] for r in rows),
        }
    manifest = {
        "scope": "First-action compliance only; no execution, patches, "
        "repairs or benchmark score",
        "model": model,
        "endpoint": url,
        "temperature": 0,
        "max_tokens": 3000,
        "tasks": len(TASKS),
        "calls": len(records),
        "order": "alternating paired variants",
        "limitations": "One model, one response per task/variant, "
        "correlated paraphrases; no population inference",
        "python": sys.version,
        "platform": platform.platform(),
        "summary": summaries,
        "response_sha256": hashlib.sha256(
            (output / "responses.jsonl").read_bytes()
        ).hexdigest(),
    }
    (output / "summary.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="devmind-qwen-coder")
    parser.add_argument("--url", default="http://127.0.0.1:18001/v1")
    args = parser.parse_args()
    print(json.dumps(study(args.output, args.model, args.url), indent=2))
