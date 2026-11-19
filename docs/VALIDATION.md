# Validation evidence — fresh implementation

Revised on **19 November 2026**, macOS ARM64, Python 3.14.
Browser visual QA below was originally performed on 18 November.

| Gate | Observed outcome |
|---|---|
| Source ingestion | Newly supplied one-page PDF fully extracted and visually inspected |
| Source independence | Separate new project/package; no dependency on previous implementation |
| Dependency installation | New virtual environment; package installed successfully |
| Installed wheel | Built and installed; console routes and readiness passed outside source checkout |
| Live HTTP + worker | Actual Uvicorn submission and worker pickup; missing Docker failed explicitly |
| Dependency consistency | `pip check`: no broken requirements |
| Core tests | **47 passed, 3 skipped**, 4.66 seconds in the final recorded run |
| Ruff lint | All checks passed |
| Ruff formatting | All authored Python files formatted |
| JavaScript syntax | Node syntax check passed |
| Browser login | Successful against actual local FastAPI server |
| Browser run submission | Actual database run created and shown queued |
| Browser cancellation | Actual run changed to cancelled; timeline event observed |
| Other browser views | Project policies, evaluation empty state and runtime readiness verified |
| Browser console | No JavaScript error logs during inspected workflow |
| Repair integration | Scripted test policy drives real authored cache tests; bad patch then correction |
| Docker integration | Skipped: portable Lima startup denied access to macOS boot-session ID |
| PostgreSQL integration | Two tests skipped: PostgreSQL 17.12 compiled, but initdb failed with shared-memory creation denied |
| Live-model inference | Real Qwen2.5-Coder-1.5B Q4_K_M CPU inference; aci-v1 premature submit, aci-v2 valid plan |
| Official SWE-bench | Not run; no resolution score claimed |
| LoRA/QLoRA training | Script supplied and syntax-checked; no weights/GPU/data experiment run |
| CI and systemd deployment | Configuration supplied; remote jobs/services not launched |
| Load/HA/security audit | Not performed |

The screenshot `console.jpg` records a real **cancelled QA attempt**, not a fabricated
successful repair. Browser preview data and its temporary token live outside the
project deliverable. The preview session is no longer controllable from the current tool session, and
its shutdown could not be confirmed because process inspection/signalling is blocked.
Use the README commands for a reproducible runtime; do not treat a cached browser
page as evidence that the server remains healthy.

## Machine-readable evidence

`test-results.xml` records the final pytest outcomes. `source-manifest.json` records
source provenance. `schema.sql` is compiled from the actual model metadata.
`requirements.lock` records the resolved core dependency versions. `console.jpg`
is the captured browser page. The technical manuscript PDF is rendered and visually
reviewed separately; it is not an institutional approval document.

## Reproduction

```bash
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
python -m pip check
ruff check .
ruff format --check .
node --check web/app.js
python -m pytest -q --junitxml=docs/test-results.xml
```

The three explicitly gated integration tests can be enabled on a provisioned host:

```bash
docker build -f deploy/Dockerfile.executor -t devmind-executor:1 .
export DEVMIND_TEST_DOCKER=1
export DEVMIND_TEST_POSTGRES='postgresql+psycopg://USER:PASSWORD@HOST/DEDICATED_TEST_DB'
python -m pytest -q
```

Use an isolated test database. The PostgreSQL integration case expects no unrelated
queued attempts in that database. The CI file provides a fresh PostgreSQL service.

One non-failing warning is present in local tests: Starlette deprecates TestClient's
httpx transport in favor of httpx2. A future dependency update should migrate that
transport deliberately. The actual browser HTTP workflow also passed.

## What the tests establish

They exercise selected invariants: queue admission and idempotency, concurrent claim
ownership, cancelled/expired worker fencing, transactional review, private API fields,
body/schema/auth limits, source path and symlink checks, output/time limits, immutable
Git ingestion, binary patch application, typed action rejection, plan/read enforcement,
independent repair verification, protected tests, malformed-action recovery, missing
model/Docker failure, bounded provider retries, benchmark gold exclusion and
repository-held-out training preparation.

They do not establish broad model competence, exhaustive security, all repository
compatibility, production availability or large-scale latency. Release gates in
OPERATIONS.md remain required before a mission-critical deployment.

## Completion revision and remaining gates

Added full Compose services, wheel web assets, versioned baseline initialization,
resource settings validation, live dependency probes, graceful shutdown, deadline
watchdog, auto-expiring/auto-removing execution containers, interruption events,
candidate preservation after action exhaustion and an audited SWE-bench launcher.
New tests cover those control and validation behaviors; official harness launching
is mocked in regression tests, not misrepresented as an executed benchmark.

The Docker VM attempt failed with `failed to determine the boot session ID:
operation not permitted`. The PostgreSQL source archive SHA-256 was verified and
compilation succeeded; `initdb` failed on `shmget` with `Operation not permitted`.
No sandbox restriction was disabled. These services must be validated on a host
that permits them; the CI configuration includes the necessary integration gates.

`inference-v1.json` and `inference-v2.json` preserve real-model observations. Neither
is evidence of successful repair. `live-api-smoke.json` records actual HTTP/API/worker
failure handling. The API and local inference processes for this revision were terminated and their exits
confirmed. The original preview shutdown caveat above refers to the earlier session.

Still unexecuted: Docker isolation and full Compose startup; PostgreSQL concurrency;
real-model repository repair; official SWE-bench resolution; optional LoRA/QLoRA
training; remote CI/systemd rollout; load, recovery and adversarial security audits.
The package must not be labelled mission-critical production-ready until those
relevant release gates pass. External deployment and benchmark scores are not claimed.

`SHA256SUMS` and the adjacent ZIP checksum are regenerated for the revised handoff.

## Paper revision validation

The v3 paper revision adds 24 real first-action completions and a reproducible
20,000-input path-oracle comparison. See PAPER_REVISION.md and
`research/paper_revision/README.md` for exact scope, artifacts and limitations.
Historical v2 paper numbers were not reproduced; original experiment records are missing.

## Subsequent abstract and publication audit

The later audit recorded **59 passed, 3 skipped** in 5.26 seconds. Its independent
report is `abstract-audit-tests.xml`; see ABSTRACT_AUDIT.md. The 47-pass report above
and `test-results.xml` remain the evidence cited by the research-paper revision.
