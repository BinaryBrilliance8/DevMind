"""
DevMind Dashboard
=================
A minimal Flask app that reads the JSON logs written by devmind.agent.DevMindAgent
and renders them as a readable run history + per-step trajectory view.

This is the "Evaluation & Benchmarking Module" UI referenced in the project's
Proposed Method slide.

Run with:
    python -m dashboard.app
Then open http://localhost:5000
"""

import json
from pathlib import Path

from flask import Flask, render_template, abort

LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

app = Flask(__name__)


def load_index():
    index_path = LOG_DIR / "index.json"
    if not index_path.exists():
        return []
    return sorted(json.loads(index_path.read_text()), key=lambda r: r["run_id"], reverse=True)


@app.route("/")
def home():
    runs = load_index()
    totals = {
        "runs": len(runs),
        "resolved": sum(1 for r in runs if r.get("resolved")),
        "total_cost": round(sum(r.get("total_cost", 0) for r in runs), 4),
        "avg_steps": round(sum(r.get("total_steps", 0) for r in runs) / len(runs), 1) if runs else 0,
    }
    return render_template("index.html", runs=runs, totals=totals)


@app.route("/run/<run_id>")
def run_detail(run_id):
    steps_path = LOG_DIR / f"{run_id}_steps.json"
    summary_path = LOG_DIR / f"{run_id}_summary.json"
    if not steps_path.exists() or not summary_path.exists():
        abort(404)
    steps = json.loads(steps_path.read_text())
    summary = json.loads(summary_path.read_text())
    return render_template("run_detail.html", steps=steps, summary=summary)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
