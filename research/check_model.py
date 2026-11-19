"""Smoke-test inference and first-action validity without executing code."""

import json
import time

from devmind.config import load
from devmind.model import PROMPT_VERSION, Gateway, initial_messages


def main() -> None:
    config = load()
    if not config.model:
        raise ValueError("Set DEVMIND_MODEL and DEVMIND_MODEL_URL")
    gateway = Gateway(config)
    started = time.monotonic()
    action = gateway.decide(
        initial_messages(
            "Items must expire at the exact TTL boundary, including zero TTL.",
            {"protected": ["tests"], "verification_argv": ["python", "-m", "unittest"]},
        )
    )
    result = {
        "model": config.model,
        "prompt": PROMPT_VERSION,
        "action": action.model_dump(),
        "tokens": gateway.tokens,
        "seconds": round(time.monotonic() - started, 3),
        "first_action_valid": action.kind == "plan",
        "scope": "Inference smoke test only; no code executed or repair score implied",
    }
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["first_action_valid"] else 1)


if __name__ == "__main__":
    main()
