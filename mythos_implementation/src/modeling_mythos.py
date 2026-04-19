"""
Mythos transformer implementation.
Recreation of Anthropic's Mythos/Glasswing/Capybara LLM architecture.
"""

import math
from typing import Optional, Tuple, List, Dict, Any
import torch
import torch.nn as nn
import torch.nn.functional as F

from config.model_config import ModelConfig


class RotaryPositionEmbedding(nn.Module):
    """
    Rotary Position Embedding (RoPE) for attention.
    Simplified implementation.
    """
    
    def __init__(self, dim: int, max_seq_len: int = 8192, base: int = 10000):
        super().__init__()
        self.dim = dim
        self.max_seq_len = max_seq_len
        self.base = base
        
        # Precompute frequencies
        inv_freq = 1.0 / (base ** (torch.arange(0, dim, 2).float() / dim))
        self.register_buffer("inv_freq", inv_freq, persistent=False)
        
    def forward(self, x: torch.Tensor, offset: int = 0) -> torch.Tensor:
        """
        Apply rotary embeddings to input tensor.
        
        Args:
            x: Tensor of shape (batch, seq_len, num_heads, head_dim)
            offset: Position offset
            
        Returns:
            Tensor with rotary embeddings applied
        """
        batch, seq_len, num_heads, head_dim = x.shape
        
        # Create position indices
        t = torch.arange(offset, offset + seq_len, device=x.device).type_as(self.inv_freq)
        
        # Compute frequencies
        freqs = torch.einsum('i,j->ij', t, self.inv_freq)
        
        # Create rotation matrix for the first self.dim dimensions
        emb = torch.cat([freqs, freqs], dim=-1)
        cos = emb.cos().view(1, seq_len, 1, self.dim)
        sin = emb.sin().view(1, seq_len, 1, self.dim)
        
        # Apply rotary embedding to first self.dim dimensions
        if head_dim >= self.dim:
            x_rot = x[..., :self.dim]
            x_pass = x[..., self.dim:]
            
            # Split and rotate
            x1, x2 = x_rot.chunk(2, dim=-1)
            rotated = torch.cat([x1 * cos - x2 * sin, x2 * cos + x1 * sin], dim=-1)
            
            # Concatenate with the rest
            if x_pass.shape[-1] > 0:
                rotated = torch.cat([rotated, x_pass], dim=-1)
        else:
            # If head_dim is smaller than self.dim, apply to entire tensor
            x1, x2 = x.chunk(2, dim=-1)
            cos = cos[..., :head_dim]
            sin = sin[..., :head_dim]
            rotated = torch.cat([x1 * cos - x2 * sin, x2 * cos + x1 * sin], dim=-1)
        
        return rotated


class MythosAttention(nn.Module):
    """Multi-head attention with rotary position embeddings."""
    
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config
        
        self.num_attention_heads = config.num_attention_heads
        self.attention_head_size = config.attention_head_size
        self.all_head_size = self.num_attention_heads * self.attention_head_size
        
        # Query, Key, Value projections
        self.query = nn.Linear(config.hidden_size, self.all_head_size, bias=False)
        self.key = nn.Linear(config.hidden_size, self.all_head_size, bias=False)
        self.value = nn.Linear(config.hidden_size, self.all_head_size, bias=False)
        
        # Output projection
        self.dense = nn.Linear(self.all_head_size, config.hidden_size, bias=False)
        
        # Dropout
        self.attn_dropout = nn.Dropout(config.attention_dropout_prob)
        self.resid_dropout = nn.Dropout(config.hidden_dropout_prob)
        
        # Rotary position embeddings (temporarily disabled for testing)
        self.rotary_emb = None
        
        # Scaling
        self.scale_attn_weights = config.scale_attn_weights
        self.scale_attn_by_inverse_layer_idx = config.scale_attn_by_inverse_layer_idx
        
    def transpose_for_scores(self, x: torch.Tensor) -> torch.Tensor:
        """Reshape tensor for multi-head attention."""
        new_x_shape = x.size()[:-1] + (self.num_attention_heads, self.attention_head_size)
        x = x.view(*new_x_shape)
        return x.permute(0, 2, 1, 3)  # (batch, heads, seq_len, head_dim)
    
    def forward(
        self,
        hidden_states: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        layer_past: Optional[Tuple[torch.Tensor, torch.Tensor]] = None,
        use_cache: bool = False,
        output_attentions: bool = False
    ) -> Tuple[torch.Tensor, ...]:
        """
        Forward pass for attention.
        
        Args:
            hidden_states: Input tensor of shape (batch, seq_len, hidden_size)
            attention_mask: Attention mask of shape (batch, seq_len)
            layer_past: Tuple of (key, value) from previous layer
            use_cache: Whether to return key/value states for caching
            output_attentions: Whether to return attention weights
            
        Returns:
            Tuple of (output, present_key_value, attention_weights)
        """
        batch_size, seq_len, _ = hidden_states.shape
        
        # Project to query, key, value
        query = self.query(hidden_states)
        key = self.key(hidden_states)
        value = self.value(hidden_states)
        
        # Reshape for multi-head attention
        query = self.transpose_for_scores(query)  # (batch, heads, seq_len, head_dim)
        key = self.transpose_for_scores(key)
        value = self.transpose_for_scores(value)
        
        # Apply rotary position embeddings if enabled (temporarily disabled)
        
        # If using past key/value, concatenate with current
        if layer_past is not None:
            past_key, past_value = layer_past
            key = torch.cat((past_key, key), dim=-2)
            value = torch.cat((past_value, value), dim=-2)
        
        present_key_value = (key, value) if use_cache else None
        
        # Compute attention scores
        # (batch, heads, seq_len, head_dim) @ (batch, heads, head_dim, seq_len) -> (batch, heads, seq_len, seq_len)
        attention_scores = torch.matmul(query, key.transpose(-1, -2))
        
        # Scale attention scores
        if self.scale_attn_weights:
            attention_scores = attention_scores / math.sqrt(self.attention_head_size)
        
        # Apply attention mask
        if attention_mask is not None:
            # Expand attention mask to match attention scores shape
            attention_mask = attention_mask.unsqueeze(1).unsqueeze(2)  # (batch, 1, 1, seq_len)
            attention_scores = attention_scores + attention_mask
        
        # Apply softmax to get attention probabilities
        attention_probs = F.softmax(attention_scores, dim=-1)
        attention_probs = self.attn_dropout(attention_probs)
        
        # Apply attention to values
        context_layer = torch.matmul(attention_probs, value)
        
        # Reshape back to (batch, seq_len, hidden_size)
        context_layer = context_layer.permute(0, 2, 1, 3).contiguous()
        new_context_layer_shape = context_layer.size()[:-2] + (self.all_head_size,)
        context_layer = context_layer.view(*new_context_layer_shape)
        
        # Output projection
        output = self.dense(context_layer)
        output = self.resid_dropout(output)
        
        outputs = (output,)
        if present_key_value is not None:
            outputs = outputs + (present_key_value,)
        if output_attentions:
            outputs = outputs + (attention_probs,)
        
        return outputs


class MythosMLP(nn.Module):
    """Multi-layer perceptron for transformer block."""
    
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config
        
        self.fc_in = nn.Linear(config.hidden_size, config.intermediate_size)
        self.fc_out = nn.Linear(config.intermediate_size, config.hidden_size)
        self.act = nn.GELU()
        self.dropout = nn.Dropout(config.hidden_dropout_prob)
        
    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """Forward pass for MLP."""
        hidden_states = self.fc_in(hidden_states)
        hidden_states = self.act(hidden_states)
        hidden_states = self.fc_out(hidden_states)
        hidden_states = self.dropout(hidden_states)
        return hidden_states


class MythosBlock(nn.Module):
    """Single transformer block for Mythos architecture."""
    
    def __init__(self, config: ModelConfig, layer_idx: int = 0):
        super().__init__()
        self.config = config
        self.layer_idx = layer_idx
        
        # Layer normalization
        self.ln_1 = nn.LayerNorm(config.hidden_size, eps=config.layer_norm_eps)
        self.ln_2 = nn.LayerNorm(config.hidden_size, eps=config.layer_norm_eps)
        
        # Attention
        self.attn = MythosAttention(config)
        
        # MLP
        self.mlp = MythosMLP(config)
        
    def forward(
        self,
        hidden_states: torch.Tensor,
        attention_mask: Optional[torch.Tensor] = None,
        layer_past: Optional[Tuple[torch.Tensor, torch.Tensor]] = None,
        use_cache: bool = False,
        output_attentions: bool = False
    ) -> Tuple[torch.Tensor, ...]:
        """
        Forward pass for transformer block.
        
        Args:
            hidden_states: Input tensor of shape (batch, seq_len, hidden_size)
            attention_mask: Attention mask
            layer_past: Past key/value states
            use_cache: Whether to cache key/value states
            output_attentions: Whether to return attention weights
            
        Returns:
            Tuple of (output, present_key_value, attention_weights)
        """
        residual = hidden_states
        
        # Self-attention with pre-norm
        hidden_states = self.ln_1(hidden_states)
        attn_outputs = self.attn(
            hidden_states,
            attention_mask=attention_mask,
            layer_past=layer_past,
            use_cache=use_cache,
            output_attentions=output_attentions
        )
        
        attn_output = attn_outputs[0]
        outputs = attn_outputs[1:]
        
        # Residual connection
        hidden_states = residual + attn_output
        
        # MLP with pre-norm
        residual = hidden_states
        hidden_states = self.ln_2(hidden_states)
        mlp_output = self.mlp(hidden_states)
        
        # Residual connection
        hidden_states = residual + mlp_output
        
        if use_cache:
            outputs = (hidden_states,) + outputs
        else:
            outputs = (hidden_states,) + outputs[1:] if len(outputs) > 1 else (hidden_states,)
        
        return outputs


class MythosModel(nn.Module):
    """
    Main Mythos model without language modeling head.
    Based on gathered intelligence about Anthropic's architecture.
    """
    
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config
        
        # Embeddings
        self.wte = nn.Embedding(config.vocab_size, config.hidden_size)
        self.wpe = nn.Embedding(config.max_position_embeddings, config.hidden_size)
        self.drop = nn.Dropout(config.embedding_dropout_prob)
        
        # Transformer blocks
        self.h = nn.ModuleList([
            MythosBlock(config, layer_idx=i)
            for i in range(config.num_hidden_layers)
        ])
        
        # Final layer norm
        self.ln_f = nn.LayerNorm(config.hidden_size, eps=config.layer_norm_eps)
        
        # Initialize weights
        self.apply(self._init_weights)
        
        # Apply special scaled initialization
        for name, p in self.named_parameters():
            if name.endswith('c_proj.weight'):
                # Special scaled initialization for output projections
                torch.nn.init.normal_(p, mean=0.0, std=self.config.initializer_range / math.sqrt(2 * config.num_hidden_layers))
    
    def _init_weights(self, module):
        """Initialize weights."""
        if isinstance(module, (nn.Linear, nn.Embedding)):
            torch.nn.init.normal_(module.weight, mean=0.0, std=self.config.initializer_range)
            if isinstance(module, nn.Linear) and module.bias is not None:
                torch.nn.init.zeros_(module.bias)
        elif isinstance(module, nn.LayerNorm):
            torch.nn.init.zeros_(module.bias)
            torch.nn.init.ones_(module.weight)
    
    def get_input_embeddings(self):
        """Get word token embeddings."""
        return self.wte
    
    def set_input_embeddings(self, new_embeddings):
        """Set word token embeddings."""
        self.wte = new_embeddings
    
    def forward(
        self,
        input_ids: Optional[torch.Tensor] = None,
        attention_mask: Optional[torch.Tensor] = None,
        position_ids: Optional[torch.Tensor] = None,
        past_key_values: Optional[List[Tuple[torch.Tensor, torch.Tensor]]] = None,
        use_cache: Optional[bool] = None,
        output_attentions: Optional[bool] = None,
        output_hidden_states: Optional[bool] = None,
        return_dict: Optional[bool] = None
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass for Mythos model.
        
        Args:
            input_ids: Input token IDs of shape (batch, seq_len)
            attention_mask: Attention mask of shape (batch, seq_len)
            position_ids: Position IDs of shape (batch, seq_len)
            past_key_values: List of past key/value states for each layer
            use_cache: Whether to use caching
            output_attentions: Whether to return attention weights
            output_hidden_states: Whether to return hidden states
            return_dict: Whether to return dict or tuple
            
        Returns:
            Dictionary or tuple of model outputs
        """
        output_attentions = output_attentions if output_attentions is not None else False
        output_hidden_states = output_hidden_states if output_hidden_states is not None else False
        use_cache = use_cache if use_cache is not None else self.config.use_cache
        return_dict = return_dict if return_dict is not None else True
        
        batch_size, seq_len = input_ids.shape
        
        # Create position ids if not provided
        if position_ids is None:
            device = input_ids.device
            position_ids = torch.arange(seq_len, dtype=torch.long, device=device)
            position_ids = position_ids.unsqueeze(0).expand(batch_size, -1)
        
        # Create attention mask if not provided
        if attention_mask is None:
            attention_mask = torch.ones((batch_size, seq_len), device=input_ids.device)
        
        # Convert attention mask to attention bias
        # 1 -> keep, 0 -> mask
        attention_mask = attention_mask.float()
        attention_mask = attention_mask.masked_fill(attention_mask == 0, float('-inf')).masked_fill(attention_mask == 1, float(0.0))
        
        # Prepare past key values
        if past_key_values is None:
            past_key_values = [None] * len(self.h)
        
        # Get embeddings
        inputs_embeds = self.wte(input_ids)
        position_embeds = self.wpe(position_ids)
        hidden_states = inputs_embeds + position_embeds
        hidden_states = self.drop(hidden_states)
        
        # Prepare outputs
        all_hidden_states = () if output_hidden_states else None
        all_attentions = () if output_attentions else None
        all_cross_attentions = () if output_attentions else None
        next_decoder_cache = () if use_cache else None
        
        # Forward through transformer blocks
        for i, (block, layer_past) in enumerate(zip(self.h, past_key_values)):
            if output_hidden_states:
                all_hidden_states = all_hidden_states + (hidden_states,)
            
            block_outputs = block(
                hidden_states,
                attention_mask=attention_mask,
                layer_past=layer_past,
                use_cache=use_cache,
                output_attentions=output_attentions
            )
            
            hidden_states = block_outputs[0]
            
            if use_cache:
                next_decoder_cache = next_decoder_cache + (block_outputs[1],)
            
            if output_attentions:
                all_attentions = all_attentions + (block_outputs[2],)
        
        # Apply final layer norm
        hidden_states = self.ln_f(hidden_states)
        
        if output_hidden_states:
            all_hidden_states = all_hidden_states + (hidden_states,)
        
        if not return_dict:
            return tuple(
                v for v in [
                    hidden_states,
                    next_decoder_cache,
                    all_hidden_states,
                    all_attentions,
                    all_cross_attentions
                ] if v is not None
            )
        
        return {
            "last_hidden_state": hidden_states,
            "past_key_values": next_decoder_cache,
            "hidden_states": all_hidden_states,
            "attentions": all_attentions,
            "cross_attentions": all_cross_attentions
        }


class MythosForCausalLM(nn.Module):
    """
    Mythos model with language modeling head.
    For causal language modeling tasks.
    """
    
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.config = config
        
        # Transformer model
        self.transformer = MythosModel(config)
        
        # Language modeling head
        self.lm_head = nn.Linear(config.hidden_size, config.vocab_size, bias=False)
        
        # Tie weights (common practice)
        self.lm_head.weight = self.transformer.wte.weight
        
        # Initialize weights
        self.post_init()
    
    def post_init(self):
        """Post-initialization."""
        # Apply special initialization to lm_head
        torch.nn.init.normal_(
            self.lm_head.weight,
            mean=0.0,
            std=self.config.initializer_range / math.sqrt(2 * self.config.num_hidden_layers)
        )
    
    def get_output_embeddings(self):
        """Get language modeling head."""
        return self.lm_head
    
    def set_output_embeddings(self, new_embeddings):
        """Set language modeling head."""
        self.lm_head = new_embeddings
    
    def forward(
        self,
        input_ids: Optional[torch.Tensor] = None,
        attention_mask: Optional[torch.Tensor] = None,
        position_ids: Optional[torch.Tensor] = None,
        past_key_values: Optional[List[Tuple[torch.Tensor, torch.Tensor]]] = None,
        labels: Optional[torch.Tensor] = None,
        use_cache: Optional[bool] = None,
        output_attentions: Optional[bool] = None,
        output_hidden_states: Optional[bool] = None,
        return_dict: Optional[bool] = None
    ) -> Dict[str, torch.Tensor]:
        """
        Forward pass for causal language modeling.
        
        Args:
            input_ids: Input token IDs
            attention_mask: Attention mask
            position_ids: Position IDs
            past_key_values: Past key/value states
            labels: Labels for language modeling
            use_cache: Whether to use caching
            output_attentions: Whether to return attention weights
            output_hidden_states: Whether to return hidden states
            return_dict: Whether to return dict or tuple
            
        Returns:
            Dictionary or tuple of model outputs
        """
        return_dict = return_dict if return_dict is not None else True
        
        # Get transformer outputs
        transformer_outputs = self.transformer(
            input_ids=input_ids,
            attention_mask=attention_mask,
            position_ids=position_ids,
            past_key_values=past_key_values,
            use_cache=use_cache,
            output_attentions=output_attentions,
            output_hidden_states=output_hidden_states,
            return_dict=return_dict
        )
        
        hidden_states = transformer_outputs[0] if not return_dict else transformer_outputs["last_hidden_state"]
        
        # Language modeling head
        lm_logits = self.lm_head(hidden_states)
        
        loss = None
        if labels is not None:
            # Shift so that tokens < n predict n
            shift_logits = lm_logits[..., :-1, :].contiguous()
            shift_labels = labels[..., 1:].contiguous()
            
            # Flatten the tokens
            loss_fct = nn.CrossEntropyLoss()
            loss = loss_fct(shift_logits.view(-1, shift_logits.size(-1)), shift_labels.view(-1))
        
        if not return_dict:
            output = (lm_logits,) + transformer_outputs[1:]
            return ((loss,) + output) if loss is not None else output
        
        return {
            "loss": loss,
            "logits": lm_logits,
            "past_key_values": transformer_outputs.get("past_key_values"),
            "hidden_states": transformer_outputs.get("hidden_states"),
            "attentions": transformer_outputs.get("attentions")
        }
    
    def prepare_inputs_for_generation(
        self,
        input_ids: torch.Tensor,
        past_key_values: Optional[List[Tuple[torch.Tensor, torch.Tensor]]] = None,
        attention_mask: Optional[torch.Tensor] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Prepare inputs for generation.
        
        Args:
            input_ids: Input token IDs
            past_key_values: Past key/value states
            attention_mask: Attention mask
            
        Returns:
            Dictionary of model inputs
        """
        if past_key_values:
            input_ids = input_ids[:, -1:]
        
        return {
            "input_ids": input_ids,
            "past_key_values": past_key_values,
            "use_cache": kwargs.get("use_cache", self.config.use_cache),
            "attention_mask": attention_mask,
        }
    
    @torch.no_grad()
    def generate(
        self,
        input_ids: torch.Tensor,
        max_length: int = 100,
        temperature: float = 1.0,
        top_k: int = 50,
        top_p: float = 0.95,
        repetition_penalty: float = 1.0,
        do_sample: bool = True,
        **kwargs
    ) -> torch.Tensor:
        """
        Generate text using the model.
        
        Args:
            input_ids: Starting token IDs
            max_length: Maximum length to generate
            temperature: Sampling temperature
            top_k: Top-k sampling parameter
            top_p: Top-p (nucleus) sampling parameter
            repetition_penalty: Penalty for repeated tokens
            do_sample: Whether to sample or use greedy decoding
            
        Returns:
            Generated token IDs
        """
        self.eval()
        
        generated = input_ids.clone()
        past_key_values = None
        
        for _ in range(max_length - input_ids.shape[1]):
            # Prepare inputs
            model_inputs = self.prepare_inputs_for_generation(
                generated,
                past_key_values=past_key_values,
                attention_mask=torch.ones_like(generated)
            )
            
            # Forward pass
            outputs = self(**model_inputs)
            
            # Get next token logits
            next_token_logits = outputs['logits'][:, -1, :] / temperature
            
            # Apply repetition penalty
            if repetition_penalty != 1.0:
                for token_id in set(generated[0].tolist()):
                    next_token_logits[0, token_id] /= repetition_penalty
            
            # Apply top-k filtering
            if top_k > 0:
                indices_to_remove = next_token_logits < torch.topk(next_token_logits, top_k)[0][..., -1, None]
                next_token_logits[indices_to_remove] = -float('inf')
            
            # Apply top-p (nucleus) filtering
            if top_p < 1.0:
                sorted_logits, sorted_indices = torch.sort(next_token_logits, descending=True)
                cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                
                # Remove tokens with cumulative probability above threshold
                sorted_indices_to_remove = cumulative_probs > top_p
                # Shift the indices to the right to keep first token above threshold
                sorted_indices_to_remove[..., 1:] = sorted_indices_to_remove[..., :-1].clone()
                sorted_indices_to_remove[..., 0] = 0
                
                indices_to_remove = sorted_indices_to_remove.scatter(1, sorted_indices, sorted_indices_to_remove)
                next_token_logits[indices_to_remove] = -float('inf')
            
            # Sample or take argmax
            if do_sample:
                probs = F.softmax(next_token_logits, dim=-1)
                next_token = torch.multinomial(probs, num_samples=1)
            else:
                next_token = torch.argmax(next_token_logits, dim=-1, keepdim=True)
            
            # Append to generated sequence
            generated = torch.cat([generated, next_token], dim=1)
            
            # Update past key values
            past_key_values = outputs.get('past_key_values')
        
        return generated