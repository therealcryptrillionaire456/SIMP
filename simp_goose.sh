#!/bin/bash

# SIMP Goose wrapper script
# Run this from the SIMP directory to use DeepSeek

echo "========================================"
echo "Starting SIMP Goose with DeepSeek"
echo "========================================"
echo "Configuration:"
echo "- Provider: deepseek_native"
echo "- Model: deepseek-chat"
echo ""
echo "========================================"
echo "Starting goose session..."
echo "========================================"

# Run goose (will use global config with deepseek_native)
goose
