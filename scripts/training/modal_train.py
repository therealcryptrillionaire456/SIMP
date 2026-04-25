"""ProjectX Economic Brain - Modal Training Launcher
Run: modal run scripts/training/modal_train.py --phase 1
Requirements: pip install modal
Setup: modal token new

Uses @app.function API (stable for Modal 1.4)
"""

import modal

HF_USERNAME = "automationkasey"

image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install(
        "transformers>=4.36.0",
        "datasets",
        "accelerate>=0.24.0",
        "peft>=0.7.0",
        "trl>=0.12.0",
        "bitsandbytes",
        "huggingface_hub",
    )
    .env({"HF_USERNAME": HF_USERNAME})
)

app = modal.App("projectx-economic-brain")

HF_SECRET = modal.Secret.from_name("huggingface")


@app.function(gpu="H100", image=image, timeout=3600 * 3, secrets=[HF_SECRET])
def run_sft():
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import LoraConfig
    from trl import SFTTrainer, SFTConfig

    H = "automationkasey"

    print("=" * 60)
    print("PHASE 1: SFT on Modal (A10G)")
    print("=" * 60)
    print(f"User: {H}")

    MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"

    print(f"Loading model: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        device_map="auto",
        trust_remote_code=True,
    )

    print("Loading gbharti/finance-alpaca...")
    dataset = load_dataset("gbharti/finance-alpaca", split="train")

    def fmt(example):
        return {
            "text": f"<|im_start|>user\n{example['instruction']}<|im_end|>\n<|im_start|>assistant\n{example['output']}<|im_end|>"
        }

    dataset = dataset.map(fmt)
    split = dataset.train_test_split(test_size=0.1, seed=42)

    print(f"Train: {len(split['train'])} | Eval: {len(split['test'])}")

    config = SFTConfig(
        output_dir="projectx-economic-brain-sft",
        push_to_hub=True,
        hub_model_id=f"{H}/projectx-economic-brain-sft",
        hub_strategy="every_save",
        num_train_epochs=2,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=16,
        learning_rate=2e-4,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        logging_steps=10,
        save_steps=100,
        save_total_limit=2,
        eval_steps=100,
        report_to="none",
        dataset_text_field="text",
        packing=True,
        max_length=2048,
        gradient_checkpointing=True,
    )

    peft_config = LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05,
        bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    )

    trainer = SFTTrainer(
        model=model, processing_class=tokenizer,
        train_dataset=split["train"], eval_dataset=split["test"],
        args=config, peft_config=peft_config,
    )

    print("Starting SFT training (~30-60 min)...")
    trainer.train()
    trainer.push_to_hub()
    print(f"✅ SFT done: https://huggingface.co/{H}/projectx-economic-brain-sft")


@app.function(gpu="H100", image=image, timeout=3600 * 3, secrets=[HF_SECRET])
def run_dpo():
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import LoraConfig
    from trl import DPOTrainer, DPOConfig

    H = "automationkasey"

    print("=" * 60)
    print("PHASE 2: DPO on Modal (A10G)")
    print("=" * 60)
    print(f"User: {H}")

    MODEL_NAME = f"{H}/projectx-economic-brain-sft"

    print(f"Loading SFT model: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        device_map="auto",
        trust_remote_code=True,
    )

    print(f"Loading ProjectX DPO dataset...")
    dataset = load_dataset(f"{H}/projectx-dpo-dataset", split="train")
    split = dataset.train_test_split(test_size=0.1, seed=42)

    print(f"Train: {len(split['train'])} | Eval: {len(split['test'])}")

    config = DPOConfig(
        output_dir="projectx-economic-brain-dpo",
        push_to_hub=True,
        hub_model_id=f"{H}/projectx-economic-brain-dpo",
        hub_strategy="every_save",
        num_train_epochs=1,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=1e-5,
        beta=0.3,
        warmup_ratio=0.1,
        logging_steps=10,
        save_steps=100,
        save_total_limit=2,
        eval_steps=100,
        remove_unused_columns=False,
        gradient_checkpointing=True,
        report_to="none",
    )

    peft_config = LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05,
        bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    )

    trainer = DPOTrainer(
        model=model, ref_model=None, processing_class=tokenizer,
        train_dataset=split["train"], eval_dataset=split["test"],
        args=config, peft_config=peft_config,
    )

    print("Starting DPO training (~30-60 min)...")
    trainer.train()
    trainer.push_to_hub()
    print(f"✅ DPO done: https://huggingface.co/{H}/projectx-economic-brain-dpo")


@app.local_entrypoint()
def main(phase: int = 1):
    """Submit ProjectX Economic Brain training to Modal.
    
    Usage: modal run scripts/training/modal_train.py --phase 1
           modal run scripts/training/modal_train.py --phase 2
    """
    print(f"🚀 Starting Phase {phase} on Modal (A10G)...")
    print(f"   Estimated cost: ~$0.30-0.60 per phase")
    print(f"   HF Username: {HF_USERNAME}")
    print(f"   GPU: A10G")
    print()

    if phase == 1:
        run_sft.remote()
    elif phase == 2:
        run_dpo.remote()
    else:
        print("Phase must be 1 (SFT) or 2 (DPO)")
