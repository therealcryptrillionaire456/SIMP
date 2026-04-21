# Bill Russell Protocol - Mistral 7B Fine-tuning
# Google Colab Notebook for Security Log Reasoning

# Install dependencies
!pip install -q transformers accelerate bitsandbytes peft datasets

# Import libraries
import torch
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from peft import LoraConfig, get_peft_model, TaskType
from datasets import Dataset
import pandas as pd

# Check GPU
print(f"GPU available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")

# Load Mistral 7B with 4-bit quantization
model_name = "mistralai/Mistral-7B-v0.1"
tokenizer = AutoTokenizer.from_pretrained(model_name)
tokenizer.pad_token = tokenizer.eos_token

model = AutoModelForCausalLM.from_pretrained(
    model_name,
    load_in_4bit=True,
    device_map="auto",
    torch_dtype=torch.float16
)

# Configure QLoRA
lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r=8,
    lora_alpha=32,
    lora_dropout=0.1,
    target_modules=["q_proj", "v_proj"]
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

# Create security reasoning dataset
def create_training_data():
    """Create security reasoning training data."""
    examples = [
        {
            "input": "Log: Multiple failed SSH attempts from 192.168.1.100
Question: What type of attack is this?",
            "output": "This appears to be a brute force attack on SSH credentials."
        },
        {
            "input": "Log: Port scan detected from 10.0.0.50 scanning ports 22, 80, 443
Question: What is the attacker looking for?",
            "output": "The attacker is scanning for open services: SSH (22), HTTP (80), HTTPS (443)."
        },
        {
            "input": "Log: Large outbound transfer to external IP during off-hours
Question: What should be investigated?",
            "output": "Investigate for possible data exfiltration. Check what data was transferred and user involved."
        }
    ]
    
    # Format for training
    texts = []
    for ex in examples:
        text = f"### Instruction: Analyze this security log
### Input: {ex['input']}
### Response: {ex['output']}"
        texts.append(text)
    
    return Dataset.from_dict({"text": texts})

# Prepare dataset
dataset = create_training_data()

def tokenize_function(examples):
    return tokenizer(examples["text"], truncation=True, max_length=512)

tokenized_dataset = dataset.map(tokenize_function, batched=True)

# Training arguments
training_args = TrainingArguments(
    output_dir="./mistral-security",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    warmup_steps=100,
    logging_steps=10,
    save_steps=100,
    evaluation_strategy="no",
    save_total_limit=2,
    learning_rate=2e-4,
    fp16=True,
    push_to_hub=False
)

# Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset,
    data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
)

# Train
print("Starting training...")
trainer.train()

# Save model
model.save_pretrained("./mistral-security-trained")
tokenizer.save_pretrained("./mistral-security-trained")

print("Training complete! Model saved.")

# Test inference
test_prompt = "### Instruction: Analyze this security log
### Input: Log: DNS queries for known malicious domains from workstation
Question: What does this indicate?
### Response:"

inputs = tokenizer(test_prompt, return_tensors="pt").to("cuda")
outputs = model.generate(**inputs, max_length=200, temperature=0.7)
response = tokenizer.decode(outputs[0], skip_special_tokens=True)

print("\nTest inference:")
print(response)
