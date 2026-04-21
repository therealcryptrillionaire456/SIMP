#!/bin/bash
# Enable TimesFM for QuantumArb integration

set -e

echo "========================================="
echo "ENABLING TIMESFM FOR QUANTUMARB"
echo "========================================="

# Set environment variables
export SIMP_TIMESFM_ENABLED=true
export SIMP_TIMESFM_SHADOW_MODE=true
export SIMP_TIMESFM_CHECKPOINT="google/timesfm-2.0-500m-pytorch"
export SIMP_TIMESFM_CONTEXT_LEN=512
export SIMP_TIMESFM_HORIZON=64

echo "Environment variables set:"
echo "  SIMP_TIMESFM_ENABLED=$SIMP_TIMESFM_ENABLED"
echo "  SIMP_TIMESFM_SHADOW_MODE=$SIMP_TIMESFM_SHADOW_MODE"
echo "  SIMP_TIMESFM_CHECKPOINT=$SIMP_TIMESFM_CHECKPOINT"
echo "  SIMP_TIMESFM_CONTEXT_LEN=$SIMP_TIMESFM_CONTEXT_LEN"
echo "  SIMP_TIMESFM_HORIZON=$SIMP_TIMESFM_HORIZON"

# Run tests to verify TimesFM integration
echo ""
echo "Running TimesFM integration tests..."
cd "$(dirname "$0")"

# Run TimesFM service tests
python3.10 -m pytest tests/test_timesfm_service.py -v --tb=short

# Run TimesFM integration tests
python3.10 -m pytest tests/test_timesfm_integration.py -v --tb=short

# Run QuantumArb integration tests with TimesFM enabled
python3.10 -m pytest tests/test_integration_quantumarb_kashclaw.py -v --tb=short

echo ""
echo "========================================="
echo "TIMESFM ENABLED SUCCESSFULLY"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Restart the broker to pick up TimesFM changes"
echo "2. Test QuantumArb agent with TimesFM forecasts"
echo "3. Monitor TimesFM health via /stats endpoint"
echo "4. When ready, set SIMP_TIMESFM_SHADOW_MODE=false for live forecasts"