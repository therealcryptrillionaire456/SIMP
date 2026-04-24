# ProjectX Economic Brain Training

Complete training pipeline to create an LLM economic brain for ProjectX.

## Overview

The economic brain will optimize ProjectX for:
- **Revenue generation** - maximizing value creation
- **Cost efficiency** - minimizing unnecessary spend
- **Risk-adjusted decisions** - balanced risk/reward tradeoffs
- **Resource allocation** - optimal distribution of compute/agent capacity

## Training Pipeline

### Phase 1: Supervised Fine-Tuning (SFT)
- Teaches financial/economic vocabulary and reasoning
- Uses HuggingFace datasets: `finance-alpaca`, `finance-bench`, `financial_phrasebank`
- Model learns domain knowledge before preference learning

### Phase 2: Direct Preference Optimization (DPO)
- Aligns model to ProjectX-specific preferences
- Based on YOUR operational data: trades, tasks, costs
- Teaches revenue optimization over generic financial reasoning

## Files

```
scripts/training/
├── projectx_dpo_converter.py     # Convert ProjectX logs → preference pairs
├── train_projectx_dpo.py         # DPO training script
├── train_projectx_economic_brain.py  # Combined SFT+DPO pipeline
└── convert_to_gguf.py           # GGUF conversion for local deployment
```

## Quick Start

### Step 1: Generate Preference Dataset

First, create the DPO dataset from your ProjectX operational data:

```bash
# Run locally (has network access)
python scripts/training/projectx_dpo_converter.py
```

This reads from your `data/` directory and creates preference pairs for:
- Cost optimization decisions
- Trade risk management
- Task routing optimization
- Revenue reasoning

### Step 2: Push Dataset to HuggingFace Hub

```bash
# Install HF CLI
curl -LsSf https://hf.co/cli/install.sh | bash

# Login
hf auth login

# Create dataset repo
hf repos create automationkasey/projectx-dpo-dataset --type dataset

# Upload
hf upload automationkasey/projectx-dpo-dataset scripts/training/projectx_dpo_dataset/
```

### Step 3: Submit Training Jobs

**SFT Job:**
```bash
hf jobs uv run scripts/training/train_projectx_economic_brain.py \
    --flavor a10g-large \
    --timeout 3h \
    --env PHASE=1 \
    --env HF_USERNAME=automationkasey \
    --secrets HF_TOKEN=$HF_TOKEN
```

**DPO Job (after SFT completes):**
```bash
hf jobs uv run scripts/training/train_projectx_economic_brain.py \
    --flavor a10g-large \
    --timeout 3h \
    --env PHASE=2 \
    --env HF_USERNAME=automationkasey \
    --env MODEL_NAME=automationkasey/projectx-economic-brain-sft \
    --secrets HF_TOKEN=$HF_TOKEN
```

### Step 4: Deploy

After training completes, your model will be at:
`https://huggingface.co/automationkasey/projectx-economic-brain-dpo`

**Option A: Ollama**
```bash
ollama create projectx-economic-brain -f https://huggingface.co/automationkasey/projectx-economic-brain-dpo
```

**Option B: HuggingFace Inference**
```python
from huggingface_hub import InferenceClient

client = InferenceClient(model="automationkasey/projectx-economic-brain-dpo")
response = client.chat_completion(messages=[
    {"role": "system", "content": "You are the ProjectX Economic Brain..."},
    {"role": "user", "content": "Should we scale up our API usage?"}
])
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PHASE` | `1` | Training phase (1=SFT, 2=DPO) |
| `MODEL_NAME` | `Qwen/Qwen2.5-7B-Instruct` | Base model |
| `HF_USERNAME` | `automationkasey` | Your HuggingFace username |

## Hardware Requirements

| Model Size | GPU | VRAM | Quantization |
|------------|-----|------|-------------|
| 3B | T4 | 6GB | QLoRA |
| 7B | A10G/T4 | 12GB | QLoRA |
| 13B | A100 | 24GB | QLoRA |

## Dataset Format

The DPO converter outputs HuggingFace dataset with:
```python
{
    "prompt": "Context/question for the model",
    "chosen": "Preferred response",
    "rejected": "Less preferred response",
}
```

## Launch Options

Choose the option that works best for your budget and setup:

| Option | Cost/hr | Time/Phase | Setup |
|--------|---------|------------|-------|
| **HuggingFace Jobs** | ~$0.65 (A10G) | 30-60 min | `hf jobs uv run ...` (needs credits) |
| **Modal** | ~$0.50 (A10G) | 30-60 min | `pip install modal && modal setup` |
| **Google Colab (free)** | Free (T4) | 1-2 hr | Open notebook, paste script |
| **RunPod** | ~$0.34 (RTX 4090) | 20-40 min | 1-click template |
| **Local (MPS)** | Free | 4-8 hr | Good for 3B models only |

### Option A: HuggingFace Jobs (easiest, needs credits)

1. Add credits at https://huggingface.co/settings/billing (~$5 covers both phases)
2. Run the commands below

### Option B: Modal (serverless, pay-per-second)

```bash
# Install Modal
pip install modal
modal token new

# Phase 1: SFT
modal run scripts/training/modal_train.py --phase 1

# Phase 2: DPO (after SFT completes)
modal run scripts/training/modal_train.py --phase 2
```

### Option C: Google Colab (free, T4 GPU)

1. Go to https://colab.research.google.com/
2. Runtime → Change runtime type → T4 GPU
3. Paste the Colab script into a cell:

```python
!wget -q https://huggingface.co/datasets/automationkasey/projectx-dpo-dataset/resolve/main/colab_train.py
%run colab_train.py --phase 1
```

Or upload the script directly:
```python
from google.colab import files
uploaded = files.upload()  # Upload scripts/training/train_projectx_colab.py
%run train_projectx_colab.py --phase 1
```

### Option D: RunPod (1-click)

1. Go to https://www.runpod.io/console/gpu-cloud
2. Select: 1x RTX 4090 ($0.34/hr)
3. Use the start script in `runpod_template.py`
4. Set environment variables: `HF_TOKEN`, `PHASE=1`

## Cost Estimate (All Options)

- **Free (Colab T4)**: ~2-4 hours per phase
- **Modal A10G** (~$0.50/hr): ~30-60 minutes per phase (~$0.50-1.00 total)
- **RunPod RTX 4090** (~$0.34/hr): ~20-40 minutes per phase (~$0.30-0.60 total)

## Next Steps

After deployment, integrate with ProjectX:

1. **Load the model** as an economic reasoning subsystem
2. **Query before decisions** that have >$10 impact
3. **Log decisions** back to `data/` for continuous improvement
4. **Retrain quarterly** with accumulated preference data

## Troubleshooting

**Job fails with OOM:**
- Reduce `per_device_train_batch_size` to 1
- Increase `gradient_accumulation_steps` to 16

**Dataset not found:**
- Verify dataset is on Hub: `hf repos list`
- Check repo name matches exactly

**Model not saving:**
- Ensure `HF_TOKEN` has write permissions
- Check `hub_model_id` is correct format

## Market Cognition Training Data (Tranche 3 - Phase 13)

Generate preference pairs for market cognition DPO training from trade and PNL data.

### Usage

```bash
python3.10 scripts/training/market_data_prep.py
```

### Input Files
- `logs/gate4_trades.jsonl` - Gate4 trade executions
- `data/phase4_pnl_ledger.jsonl` - PNL ledger entries

### Output
- `data/quantum_dataset/market_cognition_tranche3/` - HuggingFace dataset
- `data/quantum_dataset/market_cognition_tranche3/preference_pairs.jsonl` - JSONL for inspection

### Dataset Format
```python
{
    "prompt": "Market context description",
    "chosen": "Optimal strategy recommendation",
    "rejected": "Suboptimal or risky recommendation",
    "regime_type": "trending|ranging|high_volatility|low_volatility",
    "volatility_score": 0.0-1.0,
    "trend_direction": "bullish|bearish|neutral",
    "liquidity_state": "high|medium|low",
    "timestamp": "ISO timestamp",
    "symbol": "BTC-USD|ETH-USD|SOL-USD|PORTFOLIO"
}
```

### Pair Types
- `single_symbol` - Per-symbol strategy recommendations
- `cross_asset` - Multi-asset portfolio allocation
- `regime_comparison` - Compare regimes across symbols
- `signal_based` - Signal-level execution analysis
