# Abstract re-audit and GitHub publication candidate

Date: 19 November 2026. The reattached one-page abstract was fully re-read and has
the same SHA-256 as the preserved source in source-manifest.json. The build remains
the fresh implementation; it does not switch back to the earlier DevMind project.

## Decision

**Implemented research platform; end-to-end production acceptance is incomplete.**
The abstract is broader than a front-end demo: it requires actual sandboxed planning,
localization, patching, tests, correction, tools and SWE-bench research evaluation.
There are implemented paths for each, but implementation and measured acceptance
are distinct. No massive-scale, availability, benchmark or alignment guarantee is made.

| Requirement | Implementation and evidence | Remaining acceptance |
|---|---|---|
| LLM/ACI | Gateway, discriminated actions, 24 recorded live first actions | Full live-model repair trajectories |
| Plan/localize/edit | Runner gates, locate/read/replace, controller-generated patches | Real repository workload coverage |
| Sandbox/tools | Network-disabled resource-limited Docker executor, disposable Git | Actual isolation tests on Docker-capable host |
| Testing/correction | Baseline and fresh verification, scripted failed-then-fixed tests | Live-model correction inside Docker |
| Durable feedback | SQL queue, ownership fencing, events and browser console | Real PostgreSQL integration/concurrency gates |
| SWE-bench | Gold-excluding intake, prediction export and official harness launcher | Official run and independently graded outcomes |
| Train/evaluate/compare | Approved traces, held-out preparation, optional adapter code, recorded studies | Completed training and broader comparisons |
| Production scale | Worker separation, bounded admission and resource limits | Load, failure, recovery and security testing |

## Additional defect fixed in this audit

`Project.protected` previously accepted `./tests`, but the submission guard compared
it literally with snapshot paths such as `tests/test_cache.py`. That could make the
configured protection ineffective. Registration now canonicalizes protected paths,
rejects root/parent/absolute/Git-metadata forms, and deduplicates aliases. Verification
argv now applies the same empty-string/NUL/length validation as command actions.

New regression coverage includes a full scripted tampering attempt with `./tests/`;
it must fail before a fresh verifier is created. Current suite: **59 passed, 3 skipped**
(5.26 seconds), with the existing non-failing Starlette/httpx warning. See
abstract-audit-tests.xml. The 47-pass paper-revision test report remains preserved
separately as test-results.xml; historical paper measurements are not overwritten.

The production sources used for the paper revision are preserved under
`research/paper_revision/evaluated_source/devmind/`, with hashes matching the study's
MANIFEST.json. They are an evidence snapshot of this same fresh implementation,
not the current deployment source. Current source remains `server/devmind/`.

## GitHub boundary

The repository is prepared for publication as a research/release candidate. GitHub
Actions is configured to build the images and run the actual Docker and PostgreSQL
integration gates, with retained JUnit output. A passing local unit suite does not
imply these remote jobs passed. No GitHub account connection or remote repository
was confirmed at preparation time.

Publishing source to GitHub does not host the FastAPI service, database, worker or
model. GitHub Pages cannot run this Python/Docker stack. Runtime deployment uses the
provided Compose/systemd configuration on an appropriate host. Public exposure,
cloud-host provisioning and unsupported claims of completion are not implied.
