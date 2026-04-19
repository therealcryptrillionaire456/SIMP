"""
Model configuration for Mythos reconstruction.
Based on gathered intelligence about Anthropic's Mythos/Glasswing/Capybara.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import json
from pathlib import Path


@dataclass
class ModelConfig:
    """
    Configuration for Mythos reconstruction model.
    
    Based on gathered intelligence:
    - Transformer architecture with improvements
    - Constitutional AI safety framework
    - Estimated 10B+ parameters
    - 8192 context length
    """
    
    # Architecture parameters
    vocab_size: int = 50257  # GPT-2 vocabulary (common baseline)
    hidden_size: int = 4096  # Based on Claude model sizes
    num_hidden_layers: int = 32  # Typical for large models
    num_attention_heads: int = 32  # 4096/128 = 32 heads
    intermediate_size: int = 16384  # 4x hidden size
    max_position_embeddings: int = 8192  # Context length
    hidden_dropout_prob: float = 0.1
    attention_probs_dropout_prob: float = 0.1
    layer_norm_eps: float = 1e-5
    
    # Embeddings
    embedding_dropout_prob: float = 0.1
    use_rotary_position_embeddings: bool = True  # Common in modern models
    rotary_dim: int = 64  # Dimension for rotary embeddings
    
    # Attention
    attention_dropout_prob: float = 0.1
    use_flash_attention: bool = False  # Can enable for efficiency
    scale_attn_weights: bool = True
    scale_attn_by_inverse_layer_idx: bool = False
    
    # Initialization
    initializer_range: float = 0.02
    use_cache: bool = True
    
    # Training parameters
    learning_rate: float = 3e-4
    batch_size: int = 32
    gradient_accumulation_steps: int = 4
    num_train_epochs: int = 3
    warmup_steps: int = 1000
    weight_decay: float = 0.01
    adam_beta1: float = 0.9
    adam_beta2: float = 0.95
    adam_epsilon: float = 1e-8
    
    # Safety and alignment
    use_constitutional_ai: bool = True
    safety_filters: List[str] = field(default_factory=lambda: [
        "harmlessness", "helpfulness", "honesty", "constitutional"
    ])
    max_response_length: int = 2048
    
    # Resources
    model_size_gb: float = 80.0  # Estimated model size
    training_tflops: float = 120.0  # Estimated compute requirement
    mixed_precision: bool = True  # Use mixed precision training
    
    # Model metadata
    model_type: str = "mythos"
    architectures: List[str] = field(default_factory=lambda: ["MythosForCausalLM"])
    auto_map: Dict[str, str] = field(default_factory=lambda: {
        "AutoConfig": "config.model_config.ModelConfig",
        "AutoModelForCausalLM": "src.modeling_mythos.MythosForCausalLM"
    })
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        # Ensure hidden size is divisible by number of attention heads
        assert self.hidden_size % self.num_attention_heads == 0, \
            f"hidden_size ({self.hidden_size}) must be divisible by num_attention_heads ({self.num_attention_heads})"
        
        # Calculate derived parameters
        self.attention_head_size = self.hidden_size // self.num_attention_heads
        
        # Estimate parameter count
        self.estimated_parameters = self._estimate_parameters()
        self.total_params = self.estimated_parameters  # Alias for compatibility
        
        # Calculate model size
        self.model_size_gb = self.estimated_parameters * 4 / 1e9  # float32
    
    def _estimate_parameters(self) -> int:
        """Estimate total number of parameters."""
        # Embeddings
        embeddings = self.vocab_size * self.hidden_size + \
                    self.max_position_embeddings * self.hidden_size
        
        # Transformer layers
        # Attention: Q, K, V, O projections
        attention = 4 * self.hidden_size * self.hidden_size
        
        # MLP: two linear layers
        mlp = self.hidden_size * self.intermediate_size + \
              self.intermediate_size * self.hidden_size
        
        # Layer norms (2 per layer)
        layer_norms = 2 * self.hidden_size
        
        # Per layer
        per_layer = attention + mlp + layer_norms
        
        # All layers
        all_layers = self.num_hidden_layers * per_layer
        
        # Final layer norm and LM head
        final = self.hidden_size + self.hidden_size * self.vocab_size
        
        total = embeddings + all_layers + final
        
        return int(total)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            k: v for k, v in self.__dict__.items() 
            if not k.startswith('_') and not callable(v)
        }
    
    def to_json_string(self) -> str:
        """Serialize configuration to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    def save_pretrained(self, save_directory: str):
        """Save configuration to directory."""
        save_path = Path(save_directory)
        save_path.mkdir(parents=True, exist_ok=True)
        
        config_file = save_path / "config.json"
        with open(config_file, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "ModelConfig":
        """Create configuration from dictionary."""
        return cls(**config_dict)
    
    @classmethod
    def from_json_file(cls, json_file: str) -> "ModelConfig":
        """Load configuration from JSON file."""
        with open(json_file, 'r') as f:
            config_dict = json.load(f)
        return cls.from_dict(config_dict)
    
    @classmethod
    def from_pretrained(cls, model_name_or_path: str) -> "ModelConfig":
        """Load configuration from pretrained model directory."""
        config_path = Path(model_name_or_path) / "config.json"
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        return cls.from_json_file(str(config_path))
    
    def get_scaled_config(self, scale: float = 1.0) -> "ModelConfig":
        """Get scaled configuration for different model sizes."""
        if scale == 1.0:
            return self
        
        scaled = ModelConfig(
            vocab_size=self.vocab_size,
            hidden_size=int(self.hidden_size * scale),
            num_hidden_layers=int(self.num_hidden_layers * scale),
            num_attention_heads=int(self.num_attention_heads * scale),
            intermediate_size=int(self.intermediate_size * scale),
            max_position_embeddings=self.max_position_embeddings,
            hidden_dropout_prob=self.hidden_dropout_prob,
            attention_probs_dropout_prob=self.attention_probs_dropout_prob,
            layer_norm_eps=self.layer_norm_eps,
            embedding_dropout_prob=self.embedding_dropout_prob,
            use_rotary_position_embeddings=self.use_rotary_position_embeddings,
            rotary_dim=self.rotary_dim,
            attention_dropout_prob=self.attention_dropout_prob,
            use_flash_attention=self.use_flash_attention,
            scale_attn_weights=self.scale_attn_weights,
            scale_attn_by_inverse_layer_idx=self.scale_attn_by_inverse_layer_idx,
            initializer_range=self.initializer_range,
            use_cache=self.use_cache,
            learning_rate=self.learning_rate,
            batch_size=self.batch_size,
            gradient_accumulation_steps=self.gradient_accumulation_steps,
            num_train_epochs=self.num_train_epochs,
            warmup_steps=self.warmup_steps,
            weight_decay=self.weight_decay,
            adam_beta1=self.adam_beta1,
            adam_beta2=self.adam_beta2,
            adam_epsilon=self.adam_epsilon,
            use_constitutional_ai=self.use_constitutional_ai,
            safety_filters=self.safety_filters.copy(),
            max_response_length=self.max_response_length,
            model_size_gb=self.model_size_gb * (scale ** 2),  # Scale quadratically
            training_tflops=self.training_tflops * (scale ** 2),
            mixed_precision=self.mixed_precision,
            model_type=self.model_type,
            architectures=self.architectures.copy(),
            auto_map=self.auto_map.copy()
        )
        
        return scaled


# Predefined configurations for different model sizes
MYTHOS_TINY = ModelConfig(
    hidden_size=256,
    num_hidden_layers=4,
    num_attention_heads=4,
    intermediate_size=1024,
    max_position_embeddings=512
)

MYTHOS_SMALL = ModelConfig(
    hidden_size=512,
    num_hidden_layers=8,
    num_attention_heads=8,
    intermediate_size=2048,
    max_position_embeddings=1024
)

MYTHOS_MEDIUM = ModelConfig(
    hidden_size=1024,
    num_hidden_layers=16,
    num_attention_heads=16,
    intermediate_size=4096,
    max_position_embeddings=2048
)

MYTHOS_LARGE = ModelConfig(
    hidden_size=2048,
    num_hidden_layers=24,
    num_attention_heads=16,
    intermediate_size=8192,
    max_position_embeddings=4096
)

MYTHOS_XL = ModelConfig(
    hidden_size=4096,
    num_hidden_layers=32,
    num_attention_heads=32,
    intermediate_size=16384,
    max_position_embeddings=8192
)

MYTHOS_2X = ModelConfig(
    hidden_size=8192,
    num_hidden_layers=48,
    num_attention_heads=64,
    intermediate_size=32768,
    max_position_embeddings=16384
)


def get_model_config(model_size: str = "xl") -> ModelConfig:
    """Get predefined model configuration by size."""
    configs = {
        "tiny": MYTHOS_TINY,
        "small": MYTHOS_SMALL,
        "medium": MYTHOS_MEDIUM,
        "large": MYTHOS_LARGE,
        "xl": MYTHOS_XL,
        "2x": MYTHOS_2X
    }
    
    if model_size not in configs:
        raise ValueError(f"Unknown model size: {model_size}. Available: {list(configs.keys())}")
    
    return configs[model_size]