#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "transformers>=4.36.0",
#     "accelerate>=0.24.0",
#     "huggingface_hub",
# ]
# ///
"""
ProjectX Economic Brain - GGUF Conversion
Converts trained LoRA adapter or full model to GGUF for local deployment.
"""

import os

MODEL_ID = os.getenv("MODEL_ID", "automationkasey/projectx-economic-brain-dpo")
OUTPUT_REPO = os.getenv("OUTPUT_REPO", "automationkasey/projectx-economic-brain-gguf")

print("=" * 60)
print("GGUF Conversion for ProjectX Economic Brain")
print("=" * 60)
print(f"Source: {MODEL_ID}")
print(f"Output: {OUTPUT_REPO}")
print()
print("Note: This script requires llama.cpp/llama-cli installed.")
print("For HF Jobs, use the pre-configured conversion job instead.")
print()
print("To convert locally, run:")
print(f"  huggingface-cli download {MODEL_ID}")
print(f"  llama-cli \\")
print(f"    --model {MODEL_ID} \\")
print(f"    --hf \\")
print(f"    --output {OUTPUT_REPO}-Q4_K_M.gguf \\")
print(f"    --quantize Q4_K_M")
print()
print("Or use ollama import:")
print(f"  ollama create projectx-economic-brain -f {MODEL_ID}")
print("=" * 60)
