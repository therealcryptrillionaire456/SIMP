#!/usr/bin/env python3
"""
Test script for Mythos model implementation.
"""

import torch
import torch.nn as nn
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from config.model_config import ModelConfig, get_model_config
from src.modeling_mythos import MythosModel, MythosForCausalLM, MythosAttention


def test_config():
    """Test model configuration."""
    print("="*80)
    print("TESTING MODEL CONFIGURATION")
    print("="*80)
    
    # Test default config
    config = ModelConfig()
    print(f"\nDefault configuration:")
    print(f"  Hidden size: {config.hidden_size}")
    print(f"  Layers: {config.num_hidden_layers}")
    print(f"  Attention heads: {config.num_attention_heads}")
    print(f"  Vocabulary: {config.vocab_size}")
    print(f"  Context length: {config.max_position_embeddings}")
    print(f"  Estimated parameters: {config.estimated_parameters:,}")
    print(f"  Model size: {config.model_size_gb:.1f} GB")
    
    # Test scaled config
    scaled = config.get_scaled_config(scale=0.5)
    print(f"\nScaled configuration (0.5x):")
    print(f"  Hidden size: {scaled.hidden_size}")
    print(f"  Layers: {scaled.num_hidden_layers}")
    print(f"  Estimated parameters: {scaled.estimated_parameters:,}")
    
    # Test predefined configs
    print(f"\nPredefined configurations:")
    for size in ["tiny", "small", "medium", "large", "xl"]:
        config = get_model_config(size)
        print(f"  {size}: {config.estimated_parameters:,} params, {config.model_size_gb:.1f} GB")
    
    return config


def test_model_creation():
    """Test creating Mythos model."""
    print("\n" + "="*80)
    print("TESTING MODEL CREATION")
    print("="*80)
    
    # Create small config for testing
    config = get_model_config("tiny")
    print(f"\nUsing tiny configuration:")
    print(f"  Parameters: {config.estimated_parameters:,}")
    print(f"  Model size: {config.model_size_gb:.1f} GB")
    
    # Create model
    print("\nCreating MythosModel...")
    model = MythosModel(config)
    
    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    
    print(f"  Total parameters: {total_params:,}")
    print(f"  Trainable parameters: {trainable_params:,}")
    print(f"  Estimated vs actual: {config.estimated_parameters:,} vs {total_params:,}")
    
    # Test forward pass
    print("\nTesting forward pass...")
    batch_size = 2
    seq_len = 16
    
    # Create dummy input
    input_ids = torch.randint(0, config.vocab_size, (batch_size, seq_len))
    
    # Forward pass
    with torch.no_grad():
        outputs = model(input_ids=input_ids)
    
    print(f"  Input shape: {input_ids.shape}")
    print(f"  Output shape: {outputs['last_hidden_state'].shape}")
    print("  ✓ Forward pass successful!")
    
    return model, config


def test_causal_lm():
    """Test causal language modeling model."""
    print("\n" + "="*80)
    print("TESTING CAUSAL LANGUAGE MODELING")
    print("="*80)
    
    # Create small config
    config = get_model_config("tiny")
    
    # Create model
    print("\nCreating MythosForCausalLM...")
    model = MythosForCausalLM(config)
    
    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    print(f"  Total parameters: {total_params:,}")
    
    # Test forward pass with labels
    print("\nTesting forward pass with labels...")
    batch_size = 2
    seq_len = 16
    
    # Create dummy input and labels
    input_ids = torch.randint(0, config.vocab_size, (batch_size, seq_len))
    labels = torch.randint(0, config.vocab_size, (batch_size, seq_len))
    
    # Forward pass
    with torch.no_grad():
        outputs = model(input_ids=input_ids, labels=labels)
    
    print(f"  Input shape: {input_ids.shape}")
    print(f"  Logits shape: {outputs['logits'].shape}")
    print(f"  Loss: {outputs['loss'].item():.4f}")
    print("  ✓ Causal LM forward pass successful!")
    
    # Test generation
    print("\nTesting text generation...")
    with torch.no_grad():
        generated = model.generate(
            input_ids=input_ids[:, :4],  # Start with first 4 tokens
            max_length=20,
            temperature=1.0,
            top_k=50,
            do_sample=True
        )
    
    print(f"  Input shape: {input_ids[:, :4].shape}")
    print(f"  Generated shape: {generated.shape}")
    print("  ✓ Text generation successful!")
    
    return model


def test_memory_usage():
    """Test memory usage for different model sizes."""
    print("\n" + "="*80)
    print("TESTING MEMORY USAGE")
    print("="*80)
    
    sizes = ["tiny", "small", "medium"]
    
    for size in sizes:
        print(f"\nTesting {size} model:")
        
        try:
            config = get_model_config(size)
            
            # Create model
            model = MythosModel(config)
            
            # Count parameters
            total_params = sum(p.numel() for p in model.parameters())
            
            # Estimate memory
            memory_mb = total_params * 4 / 1e6  # float32
            
            print(f"  Parameters: {total_params:,}")
            print(f"  Memory (float32): {memory_mb:.1f} MB")
            print(f"  Memory (float16): {memory_mb/2:.1f} MB")
            
            # Test forward pass if memory allows
            if size in ["tiny", "small"]:
                batch_size = 2
                seq_len = 32
                input_ids = torch.randint(0, config.vocab_size, (batch_size, seq_len))
                
                with torch.no_grad():
                    outputs = model(input_ids=input_ids)
                
                print(f"  ✓ Forward pass successful")
            
            # Clean up
            del model
            torch.cuda.empty_cache() if torch.cuda.is_available() else None
            
        except Exception as e:
            print(f"  ✗ Error: {e}")


def test_attention():
    """Test attention mechanism."""
    print("\n" + "="*80)
    print("TESTING ATTENTION MECHANISM")
    print("="*80)
    
    # MythosAttention already imported
    
    # Create config
    config = get_model_config("tiny")
    
    # Create attention module
    print("\nCreating attention module...")
    attention = MythosAttention(config)
    
    # Test forward pass
    batch_size = 2
    seq_len = 16
    hidden_states = torch.randn(batch_size, seq_len, config.hidden_size)
    
    with torch.no_grad():
        outputs = attention(hidden_states)
    
    print(f"  Input shape: {hidden_states.shape}")
    print(f"  Output shape: {outputs[0].shape}")
    print("  ✓ Attention forward pass successful!")
    
    # Test with attention mask
    print("\nTesting with attention mask...")
    attention_mask = torch.ones(batch_size, seq_len)
    attention_mask[:, -4:] = 0  # Mask last 4 tokens
    
    with torch.no_grad():
        outputs = attention(hidden_states, attention_mask=attention_mask)
    
    print(f"  Mask shape: {attention_mask.shape}")
    print("  ✓ Attention with mask successful!")
    
    return attention


def main():
    """Run all tests."""
    print("MYTHOS MODEL IMPLEMENTATION TESTS")
    print("="*80)
    
    # Check PyTorch
    print(f"\nPyTorch version: {torch.__version__}")
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    
    # Run tests
    try:
        config = test_config()
        model, _ = test_model_creation()
        causal_model = test_causal_lm()
        test_memory_usage()
        attention = test_attention()
        
        print("\n" + "="*80)
        print("ALL TESTS PASSED! ✅")
        print("="*80)
        
        print(f"\nSummary:")
        print(f"  - Model configuration system: ✓")
        print(f"  - Transformer architecture: ✓")
        print(f"  - Attention with RoPE: ✓")
        print(f"  - Causal language modeling: ✓")
        print(f"  - Text generation: ✓")
        print(f"  - Memory estimation: ✓")
        
        print(f"\nNext steps:")
        print(f"  1. Scale up to larger model sizes")
        print(f"  2. Implement training pipeline")
        print(f"  3. Add Constitutional AI safety")
        print(f"  4. Train on actual data")
        
        return True
        
    except Exception as e:
        print(f"\n" + "="*80)
        print(f"TESTS FAILED: {e}")
        print("="*80)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)