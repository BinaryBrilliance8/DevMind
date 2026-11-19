"""Train a local LoRA/QLoRA adapter on explicitly reviewed DevMind examples.

Optional GPU workflow. No weights are downloaded or uploaded by this program.
"""

import argparse
import hashlib
import json
from importlib.metadata import version
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reviewed", action="store_true", required=True)
    parser.add_argument("--four-bit", action="store_true")
    parser.add_argument("--max-steps", type=int, default=100)
    parser.add_argument("--max-length", type=int, default=4096)
    args = parser.parse_args()
    if not args.checkpoint.is_dir() or args.max_steps < 1 or args.max_length < 512:
        raise ValueError("Use an existing local checkpoint and valid training limits")
    if args.output.exists() and any(args.output.iterdir()):
        raise ValueError("Output directory must be empty to preserve existing adapters")

    import torch
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        DataCollatorForSeq2Seq,
        Trainer,
        TrainingArguments,
    )

    if args.four_bit and not torch.cuda.is_available():
        raise ValueError("This QLoRA path requires a supported CUDA GPU")
    tokenizer = AutoTokenizer.from_pretrained(
        str(args.checkpoint), local_files_only=True, trust_remote_code=False
    )
    if not tokenizer.chat_template or tokenizer.eos_token_id is None:
        raise ValueError("Checkpoint needs a chat template and an EOS token")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    examples = []
    for line in args.data.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        prompt = tokenizer.apply_chat_template(
            row["prompt"], tokenize=True, add_generation_prompt=True
        )
        target = tokenizer.encode(row["completion"], add_special_tokens=False) + [
            tokenizer.eos_token_id
        ]
        # Reject oversized examples rather than silently dropping policy context.
        if len(prompt) + len(target) > args.max_length:
            continue
        examples.append(
            {
                "input_ids": prompt + target,
                "attention_mask": [1] * (len(prompt) + len(target)),
                "labels": [-100] * len(prompt) + target,
            }
        )
    if not examples:
        raise ValueError(
            "No examples fit the training context; review data and max-length"
        )
    options = {"local_files_only": True, "trust_remote_code": False}
    if args.four_bit:
        options["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_use_double_quant=True,
            bnb_4bit_compute_dtype=torch.bfloat16
            if torch.cuda.is_bf16_supported()
            else torch.float16,
        )
        options["device_map"] = {"": torch.cuda.current_device()}
    model = AutoModelForCausalLM.from_pretrained(str(args.checkpoint), **options)
    if args.four_bit:
        model = prepare_model_for_kbit_training(model)
    model = get_peft_model(
        model,
        LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            target_modules="all-linear",
            task_type="CAUSAL_LM",
        ),
    )
    model.config.use_cache = False
    arguments = TrainingArguments(
        output_dir=str(args.output),
        max_steps=args.max_steps,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        logging_steps=5,
        save_steps=50,
        save_total_limit=2,
        report_to="none",
        seed=42,
        bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
        push_to_hub=False,
        remove_unused_columns=False,
    )
    trainer = Trainer(
        model=model,
        args=arguments,
        train_dataset=examples,
        processing_class=tokenizer,
        data_collator=DataCollatorForSeq2Seq(
            tokenizer, padding=True, label_pad_token_id=-100, pad_to_multiple_of=8
        ),
    )
    outcome = trainer.train()
    trainer.save_model(str(args.output))
    tokenizer.save_pretrained(str(args.output))
    manifest = {
        "checkpoint": str(args.checkpoint.resolve()),
        "four_bit": args.four_bit,
        "examples": len(examples),
        "data_sha256": hashlib.sha256(args.data.read_bytes()).hexdigest(),
        "versions": {name: version(name) for name in ("torch", "transformers", "peft")},
        "metrics": outcome.metrics,
    }
    (args.output / "devmind-training-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )


if __name__ == "__main__":
    main()
