# DevMind: An LLM-Based Autonomous Agent Framework for Automated Software Engineering

**Technical manuscript for U18IT707 Major Project (Phase-1), VII Semester**  
Department of Information Technology  
Kakatiya Institute of Technology & Science, Warangal

**Students:** Syed Qadeer Ahmed — B23IT009; Vilasagarapu Shiva Charan — B23IT064;
Deshini Jayanth Goud — B23IT015; Rajarapu Hemanth Durga Prasad — B21IT006.

This is an engineering manuscript based on the supplied abstract, not an institutionally
approved thesis. No departmental formatting template was supplied. Certificates,
approvals, signatures, original-research claims and experimental results are not
fabricated. The source metadata and source hash are preserved separately.

## Abstract

Repository-level software engineering requires contextual inspection, compatible
modification and repeated behavioral verification. DevMind implements an autonomous
agent framework in which a language model proposes typed actions through an explicit
Agent–Computer Interface. A control plane manages issue submission, durable ownership,
source snapshots, isolated execution, feedback, independent testing and human review.
The framework combines a browser research console, transactional queue, bounded model
gateway, Docker execution broker and controller-owned patch generation. Standardized
prediction export supports external SWE-bench evaluation, and approved trajectory
export supports repository-separated supervised-data preparation. Optional adapter
training code includes a CUDA 4-bit QLoRA path. Local tests validate selected control,
state and repair-loop properties, while browser testing demonstrates actual queue
submission and cancellation. A local CPU model smoke test validates first-action
schema adherence with a revised prompt. Repair performance, official benchmark outcomes,
GPU training and distributed production characteristics remain unmeasured. The result
is a concrete research implementation with explicit evidence boundaries and a protocol
for subsequent empirical evaluation.

**Keywords:** software engineering agents; language models; ACI; program repair;
sandboxing; verification; reproducible benchmarks; parameter-efficient training.

## 1. Introduction

### 1.1 Motivation

Software maintenance spans files, tests, dependencies and version history. A response
that looks like code is not evidence that it resolves an issue in its original
repository. The supplied abstract identifies repository-level bug and feature work
as a bottleneck and proposes an execution-grounded agent framework. DevMind turns
that proposal into a visible sequence of controlled interactions rather than treating
single-shot text generation as completed engineering.

### 1.2 Problem statement

Given an issue I and a repository at commit R₀, construct a candidate change Δ that
addresses the issue while preserving required behavior, under bounded execution and
model resources. Preserve enough evidence to reproduce the attempt and evaluate its
outcome independently. The framework must distinguish a candidate, local test success,
human acceptance and benchmark resolution.

### 1.3 Objectives and contributions

The implementation supplies typed action contracts, isolated tools, transactional
run ownership, iteration on execution feedback, independent verification, an evidence
console and benchmark/training-data interfaces. The engineering contribution is the
composition of these mechanisms into a runnable workflow. Novel learning performance
or state-of-the-art benchmark superiority is not asserted without experiments.

## 2. Background and related work

### 2.1 Repository-level agents

Repository tasks combine localization, planning, editing and checking. A model policy
can use tool observations to revise its actions; the environment supplies executable
signals rather than only textual plausibility. Nevertheless, finite tests are an
incomplete specification and can be indirectly evaded by malicious or mistaken code.

### 2.2 Structured interfaces

An ACI defines permitted action syntax and the observation boundary. DevMind's action
space comprises plan, locate, read, replace, command, verify and submit. Discriminated
schemas make unknown capabilities and malformed arguments rejectable before execution.
An interface is not a security sandbox: interpreters invoked within the command tool
can execute arbitrary code, so a separate execution environment is required.

### 2.3 Independent evaluation and learning

SWE-bench supplies repository issues and an independent harness for evaluating patches.
The framework exports the documented prediction fields and excludes gold solutions
from generation inputs. Approved interaction traces can form supervised examples,
but final-patch approval does not certify every intermediate action as an ideal target.
Data preparation and training must therefore be separated from outcome reporting.

## 3. Requirements and scope

The source is a one-page Phase-1 abstract, not a detailed technical specification.
Its functional requirements are planning, localization, patch generation, testing,
self-correction, controlled tools, sandboxing and standardized evaluation. The complete
source-to-code matrix appears in REQUIREMENTS.md. No source contradiction was found.

The browser UI, FastAPI, PostgreSQL, SQLite development mode, Docker and review workflow
are explicit engineering choices. No particular model, hardware configuration,
quantization method or thesis template is claimed to be mandated by the abstract.
The current supported source envelope contains regular committed Git files within
explicit byte/file limits; unsupported repository structures fail visibly.

## 4. Formalization and methodology

### 4.1 Interaction process

Let Hₜ denote the observed interaction history and πθ the model policy. The next action
is `aₜ ~ πθ(a | I, Hₜ)`. The execution environment applies the permitted action to the
workspace and returns observation oₜ. The controller records `(aₜ, oₜ)` and updates the
policy context. Full events remain durable even when old messages are evicted from
the model's bounded context.

Actions are proposals. A plan must precede execution/mutation; an existing file must
be read before typed replacement. Invalid proposals consume a bounded step and produce
an error observation. This improves inspectability and constrains control flow, but
it does not prove that the plan is correct or that arbitrary shell actions are benign.

### 4.2 Candidate verification

Let P be protected repository paths. Compute Δ using the immutable original bytes
and candidate bytes in a controller-owned Git index. A candidate becomes eligible
for human review when:

`Eligible(Δ) = Nonempty(Δ) ∧ Unchanged(P) ∧ TestPass(Fresh(R₀ ⊕ Δ))`.

The persisted transition also requires active, unexpired worker ownership. TestPass
means the fixed operator command exited zero without timeout or output overflow.
It does not imply semantic correctness. Human approval records a review decision;
the official benchmark label remains an independent external result.

### 4.3 Resource bounds

The framework bounds steps, model context, token accounting, subprocess time/output,
container resources and repository size. A watchdog fences terminal state at the
run deadline and requests container disposal. Execution containers also expire and
auto-remove. In-flight inference and cleanup can finish later; one response can
overshoot the token budget. Hard cross-service deadlines require external supervision. These operational semantics must accompany any reliability claim.

### 4.4 Research hypotheses

H1: Test-feedback iteration improves official resolution over single-shot generation
under equal budgets. H2: Independent fresh verification reduces acceptance caused by
workspace contamination. H3: Typed action contracts reduce invalid tool invocation
relative to unconstrained command text. H4: Parameter-efficient training on reviewed
trajectories can improve action validity or resolution without contaminating evaluation.
These are proposed hypotheses, not findings established by the local tests.

## 5. System implementation

### 5.1 Control plane and persistence

The authenticated API exposes project policies, run submission, events, artifacts,
review and research export. The browser polls current state, renders source-bearing
content as text and keeps the credential in session memory. The database stores runs,
events and artifacts with indexed queue and cursor access.

Submission checks idempotency and capacity in a transaction. PostgreSQL workers claim
rows with skip-locked semantics; the local SQLite path uses a conditional state change.
Every state/event publication requires the current owner and lease. PostgreSQL uses
database time for lease comparisons. Final state, patch artifact and completion event
commit atomically. Cancellation clears authority; stale workers cannot overwrite it.

### 5.2 Source and execution plane

Committed blobs are read directly from Git, independent of dirty working files and
archive attributes. Validated source bytes enter an offline container without a host
checkout mount. The helper code is read-only and runs under isolated Python startup.
Model credentials stay in the worker process, separate from repository execution.

The sandbox restricts resources, privileges and networking. Disposable Git metadata
allows repository tooling inside the sandbox, while final patch derivation trusts
only the controller baseline. A new container tests each submitted candidate. This
provides reproducible separation between work-in-progress execution and final evidence.

### 5.3 Research pipeline

Benchmark intake omits solution fields. Prediction exports match the external harness
schema and preserve failed attempts. Approved trace preparation reconstructs action
contexts, deduplicates exact examples and holds out entire repository keys. The optional
LoRA trainer masks prompt tokens and predicts action JSON; the QLoRA path quantizes the
base model while training low-rank adapters on supported CUDA hardware. No model was
trained during this implementation exercise.

## 6. Testing and evaluation design

The authoritative local evidence record is VALIDATION.md and its machine-readable
pytest XML. Component tests cover auth/schema limits, idempotency, queue contention,
lease expiry, cancellation fencing, patch application, path boundaries, process bounds,
planning/read requirements, protected tests, model transport, benchmark leakage checks,
and repository-separated dataset preparation.

An authored scripted policy drives real reference-code tests through a failed candidate
and a corrected candidate. That experiment tests orchestration, not model intelligence.
Browser QA demonstrates login, project-policy viewing, actual queue submission and
cancellation, evaluation empty-state behavior and runtime readiness reporting.
Docker and PostgreSQL integration tests are gated separately; their absence locally
is explicitly reported. Live CPU inference returned a premature submit under aci-v1;
aci-v2 returned a valid initial plan. This is a smoke test, not a completed repair.
Official benchmark, GPU training and live-model repair experiments remain open.

For official outcomes r_i over N submitted instances, report `Σr_i/N`, patch-application
rate, invalid-action frequency, token usage, elapsed-time quantiles and infrastructure
failures. Keep empty predictions in the denominator. Report uncertainty and account
for repository dependence. Preserve dataset/checkpoint revisions, image digests,
prompt version, budgets and decoding settings with each experiment.

## 7. Security and threats to validity

Prompt injection can influence model actions; prompts alone do not enforce safety.
Docker shares a kernel and is not a proof against hostile multi-tenant workloads.
Protected tests cannot prevent all indirect evasion. Shared operator authentication
is not per-user authorization. Source traces can contain sensitive code and require
private storage, provider consent and reviewed retention.

Experimental validity can be compromised by gold-patch leakage, overlapping training
and evaluation repositories, changing dependency environments, unreported failed
attempts, model nondeterminism and selecting favorable repeated runs. Local test success
must not substitute for the official harness outcome. Optional quantization results
must include hardware/cost/accuracy measurements rather than theoretical memory claims.

## 8. Scaling and deployment discussion

API replicas and execution workers can share PostgreSQL state. Dedicated worker hosts
must have consistent project registrations and trusted images. Admission is bounded;
lease fencing limits stale writes. Initial capacity estimation can use
`workers ≥ ceil(λ E[S]/ρ)` under steady-state assumptions, but measured tail duration
and resource contention determine deployment capacity.

Further production work includes HA database operations, immutable shared artifact
storage, stronger execution isolation, OIDC/RBAC, per-tenant quotas, centralized
observability, host-recovery orphan supervision, future schema migrations and load/failure
experiments. These are explicit extensions and release gates, not hidden placeholders
presented as completed distributed infrastructure.

## 9. Conclusion

This fresh implementation operationalizes the abstract's execution-grounded agent
framework while maintaining clear boundaries between model suggestions, observed
behavior, human review and independent evaluation. Its source, tests, UI and research
utilities form a concrete major-project artifact. The next scientific contribution
must come from reproducible live-model and benchmark experiments; those results must
be measured rather than inferred from implementation quality.

## References

1. Supplied KITSW U18IT707 DevMind Phase-1 abstract, preserved with SHA-256 provenance.
2. SWE-bench, Evaluation Guide: https://www.swebench.com/SWE-bench/guides/evaluation/
3. SWE-bench harness source: https://github.com/swe-bench/SWE-bench/blob/main/swebench/harness/run_evaluation.py
4. SQLAlchemy, SELECT and related constructs: https://docs.sqlalchemy.org/en/20/core/selectable.html
5. Hugging Face PEFT, Quantization: https://huggingface.co/docs/peft/en/developer_guides/quantization
6. Hugging Face Transformers, Trainer: https://huggingface.co/docs/transformers/main_classes/trainer

Primary online references were consulted on 18 November 2026. Full engineering
contracts, operational limits and reproducible commands accompany this manuscript.
