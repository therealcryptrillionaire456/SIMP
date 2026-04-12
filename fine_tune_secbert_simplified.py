#!/usr/bin/env python3
"""
Simplified SecBERT Fine-tuning
Phase 3: Train ML model using simulated data (faster execution)
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd
import numpy as np

# ML imports
import torch
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    Trainer,
    TrainingArguments,
    DataCollatorWithPadding
)
from datasets import Dataset as HFDataset

# Setup logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"secbert_simple_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# Configuration
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data" / "security_datasets"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = BASE_DIR / "models" / "secbert_simple"

# Ensure directories exist
for dir_path in [PROCESSED_DIR, MODELS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

def create_simulated_training_data():
    """Create simulated training data for quick fine-tuning."""
    log.info("Creating simulated training data...")
    
    np.random.seed(42)
    n_samples = 2000  # Smaller dataset for faster training
    
    # Generate diverse log texts
    log_texts = []
    labels = []
    
    # Benign logs (70%)
    for _ in range(int(n_samples * 0.7)):
        src_ip = f"192.168.{np.random.randint(1, 255)}.{np.random.randint(1, 255)}"
        dst_ip = f"10.0.{np.random.randint(1, 255)}.{np.random.randint(1, 255)}"
        protocol = np.random.choice(['TCP', 'UDP', 'ICMP'])
        service = np.random.choice(['HTTP', 'DNS', 'HTTPS', 'SSH', '-'])
        bytes_sent = np.random.randint(100, 5000)
        bytes_recv = np.random.randint(100, 5000)
        duration = np.random.uniform(0.1, 5.0)
        
        text = f"Connection from {src_ip} to {dst_ip} using {protocol}. "
        text += f"Service: {service}. Sent {bytes_sent} bytes, received {bytes_recv} bytes. "
        text += f"Duration: {duration:.2f} seconds. Connection state: established."
        
        log_texts.append(text)
        labels.append(0)  # Benign
    
    # Malicious logs (30%)
    attack_types = [
        "port scanning", "brute force attempt", "DDoS traffic", 
        "malware communication", "data exfiltration", "command and control"
    ]
    
    for _ in range(int(n_samples * 0.3)):
        src_ip = f"10.{np.random.randint(0, 255)}.{np.random.randint(0, 255)}.{np.random.randint(1, 254)}"
        dst_ip = f"192.168.{np.random.randint(1, 255)}.{np.random.randint(1, 255)}"
        protocol = np.random.choice(['TCP', 'UDP'])
        attack = np.random.choice(attack_types)
        bytes_sent = np.random.randint(5000, 50000)  # Higher for attacks
        bytes_recv = np.random.randint(0, 1000)
        duration = np.random.uniform(0.01, 0.5)  # Shorter for scans
        
        text = f"Suspicious connection from {src_ip} to {dst_ip} using {protocol}. "
        text += f"Pattern indicates {attack}. Sent {bytes_sent} bytes, received {bytes_recv} bytes. "
        text += f"Duration: {duration:.2f} seconds. Multiple rapid connections detected."
        
        log_texts.append(text)
        labels.append(1)  # Malicious
    
    # Create DataFrame
    df = pd.DataFrame({
        'text': log_texts,
        'label': labels
    })
    
    log.info(f"Created {len(df)} simulated training samples")
    log.info(f"Class distribution: {df['label'].value_counts().to_dict()}")
    
    # Save for reference
    df.to_csv(PROCESSED_DIR / "simulated_training_data.csv", index=False)
    
    return df

def fine_tune_secbert_simple(training_df, output_dir):
    """Simple fine-tuning function."""
    log.info("Starting simplified fine-tuning...")
    
    # Check for GPU
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.info(f"Using device: {device}")
    
    # Use a smaller model for faster training
    model_name = "distilbert-base-uncased"  # Smaller than BERT
    
    try:
        log.info(f"Loading model: {model_name}")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            num_labels=2
        )
        model.to(device)
    except Exception as e:
        log.error(f"Error loading model: {e}")
        return None
    
    # Convert to Hugging Face dataset
    hf_dataset = HFDataset.from_pandas(training_df[['text', 'label']])
    
    # Tokenize
    def tokenize_function(examples):
        return tokenizer(
            examples['text'],
            padding="max_length",
            truncation=True,
            max_length=256  # Shorter for speed
        )
    
    tokenized_dataset = hf_dataset.map(tokenize_function, batched=True)
    
    # Split
    split_dataset = tokenized_dataset.train_test_split(test_size=0.2, seed=42)
    train_dataset = split_dataset['train']
    val_dataset = split_dataset['test']
    
    log.info(f"Training samples: {len(train_dataset)}")
    log.info(f"Validation samples: {len(val_dataset)}")
    
    # Simple training arguments
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=2,  # Fewer epochs
        per_device_train_batch_size=16,
        per_device_eval_batch_size=16,
        learning_rate=2e-5,
        warmup_steps=100,
        weight_decay=0.01,
        logging_dir=str(output_dir / "logs"),
        logging_steps=10,
        evaluation_strategy="steps",
        eval_steps=20,
        save_steps=50,
        save_total_limit=1,
        load_best_model_at_end=True,
        report_to="none"
    )
    
    # Simple compute metrics
    def compute_metrics(eval_pred):
        import numpy as np
        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=1)
        accuracy = np.mean(predictions == labels)
        return {"accuracy": accuracy}
    
    # Data collator
    data_collator = DataCollatorWithPadding(tokenizer=tokenizer)
    
    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )
    
    # Train
    log.info("Training model (this may take a few minutes)...")
    trainer.train()
    
    # Save
    model.save_pretrained(str(output_dir / "model"))
    tokenizer.save_pretrained(str(output_dir / "model"))
    
    # Evaluate
    eval_results = trainer.evaluate()
    log.info(f"Evaluation results: {eval_results}")
    
    return eval_results

def create_deployment_package(output_dir, eval_results):
    """Create simple deployment package."""
    deployment_dir = MODELS_DIR / "deployment"
    deployment_dir.mkdir(parents=True, exist_ok=True)
    
    # Model info
    model_info = {
        "model_name": "bill_russel_distilbert",
        "version": "1.0.0",
        "description": "DistilBERT fine-tuned for security log classification",
        "training_samples": 2000,
        "accuracy": eval_results.get("eval_accuracy", 0),
        "training_date": datetime.now().isoformat() + "Z",
        "model_type": "distilbert-base-uncased",
        "purpose": "Classify network logs as benign or malicious"
    }
    
    info_file = deployment_dir / "model_info.json"
    with open(info_file, 'w') as f:
        json.dump(model_info, f, indent=2)
    
    log.info(f"Model info saved to: {info_file}")
    
    # Create test script
    test_script = '''#!/usr/bin/env python3
"""
Test the fine-tuned security classifier.
"""

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import sys

def test_model():
    # Load model
    model_path = "./model"  # Update with actual path
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    
    # Test samples
    test_texts = [
        "Normal HTTP connection from 192.168.1.100 to 8.8.8.8, 512 bytes sent, 1024 bytes received",
        "Multiple rapid connections from 10.0.0.50 to port 22, possible brute force attempt",
        "Large data transfer from internal host to external server, possible exfiltration"
    ]
    
    model.eval()
    results = []
    
    for text in test_texts:
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=256)
        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)
        
        prediction = "MALICIOUS" if probs[0][1] > probs[0][0] else "BENIGN"
        confidence = max(probs[0][0], probs[0][1]).item()
        
        results.append({
            "text": text[:50] + "...",
            "prediction": prediction,
            "confidence": f"{confidence:.1%}",
            "benign_prob": f"{probs[0][0].item():.1%}",
            "malicious_prob": f"{probs[0][1].item():.1%}"
        })
    
    return results

if __name__ == "__main__":
    results = test_model()
    for r in results:
        print(f"{r['prediction']} ({r['confidence']}): {r['text']}")
'''
    
    script_file = deployment_dir / "test_model.py"
    with open(script_file, 'w') as f:
        f.write(test_script)
    
    log.info(f"Test script saved to: {script_file}")
    
    return deployment_dir

def main():
    """Main simplified fine-tuning process."""
    log.info("=" * 80)
    log.info("BILL RUSSELL PROTOCOL - SIMPLIFIED SECBERT FINE-TUNING")
    log.info("=" * 80)
    log.info("Phase 3: Quick fine-tuning for demonstration")
    log.info("Defending against: Anthropic, Meta, OpenAI, Enterprise threats")
    log.info("=" * 80)
    
    # Step 1: Create training data
    log.info("\nStep 1: Creating training data")
    log.info("-" * 40)
    
    training_df = create_simulated_training_data()
    
    if training_df.empty:
        log.error("Failed to create training data")
        return False
    
    # Step 2: Fine-tune model
    log.info("\nStep 2: Fine-tuning model")
    log.info("-" * 40)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = MODELS_DIR / f"model_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    eval_results = fine_tune_secbert_simple(training_df, output_dir)
    
    if eval_results is None:
        log.error("Fine-tuning failed")
        return False
    
    # Step 3: Create deployment package
    log.info("\nStep 3: Creating deployment package")
    log.info("-" * 40)
    
    deployment_dir = create_deployment_package(output_dir, eval_results)
    
    # Summary
    log.info("\n" + "=" * 80)
    log.info("FINE-TUNING SUMMARY")
    log.info("=" * 80)
    log.info(f"✓ Training samples: {len(training_df)}")
    log.info(f"✓ Model saved to: {output_dir}")
    log.info(f"✓ Accuracy: {eval_results.get('eval_accuracy', 0):.2%}")
    log.info(f"✓ Deployment package: {deployment_dir}")
    log.info(f"✓ Log file: {log_file}")
    log.info("=" * 80)
    log.info("✅ Phase 3 complete - Model trained successfully")
    log.info("\nNote: This is a simplified demonstration model.")
    log.info("For production, use the full SecBERT with real IoT-23 data.")
    log.info("\nNext steps:")
    log.info("  1. Proceed to Phase 4: Deploy Mistral 7B with cloud credits")
    log.info("  2. Integrate this model into Bill Russell Protocol")
    log.info("  3. For production: Fine-tune on full IoT-23 dataset")
    log.info("=" * 80)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)