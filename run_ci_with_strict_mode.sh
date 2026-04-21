#!/bin/bash
# CI test runner with SIMP_STRICT_TESTS=1
# This script runs tests in strict mode to catch bugs that would otherwise go undetected

set -e  # Exit on error

echo "================================================"
echo "SIMP CI Test Runner with STRICT MODE"
echo "================================================"
echo "Running with SIMP_STRICT_TESTS=1"
echo "This will cause tests to FAIL instead of being skipped"
echo "when exceptions occur in test bodies."
echo "================================================"
echo ""

# Set strict mode
export SIMP_STRICT_TESTS=1

# Run packet assertion tests
echo "1. Running packet-API assertion tests..."
echo "   Testing that SmartMeshClient.send() creates packets with:"
echo "   - packet.sender_id != ''"
echo "   - packet.channel != ''"
echo ""
python3.10 -m pytest tests/test_mesh_packet_assertions.py -v --tb=short
echo "✓ Packet assertion tests passed"
echo ""

# Run security layer tests
echo "2. Running mesh security layer tests..."
echo "   Testing cryptography, fastapi, uvicorn dependencies"
echo "   Ensuring security layer is actually exercised"
echo ""
python3.10 -m pytest tests/test_security_layer_basic.py -v --tb=short
echo "✓ Security layer tests passed"
echo ""

# Run strict mode demo
echo "3. Running strict mode demonstration..."
echo "   Showing difference between normal and strict mode"
echo ""
python3.10 -m pytest tests/test_strict_mode_demo.py -v --tb=short
echo "✓ Strict mode demo passed"
echo ""

# Run mesh-related tests
echo "4. Running mesh system tests..."
echo "   Testing core mesh functionality"
echo ""
python3.10 -m pytest tests/test_mesh_simple.py -v --tb=short
echo "✓ Mesh system tests passed"
echo ""

# Run a broader set of tests in strict mode
echo "5. Running critical system tests in strict mode..."
echo "   Testing broker, delivery, and routing"
echo ""
python3.10 -m pytest tests/test_broker_delivery.py tests/test_routing_engine.py -v --tb=short
echo "✓ Critical system tests passed"
echo ""

echo "================================================"
echo "✅ ALL TESTS PASSED IN STRICT MODE"
echo "================================================"
echo ""
echo "Summary:"
echo "- Packet-API assertions are working"
echo "- Security layer dependencies are installed and working"
echo "- Tests fail properly when exceptions occur (strict mode)"
echo "- No bugs are being silently skipped"
echo ""
echo "Recommendation: Use this script in CI to catch bugs early."
echo "Set SIMP_STRICT_TESTS=1 in your CI environment variables."
echo "================================================"