import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from devmind.agent import DevMindAgent


class AgentLoggingTests(unittest.TestCase):
    def test_step_metrics_are_written_as_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("devmind.agent.LOG_DIR", Path(tmp)):
                agent = DevMindAgent.__new__(DevMindAgent)
                agent.run_id = "unit_test_run"
                agent.step_log = [{
                    "step_index": 1,
                    "elapsed_seconds": 0.5,
                    "cumulative_cost": 0.0,
                }]

                agent._write_metrics()

                path = Path(tmp) / "unit_test_run_steps.json"
                self.assertTrue(path.exists())
                self.assertEqual(
                    json.loads(path.read_text()),
                    agent.step_log,
                )

    def test_summary_is_written_and_indexed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("devmind.agent.LOG_DIR", Path(tmp)):
                agent = DevMindAgent.__new__(DevMindAgent)
                agent.run_id = "unit_test_run"

                summary = {
                    "run_id": "unit_test_run",
                    "task": "UNIT TEST ONLY",
                    "resolved": False,
                    "total_steps": 0,
                    "total_cost": 0.0,
                }

                agent._write_summary(summary)

                summary_path = Path(tmp) / "unit_test_run_summary.json"
                index_path = Path(tmp) / "index.json"

                self.assertEqual(
                    json.loads(summary_path.read_text()),
                    summary,
                )
                index = json.loads(index_path.read_text())
                self.assertEqual(len(index), 1)
                self.assertEqual(index[0]["run_id"], "unit_test_run")

                # Writing the same run again must not duplicate its index entry.
                agent._write_summary(summary)
                index = json.loads(index_path.read_text())
                self.assertEqual(len(index), 1)


if __name__ == "__main__":
    unittest.main()
