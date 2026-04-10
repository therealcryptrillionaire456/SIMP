#!/usr/bin/env python3
"""
Fine-tune SecBERT on Actual Security Logs
Phase 3: Train ML model for threat detection against major AI threats
"""

import os
import sys
import json
import logging
import random
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from tqdm import tqdm

# ML imports
import torch
from torch.utils.data import Dataset, DataLoader
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    TrainingArguments,
    Trainer,
    DataCollatorWithPadding
)
from datasets import Dataset as HFDataset
import evaluate

# Setup logging
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"secbert_training_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

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
MODELS_DIR = BASE_DIR / "models" / "secbert"
RESULTS_DIR = MODELS_DIR / "results"

# Ensure directories exist
for dir_path in [PROCESSED_DIR, MODELS_DIR, RESULTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

class SecurityLogProcessor:
    """Process security logs for ML training."""
    
    def __init__(self):
        self.log = logging.getLogger(__name__)
    
    def process_zeek_logs(self, log_dir: Path) -> pd.DataFrame:
        """Process Zeek/Bro connection logs from IoT-23 dataset."""
        self.log.info(f"Processing Zeek logs from: {log_dir}")
        
        all_logs = []
        
        # Find all conn.log.labeled files
        log_files = list(log_dir.rglob("conn.log.labeled"))
        self.log.info(f"Found {len(log_files)} Zeek log files")
        
        for log_file in tqdm(log_files[:10], desc="Processing Zeek logs"):  # Limit to 10 files for speed
            try:
                # Read Zeek log (TSV format with headers)
                df = pd.read_csv(
                    log_file,
                    sep='\t',
                    comment='#',
                    low_memory=False,
                    on_bad_lines='skip'
                )
                
                # Add source information
                df['source_file'] = str(log_file)
                df['capture_id'] = log_file.parent.parent.name
                
                all_logs.append(df)
                
            except Exception as e:
                self.log.warning(f"Error processing {log_file}: {e}")
                continue
        
        if not all_logs:
            self.log.error("No Zeek logs processed successfully")
            return pd.DataFrame()
        
        # Combine all logs
        combined_df = pd.concat(all_logs, ignore_index=True)
        self.log.info(f"Processed {len(combined_df)} Zeek log entries")
        
        return combined_df
    
    def create_training_data(self, zeek_df: pd.DataFrame) -> pd.DataFrame:
        """Create training data from Zeek logs."""
        self.log.info("Creating training data from Zeek logs...")
        
        if zeek_df.empty:
            self.log.error("No Zeek data available")
            return pd.DataFrame()
        
        # Select relevant columns
        relevant_cols = [
            'id.orig_h', 'id.orig_p', 'id.resp_h', 'id.resp_p',
            'proto', 'service', 'duration', 'orig_bytes', 'resp_bytes',
            'conn_state', 'missed_bytes', 'history', 'orig_pkts',
            'orig_ip_bytes', 'resp_pkts', 'resp_ip_bytes'
        ]
        
        # Keep only columns that exist
        available_cols = [col for col in relevant_cols if col in zeek_df.columns]
        
        # Create text representation for each connection
        training_data = []
        
        for idx, row in tqdm(zeek_df.iterrows(), total=len(zeek_df), desc="Creating training texts"):
            # Build text description
            text_parts = []
            
            # Add basic connection info
            if 'id.orig_h' in row and pd.notna(row['id.orig_h']):
                text_parts.append(f"Source: {row['id.orig_h']}")
            if 'id.resp_h' in row and pd.notna(row['id.resp_h']):
                text_parts.append(f"Destination: {row['id.resp_h']}")
            if 'proto' in row and pd.notna(row['proto']):
                text_parts.append(f"Protocol: {row['proto']}")
            if 'service' in row and pd.notna(row['service']):
                text_parts.append(f"Service: {row['service']}")
            
            # Add traffic stats
            if 'orig_bytes' in row and pd.notna(row['orig_bytes']):
                text_parts.append(f"Sent: {row['orig_bytes']} bytes")
            if 'resp_bytes' in row and pd.notna(row['resp_bytes']):
                text_parts.append(f"Received: {row['resp_bytes']} bytes")
            if 'duration' in row and pd.notna(row['duration']):
                text_parts.append(f"Duration: {row['duration']} seconds")
            
            # Add connection state
            if 'conn_state' in row and pd.notna(row['conn_state']):
                text_parts.append(f"State: {row['conn_state']}")
            
            # Combine into text
            text = ". ".join(text_parts)
            
            # Determine label based on capture ID (malware vs benign)
            capture_id = row.get('capture_id', '')
            if 'Malware' in capture_id:
                label = 1  # Malicious
            elif 'Honeypot' in capture_id:
                label = 1  # Malicious (honeypot captures)
            else:
                label = 0  # Benign (or unknown)
            
            training_data.append({
                'text': text,
                'label': label,
                'source': row.get('source_file', ''),
                'capture_id': capture_id
            })
        
        training_df = pd.DataFrame(training_data)
        self.log.info(f"Created {len(training_df)} training samples")
        self.log.info(f"Class distribution: {training_df['label'].value_counts().to_dict()}")
        
        return training_df
    
    def process_simulated_datasets(self) -> pd.DataFrame:
        """Process simulated datasets for additional training data."""
        self.log.info("Processing simulated datasets...")
        
        simulated_data = []
        
        # Process UNSW-NB15 simulated data
        unsw_path = DATA_DIR / "raw" / "unsw_nb15" / "unsw_nb15_simulated.csv"
        if unsw_path.exists():
            try:
                unsw_df = pd.read_csv(unsw_path)
                self.log.info(f"Loaded UNSW-NB15: {len(unsw_df)} samples")
                
                for _, row in unsw_df.iterrows():
                    text = f"Source IP: {row.get('srcip', '')}. Destination IP: {row.get('dstip', '')}. "
                    text += f"Protocol: {row.get('proto', '')}. Service: {row.get('service', '')}. "
                    text += f"Source bytes: {row.get('sbytes', 0)}. Destination bytes: {row.get('dbytes', 0)}. "
                    text += f"Duration: {row.get('dur', 0)} seconds."
                    
                    simulated_data.append({
                        'text': text,
                        'label': row.get('label', 0),
                        'source': 'unsw_nb15_simulated',
                        'dataset': 'UNSW-NB15'
                    })
            except Exception as e:
                self.log.warning(f"Error processing UNSW-NB15: {e}")
        
        # Process CIC-DDoS simulated data
        cic_path = DATA_DIR / "raw" / "cic_ddos_2019" / "cic_ddos_2019_simulated.csv"
        if cic_path.exists():
            try:
                cic_df = pd.read_csv(cic_path)
                self.log.info(f"Loaded CIC-DDoS: {len(cic_df)} samples")
                
                for _, row in cic_df.iterrows():
                    text = f"Source IP: {row.get('Src IP', '')}. Destination IP: {row.get('Dst IP', '')}. "
                    text += f"Protocol: {row.get('Protocol', '')}. "
                    text += f"Flow duration: {row.get('Flow Duration', 0)}. "
                    text += f"Total packets: {row.get('Total Fwd Packets', 0) + row.get('Total Backward Packets', 0)}."
                    
                    label = 1 if row.get('Label', '') == 'DDoS' else 0
                    
                    simulated_data.append({
                        'text': text,
                        'label': label,
                        'source': 'cic_ddos_simulated',
                        'dataset': 'CIC-DDoS'
                    })
            except Exception as e:
                self.log.warning(f"Error processing CIC-DDoS: {e}")
        
        if simulated_data:
            simulated_df = pd.DataFrame(simulated_data)
            self.log.info(f"Total simulated samples: {len(simulated_df)}")
            return simulated_df
        
        return pd.DataFrame()

class SecBERTFineTuner:
    """Fine-tune SecBERT model for security log classification."""
    
    def __init__(self, model_name: str = "jackaduma/SecBERT"):
        self.model_name = model_name
        self.log = logging.getLogger(__name__)
        
        # Check for GPU
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.log.info(f"Using device: {self.device}")
        
        # Initialize tokenizer and model
        self.log.info(f"Loading model: {model_name}")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                model_name,
                num_labels=2,  # Binary classification: benign vs malicious
                ignore_mismatched_sizes=True
            )
            self.model.to(self.device)
            self.log.info("✓ Model loaded successfully")
        except Exception as e:
            self.log.error(f"Error loading model: {e}")
            # Fallback to a more common model
            self.log.info("Falling back to bert-base-uncased")
            self.tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
            self.model = AutoModelForSequenceClassification.from_pretrained(
                "bert-base-uncased",
                num_labels=2
            )
            self.model.to(self.device)
    
    def prepare_datasets(self, training_df: pd.DataFrame, test_size: float = 0.2):
        """Prepare training and validation datasets."""
        self.log.info("Preparing datasets...")
        
        if training_df.empty:
            self.log.error("No training data available")
            return None, None
        
        # Convert to Hugging Face dataset
        hf_dataset = HFDataset.from_pandas(training_df[['text', 'label']])
        
        # Tokenize the dataset
        def tokenize_function(examples):
            return self.tokenizer(
                examples['text'],
                padding="max_length",
                truncation=True,
                max_length=512
            )
        
        tokenized_dataset = hf_dataset.map(tokenize_function, batched=True)
        
        # Split into train and validation
        split_dataset = tokenized_dataset.train_test_split(test_size=test_size, seed=42)
        
        train_dataset = split_dataset['train']
        val_dataset = split_dataset['test']
        
        self.log.info(f"Training samples: {len(train_dataset)}")
        self.log.info(f"Validation samples: {len(val_dataset)}")
        
        return train_dataset, val_dataset
    
    def train(self, train_dataset, val_dataset, output_dir: Path):
        """Train the SecBERT model."""
        self.log.info("Starting training...")
        
        # Training arguments
        training_args = TrainingArguments(
            output_dir=str(output_dir),
            num_train_epochs=3,
            per_device_train_batch_size=8,
            per_device_eval_batch_size=8,
            warmup_steps=500,
            weight_decay=0.01,
            logging_dir=str(output_dir / "logs"),
            logging_steps=10,
            evaluation_strategy="steps",
            eval_steps=50,
            save_steps=100,
            save_total_limit=2,
            load_best_model_at_end=True,
            metric_for_best_model="accuracy",
            greater_is_better=True,
            report_to="none"  # Disable wandb/tensorboard
        )
        
        # Metrics
        accuracy_metric = evaluate.load("accuracy")
        f1_metric = evaluate.load("f1")
        
        def compute_metrics(eval_pred):
            predictions, labels = eval_pred
            predictions = np.argmax(predictions, axis=1)
            
            accuracy = accuracy_metric.compute(predictions=predictions, references=labels)["accuracy"]
            f1 = f1_metric.compute(predictions=predictions, references=labels, average="weighted")["f1"]
            
            return {"accuracy": accuracy, "f1": f1}
        
        # Data collator
        data_collator = DataCollatorWithPadding(tokenizer=self.tokenizer)
        
        # Trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
            eval_dataset=val_dataset,
            tokenizer=self.tokenizer,
            data_collator=data_collator,
            compute_metrics=compute_metrics,
        )
        
        # Train
        self.log.info("Training model...")
        trainer.train()
        
        # Save model
        self.log.info("Saving model...")
        trainer.save_model(str(output_dir / "final_model"))
        self.tokenizer.save_pretrained(str(output_dir / "final_model"))
        
        # Evaluate
        self.log.info("Evaluating model...")
        eval_results = trainer.evaluate()
        
        # Save evaluation results
        results_file = output_dir / "evaluation_results.json"
        with open(results_file, 'w') as f:
            json.dump(eval_results, f, indent=2)
        
        self.log.info(f"Evaluation results: {eval_results}")
        self.log.info(f"Model saved to: {output_dir / 'final_model'}")
        
        return eval_results
    
    def predict(self, texts: List[str], model_path: Optional[Path] = None):
        """Make predictions using the trained model."""
        if model_path:
            self.log.info(f"Loading model from: {model_path}")
            self.model = AutoModelForSequenceClassification.from_pretrained(str(model_path))
            self.model.to(self.device)
        
        self.model.eval()
        
        # Tokenize inputs
        inputs = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt"
        )
        
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Make predictions
        with torch.no_grad():
            outputs = self.model(**inputs)
            predictions = torch.softmax(outputs.logits, dim=-1)
        
        # Convert to probabilities and labels
        results = []
        for i, text in enumerate(texts):
            prob_benign = predictions[i][0].item()
            prob_malicious = predictions[i][1].item()
            label = 1 if prob_malicious > prob_benign else 0
            confidence = max(prob_benign, prob_malicious)
            
            results.append({
                'text': text[:100] + "..." if len(text) > 100 else text,
                'prediction': 'malicious' if label == 1 else 'benign',
                'confidence': confidence,
                'probabilities': {
                    'benign': prob_benign,
                    'malicious': prob_malicious
                }
            })
        
        return results

def main():
    """Main fine-tuning process."""
    log.info("=" * 80)
    log.info("BILL RUSSELL PROTOCOL - SECBERT FINE-TUNING")
    log.info("=" * 80)
    log.info("Phase 3: Fine-tuning SecBERT on actual security logs")
    log.info("Defending against: Anthropic, Meta, OpenAI, Enterprise threats")
    log.info("=" * 80)
    
    # Step 1: Process real IoT-23 logs
    log.info("\nStep 1: Processing real security logs")
    log.info("-" * 40)
    
    processor = SecurityLogProcessor()
    
    # Process real IoT-23 Zeek logs
    iot23_dir = DATA_DIR / "raw" / "iot_23"
    zeek_df = processor.process_zeek_logs(iot23_dir)
    
    if zeek_df.empty:
        log.error("Failed to process Zeek logs")
        # Use simulated data as fallback
        log.info("Using simulated datasets instead")
        training_df = processor.process_simulated_datasets()
    else:
        # Create training data from Zeek logs
        real_training_df = processor.create_training_data(zeek_df)
        
        # Also include simulated data for diversity
        simulated_df = processor.process_simulated_datasets()
        
        # Combine real and simulated data
        if not simulated_df.empty:
            training_df = pd.concat([real_training_df, simulated_df], ignore_index=True)
            log.info(f"Combined dataset: {len(training_df)} samples")
        else:
            training_df = real_training_df
    
    if training_df.empty:
        log.error("No training data available")
        return False
    
    log.info(f"Total training samples: {len(training_df)}")
    log.info(f"Class distribution: {training_df['label'].value_counts().to_dict()}")
    
    # Save training data
    training_file = PROCESSED_DIR / "training_data.csv"
    training_df.to_csv(training_file, index=False)
    log.info(f"Saved training data to: {training_file}")
    
    # Step 2: Prepare and train SecBERT
    log.info("\nStep 2: Fine-tuning SecBERT model")
    log.info("-" * 40)
    
    # Create unique output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = MODELS_DIR / f"secbert_finetuned_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize fine-tuner
    fine_tuner = SecBERTFineTuner()
    
    # Prepare datasets
    train_dataset, val_dataset = fine_tuner.prepare_datasets(training_df)
    
    if train_dataset is None or val_dataset is None:
        log.error("Failed to prepare datasets")
        return False
    
    # Train model
    eval_results = fine_tuner.train(train_dataset, val_dataset, output_dir)
    
    # Step 3: Test the model
    log.info("\nStep 3: Testing the fine-tuned model")
    log.info("-" * 40)
    
    # Sample test texts
    test_texts = [
        "Source: 192.168.1.100. Destination: 8.8.8.8. Protocol: tcp. Service: dns. Sent: 512 bytes. Received: 1024 bytes. Duration: 0.5 seconds. State: SF",
        "Source: 10.0.0.50. Destination: 192.168.1.1. Protocol: udp. Service: -. Sent: 1500 bytes. Received: 0 bytes. Duration: 60 seconds. State: S0",
        "Source: 172.16.0.100. Destination: 1.1.1.1. Protocol: tcp. Service: http. Sent: 2048 bytes. Received: 4096 bytes. Duration: 2.3 seconds. State: REJ",
    ]
    
    predictions = fine_tuner.predict(test_texts, output_dir / "final_model")
    
    log.info("Sample predictions:")
    for pred in predictions:
        log.info(f"  Text: {pred['text']}")
        log.info(f"  Prediction: {pred['prediction']} (confidence: {pred['confidence']:.2%})")
        log.info(f"  Probabilities: benign={pred['probabilities']['benign']:.3f}, malicious={pred['probabilities']['malicious']:.3f}")
        log.info("")
    
    # Step 4: Create deployment package
    log.info("\nStep 4: Creating deployment package")
    log.info("-" * 40)
    
    deployment_dir = MODELS_DIR / "deployment"
    deployment_dir.mkdir(parents=True, exist_ok=True)
    
    # Create model card
    model_card = {
        "model_name": "bill_russel_secbert",
        "version": "1.0.0",
        "description": "SecBERT fine-tuned for security log classification",
        "training_data": {
            "samples": len(training_df),
            "benign": int(training_df['label'].value_counts().get(0, 0)),
            "malicious": int(training_df['label'].value_counts().get(1, 0)),
            "sources": training_df['source'].unique().tolist()
        },
        "performance": eval_results,
        "training_date": datetime.now().isoformat() + "Z",
        "usage": "Classify security logs as benign or malicious",
        "limitations": "Trained on simulated and limited real data. For production, fine-tune on more diverse real logs."
    }
    
    model_card_file = deployment_dir / "model_card.json"
    with open(model_card_file, 'w') as f:
        json.dump(model_card, f, indent=2)
    
    log.info(f"Model card saved to: {model_card_file}")
    
    # Create simple inference script
    inference_script = deployment_dir / "inference.py"
    inference_code = '''#!/usr/bin/env python3
"""
Bill Russell Protocol - SecBERT Inference
Usage: python inference.py "log text to classify"
"""

import sys
import json
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

def load_model(model_path):
    """Load the fine-tuned SecBERT model."""
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    model = AutoModelForSequenceClassification.from_pretrained(model_path)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    return tokenizer, model, device

def classify_log(text, tokenizer, model, device):
    """Classify a log text as benign or malicious."""
    inputs = tokenizer(
        text,
        padding=True,
        truncation=True,
        max_length=512,
        return_tensors="pt"
    )
    
    inputs = {k: v.to(device) for k, v in inputs.items()}
    
    model.eval()
    with torch.no_grad():
        outputs = model(**inputs)
        predictions = torch.softmax(outputs.logits, dim=-1)
    
    prob_benign = predictions[0][0].item()
    prob_malicious = predictions[0][1].item()
    
    return {
        'text': text[:200] + "..." if len(text) > 200 else text,
        'prediction': 'malicious' if prob_malicious > prob_benign else 'benign',
        'confidence': max(prob_benign, prob_malicious),
        'probabilities': {
            'benign': prob_benign,
            'malicious': prob_malicious
        }
    }

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python inference.py 'log text to classify'")
        sys.exit(1)
    
    text = sys.argv[1]
    
    # Load model (update path as needed)
    model_path = "./final_model"  # Update this path
    tokenizer, model, device = load_model(model_path)
    
    result = classify_log(text, tokenizer, model, device)
    
    print(json.dumps(result, indent=2))
'''
    
    with open(inference_script, 'w') as f:
        f.write(inference_code)
    
    log.info(f"Inference script saved to: {inference_script}")
    
    # Summary
    log.info("\n" + "=" * 80)
    log.info("SECBERT FINE-TUNING SUMMARY")
    log.info("=" * 80)
    log.info(f"✓ Training samples: {len(training_df)}")
    log.info(f"✓ Model saved to: {output_dir}")
    log.info(f"✓ Evaluation accuracy: {eval_results.get('eval_accuracy', 0):.2%}")
    log.info(f"✓ Deployment package: {deployment_dir}")
    log.info(f"✓ Log file: {log_file}")
    log.info("=" * 80)
    log.info("✅ Phase 3 complete - SecBERT fine-tuned successfully")
    log.info("\nNext steps:")
    log.info("  1. Test the model with more diverse logs")
    log.info("  2. Proceed to Phase 4: Deploy Mistral 7B with cloud credits")
    log.info("  3. Integrate model into Bill Russell Protocol pipeline")
    log.info("=" * 80)
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)