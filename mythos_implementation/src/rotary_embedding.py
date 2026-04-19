"""
Simplified Rotary Position Embedding implementation.
"""

import torch
import torch.nn as nn
import math


class RotaryEmbedding(nn.Module):
    """Rotary Position Embedding (RoPE) - simplified implementation."""
    
    def __init__(self, dim: int, max_seq_len: int = 2048, base: int = 10000):
        super().__init__()
        self.dim = dim
        self.max_seq_len = max_seq_len
        self.base = base
        
        # Precompute inverse frequencies
        inv_freq = 1.0 / (base ** (torch.arange(0, dim, 2).float() / dim))
        self.register_buffer("inv_freq", inv_freq, persistent=False)
        
    def forward(self, x: torch.Tensor, offset: int = 0) -> torch.Tensor:
        """
        Apply rotary embeddings to input tensor.
        
        Args:
            x: Tensor of shape (batch_size, seq_len, num_heads, head_dim)
            offset: Position offset for caching
            
        Returns:
            Tensor with rotary embeddings applied
        """
        batch_size, seq_len, num_heads, head_dim = x.shape
        
        # Create position indices
        t = torch.arange(offset, offset + seq_len, device=x.device).type_as(self.inv_freq)
        
        # Compute frequencies
        freqs = torch.einsum('i,j->ij', t, self.inv_freq)
        
        # Create rotation matrix
        emb = torch.cat([freqs, freqs], dim=-1)
        cos = emb.cos().view(1, seq_len, 1, head_dim)
        sin = emb.sin().view(1, seq_len, 1, head_dim)
        
        # Apply rotary embedding
        x_rot = x * cos + self._rotate_half(x) * sin
        
        return x_rot
    
    def _rotate_half(self, x: torch.Tensor) -> torch.Tensor:
        """Rotate the second half of the dimensions."""
        x1, x2 = x.chunk(2, dim=-1)
        return torch.cat([-x2, x1], dim=-1)


def apply_rotary_pos_emb(q, k, cos, sin, position_ids=None):
    """
    Apply rotary position embedding to query and key tensors.
    
    Args:
        q, k: Query and key tensors of shape (batch, seq_len, heads, head_dim)
        cos, sin: Cosine and sine tensors
        position_ids: Optional position IDs
        
    Returns:
        Rotary position embedded query and key
    """
    # q, k: [batch, seq_len, heads, head_dim]
    # cos, sin: [batch, seq_len, head_dim] or [1, seq_len, head_dim]
    
    # Reshape cos and sin to match q and k
    cos = cos.unsqueeze(2)  # [batch, seq_len, 1, head_dim]
    sin = sin.unsqueeze(2)  # [batch, seq_len, 1, head_dim]
    
    # Apply rotary embedding
    q_embed = (q * cos) + (rotate_half(q) * sin)
    k_embed = (k * cos) + (rotate_half(k) * sin)
    
    return q_embed, k_embed


def rotate_half(x):
    """Rotate the second half of the dimensions."""
    x1, x2 = x[..., :x.shape[-1] // 2], x[..., x.shape[-1] // 2:]
    return torch.cat([-x2, x1], dim=-1)


def precompute_freqs_cis(dim: int, end: int, theta: float = 10000.0):
    """
    Precompute the frequency tensor for complex exponentials (cis) with given dimensions.
    
    Args:
        dim: Dimension of the frequency tensor
        end: End index for precomputation
        theta: Scaling factor for frequency computation
        
    Returns:
        Complex tensor of shape (end, dim/2)
    """
    freqs = 1.0 / (theta ** (torch.arange(0, dim, 2)[: (dim // 2)].float() / dim))
    t = torch.arange(end, device=freqs.device)
    freqs = torch.outer(t, freqs).float()
    freqs_cis = torch.polar(torch.ones_like(freqs), freqs)
    return freqs_cis