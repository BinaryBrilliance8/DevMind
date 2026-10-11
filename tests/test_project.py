import ast
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class DevMindTests(unittest.TestCase):
    def test_python_files_parse(self):
        for path in ROOT.rglob("*.py"):
            if ".venv" not in path.parts:
                with self.subTest(path=str(path.relative_to(ROOT))):
                    ast.parse(path.read_text(encoding="utf-8"))

    def test_dashboard_home_without_runs(self):
        from dashboard.app import app

        with TemporaryDirectory() as tmp:
            with patch("dashboard.app.LOG_DIR", Path(tmp)):
                response = app.test_client().get("/")
                self.assertEqual(response.status_code, 200)
                self.assertIn(b"DevMind", response.data)

    def test_dashboard_reads_run_and_steps(self):
        from dashboard.app import app

        summary = {
            "run_id": "test_run",
            "task": "TEST ONLY",
            "exit_status": "Submitted",
            "resolved": True,
            "total_steps": 1,
            "total_cost": 0.01,
            "total_wall_time_seconds": 1.0,
            "api_calls": 1,
        }
        steps = [{
            "step_index": 1,
            "elapsed_seconds": 1.0,
            "cumulative_cost": 0.01,
            "n_calls_so_far": 1,
            "consecutive_format_errors": 0,
            "last_role": "assistant",
        }]

        with TemporaryDirectory() as tmp:
            logs = Path(tmp)
            (logs / "index.json").write_text(
                json.dumps([summary]), encoding="utf-8"
            )
            (logs / "test_run_summary.json").write_text(
                json.dumps(summary), encoding="utf-8"
            )
            (logs / "test_run_steps.json").write_text(
                json.dumps(steps), encoding="utf-8"
            )

            with patch("dashboard.app.LOG_DIR", logs):
                client = app.test_client()
                home = client.get("/")
                detail = client.get("/run/test_run")

                self.assertEqual(home.status_code, 200)
                self.assertIn(b"test_run", home.data)
                self.assertEqual(detail.status_code, 200)
                self.assertIn(b"TEST ONLY", detail.data)

    def test_missing_run_returns_404(self):
        from dashboard.app import app

        with TemporaryDirectory() as tmp:
            with patch("dashboard.app.LOG_DIR", Path(tmp)):
                response = app.test_client().get("/run/does_not_exist")
                self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
