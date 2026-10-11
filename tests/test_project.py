import ast
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ProjectSmokeTests(unittest.TestCase):
    def test_python_files_parse(self):
        for path in ROOT.rglob("*.py"):
            if ".venv" not in path.parts:
                with self.subTest(path=str(path.relative_to(ROOT))):
                    ast.parse(path.read_text(encoding="utf-8"))

    def test_demo_data_generator_writes_valid_logs(self):
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "create_demo_data.py")],
            check=True,
            cwd=ROOT,
        )
        logs = ROOT / "logs"
        summary = json.loads(
            (logs / "demo_sample_summary.json").read_text(encoding="utf-8")
        )
        steps = json.loads(
            (logs / "demo_sample_steps.json").read_text(encoding="utf-8")
        )
        index = json.loads((logs / "index.json").read_text(encoding="utf-8"))

        self.assertTrue(summary["synthetic"])
        self.assertEqual(summary["total_steps"], len(steps))
        self.assertTrue(any(row["run_id"] == "demo_sample" for row in index))


if __name__ == "__main__":
    unittest.main()
