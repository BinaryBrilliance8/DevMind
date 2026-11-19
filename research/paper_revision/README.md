# Paper revision and reproducible validation

This directory accompanies the 19 November 2026 v3 revision. It does **not** contain
or reconstruct the missing original `devmind_eval.py`, original figure script or
raw v2 experiment records. The supplied PDF is preserved as `source-paper-v2.pdf`.
Its historical numbers are distinguished from newly executed measurements.

## New measurements

- `results/live`: 24 genuine completions, 12 issue prompts paired across aci-v1/v2.
  Schema-valid: 12/12 for both. Initial plan: 0/12 vs 12/12. Premature actions that
  would hit the plan gate: 12/12 vs 0/12. No generated code was executed. These are
  first-action diagnostics, **not** repair scores or independent repository samples.
- `results/paths`: 20,000 exact stored inputs, seed 20261119. The pre-fix predicate
  falsely accepts 151 occurrences of `.`; the revised predicate has zero oracle
  disagreements on this corpus. This is not the v2 corpus (167 disagreements).
- `results/repair-preflight`: actual dependency probes blocked a production-path
  attempt before submission or execution. There is no host execution fallback.
- `results/docker-attempt.log` and `results/postgres-attempt.log`: concrete operating
  system restrictions observed again during this revision.
- `../../docs/test-results.xml`: 47 passed, 3 skipped. Docker and PostgreSQL require
  real integration gates; passed mocked checks are not substitutes.

## Reproduce from the project root

Install the project's locked core environment as described in the main README.
Every output directory must be new, preventing silent overwrite of evidence.

```bash
python research/paper_revision/path_study.py --output work/new-path-study
python research/paper_revision/live_actions.py --output work/new-live-study \
  --model devmind-qwen-coder --url http://127.0.0.1:18001/v1
python -m pytest -q --junitxml=work/new-test-results.xml
```

The live study uses the production Gateway, includes its bounded transient retries,
records every parsed provider response (including invalid schema responses), and
alternates variant order. Both variants request temperature zero and 3,000 output
tokens. The model alias must identify the expected checkpoint; the recorded model
and runtime file hashes are in `../../docs/model-provenance.json`. See
`../../docs/RESEARCH.md` for the exact tested CPU server flags. Different runtime,
weights, scheduling or server configuration can change outputs; this small diagnostic
is not a statistical population estimate.

## Real repair pipeline

Configure `DEVMIND_PROJECTS`, `DEVMIND_MODEL`, `DEVMIND_MODEL_URL`, and a private
`DEVMIND_API_TOKEN` using the main README. Start Docker and build the executor image.
Register repositories and supply task JSONL records matching the RunRequest schema.
Use a **new, dedicated database**, never a live production queue:

```bash
python research/paper_revision/live_repair.py \
  --database 'sqlite:///./work/new-evaluation.sqlite' \
  --tasks research/paper_revision/tasks.example.jsonl \
  --output work/new-repair-study
```

Create the `work` parent directory first. PostgreSQL URLs are also supported, but
must point to a new dedicated evaluation database. Failure of readiness returns exit
2 and preserves the probe report. A completed launcher does not imply successful
repair: inspect each run's status, tests and patch, and grade with independent tests.
No run is automatically approved. Model/provider credentials never enter the report.

## Rebuild the paper

```bash
python -m pip install -r research/paper_revision/requirements-paper.txt
python research/paper_revision/build_paper.py --output work/revised-paper.pdf
```

The recipe preserves the original vector figures and historical tables, replaces
specified text regions, and appends a three-page supplement generated from recorded
results. The editable source for the original paper was unavailable. The build script
is the editable source for this revision; its assertive block matching fails rather
than silently editing a different source document. PDF byte hashes can differ across
builds because PDF metadata/document IDs are generated at build time. The reviewed
release PDF is hashed in the top-level project SHA256SUMS.

## Publication status

No public GitHub or Zenodo artifact URL has been created or verified. Local artifacts
are provided, and missing public availability is explicitly stated in the paper.
Do not replace this with a fabricated link or claim double-blind submission status.
Before a research submission, recover/reproduce the historical studies or remove
those claims; run Docker/PostgreSQL integration and declared live-repair benchmarks.
