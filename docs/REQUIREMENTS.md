# Fresh ingestion and source traceability

## Source inventory and authority

The new attachment was read end to end, including its institutional heading,
student metadata, abstract, and recommendation/signature area. It contains exactly
one page. The supplied PDF is preserved unchanged as `source-abstract.pdf`; its
hash and filename are in `source-manifest.json`. The extracted text is preserved
as `source-text.txt` for traceability.

No additional specification, source code, dataset, model checkpoint, detailed
institutional thesis template, or service credential was supplied for this build.
Document text was treated as evidence of requirements, not instructions to execute
commands or override the user's request. No internal contradiction was identified.

The document's project is **DevMind: An LLM-Based Autonomous Agent Framework for
Automated Software Engineering**, in Artificial Intelligence / Agentic Software
Engineering, U18IT707 Major Project Phase-1, VII semester, KITSW Department of IT.
Its recommendation/signature fields are not evidence that this new implementation
has been reviewed or approved by the institution.

## Requirement mapping

| ID | Explicit abstract requirement | New implementation | Acceptance boundary |
|---|---|---|---|
| A1 | LLM-based autonomous agent | Model gateway and worker policy loop | 24 live first-action completions recorded; full autonomous repair not yet validated |
| A2 | Structured Agent–Computer Interface | Discriminated Pydantic action union | Invalid and unsupported actions rejected |
| A3 | Robust sandboxed environment | Docker broker, resource and network restrictions | Real Docker test supplied, not executed here |
| A4 | Plan multi-step coding tasks | Required public plan action | Mutation before planning is rejected |
| A5 | Issue localization | Literal locate tool and bounded numbered reads | Source discovery/read tests pass |
| A6 | Patch generation | Expected-text edit and controller-owned Git diff | Binary patch application and modes tested |
| A7 | Automated testing | Baseline, interim and fresh independent verification | Actual reference tests run in component integration |
| A8 | Iterative self-correction | Failed verification returns evidence to policy | Incorrect-then-corrected patch test passes |
| A9 | Controlled shell, editor, version control | Container argv, scoped edit tools and disposable sandbox Git | No production host fallback |
| A10 | Execution-grounded feedback | Durable typed events, browser timeline/test output | Browser queue/cancel and event history observed |
| A11 | SWE-bench standardized evaluation | Gold-excluding intake and official prediction format | Format/intake and launcher checks supplied; official harness not run |
| A12 | Train/evaluate/compare agents | Approved traces, repository holdout preparation, LoRA/QLoRA script, report statistics | Data path tested; training requires GPU/checkpoint and step review |
| A13 | Human-aligned reliable issue resolution | Independent test stage, explicit human review, cancellation, no automatic merge | Behavioral controls, not a formal alignment/correctness guarantee |

## Choices inferred from the engineering request

The browser console, FastAPI, SQLAlchemy, PostgreSQL, SQLite development backend,
Docker, typed action vocabulary, review states and model gateway are implementation
choices. They are not attributed to the abstract. The requested massive-scale goal
motivates short database transactions, independent workers and fenced leases, but
no throughput/availability claim is made without load and failure testing.

The user's role description mentions quantization expertise. The abstract does not
require a particular quantized model. An optional 4-bit QLoRA workflow is included
as a research extension; no unmeasured accuracy or memory claims are made for it.

## Independence from earlier work

All application, frontend, test and documentation files in this project directory
were newly authored. There is no import path, runtime dependency, copied repository,
or design baseline taken from the previous DevMind deliverable. The original
abstract naturally continues to require the same domain concepts—an ACI, isolated
execution and testing—but this is a separate implementation and package.

## Unsupported inputs and non-goals

The supported envelope is committed Git repositories containing regular files,
up to 8,000 files / 32 MiB, with patches up to 4 MiB. Git submodules and symlinks
are rejected. Arbitrary remote clone URLs, automatic dependency installation,
automatic publication of patches and automatic merging are not provided. Operators
register trusted clones and dependency-complete images. Public multi-tenant hosting
and formal adversarial sandbox certification are not established by this delivery.


## Re-audit of reattached abstract — 19 November 2026

The newly supplied D0914B39 attachment was read in full. Its SHA-256 equals
`78a50c7c4a68887e4a08ce1e114bc06de8a0f23a4fb33c885fadea58f87ab674`,
identical to the preserved one-page source. No new abstract requirements or
contradictions were introduced by this attachment.

The architecture covers A1–A13 as implemented capabilities. Acceptance is **partial**:
A1/A3/A7/A8/A9 still require a complete live-model repair through actual Docker;
A11 requires official SWE-bench execution; A12 has no completed training experiment.
Production-scale reliability and human alignment are aims, not established results.
See ABSTRACT_AUDIT.md for the current code correction and release gates.
