# DevMind

**An LLM-Based Autonomous Agent Framework for Automated Software Engineering**

DevMind is an instrumented wrapper around [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent)
(Princeton/Stanford, NeurIPS 2024 lineage), which already implements the core
autonomous software-engineering loop: an Agent-Computer Interface (ACI),
sandboxed execution, LLM-driven planning, patch generation, and iterative
self-correction.

DevMind adds the **Evaluation & Benchmarking Module** on top: structured
per-step metrics logging and a web dashboard to visualize agent trajectories,
resolve rates, cost, and timing — which `mini-swe-agent` does not provide
out of the box.

## What's actually ours vs. what's the base agent

| Component | Source |
|---|---|
| ACI (structured shell commands) | mini-swe-agent (base) |
| Sandboxed execution | mini-swe-agent (base) |
| Planning / reasoning loop | mini-swe-agent (base) |
| Patch generation | mini-swe-agent (base) |
| Iterative self-correction | mini-swe-agent (base) |
| **Step-level metrics logging** (`devmind/agent.py`) | **DevMind (this project)** |
| **Run dashboard** (`dashboard/app.py`) | **DevMind (this project)** |
| **SWE-bench mini-eval harness** (`scripts/eval_mini_swebench.py`) | **DevMind (this project)** |

Be upfront about this split in your presentation and viva — it's a legitimate
and common pattern (build a measurement/evaluation layer on a well-established
base agent) and it's much easier to defend than pretending the whole agent
loop was written from scratch.

## Setup

```bash
git clone <your-fork-url>
cd DevMind
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Set your own API key (don't share this — each team member should use their own)
export ANTHROPIC_API_KEY=sk-ant-...
# or
export OPENAI_API_KEY=sk-...
```

## Run the agent on a real task

```bash
python -m devmind.run \
  --repo /path/to/some/local/git/repo \
  --task "Fix the bug where pagination skips the last item" \
  --model claude-sonnet-4-6 \
  --cost-limit 1.0 \
  --step-limit 40
```

This writes logs to `logs/<run_id>_summary.json` and `logs/<run_id>_steps.json`.

## View results in the dashboard

```bash
python -m dashboard.app
```

Open `http://localhost:5000` — shows run history, resolve rate, cost, and a
per-step trajectory view for each run.

## Run a small SWE-bench evaluation

```bash
python scripts/eval_mini_swebench.py --n 10 --model claude-sonnet-4-6
```

This pulls 10 real instances from SWE-bench Verified and prints the exact
commands to run DevMind against each one, plus a pointer to the official
scoring harness. (Intentionally scoped small — the full 500/2,294-instance
benchmark is expensive; 10 instances is enough for an honest, reportable
number in a project evaluation section.)

## Project structure

```
DevMind/
├── devmind/
│   ├── agent.py        # DevMindAgent: metrics-logging subclass of DefaultAgent
│   └── run.py           # CLI entry point
├── dashboard/
│   ├── app.py            # Flask dashboard
│   └── templates/        # HTML templates
├── scripts/
│   └── eval_mini_swebench.py
├── logs/                 # Run logs land here (gitignored except .gitkeep)
├── requirements.txt
└── README.md
```

## Team

- Syed Qadeer Ahmed — B23IT009
- Vilasagarapu Shiva Charan — B23IT064
- Deshini Jayanth Goud — B23IT015
- Rajarapu Hemanth Durga Prasad — B21IT006

Batch 3, Dept. of IT, Kakatiya Institute of Technology & Science.
Supervisor: Sri. G. Yeshwanth.

Built on [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) (MIT License).
