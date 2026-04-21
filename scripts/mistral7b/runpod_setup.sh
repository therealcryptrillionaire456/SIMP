#!/bin/bash
# Bill Russell Protocol - Mistral 7B RunPod Deployment
# Cost: ~$3-5 for fine-tuning

echo "Setting up Mistral 7B on RunPod..."

# Update and install basics
apt-get update
apt-get install -y python3-pip git

# Clone repository
git clone https://github.com/yourusername/bill-russel-protocol.git
cd bill-russel-protocol

# Install Python dependencies
pip3 install torch transformers accelerate bitsandbytes peft datasets

# Create training script
cat > train_mistral.py << 'EOF'
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import LoraConfig, get_peft_model
import json

# Load model with 4-bit quantization
model_name = "mistralai/Mistral-7B-v0.1"
tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    load_in_4bit=True,
    device_map="auto",
    torch_dtype=torch.float16
)

# QLoRA configuration
lora_config = LoraConfig(
    r=8,
    lora_alpha=32,
    target_modules=["q_proj", "v_proj"],
    lora_dropout=0.1,
    bias="none",
    task_type="CAUSAL_LM"
)

model = get_peft_model(model, lora_config)
print(f"Trainable parameters: {model.print_trainable_parameters()}")

# Load security reasoning dataset
with open("security_reasoning_data.json", "r") as f:
    training_data = json.load(f)

print(f"Loaded {len(training_data)} training examples")
print("Setup complete. Ready for training.")
EOF

echo "RunPod setup script created."
echo "Next steps:"
echo "1. Upload security_reasoning_data.json"
echo "2. Run: python3 train_mistral.py"
echo "3. Fine-tune for 4-8 hours"
echo "4. Download trained model"
