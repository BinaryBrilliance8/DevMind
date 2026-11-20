# DevMind — Autonomous Software Engineering Research Platform

A **new implementation**, authored from the newly attached KITSW Phase-1 abstract.
This directory does not import, copy, or depend on the earlier DevMind project.

DevMind converts an issue into a planned, instrumented coding attempt: repository
localization → scoped edits → test feedback → correction → independent verification
→ human review. The browser console is backed by real API/database state, with no
fabricated run counts or benchmark scores.

![Browser console](docs/console.jpg)

## Release status

This is an implemented research platform, not a production-certified system.
The latest abstract audit recorded **59 passing tests and 3 skipped integration tests**.
Read [the abstract audit](docs/ABSTRACT_AUDIT.md) for completed paths and remaining gates.
The paper's earlier 47-test report remains a separate historical measurement.

## Executive Summary

The delivered system includes a browser console, authenticated FastAPI API,
PostgreSQL-compatible transactional queue, independent workers, typed ACI actions,
Docker execution broker, controller-owned patches, review workflow, SWE-bench
prediction export, research-data preparation, optional LoRA/QLoRA training code,
tests, CI and technical documentation.

**Validation boundary:** local tests and browser/API interactions were exercised.
Live CPU inference was tested using Qwen2.5-Coder-1.5B Q4_K_M. Docker and
PostgreSQL startup were blocked by sandbox restrictions; GPU training and official
SWE-bench runs remain unexecuted. Those capabilities
are implemented or configured but are not falsely described as successfully tested.
See [Validation](docs/VALIDATION.md).

## System Architecture

```mermaid
flowchart LR
    UI[Browser research console] --> API[Authenticated control API]
    API --> DB[(PostgreSQL: runs / events / artifacts)]
    DB --> Worker[Worker + renewable lease]
    Git[Registered repository at commit SHA] --> Worker
    Worker <--> Model[Configured model endpoint]
    Worker <--> ACI[Typed ACI + isolated Docker execution]
    ACI --> Patch[Controller-owned patch generation]
    Patch --> Verify[Fresh verification container]
    Verify --> Review[Human review]
    Review --> Export[SWE-bench / approved trajectories]
    Export --> Research[Independent evaluation / optional training]
```

SQLite is supported for local development. PostgreSQL is the multi-worker deployment
backend; claims use row locking and terminal writes are fenced by current ownership.
Database time is used for PostgreSQL lease checks across hosts. Large-scale capacity
and availability must be measured, not inferred from this architecture.

## Core Implementation

### 1. Install

From this directory, on macOS or Linux with Python 3.12+ and Git:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
```

The lock records versions validated on Python 3.14/macOS. The CI configuration uses
Python 3.12/Linux; it must pass on that platform before release. Optional GPU libraries
are separated in `research/requirements.txt` and are not in the validated core lock.

### 2. Configure the control plane

Generate a private token in your shell; use the same token when signing in to the
browser console. It is not a model-provider key.

```bash
export DEVMIND_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
cp projects.example.json projects.json
export DEVMIND_PROJECTS="$PWD/projects.json"
devmind init
devmind serve
```

Open **http://127.0.0.1:8090**. The UI works with the database immediately. It explicitly
reports missing model or Docker configuration. The browser holds the operator token
in memory, not localStorage, cookies, URLs or the repository.

### 3. Register a real repository

Each `projects.json` entry specifies a unique key, display name, local checkout,
trusted execution image, fixed verification argv and protected paths. API clients
cannot choose arbitrary host paths or verification commands.

Use your own repository for research. The included TTL cache is only an intentionally
buggy integration reference. To use that reference, first initialize its Git baseline:

```bash
git -C examples/cache_repo init
git -C examples/cache_repo add cache.py tests/test_cache.py
git -C examples/cache_repo -c user.name=DevMind -c user.email=research@example.invalid commit -m baseline
```

### 4. Configure actual agent execution

Install/start Docker and build the broker image:

```bash
docker build -f deploy/Dockerfile.executor -t devmind-executor:1 .
```

Use dependency-complete project images for nontrivial repositories. Execution
containers have no network; dependencies must be installed at image-build time.

Configure a running chat-completion-compatible model service:

```bash
export DEVMIND_MODEL_URL="http://127.0.0.1:8001/v1"
export DEVMIND_MODEL="your-served-model-identifier"
# Set DEVMIND_MODEL_KEY privately if the service requires authentication.
```

Restart the API with that configuration so the runtime view is accurate. In another
terminal with the same configuration, run `devmind worker`. The worker consumes
queued tasks independently of the API. `devmind worker --once` processes one attempt.
A model service must support JSON-object responses; no model weights are bundled.

In the browser, choose **New run**, select a registered project, and enter the issue.
Inspect Timeline, Tests and Patch. Passing verification produces **review**, not an
automatic merge. Approval records a human decision only.

### 5. PostgreSQL deployment

```bash
export DEVMIND_DB_PASSWORD='a-private-database-password'
docker compose -f deploy/compose.yaml up -d
export DEVMIND_DATABASE='postgresql+psycopg://devmind:URL_ENCODED_PASSWORD@127.0.0.1:5432/devmind'
devmind init
```

Use the same database/configuration for API and workers. Keep credentials in protected
service environments. Production service examples are in `deploy/`; they assume
PostgreSQL and intentionally separate API and worker OS identities. A TLS gateway,
image pinning, host isolation and release checks remain deployment responsibilities.

## Edge Cases

- Duplicate request keys return the same run; changed payloads conflict.
- Invalid actions consume a bounded step and yield corrective feedback.
- A plan is required before execution or mutation; an existing file must be read
  before editing it through the ACI.
- Failed independent tests return to the repair loop.
- Empty patches and protected-path modifications cannot reach review.
- Cancellation fences subsequent worker writes. Expired leases become interrupted.
- Missing Docker fails explicitly; no unsafe production host-execution fallback exists.
- Symlinks, submodules, ambiguous names and oversized snapshots are rejected.
- Credentials remain outside execution containers; source-bearing traces remain private.

Passing finite tests is not proof of correctness. Local verification and official
SWE-bench resolution remain distinct labels throughout the system.

## Next Steps

Run the real integration gates, configure the chosen model, evaluate held-out issues,
and complete the release checklist before external deployment. The included local
browser screenshot shows a **cancelled QA run**, not a successful AI repair.

### Documentation

- [Requirements and source provenance](docs/REQUIREMENTS.md)
- [Architecture, schemas and API](docs/ARCHITECTURE.md)
- [Security and deployment operations](docs/OPERATIONS.md)
- [Benchmarking and training](docs/RESEARCH.md)
- [Academic technical manuscript](docs/THESIS.md)
- [Validation evidence](docs/VALIDATION.md)


### Completion revision — 19 November 2026

The revision adds full API/worker/database Compose deployment, installed-wheel web
assets, schema-version enforcement, dependency probes, environment-configurable
budgets, graceful shutdown, a deadline watchdog, container lifetime/auto-removal,
interruption events and candidate preservation on action exhaustion.
See `deploy/compose.full.yaml` and the exact commands in `docs/OPERATIONS.md`.

Run `devmind doctor` on a worker host to check dependencies. To validate your live
model separately, run `python research/check_model.py`. The supplied local inference
evidence covers first-action validity, not an autonomous repair or benchmark score.
The official benchmark launcher is `python -m devmind.evaluation`; its usage and
result boundaries are described in `docs/RESEARCH.md`.


### Research-paper v3 revision

The earlier v3 paper is `docs/DevMind_Research_Paper_NewBuild_v3.pdf`. New scripts, raw
live responses, path-fuzz inputs and infrastructure failure logs are under
`research/paper_revision/`. Read `docs/PAPER_REVISION.md` before citing results:
the supplied v2 historical experiments could not be reproduced from their missing
artifacts. New measurements and historical claims are explicitly separated.

### Camera-ready paper — 20 November 2026

[Read the updated paper](docs/DevMind_Research_Paper_CameraReady.pdf), preserved exactly as supplied.
[Repository and artifact verification](docs/CAMERA_READY_AUDIT.md) identifies this fresh
implementation and records the missing evaluation scripts behind several new paper results.
Those results are not presented as independently reproduced by this release.
