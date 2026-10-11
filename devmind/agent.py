"""
DevMind Agent
=============
An instrumented extension of mini-swe-agent's DefaultAgent.

mini-swe-agent (https://github.com/SWE-agent/mini-swe-agent) already implements
the core autonomous software-engineering loop described in the DevMind abstract:
  - Agent-Computer Interface (ACI): structured shell-command actions
  - Sandboxed execution: each action runs via subprocess/Docker environment
  - Planning & Reasoning: the LLM query/response loop in `step()`
  - Patch Generation: produced via the agent's shell actions (git diff/apply)
  - Iterative Self-Correction: failed commands/tests feed back into context

DevMindAgent does NOT reimplement any of that. It subclasses DefaultAgent and
adds the one real contribution this project makes on top of the base agent:

  - Evaluation & Benchmarking Module: per-step structured metrics
    (step count, cost, wall-clock time, retries, exit status) written to
    JSON logs that the dashboard (dashboard/app.py) reads and visualizes.

This is the "Evaluation & Benchmarking Module" referenced in the project
abstract and the Proposed Method slide.
"""

import json
import time
from pathlib import Path

from minisweagent.agents.default import DefaultAgent, AgentConfig

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)


class DevMindAgent(DefaultAgent):
    """DefaultAgent + structured step-level metrics logging for DevMind."""

    def __init__(self, model, env, *, run_id: str | None = None, **kwargs):
        super().__init__(model, env, config_class=AgentConfig, **kwargs)
        self.run_id = run_id or time.strftime("run_%Y%m%d_%H%M%S")
        self.step_log: list[dict] = []
        self._step_start = None

    def step(self) -> list[dict]:
        """Wrap the base step() call with timing + metric capture."""
        self._step_start = time.time()
        result = super().step()
        elapsed = time.time() - self._step_start

        last_msg = self.messages[-1] if self.messages else {}
        self.step_log.append(
            {
                "step_index": len(self.step_log) + 1,
                "elapsed_seconds": round(elapsed, 3),
                "cumulative_cost": round(self.cost, 5),
                "n_calls_so_far": self.n_calls,
                "consecutive_format_errors": self.n_consecutive_format_errors,
                "last_role": last_msg.get("role", ""),
            }
        )
        self._write_metrics()
        return result

    def run(self, task: str = "", **kwargs) -> dict:
        self.step_log = []
        start = time.time()
        result = super().run(task=task, **kwargs)
        total_time = time.time() - start

        summary = {
            "run_id": self.run_id,
            "task": task,
            "exit_status": result.get("exit_status", ""),
            "resolved": result.get("exit_status", "") == "Submitted",
            "total_steps": len(self.step_log),
            "total_cost": round(self.cost, 5),
            "total_wall_time_seconds": round(total_time, 2),
            "api_calls": self.n_calls,
        }
        self._write_summary(summary)
        return result

    def _write_metrics(self):
        path = LOG_DIR / f"{self.run_id}_steps.json"
        path.write_text(json.dumps(self.step_log, indent=2))

    def _write_summary(self, summary: dict):
        path = LOG_DIR / f"{self.run_id}_summary.json"
        path.write_text(json.dumps(summary, indent=2))

        # also append to a running index so the dashboard can list all runs
        index_path = LOG_DIR / "index.json"
        index = json.loads(index_path.read_text()) if index_path.exists() else []
        index = [r for r in index if r["run_id"] != summary["run_id"]]
        index.append(summary)
        index_path.write_text(json.dumps(index, indent=2))
