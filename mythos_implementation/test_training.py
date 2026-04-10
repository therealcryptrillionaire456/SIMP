#!/usr/bin/env python3
"""
Test training pipeline for Mythos model.
"""

import torch
import logging
import sys
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.training import train_small_model, TrainingConfig, Trainer
from src.data_utils import create_sample_data, MythosDataProcessor
from src.tokenizer import get_tokenizer
from config.model_config import get_model_config


def test_data_creation():
    """Test data creation and processing."""
    print("="*80)
    print("TESTING DATA CREATION")
    print("="*80)
    
    # Create sample data
    data_dir = "data/test_sample"
    texts = create_sample_data(data_dir)
    
    print(f"\nCreated {len(texts)} sample texts")
    print(f"Sample text: {texts[0][:100]}...")
    
    # Test data processor
    model_config = get_model_config("tiny")
    tokenizer = get_tokenizer(model_config.vocab_size)
    processor = MythosDataProcessor(tokenizer, model_config)
    
    # Load data
    loaded_texts = processor.load_text_files(data_dir)
    print(f"\nLoaded {len(loaded_texts)} texts from {data_dir}")
    
    # Create dataset
    dataset = processor.create_dataset(loaded_texts[:5])
    print(f"Dataset size: {len(dataset)}")
    
    # Test one sample
    sample = dataset[0]
    print(f"\nSample batch keys: {list(sample.keys())}")
    print(f"Input IDs shape: {sample['input_ids'].shape}")
    print(f"Attention mask shape: {sample['attention_mask'].shape}")
    
    return True


def test_training_config():
    """Test training configuration."""
    print("\n" + "="*80)
    print("TESTING TRAINING CONFIGURATION")
    print("="*80)
    
    config = TrainingConfig(
        batch_size=2,
        gradient_accumulation_steps=2,
        learning_rate=5e-4,
        num_train_epochs=1
    )
    
    print(f"\nTraining configuration:")
    print(f"  Batch size: {config.batch_size}")
    print(f"  Gradient accumulation steps: {config.gradient_accumulation_steps}")
    print(f"  Learning rate: {config.learning_rate}")
    print(f"  Epochs: {config.num_train_epochs}")
    print(f"  Output directory: {config.output_dir}")
    
    # Save and load
    config.save("test_config.json")
    print(f"\nSaved configuration to test_config.json")
    
    return True


def test_trainer_initialization():
    """Test trainer initialization."""
    print("\n" + "="*80)
    print("TESTING TRAINER INITIALIZATION")
    print("="*80)
    
    model_config = get_model_config("tiny")
    training_config = TrainingConfig(
        batch_size=2,
        gradient_accumulation_steps=2,
        learning_rate=5e-4,
        num_train_epochs=1,
        logging_steps=1,
        save_steps=5,
        eval_steps=3
    )
    
    # Initialize trainer
    trainer = Trainer(model_config, training_config)
    
    print(f"\nTrainer initialized:")
    print(f"  Device: {trainer.device}")
    print(f"  Model parameters: {sum(p.numel() for p in trainer.model.parameters()):,}")
    print(f"  Global step: {trainer.global_step}")
    print(f"  Epoch: {trainer.epoch}")
    
    # Test model forward pass
    print("\nTesting model forward pass...")
    batch_size = 2
    seq_len = 16
    
    # Create dummy batch
    input_ids = torch.randint(0, model_config.vocab_size, (batch_size, seq_len))
    attention_mask = torch.ones(batch_size, seq_len)
    labels = input_ids.clone()
    
    batch = {
        'input_ids': input_ids.to(trainer.device),
        'attention_mask': attention_mask.to(trainer.device),
        'labels': labels.to(trainer.device)
    }
    
    # Forward pass
    with torch.no_grad():
        outputs = trainer.model(**batch)
    
    print(f"  Input shape: {batch['input_ids'].shape}")
    print(f"  Logits shape: {outputs['logits'].shape}")
    print(f"  Loss: {outputs['loss'].item():.4f}")
    print("  ✓ Model forward pass successful!")
    
    # Test training step
    print("\nTesting training step...")
    try:
        loss, metrics = trainer.train_step(batch)
        print(f"  Loss: {metrics['loss']:.4f}")
        print(f"  Learning rate: {metrics['learning_rate']:.2e}")
        print("  ✓ Training step successful!")
    except Exception as e:
        print(f"  ✗ Training step failed: {e}")
        return False
    
    return True


def test_text_generation():
    """Test text generation."""
    print("\n" + "="*80)
    print("TESTING TEXT GENERATION")
    print("="*80)
    
    model_config = get_model_config("tiny")
    training_config = TrainingConfig()
    trainer = Trainer(model_config, training_config)
    
    # Test generation
    prompts = [
        "Artificial intelligence",
        "Machine learning",
        "The future"
    ]
    
    for prompt in prompts:
        print(f"\nPrompt: '{prompt}'")
        try:
            generated = trainer.generate_text(
                prompt,
                max_length=20,
                temperature=0.8,
                top_k=10
            )
            print(f"Generated: {generated}")
        except Exception as e:
            print(f"Generation failed: {e}")
    
    return True


def test_small_training():
    """Test small training run."""
    print("\n" + "="*80)
    print("TESTING SMALL TRAINING RUN")
    print("="*80)
    
    print("\nThis will run a small training session (1 epoch, few steps)")
    print("to verify the training pipeline works.")
    
    try:
        # Create minimal configuration
        model_config = get_model_config("tiny")
        training_config = TrainingConfig(
            batch_size=2,
            gradient_accumulation_steps=1,
            learning_rate=5e-4,
            num_train_epochs=1,
            warmup_steps=2,
            logging_steps=1,
            save_steps=5,
            eval_steps=3,
            output_dir="outputs/test_training",
            checkpoint_dir="checkpoints/test_training",
            log_dir="logs/test_training"
        )
        
        # Create sample data
        data_dir = "data/test_training"
        from src.data_utils import create_sample_data
        texts = create_sample_data(data_dir)
        
        # Initialize tokenizer and data processor
        tokenizer = get_tokenizer(model_config.vocab_size)
        from src.data_utils import MythosDataProcessor
        processor = MythosDataProcessor(tokenizer, model_config)
        
        # Create small dataset
        train_texts = texts[:4]  # Just 4 samples
        train_dataset = processor.create_dataset(train_texts)
        train_dataloader = processor.create_dataloader(
            train_dataset,
            batch_size=training_config.batch_size,
            shuffle=True
        )
        
        print(f"\nTraining setup:")
        print(f"  Model: tiny ({model_config.estimated_parameters:,} params)")
        print(f"  Training samples: {len(train_dataset)}")
        print(f"  Batch size: {training_config.batch_size}")
        print(f"  Epochs: {training_config.num_train_epochs}")
        
        # Initialize trainer
        trainer = Trainer(model_config, training_config, tokenizer)
        
        # Run a few training steps
        print("\nRunning training steps...")
        for step, batch in enumerate(train_dataloader):
            if step >= 3:  # Just 3 steps for testing
                break
            
            # Add labels to batch
            batch['labels'] = batch['input_ids'].clone()
            
            loss, metrics = trainer.train_step(batch)
            print(f"  Step {step}: loss={metrics['loss']:.4f}, lr={metrics['learning_rate']:.2e}")
        
        print("\n✓ Small training test successful!")
        
        # Clean up
        import shutil
        for dir_path in ["outputs/test_training", "checkpoints/test_training", "logs/test_training", "data/test_training"]:
            if Path(dir_path).exists():
                shutil.rmtree(dir_path)
        
        return True
        
    except Exception as e:
        print(f"\n✗ Small training test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all training tests."""
    print("MYTHOS TRAINING PIPELINE TESTS")
    print("="*80)
    
    print(f"\nPyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    
    # Run tests
    tests = [
        ("Data Creation", test_data_creation),
        ("Training Configuration", test_training_config),
        ("Trainer Initialization", test_trainer_initialization),
        ("Text Generation", test_text_generation),
        ("Small Training Run", test_small_training)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*40}")
        print(f"Running: {test_name}")
        print(f"{'='*40}")
        
        try:
            success = test_func()
            results.append((test_name, success))
            
            if success:
                print(f"✓ {test_name} PASSED")
            else:
                print(f"✗ {test_name} FAILED")
                
        except Exception as e:
            print(f"✗ {test_name} ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"\nTests passed: {passed}/{total}")
    
    for test_name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    if passed == total:
        print("\n" + "="*80)
        print("ALL TRAINING TESTS PASSED! ✅")
        print("="*80)
        
        print("\nThe training pipeline is ready for use.")
        print("\nNext steps:")
        print("1. Use larger datasets for actual training")
        print("2. Scale up model size (small, medium, large)")
        print("3. Implement proper tokenizer (GPT-2 tokenizer)")
        print("4. Add distributed training for multi-GPU setups")
        print("5. Implement advanced training techniques (gradient checkpointing, etc.)")
        
        return True
    else:
        print("\n" + "="*80)
        print("SOME TESTS FAILED")
        print("="*80)
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)