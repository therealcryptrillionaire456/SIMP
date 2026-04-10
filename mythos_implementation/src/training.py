"""
Training pipeline for Mythos model.
"""

import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader
from typing import Dict, Any, Optional, List, Tuple
import logging
from pathlib import Path
import json
from datetime import datetime
import time

from .modeling_mythos import MythosForCausalLM
from config.model_config import ModelConfig, get_model_config
from .data_utils import MythosDataProcessor, create_sample_data
from .tokenizer import get_tokenizer

logger = logging.getLogger(__name__)


class TrainingConfig:
    """Training configuration."""
    
    def __init__(
        self,
        batch_size: int = 4,
        gradient_accumulation_steps: int = 4,
        learning_rate: float = 3e-4,
        weight_decay: float = 0.01,
        num_train_epochs: int = 3,
        warmup_steps: int = 100,
        max_grad_norm: float = 1.0,
        logging_steps: int = 10,
        save_steps: int = 100,
        eval_steps: int = 50,
        output_dir: str = "outputs",
        checkpoint_dir: str = "checkpoints",
        log_dir: str = "logs",
        use_mixed_precision: bool = True,
        device: str = "auto"
    ):
        self.batch_size = batch_size
        self.gradient_accumulation_steps = gradient_accumulation_steps
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.num_train_epochs = num_train_epochs
        self.warmup_steps = warmup_steps
        self.max_grad_norm = max_grad_norm
        self.logging_steps = logging_steps
        self.save_steps = save_steps
        self.eval_steps = eval_steps
        self.output_dir = output_dir
        self.checkpoint_dir = checkpoint_dir
        self.log_dir = log_dir
        self.use_mixed_precision = use_mixed_precision
        self.device = device
        
        # Create directories
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        Path(checkpoint_dir).mkdir(parents=True, exist_ok=True)
        Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
    
    def save(self, path: str):
        """Save configuration to file."""
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


class Trainer:
    """Trainer for Mythos model."""
    
    def __init__(
        self,
        model_config: ModelConfig,
        training_config: TrainingConfig,
        tokenizer = None
    ):
        """
        Initialize trainer.
        
        Args:
            model_config: Model configuration
            training_config: Training configuration
            tokenizer: Tokenizer (optional)
        """
        self.model_config = model_config
        self.training_config = training_config
        self.tokenizer = tokenizer or get_tokenizer(model_config.vocab_size)
        
        # Setup device
        if training_config.device == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(training_config.device)
        
        # Initialize model
        self.model = MythosForCausalLM(model_config)
        self.model.to(self.device)
        
        # Setup optimizer
        self.optimizer = self._create_optimizer()
        
        # Setup scheduler
        self.scheduler = self._create_scheduler()
        
        # Setup scaler for mixed precision
        self.scaler = torch.cuda.amp.GradScaler() if (
            training_config.use_mixed_precision and self.device.type == "cuda"
        ) else None
        
        # Training state
        self.global_step = 0
        self.epoch = 0
        self.best_loss = float('inf')
        
        logger.info(f"Initialized trainer with device: {self.device}")
        logger.info(f"Model parameters: {sum(p.numel() for p in self.model.parameters()):,}")
    
    def _create_optimizer(self) -> AdamW:
        """Create optimizer."""
        # Separate parameters for weight decay
        no_decay = ["bias", "LayerNorm.weight"]
        optimizer_grouped_parameters = [
            {
                "params": [
                    p for n, p in self.model.named_parameters()
                    if not any(nd in n for nd in no_decay)
                ],
                "weight_decay": self.training_config.weight_decay,
            },
            {
                "params": [
                    p for n, p in self.model.named_parameters()
                    if any(nd in n for nd in no_decay)
                ],
                "weight_decay": 0.0,
            },
        ]
        
        return AdamW(
            optimizer_grouped_parameters,
            lr=self.training_config.learning_rate,
            betas=(0.9, 0.95),
            eps=1e-8
        )
    
    def _create_scheduler(self) -> CosineAnnealingLR:
        """Create learning rate scheduler."""
        # Total training steps
        total_steps = self.training_config.num_train_epochs * 1000  # Approximate
        
        return CosineAnnealingLR(
            self.optimizer,
            T_max=total_steps,
            eta_min=self.training_config.learning_rate * 0.1
        )
    
    def train_step(
        self,
        batch: Dict[str, torch.Tensor]
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Perform a single training step.
        
        Args:
            batch: Batch dictionary
            
        Returns:
            Loss and metrics dictionary
        """
        self.model.train()
        
        # Move batch to device
        batch = {k: v.to(self.device) for k, v in batch.items()}
        
        # Forward pass
        with torch.cuda.amp.autocast(enabled=self.scaler is not None):
            outputs = self.model(**batch)
            loss = outputs['loss']
            
            # Scale loss for gradient accumulation
            loss = loss / self.training_config.gradient_accumulation_steps
        
        # Backward pass
        if self.scaler is not None:
            self.scaler.scale(loss).backward()
        else:
            loss.backward()
        
        # Update weights if gradient accumulation steps reached
        if (self.global_step + 1) % self.training_config.gradient_accumulation_steps == 0:
            # Clip gradients
            if self.scaler is not None:
                self.scaler.unscale_(self.optimizer)
            
            torch.nn.utils.clip_grad_norm_(
                self.model.parameters(),
                self.training_config.max_grad_norm
            )
            
            # Update weights
            if self.scaler is not None:
                self.scaler.step(self.optimizer)
                self.scaler.update()
            else:
                self.optimizer.step()
            
            # Update scheduler
            self.scheduler.step()
            
            # Zero gradients
            self.optimizer.zero_grad()
        
        # Calculate metrics
        metrics = {
            "loss": loss.item() * self.training_config.gradient_accumulation_steps,
            "learning_rate": self.scheduler.get_last_lr()[0]
        }
        
        return loss, metrics
    
    def evaluate(self, dataloader: DataLoader) -> Dict[str, float]:
        """
        Evaluate model on validation data.
        
        Args:
            dataloader: Validation dataloader
            
        Returns:
            Evaluation metrics
        """
        self.model.eval()
        total_loss = 0
        total_samples = 0
        
        with torch.no_grad():
            for batch in dataloader:
                # Move batch to device
                batch = {k: v.to(self.device) for k, v in batch.items()}
                
                # Forward pass
                outputs = self.model(**batch)
                loss = outputs['loss']
                
                # Accumulate
                batch_size = batch['input_ids'].size(0)
                total_loss += loss.item() * batch_size
                total_samples += batch_size
        
        avg_loss = total_loss / total_samples if total_samples > 0 else 0
        
        return {
            "eval_loss": avg_loss,
            "perplexity": torch.exp(torch.tensor(avg_loss)).item()
        }
    
    def train(
        self,
        train_dataloader: DataLoader,
        eval_dataloader: Optional[DataLoader] = None,
        num_epochs: Optional[int] = None
    ):
        """
        Train the model.
        
        Args:
            train_dataloader: Training dataloader
            eval_dataloader: Evaluation dataloader (optional)
            num_epochs: Number of epochs to train
        """
        if num_epochs is None:
            num_epochs = self.training_config.num_train_epochs
        
        logger.info(f"Starting training for {num_epochs} epochs")
        logger.info(f"Training samples: {len(train_dataloader.dataset)}")
        
        start_time = time.time()
        
        for epoch in range(num_epochs):
            self.epoch = epoch
            logger.info(f"Epoch {epoch + 1}/{num_epochs}")
            
            # Training loop
            epoch_loss = 0
            epoch_samples = 0
            
            for step, batch in enumerate(train_dataloader):
                # Training step
                loss, metrics = self.train_step(batch)
                
                # Accumulate epoch statistics
                batch_size = batch['input_ids'].size(0)
                epoch_loss += metrics['loss'] * batch_size
                epoch_samples += batch_size
                
                # Logging
                if self.global_step % self.training_config.logging_steps == 0:
                    logger.info(
                        f"Step {self.global_step}: "
                        f"loss={metrics['loss']:.4f}, "
                        f"lr={metrics['learning_rate']:.2e}"
                    )
                
                # Evaluation
                if (
                    eval_dataloader is not None and
                    self.global_step % self.training_config.eval_steps == 0 and
                    self.global_step > 0
                ):
                    eval_metrics = self.evaluate(eval_dataloader)
                    logger.info(
                        f"Evaluation at step {self.global_step}: "
                        f"eval_loss={eval_metrics['eval_loss']:.4f}, "
                        f"perplexity={eval_metrics['perplexity']:.2f}"
                    )
                    
                    # Save best model
                    if eval_metrics['eval_loss'] < self.best_loss:
                        self.best_loss = eval_metrics['eval_loss']
                        self.save_checkpoint("best")
                
                # Save checkpoint
                if self.global_step % self.training_config.save_steps == 0 and self.global_step > 0:
                    self.save_checkpoint(f"step_{self.global_step}")
                
                self.global_step += 1
            
            # End of epoch
            avg_epoch_loss = epoch_loss / epoch_samples if epoch_samples > 0 else 0
            logger.info(f"Epoch {epoch + 1} completed: avg_loss={avg_epoch_loss:.4f}")
            
            # Save epoch checkpoint
            self.save_checkpoint(f"epoch_{epoch + 1}")
        
        # Training completed
        training_time = time.time() - start_time
        logger.info(f"Training completed in {training_time:.2f} seconds")
        
        # Save final model
        self.save_checkpoint("final")
    
    def save_checkpoint(self, name: str):
        """
        Save model checkpoint.
        
        Args:
            name: Checkpoint name
        """
        checkpoint_dir = Path(self.training_config.checkpoint_dir) / name
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Save model
        model_path = checkpoint_dir / "model.pt"
        torch.save(self.model.state_dict(), model_path)
        
        # Save optimizer
        optimizer_path = checkpoint_dir / "optimizer.pt"
        torch.save(self.optimizer.state_dict(), optimizer_path)
        
        # Save scheduler
        scheduler_path = checkpoint_dir / "scheduler.pt"
        torch.save(self.scheduler.state_dict(), scheduler_path)
        
        # Save training state
        state = {
            "global_step": self.global_step,
            "epoch": self.epoch,
            "best_loss": self.best_loss,
            "model_config": self.model_config.to_dict(),
            "training_config": self.training_config.to_dict()
        }
        
        state_path = checkpoint_dir / "training_state.json"
        with open(state_path, 'w') as f:
            json.dump(state, f, indent=2)
        
        logger.info(f"Saved checkpoint: {name}")
    
    def load_checkpoint(self, checkpoint_dir: str):
        """
        Load model checkpoint.
        
        Args:
            checkpoint_dir: Checkpoint directory
        """
        checkpoint_dir = Path(checkpoint_dir)
        
        # Load model
        model_path = checkpoint_dir / "model.pt"
        if model_path.exists():
            self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        
        # Load optimizer
        optimizer_path = checkpoint_dir / "optimizer.pt"
        if optimizer_path.exists():
            self.optimizer.load_state_dict(torch.load(optimizer_path, map_location=self.device))
        
        # Load scheduler
        scheduler_path = checkpoint_dir / "scheduler.pt"
        if scheduler_path.exists():
            self.scheduler.load_state_dict(torch.load(scheduler_path, map_location=self.device))
        
        # Load training state
        state_path = checkpoint_dir / "training_state.json"
        if state_path.exists():
            with open(state_path, 'r') as f:
                state = json.load(f)
            
            self.global_step = state.get("global_step", 0)
            self.epoch = state.get("epoch", 0)
            self.best_loss = state.get("best_loss", float('inf'))
        
        logger.info(f"Loaded checkpoint from {checkpoint_dir}")
    
    def generate_text(
        self,
        prompt: str,
        max_length: int = 100,
        temperature: float = 0.8,
        top_k: int = 50,
        top_p: float = 0.95
    ) -> str:
        """
        Generate text from prompt.
        
        Args:
            prompt: Input prompt
            max_length: Maximum length to generate
            temperature: Sampling temperature
            top_k: Top-k sampling
            top_p: Top-p sampling
            
        Returns:
            Generated text
        """
        self.model.eval()
        
        # Tokenize prompt
        token_ids = self.tokenizer.encode(prompt)
        input_ids = torch.tensor([token_ids]).to(self.device)
        
        # Generate
        with torch.no_grad():
            generated_ids = self.model.generate(
                input_ids=input_ids,
                max_length=max_length,
                temperature=temperature,
                top_k=top_k,
                top_p=top_p,
                do_sample=True
            )
        
        # Decode
        generated_text = self.tokenizer.decode(generated_ids[0].tolist())
        
        return generated_text


def train_small_model():
    """Train a small Mythos model as proof of concept."""
    logger.info("Starting small model training...")
    
    # Configuration
    model_config = get_model_config("tiny")
    training_config = TrainingConfig(
        batch_size=2,
        gradient_accumulation_steps=2,
        learning_rate=5e-4,
        num_train_epochs=2,
        warmup_steps=10,
        logging_steps=5,
        save_steps=20,
        eval_steps=10,
        output_dir="outputs/small_model",
        checkpoint_dir="checkpoints/small_model",
        log_dir="logs/small_model"
    )
    
    # Create sample data
    data_dir = "data/sample"
    create_sample_data(data_dir)
    
    # Initialize tokenizer and data processor
    tokenizer = get_tokenizer(model_config.vocab_size)
    data_processor = MythosDataProcessor(tokenizer, model_config)
    
    # Load data
    texts = data_processor.load_text_files(data_dir)
    
    # Split into train/validation
    split_idx = int(len(texts) * 0.8)
    train_texts = texts[:split_idx]
    val_texts = texts[split_idx:]
    
    # Create datasets
    train_dataset = data_processor.create_dataset(train_texts)
    val_dataset = data_processor.create_dataset(val_texts)
    
    # Create dataloaders
    train_dataloader = data_processor.create_dataloader(
        train_dataset,
        batch_size=training_config.batch_size,
        shuffle=True
    )
    val_dataloader = data_processor.create_dataloader(
        val_dataset,
        batch_size=training_config.batch_size,
        shuffle=False
    )
    
    logger.info(f"Train samples: {len(train_dataset)}")
    logger.info(f"Validation samples: {len(val_dataset)}")
    
    # Initialize trainer
    trainer = Trainer(model_config, training_config, tokenizer)
    
    # Train
    trainer.train(train_dataloader, val_dataloader)
    
    # Test generation
    logger.info("Testing text generation...")
    prompts = [
        "Artificial intelligence is",
        "Large language models can",
        "The future of AI will"
    ]
    
    for prompt in prompts:
        generated = trainer.generate_text(prompt, max_length=50)
        logger.info(f"Prompt: {prompt}")
        logger.info(f"Generated: {generated}")
        logger.info("-" * 50)
    
    return trainer


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Train small model
    trainer = train_small_model()
    
    logger.info("Training completed successfully!")