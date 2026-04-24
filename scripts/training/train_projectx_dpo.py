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
ProjectX Economic Brain - DPO Training
Aligns the model to prefer revenue-generating, balanced decisions.

This script runs DPO (Direct Preference Optimization) to teach the model
to make better economic decisions based on preference pairs generated from
ProjectX operational data.
"""

import trackio
from datasets import load_dataset
from peft import LoraConfig
from trl import DPOTrainer, DPOConfig

# Load the DPO dataset
# For HF Jobs, ensure this dataset is on Hub OR use load_from_disk for local
DATASET_NAME = "automationkasey/projectx-dpo-dataset"  # UPDATE: Push dataset to Hub first
MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"

print("Loading dataset...")
try:
    dataset = load_dataset(DATASET_NAME, split="train")
except Exception as e:
    print(f"Could not load from Hub, trying local...")
    dataset = load_dataset("scripts/training/projectx_dpo_dataset", split="train")

print(f"Dataset loaded: {len(dataset)} preference pairs")

# Create train/eval split
dataset_split = dataset.train_test_split(test_size=0.1, seed=42)
train_dataset = dataset_split["train"]
eval_dataset = dataset_split["test"]

# DPO Training Configuration
# IMPORTANT: Adjust beta (KL penalty) based on how much you want to follow preferences vs stay close to base model
# Higher beta (0.5-1.0) = more conservative, less change from base
# Lower beta (0.1-0.3) = more aggressive alignment to preferences
config = DPOConfig(
    # Hub settings
    output_dir="projectx-economic-brain-dpo",
    push_to_hub=True,
    hub_model_id="automationkasey/projectx-economic-brain-dpo",  # UPDATE THIS
    hub_strategy="every_save",
    
    # Training parameters
    num_train_epochs=3,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,  # Effective batch size: 16
    learning_rate=1e-5,  # DPO typically uses lower LR than SFT
    beta=0.3,  # KL penalty coefficient - controls how much to follow preferences
    
    # Optimization
    warmup_ratio=0.1,
    lr_scheduler_type="cosine",
    max_grad_norm=0.3,
    
    # Logging & checkpointing
    logging_steps=10,
    save_strategy="steps",
    save_steps=200,
    save_total_limit=2,
    
    # Evaluation
    eval_strategy="steps",
    eval_steps=200,
    
    # Monitoring
    report_to="trackio",
    project="projectx-economic-brain",
    run_name="v1-dpo-alignment",
    
    # DPO-specific
    remove_unused_columns=False,
    gradient_checkpointing=True,  # Save memory
)

# LoRA Configuration - use same target modules as SFT
peft_config = LoraConfig(
    r=16,
    lora_alpha=32,
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
)

# Initialize DPO Trainer
print("Initializing DPO trainer...")
trainer = DPOTrainer(
    model=MODEL_NAME,
    train_dataset=train_dataset,
    eval_dataset=eval_dataset,
    args=config,
    peft_config=peft_config,
    # Reference model is auto-created from base model
)

print("Starting DPO training...")
print("This aligns the model to prefer revenue-optimizing decisions...")
trainer.train()

print("Pushing to Hub...")
trainer.push_to_hub()

trackio.finish()

print("=" * 60)
print("DPO Training Complete!")
print(f"Model: https://huggingface.co/automationkasey/projectx-economic-brain-dpo")
print("=" * 60)
