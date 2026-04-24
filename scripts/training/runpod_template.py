"""ProjectX Economic Brain - RunPod Template Config"""
# Save this to RunPod as a template, or deploy via CLI.
# 1. Go to https://www.runpod.io/console/gpu-cloud
# 2. Select: 1x RTX 4090 (~$0.34/hr) or 1x A100 ($1.10/hr)
# 3. Template: RunPod Pytorch (or custom Docker)
# 4. Start script (paste below into "Start Command"):

START_SCRIPT = r"""
#!/bin/bash
set -e

echo "=== ProjectX Economic Brain - RunPod Launcher ==="

# Install dependencies
pip install -q \
    transformers datasets accelerate peft trl bitsandbytes \
    huggingface_hub wandb

# Clone repo
cd /workspace
git clone https://github.com/automationkasey/simp.git
cd simp

# Login to HF
echo "$HF_TOKEN" | huggingface-cli login --token-stdin

# Run training
HF_USERNAME="${HF_USERNAME:-automationkasey}"
PHASE="${PHASE:-1}"
MODEL="${MODEL_NAME:-Qwen/Qwen2.5-7B-Instruct}"

# Phase 1: SFT
if [ "$PHASE" = "1" ]; then
    python3 scripts/training/train_projectx_economic_brain.py
fi

# Phase 2: DPO
if [ "$PHASE" = "2" ]; then
    MODEL_NAME="${MODEL_NAME:-automationkasey/projectx-economic-brain-sft}"
    PHASE=2 python3 scripts/training/train_projectx_economic_brain.py
fi

echo "=== Training Complete! ==="
echo "Models pushed to https://huggingface.co/$HF_USERNAME/projectx-economic-brain-*"
"""

# Environment variables needed:
# HF_TOKEN (secret/private)
# HF_USERNAME=automationkasey
# PHASE=1 (or 2)
# MODEL_NAME=Qwen/Qwen2.5-7B-Instruct (or SFT checkpoint for Phase 2)

if __name__ == "__main__":
    print("Copy the START_SCRIPT or use as RunPod template config.")
    print("Min cost: ~$0.50-1.00 for a full training run on RTX 4090.")
