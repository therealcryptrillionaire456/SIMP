"""
Data utilities for Mythos training.
"""

import torch
from torch.utils.data import Dataset, DataLoader
from typing import List, Dict, Any, Optional
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class TextDataset(Dataset):
    """Dataset for text data."""
    
    def __init__(self, texts: List[str], tokenizer, max_length: int = 1024):
        """
        Initialize dataset.
        
        Args:
            texts: List of text strings
            tokenizer: Tokenizer for encoding text
            max_length: Maximum sequence length
        """
        self.texts = texts
        self.tokenizer = tokenizer
        self.max_length = max_length
        
    def __len__(self):
        return len(self.texts)
    
    def __getitem__(self, idx):
        text = self.texts[idx]
        
        # Tokenize text
        encoding = self.tokenizer.batch_encode_plus(
            [text],
            truncation=True,
            max_length=self.max_length,
            padding='max_length',
            return_tensors='pt'
        )
        
        return {
            'input_ids': encoding['input_ids'].squeeze(),
            'attention_mask': encoding['attention_mask'].squeeze()
        }


class MythosDataProcessor:
    """Process data for Mythos training."""
    
    def __init__(self, tokenizer, config):
        """
        Initialize data processor.
        
        Args:
            tokenizer: Tokenizer for encoding
            config: Model configuration
        """
        self.tokenizer = tokenizer
        self.config = config
        self.max_length = config.max_position_embeddings
        
    def load_text_files(self, data_dir: str) -> List[str]:
        """
        Load text files from directory.
        
        Args:
            data_dir: Directory containing text files
            
        Returns:
            List of text strings
        """
        data_dir = Path(data_dir)
        texts = []
        
        # Load all .txt files
        for txt_file in data_dir.glob("*.txt"):
            try:
                with open(txt_file, 'r', encoding='utf-8') as f:
                    text = f.read().strip()
                    if text:
                        texts.append(text)
            except Exception as e:
                logger.warning(f"Error reading {txt_file}: {e}")
        
        # Load all .json files
        for json_file in data_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        texts.extend([str(item) for item in data if item])
                    elif isinstance(data, dict):
                        texts.append(json.dumps(data))
                    elif isinstance(data, str):
                        texts.append(data)
            except Exception as e:
                logger.warning(f"Error reading {json_file}: {e}")
        
        logger.info(f"Loaded {len(texts)} text samples from {data_dir}")
        return texts
    
    def create_dataset(self, texts: List[str]) -> TextDataset:
        """
        Create dataset from texts.
        
        Args:
            texts: List of text strings
            
        Returns:
            TextDataset
        """
        return TextDataset(texts, self.tokenizer, self.max_length)
    
    def create_dataloader(
        self, 
        dataset: Dataset, 
        batch_size: int, 
        shuffle: bool = True,
        num_workers: int = 0
    ) -> DataLoader:
        """
        Create dataloader from dataset.
        
        Args:
            dataset: Dataset
            batch_size: Batch size
            shuffle: Whether to shuffle data
            num_workers: Number of worker processes
            
        Returns:
            DataLoader
        """
        return DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            num_workers=num_workers,
            pin_memory=True
        )
    
    def prepare_batch(self, batch: Dict[str, torch.Tensor]) -> Dict[str, torch.Tensor]:
        """
        Prepare batch for training.
        
        Args:
            batch: Batch dictionary
            
        Returns:
            Prepared batch with labels
        """
        input_ids = batch['input_ids']
        attention_mask = batch['attention_mask']
        
        # Create labels (shifted input_ids)
        labels = input_ids.clone()
        
        return {
            'input_ids': input_ids,
            'attention_mask': attention_mask,
            'labels': labels
        }


class DataCollator:
    """Collate data for training."""
    
    def __init__(self, tokenizer, max_length: int = 1024):
        """
        Initialize data collator.
        
        Args:
            tokenizer: Tokenizer
            max_length: Maximum sequence length
        """
        self.tokenizer = tokenizer
        self.max_length = max_length
        
    def __call__(self, examples: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
        """
        Collate examples into batch.
        
        Args:
            examples: List of examples
            
        Returns:
            Batch dictionary
        """
        # Pad sequences
        batch = self.tokenizer.pad(
            examples,
            padding='longest',
            max_length=self.max_length,
            return_tensors='pt'
        )
        
        # Create labels (shifted input_ids)
        batch['labels'] = batch['input_ids'].clone()
        
        return batch


def create_sample_data(data_dir: str = "data/sample"):
    """
    Create sample training data.
    
    Args:
        data_dir: Directory to save sample data
    """
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # Sample texts about AI and language models
    sample_texts = [
        "Artificial intelligence is transforming the world through machine learning and natural language processing.",
        "Large language models like GPT and Claude can understand and generate human-like text.",
        "Transformer architecture with self-attention mechanisms has revolutionized natural language processing.",
        "Training large language models requires massive datasets and significant computational resources.",
        "Constitutional AI focuses on making AI systems helpful, harmless, and honest through alignment.",
        "Reinforcement learning from human feedback is used to align language models with human values.",
        "Multimodal AI systems can process and generate text, images, audio, and video.",
        "AI safety research aims to ensure artificial intelligence systems are robust and aligned with human values.",
        "Language models can be fine-tuned for specific tasks like code generation, translation, or summarization.",
        "The future of AI includes more capable systems that can reason, plan, and solve complex problems.",
        "Ethical AI development requires transparency, fairness, and accountability in model design and deployment.",
        "AI systems should be designed to augment human capabilities rather than replace human judgment.",
        "Research in AI alignment seeks to ensure that advanced AI systems act in accordance with human intentions.",
        "Machine learning models learn patterns from data to make predictions or generate content.",
        "Natural language understanding enables AI systems to comprehend and respond to human language.",
        "Computer vision allows AI to interpret and understand visual information from the world.",
        "Robotics combines AI with physical systems to create intelligent machines that can interact with the environment.",
        "AI ethics involves addressing bias, privacy, and societal impacts of artificial intelligence systems.",
        "Explainable AI aims to make machine learning models more transparent and interpretable to humans.",
        "AI governance frameworks help ensure responsible development and deployment of artificial intelligence.",
    ]
    
    # Save as text files
    for i, text in enumerate(sample_texts):
        file_path = data_dir / f"sample_{i:03d}.txt"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(text)
    
    # Save as JSON
    json_path = data_dir / "samples.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(sample_texts, f, indent=2)
    
    logger.info(f"Created {len(sample_texts)} sample texts in {data_dir}")
    return sample_texts