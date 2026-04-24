"""ProjectX Economic Brain - Modal Training Launcher
Run: modal run scripts/training/modal_train.py --phase 1
Requirements: modal pip install
Setup: modal token new
"""

import os
import modal

HF_USERNAME = os.getenv("HF_USERNAME", "automationkasey")
HF_TOKEN = os.getenv("HF_TOKEN", "")

app = modal.App("projectx-economic-brain")

# GPU config - A10G is great value
gpu_config = modal.gpu.A10G(count=1)

# Build image with training deps
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
    .env({"HF_USERNAME": HF_USERNAME, "HF_TOKEN": HF_TOKEN})
)


@app.cls(gpu=gpu_config, image=image, timeout=3600 * 3, secrets=[modal.Secret.from_name("huggingface")])
class ProjectXTrainer:
    def __init__(self, phase: int = 1):
        self.phase = phase
        self.hf_username = os.environ["HF_USERNAME"]
    
    def run_sft(self):
        from datasets import load_dataset
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import LoraConfig
        from trl import SFTTrainer, SFTConfig
        
        print("=" * 60)
        print("PHASE 1: SFT on Modal")
        print("=" * 60)
        
        MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"
        
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
        tokenizer.pad_token = tokenizer.eos_token
        
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            device_map="auto",
            trust_remote_code=True,
        )
        
        # Load financial dataset
        dataset = load_dataset("gbharti/finance-alpaca", split="train")
        
        def fmt(example):
            return {
                "text": f"<|im_start|>user\n{example['instruction']}<|im_end|>\n<|im_start|>assistant\n{example['output']}<|im_end|>"
            }
        
        dataset = dataset.map(fmt)
        split = dataset.train_test_split(test_size=0.1, seed=42)
        
        config = SFTConfig(
            output_dir="projectx-economic-brain-sft",
            push_to_hub=True,
            hub_model_id=f"{self.hf_username}/projectx-economic-brain-sft",
            hub_strategy="every_save",
            num_train_epochs=2,
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            learning_rate=2e-4,
            warmup_ratio=0.1,
            lr_scheduler_type="cosine",
            logging_steps=10,
            save_steps=100,
            save_total_limit=2,
            eval_steps=100,
            max_seq_length=2048,
            report_to="none",
        )
        
        peft_config = LoraConfig(
            r=16, lora_alpha=32, lora_dropout=0.05,
            bias="none", task_type="CAUSAL_LM",
            target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
        )
        
        trainer = SFTTrainer(
            model=model, tokenizer=tokenizer,
            train_dataset=split["train"], eval_dataset=split["test"],
            args=config, peft_config=peft_config,
        )
        
        trainer.train()
        trainer.push_to_hub()
        print(f"✅ SFT done: https://huggingface.co/{self.hf_username}/projectx-economic-brain-sft")
    
    def run_dpo(self):
        from datasets import load_dataset
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import LoraConfig
        from trl import DPOTrainer, DPOConfig
        
        print("=" * 60)
        print("PHASE 2: DPO on Modal")
        print("=" * 60)
        
        MODEL_NAME = os.getenv("MODEL_NAME", f"{self.hf_username}/projectx-economic-brain-sft")
        
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME, trust_remote_code=True)
        tokenizer.pad_token = tokenizer.eos_token
        
        model = AutoModelForCausalLM.from_pretrained(
            MODEL_NAME,
            device_map="auto",
            trust_remote_code=True,
        )
        
        dataset = load_dataset(f"{self.hf_username}/projectx-dpo-dataset", split="train")
        split = dataset.train_test_split(test_size=0.1, seed=42)
        
        config = DPOConfig(
            output_dir="projectx-economic-brain-dpo",
            push_to_hub=True,
            hub_model_id=f"{self.hf_username}/projectx-economic-brain-dpo",
            hub_strategy="every_save",
            num_train_epochs=2,
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
            model=model, ref_model=None, tokenizer=tokenizer,
            train_dataset=split["train"], eval_dataset=split["test"],
            args=config, peft_config=peft_config,
        )
        
        trainer.train()
        trainer.push_to_hub()
        print(f"✅ DPO done: https://huggingface.co/{self.hf_username}/projectx-economic-brain-dpo")


@app.local_entrypoint()
def main(phase: int = 1):
    """Submit ProjectX Economic Brain training to Modal.
    
    Usage: modal run scripts/training/modal_train.py --phase 1
           modal run scripts/training/modal_train.py --phase 2
    """
    print(f"Starting Phase {phase} on Modal (A10G)...")
    print(f"Estimated cost: ~$0.50-1.00 per phase")
    print(f"HF Username: {HF_USERNAME}")
    
    trainer = ProjectXTrainer(phase=phase)
    
    if phase == 1:
        trainer.run_sft.remote()
    elif phase == 2:
        trainer.run_dpo.remote()
    else:
        print("Phase must be 1 (SFT) or 2 (DPO)")
