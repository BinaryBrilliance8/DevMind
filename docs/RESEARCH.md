# Evaluation and learning workflow

## Separate labels and evidence

A submitted action, a passing local command, an approved patch, and an officially
resolved benchmark instance are different observations. The UI preserves those
distinctions. The scripted policy in tests verifies orchestration, not LLM capability.
No numeric model score is supplied as though it had been measured.

## SWE-bench

Prepare a JSONL of dataset instances and a JSON mapping from dataset repository names
to operator-registered project keys. Clone the required commits and build appropriate
dependency images before submitting work.

```bash
python -m devmind.research import-benchmark instances.jsonl \
  --mapping repository-map.json --experiment run-001
```

The importer copies only instance ID, repository mapping, problem statement and base
commit. Gold patch and test patch fields do not enter task prompts. Duplicate instance
IDs in one input are rejected. Experiment ID participates in idempotency so retries
of one import are safe and new experiments remain distinct. Queue capacity can require
batched imports; already admitted rows remain admitted if a later row hits capacity.

The UI exports terminal benchmark runs as JSONL. Each prediction has `instance_id`,
`model_name_or_path`, and `model_patch`; duplicate instance IDs are rejected by the
bulk export rather than silently selecting a favorable attempt. You may export a
specific run through its prediction endpoint. Failed runs may have empty patches;
keep them in the denominator.

Run the official harness separately in its pinned environment:

```bash
python -m swebench.harness.run_evaluation \
  --dataset_name SWE-bench/SWE-bench_Lite \
  --predictions_path predictions.jsonl \
  --max_workers 2 --run_id devmind_run_001_unique
```

Consult the [official evaluation guide](https://www.swebench.com/SWE-bench/guides/evaluation/)
and [harness source](https://github.com/swe-bench/SWE-bench/blob/main/swebench/harness/run_evaluation.py)
for the installed version. Use unique run IDs for changed predictions; result caching
can otherwise reuse earlier results. The agent's generation image is not a replacement
for the harness's official evaluation environment.

For a matching official report containing `resolved_ids`:

```bash
python research/summarize_results.py predictions.jsonl official-report.json
```

The script uses all submitted prediction IDs, rejects mismatched IDs, and reports
resolution fraction with a Wilson 95% interval. It does not adjust for within-repository
dependence; use a repository-aware analysis for comparative claims.

## Training-data preparation

After actual human review, download approved trajectories with explicit consent:
`GET /api/runs/RUN_ID/trajectory?consent=true`. The content can include source code.
Combine reviewed JSONL exports and separate repository-level holdouts:

```bash
python -m devmind.research prepare-training trajectories.jsonl \
  --output research-data --holdout held-out-project-key
```

This reconstructs issue/policy/observation contexts and typed JSON-action targets,
deduplicates exact examples and writes train/validation files and source hashes.
It rejects unapproved trajectories. Approval of the final patch is not approval
of every exploratory step: inspect individual actions, secrets and licenses before
training. Do not place evaluation repositories, related leaked solutions or official
gold patches into the training split. A zero-size split is reported explicitly;
ensure your selected corpus supports the intended experiment.

## Optional LoRA and 4-bit QLoRA

`research/train_lora.py` implements supervised adapter training on a locally available
chat-model checkpoint. It never downloads weights or uploads adapters. A model chat
template/EOS token is required. Prompt tokens are masked with -100, so the supervised
loss targets assistant JSON actions only. Overlong examples are rejected rather than
silently stripping the policy context. Output folders must be empty.

In a separate, compatible GPU environment, resolve and lock the optional dependencies:

```bash
python -m pip install -r research/requirements.txt
python research/train_lora.py --checkpoint /path/to/local/checkpoint \
  --data research-data/train.jsonl --output adapters/experiment-001 \
  --reviewed --max-steps 100
```

Add `--four-bit` for the implemented CUDA NF4/double-quantized QLoRA path. This path
requires compatible CUDA hardware and bitsandbytes. It is not claimed to run on
this macOS authoring environment. The script records dependency versions, dataset
hash, training metrics and checkpoint path alongside the adapter.

The implementation follows primary [PEFT quantization guidance](https://huggingface.co/docs/peft/en/developer_guides/quantization)
and the [Transformers Trainer interface](https://huggingface.co/docs/transformers/main_classes/trainer).
Those libraries evolve; pin the versions validated with the selected checkpoint/GPU
before an experiment. The optional training environment was not installed or trained
in this delivery, and no trained or quantized model is included.

## Experiments and mathematical definitions

For N submitted instances and official binary outcomes r_i:

`ResolutionRate = Σ_i r_i / N`.

For supervised observation/action pairs D:

`L(θ) = -Σ_(x,a in D) Σ_t log π_θ(a_t | x, a_<t)`.

LoRA represents a weight update as `ΔW = (α/r) BA`, where A and B have low rank r.
The included training script uses r=16 and α=32 as configurable code defaults, not
an experimentally optimal setting. QLoRA uses a quantized base with trainable adapters;
quantization benefits must be measured jointly with task quality and hardware cost.

Compare: single-shot versus iterative ACI at equal budgets; no-test-feedback versus
feedback; original versus independently verified outcomes; model variants at fixed
prompts/images; full precision versus quantized serving for the same eligible model.
Record model/checkpoint revision, image digest, dataset split/revision, prompt hash,
decoding, budgets, seeds, token usage, p50/p95 duration, invalid-action rate,
patch-application rate, infrastructure failures and independent resolution.
Report failed attempts and uncertainty, not only successful demonstrations.


## Audited official-harness launch

Install the official `swebench` package in an isolated evaluation environment with
Docker. Then run:

```bash
python -m devmind.evaluation predictions.jsonl --output experiments/attempt-001 --workers 1
```

The output directory must not exist. The launcher validates IDs and canonical fields,
retains empty-patch attempts, rejects duplicate IDs/mixed models, copies and hashes
predictions, records the installed harness version, creates a unique run ID and
propagates failure. Logs/reports remain in that attempt directory. This prevents
accidental reuse of old harness results. Use the official report with
`research/summarize_results.py`; a zero harness exit is not itself a resolution score.
The harness command follows the [official evaluation guide](https://www.swebench.com/SWE-bench/guides/evaluation/).

## Local inference evidence

`docs/inference-v1.json` and `docs/inference-v2.json` record genuine CPU completions
from Qwen2.5-Coder-1.5B-Instruct Q4_K_M, model revision
`f86cb2c1fa58255f8052cc32aeede1b7482d4361`, llama.cpp b12532. The original prompt
returned a premature submit; aci-v2 adds an explicit first-action example and returned
a plan. These two smoke observations establish neither general reliability nor
repair accuracy. Weights came from the [official Qwen repository](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF),
and the runtime from [llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases).
No model weights are included in the ZIP.

The tested CPU service arguments are:

```bash
llama-server -m /path/to/model.gguf --alias devmind-qwen-coder \
  --host 127.0.0.1 --port 18001 --ctx-size 8192 --parallel 1 --threads 4 \
  --device none --no-op-offload --no-kv-offload --fit off \
  --cors-origins http://127.0.0.1:18001
export DEVMIND_MODEL_URL=http://127.0.0.1:18001/v1
export DEVMIND_MODEL=devmind-qwen-coder
python research/check_model.py
```

This small model is a connectivity/contract validation choice, not a claim of strong
repository-level performance. GPU acceleration was unavailable to this sandbox.
