#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "trl>=0.12.0",
#     "peft>=0.7.0",
#     "transformers>=4.36.0",
#     "accelerate>=0.24.0",
#     "trackio",
#     "datasets",
# ]
# ///
"""
ProjectX Economic Brain - Full Training Pipeline
Phase 1: SFT on financial datasets
Phase 2: DPO on ProjectX operational preferences

Run this as TWO separate jobs:
  1. SFT job (this script, set PHASE=1)
  2. DPO job (train_projectx_dpo.py, set PHASE=2)
"""

import os
import trackio
from datasets import load_dataset
from peft import LoraConfig
from trl import SFTTrainer, SFTConfig, DPOTrainer, DPOConfig

PHASE = int(os.getenv("PHASE", "1"))
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct")
HF_USERNAME = os.getenv("HF_USERNAME", "automationkasey")

# ============= PHASE 1: SFT =============
def run_sft():
    print("=" * 60)
    print("PHASE 1: Supervised Fine-Tuning")
    print("=" * 60)
    
    # Load financial datasets
    print("Loading financial datasets...")
    datasets = []
    
    try:
        ds1 = load_dataset("gbharti/finance-alpaca", split="train")
        datasets.append(("finance-alpaca", ds1))
        print(f"  + gbharti/finance-alpaca: {len(ds1)} examples")
    except Exception as e:
        print(f"  ! Skipped finance-alpaca: {e}")
    
    try:
        ds2 = load_dataset("kashif/finance-bench", split="train")
        datasets.append(("finance-bench", ds2))
        print(f"  + kashif/finance-bench: {len(ds2)} examples")
    except Exception as e:
        print(f"  ! Skipped finance-bench: {e}")
    
    try:
        ds3 = load_dataset("financial_phrasebank", "sentences_allagree", split="train")
        datasets.append(("financial_phrasebank", ds3))
        print(f"  + financial_phrasebank: {len(ds3)} examples")
    except Exception as e:
        print(f"  ! Skipped financial_phrasebank: {e}")
    
    # For simplicity, use the first available dataset
    # In production, you'd concatenate and format them properly
    if not datasets:
        raise ValueError("No datasets loaded successfully!")
    
    dataset_name, dataset = datasets[0]
    
    # Format for SFT (adjust based on actual dataset format)
    def format_for_sft(example):
        if "instruction" in example and "output" in example:
            return {
                "text": f"<|im_start|>user\n{example['instruction']}<|im_end|>\n<|im_start|>assistant\n{example['output']}<|im_end|>"
            }
        elif "text" in example:
            return example
        return example
    
    dataset = dataset.map(format_for_sft)
    
    # Split
    dataset_split = dataset.train_test_split(test_size=0.1, seed=42)
    train_dataset = dataset_split["train"]
    eval_dataset = dataset_split["test"]
    
    print(f"Train: {len(train_dataset)}, Eval: {len(eval_dataset)}")
    
    # SFT Config
    sft_config = SFTConfig(
        output_dir="projectx-economic-brain-sft",
        push_to_hub=True,
        hub_model_id=f"{HF_USERNAME}/projectx-economic-brain-sft",
        hub_strategy="every_save",
        
        num_train_epochs=3,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=8,
        learning_rate=2e-4,
        
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        max_grad_norm=0.3,
        
        logging_steps=10,
        save_strategy="steps",
        save_steps=200,
        save_total_limit=2,
        
        eval_strategy="steps",
        eval_steps=200,
        
        report_to="trackio",
        project="projectx-economic-brain",
        run_name="v1-sft-financial",
        
        max_seq_length=2048,
    )
    
    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    )
    
    print("Starting SFT training...")
    trainer = SFTTrainer(
        model=MODEL_NAME,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        args=sft_config,
        peft_config=peft_config,
    )
    
    trainer.train()
    trainer.push_to_hub()
    
    print("SFT Complete!")
    return f"{HF_USERNAME}/projectx-economic-brain-sft"

# ============= PHASE 2: DPO =============
def run_dpo():
    print("=" * 60)
    print("PHASE 2: Direct Preference Optimization")
    print("=" * 60)
    
    # Load ProjectX preference dataset
    print("Loading ProjectX preference dataset...")
    try:
        dataset = load_dataset(f"{HF_USERNAME}/projectx-dpo-dataset", split="train")
    except:
        dataset = load_dataset("scripts/training/projectx_dpo_dataset", split="train")
    
    print(f"Dataset loaded: {len(dataset)} preference pairs")
    
    dataset_split = dataset.train_test_split(test_size=0.1, seed=42)
    train_dataset = dataset_split["train"]
    eval_dataset = dataset_split["test"]
    
    # DPO Config
    dpo_config = DPOConfig(
        output_dir="projectx-economic-brain-dpo",
        push_to_hub=True,
        hub_model_id=f"{HF_USERNAME}/projectx-economic-brain-dpo",
        hub_strategy="every_save",
        
        num_train_epochs=3,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=8,
        learning_rate=1e-5,
        beta=0.3,
        
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        max_grad_norm=0.3,
        
        logging_steps=10,
        save_strategy="steps",
        save_steps=200,
        save_total_limit=2,
        
        eval_strategy="steps",
        eval_steps=200,
        
        report_to="trackio",
        project="projectx-economic-brain",
        run_name="v2-dpo-alignment",
        
        remove_unused_columns=False,
        gradient_checkpointing=True,
    )
    
    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    )
    
    print("Starting DPO training...")
    trainer = DPOTrainer(
        model=MODEL_NAME,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        args=dpo_config,
        peft_config=peft_config,
    )
    
    trainer.train()
    trainer.push_to_hub()
    
    print("DPO Complete!")
    return f"{HF_USERNAME}/projectx-economic-brain-dpo"

# ============= MAIN =============
def main():
    print(f"Starting Phase {PHASE}...")
    print(f"Model: {MODEL_NAME}")
    print(f"HuggingFace Username: {HF_USERNAME}")
    print()
    
    if PHASE == 1:
        model_id = run_sft()
    elif PHASE == 2:
        model_id = run_dpo()
    else:
        raise ValueError(f"Unknown phase: {PHASE}")
    
    trackio.finish()
    
    print("=" * 60)
    print(f"Training Phase {PHASE} Complete!")
    print(f"Model: https://huggingface.co/{model_id}")
    print("=" * 60)

if __name__ == "__main__":
    main()
