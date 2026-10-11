"""
DevMind CLI
===========
Run the instrumented DevMind agent on a task inside a local repository.

Usage:
    python -m devmind.run --repo /path/to/repo --task "Fix the bug where X happens" --model claude-sonnet-4-6

This wires together:
    - minisweagent's LocalEnvironment (the sandboxed execution module)
    - minisweagent's LiteLLM model wrapper (works with Anthropic/OpenAI/etc.)
    - devmind.agent.DevMindAgent (our evaluation/logging layer)

Requires an API key set as an environment variable, e.g.:
    export ANTHROPIC_API_KEY=sk-ant-...
    # or
    export OPENAI_API_KEY=sk-...
"""

import argparse
import sys
from pathlib import Path

from minisweagent.environments.local import LocalEnvironment
from minisweagent.models import get_model
from minisweagent.config import builtin_config_dir

from devmind.agent import DevMindAgent


def load_default_config():
    """Load mini-swe-agent's default prompt/config templates so we don't
    have to reinvent the system/instance prompts — only the metrics layer
    is custom here."""
    import yaml

    config_path = builtin_config_dir / "mini.yaml"
    with open(config_path) as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="Run the DevMind agent on a task.")
    parser.add_argument("--repo", required=True, help="Path to the local repository to work in.")
    parser.add_argument("--task", required=True, help="Natural-language description of the issue/task.")
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Model name (litellm format).")
    parser.add_argument("--run-id", default=None, help="Optional run identifier for logs.")
    parser.add_argument("--cost-limit", type=float, default=1.0, help="Stop after this much $ spent.")
    parser.add_argument("--step-limit", type=int, default=40, help="Stop after this many agent steps.")
    args = parser.parse_args()

    repo_path = Path(args.repo).resolve()
    if not repo_path.exists():
        print(f"Repo path does not exist: {repo_path}", file=sys.stderr)
        sys.exit(1)

    cfg = load_default_config()["agent"]
    cfg["cost_limit"] = args.cost_limit
    cfg["step_limit"] = args.step_limit

    env = LocalEnvironment(cwd=str(repo_path))
    model = get_model(args.model)

    agent = DevMindAgent(model, env, run_id=args.run_id, **cfg)

    print(f"[DevMind] Starting run '{agent.run_id}' on repo: {repo_path}")
    print(f"[DevMind] Task: {args.task}\n")

    result = agent.run(task=args.task)

    print("\n[DevMind] Run finished.")
    print(f"  Exit status : {result.get('exit_status')}")
    print(f"  Steps taken : {len(agent.step_log)}")
    print(f"  Total cost  : ${agent.cost:.4f}")
    print(f"  Logs saved  : logs/{agent.run_id}_summary.json")
    print(f"\n  View results with: python -m dashboard.app")


if __name__ == "__main__":
    main()
