#!/usr/bin/env python3
"""
ProjectX Economic Brain - Google Colab Launcher
Run this in Colab with a T4 (free) or A100 runtime.
Paste entire file into a Colab cell, or:
  !wget https://raw.githubusercontent.com/automationkasey/simp/main/scripts/training/train_projectx_colab.py
  %run train_projectx_colab.py --phase 1
"""

import os
import sys
import argparse

PHASE = int(os.getenv("PHASE", "1"))
HF_USERNAME = os.getenv("HF_USERNAME", "automationkasey")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")


def colab_setup():
    """Install dependencies in Colab environment."""
    print("=" * 60)
    print("ProjectX Economic Brain - Colab Setup")
    print("=" * 60)
    
    # Install core dependencies
    deps = [
        "transformers>=4.36.0",
        "datasets",
        "accelerate>=0.24.0",
        "peft>=0.7.0",
        "trl>=0.12.0",
        "bitsandbytes",
        "wandb",
    ]
    
    for dep in deps:
        print(f"Installing {dep}...")
        os.system(f"pip install -q {dep}")
    
    # Login to HF if token is set
    hf_token = os.getenv("HF_TOKEN", os.getenv("HUGGINGFACE_TOKEN", ""))
    if hf_token:
        from huggingface_hub import login
        login(token=hf_token, add_to_git_credential=True)
        print("✅ HuggingFace logged in")
    else:
        print("⚠️  No HF_TOKEN set. Models won't push to Hub.")
        print("   Set HF_TOKEN in Colab secrets or env.")
    
    print("✅ Colab setup complete\n")


def run_lightweight_sft():
    """4-bit QLoRA SFT on T4 (fits in 15GB VRAM)."""
    print("=" * 60)
    print("PHASE 1: Lightweight SFT (4-bit QLoRA)")
    print("=" * 60)
    
    from datasets import load_dataset
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
    )
    from peft import LoraConfig, prepare_model_for_kbit_training
    from trl import SFTTrainer, SFTConfig
    
    # 4-bit quantization config
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype="float16",
        bnb_4bit_use_double_quant=True,
    )
    
    print(f"Loading model: {MODEL_NAME}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)
    
    # Load financial datasets
    print("Loading datasets...")
    try:
        dataset = load_dataset("gbharti/finance-alpaca", split="train")
    except Exception:
        try:
            dataset = load_dataset("kashif/finance-bench", split="train")
        except Exception:
            print("⚠️  No external datasets, using ProjectX DPO as SFT base")
            dataset = load_dataset(f"{HF_USERNAME}/projectx-dpo-dataset", split="train")
            dataset = dataset.rename_column("prompt", "instruction")
    
    def format_sft(example):
        if "instruction" in example and "output" in example:
            text = f"<|im_start|>user\n{example['instruction']}<|im_end|>\n<|im_start|>assistant\n{example['output']}<|im_end|>"
        else:
            text = example.get("text", str(example))
        return {"text": text}
    
    dataset = dataset.map(format_sft)
    split = dataset.train_test_split(test_size=0.1, seed=42)
    
    sft_config = SFTConfig(
        output_dir="/content/projectx-economic-brain-sft",
        push_to_hub=True,
        hub_model_id=f"{HF_USERNAME}/projectx-economic-brain-sft",
        hub_strategy="every_save",
        num_train_epochs=2,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        logging_steps=10,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=2,
        eval_strategy="steps",
        eval_steps=100,
        report_to="none",
        max_seq_length=1024,
    )
    
    peft_config = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    )
    
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=split["train"],
        eval_dataset=split["test"],
        args=sft_config,
        peft_config=peft_config,
    )
    
    print("Starting SFT (T4 should complete in ~30-60min)...")
    trainer.train()
    trainer.push_to_hub()
    
    print(f"✅ SFT complete! Model: https://huggingface.co/{HF_USERNAME}/projectx-economic-brain-sft")


def run_lightweight_dpo():
    """4-bit QLoRA DPO on T4."""
    print("=" * 60)
    print("PHASE 2: Lightweight DPO Alignment (4-bit QLoRA)")
    print("=" * 60)
    
    from datasets import load_dataset
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
    )
    from peft import LoraConfig, prepare_model_for_kbit_training
    from trl import DPOTrainer, DPOConfig
    
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype="float16",
        bnb_4bit_use_double_quant=True,
    )
    
    print("Loading base model...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token
    
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    
    # Load DPO dataset
    print("Loading ProjectX preference dataset...")
    try:
        dataset = load_dataset(f"{HF_USERNAME}/projectx-dpo-dataset", split="train")
    except Exception as e:
        print(f"  Hub load failed: {e}")
        dataset = load_dataset("scripts/training/projectx_dpo_dataset", split="train")
    
    print(f"Loaded {len(dataset)} preference pairs")
    split = dataset.train_test_split(test_size=0.1, seed=42)
    
    dpo_config = DPOConfig(
        output_dir="/content/projectx-economic-brain-dpo",
        push_to_hub=True,
        hub_model_id=f"{HF_USERNAME}/projectx-economic-brain-dpo",
        hub_strategy="every_save",
        num_train_epochs=2,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=1e-5,
        beta=0.3,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        logging_steps=10,
        save_strategy="steps",
        save_steps=100,
        save_total_limit=2,
        eval_strategy="steps",
        eval_steps=100,
        report_to="none",
        remove_unused_columns=False,
        gradient_checkpointing=True,
    )
    
    peft_config = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    )
    
    trainer = DPOTrainer(
        model=model,
        ref_model=None,
        tokenizer=tokenizer,
        train_dataset=split["train"],
        eval_dataset=split["test"],
        args=dpo_config,
        peft_config=peft_config,
    )
    
    print("Starting DPO (T4 should complete in ~30-60min)...")
    trainer.train()
    trainer.push_to_hub()
    
    print(f"✅ DPO complete! Model: https://huggingface.co/{HF_USERNAME}/projectx-economic-brain-dpo")


def main():
    parser = argparse.ArgumentParser(description="ProjectX Economic Brain - Colab Training")
    parser.add_argument("--phase", type=int, default=os.getenv("PHASE", "1"), choices=[1, 2],
                        help="1=SFT, 2=DPO")
    parser.add_argument("--setup", action="store_true", default=True,
                        help="Run environment setup")
    parser.add_argument("--hf-username", default=None)
    parser.add_argument("--model-name", default=None)
    
    args = parser.parse_args()
    
    global HF_USERNAME, MODEL_NAME, PHASE  # noqa: F821
    HF_USERNAME = args.hf_username or HF_USERNAME
    MODEL_NAME = args.model_name or MODEL_NAME
    PHASE = args.phase
    
    if args.setup:
        colab_setup()
    
    if PHASE == 1:
        run_lightweight_sft()
    else:
        run_lightweight_dpo()
    
    print(f"\n🎉 Training Phase {PHASE} Complete!")
    print(f"   Model: https://huggingface.co/{HF_USERNAME}/projectx-economic-brain-{'sft' if PHASE == 1 else 'dpo'}")


if __name__ == "__main__":
    main()
