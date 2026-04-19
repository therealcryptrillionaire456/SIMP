#!/bin/bash

echo "=== EMERGENCY: UNSTICKING ALL GEESE ==="
echo "Geese are stuck at interactive prompts. Sending instructions + Enter keys..."
echo ""

# Function to send instruction and Enter key
send_instruction() {
    window=$1
    instruction=$2
    echo "Sending to window $window:"
    echo "  Instruction: $instruction"
    
    # Send the instruction
    tmux send-keys -t flock:$window "$instruction"
    
    # Send Enter key to process it
    tmux send-keys -t flock:$window Enter
    
    echo "  ✅ Instruction + Enter sent"
    echo ""
    sleep 2
}

# Send to each goose
echo "1. Goose #1 (window 2)..."
send_instruction 2 "NEW ASSIGNMENT: TimesFM Integration Hardening. Create integration test suite, enhance QuantumArb risk models with TimesFM predictions, document API patterns. Deliverables: test_timesfm_integration_suite.py, timesfm_api_patterns.md."

echo "2. Goose #2 (window 3)..."
send_instruction 3 "NEW ASSIGNMENT: BullBear Sector Adapters. Create stocks, sports, politics, and real estate adapters. Deliverables: 4 adapter files with tests in bullbear/sectors/."

echo "3. Goose #3 (window 4)..."
send_instruction 4 "NEW ASSIGNMENT: KloutBot Conversational Layer. Build response generator, web interface, integrate with SIMP broker. Deliverables: response_generator.py, web_interface.py."

echo "4. Goose #5 (window 6)..."
send_instruction 6 "NEW ASSIGNMENT: Dashboard Advanced Features. Add P&L tracking, agent health monitoring, TimesFM visualization, alert system. Deliverables: enhanced dashboard panels."

echo "5. Goose #6 (window 7)..."
send_instruction 7 "NEW ASSIGNMENT: FinancialOps Enhancements. Add Stripe integration tests, budget forecasting, multi-currency support. Deliverables: stripe_integration_tests.py, budget_forecaster.py."

echo "6. Goose #7 (window 8)..."
send_instruction 8 "CONTINUE + NEW: Complete A2A safety scenario catalog AND create mapping guide for A2A Core Schema (Goose #4's work). Deliverables: a2a_safety_scenario_catalog.md, a2a_core_schema_mapping.md."

echo "7. Goose #8 (window 9)..."
send_instruction 9 "CONTINUE: System Integration & Documentation. Create unified glossary, update all docs, build integration status tracker. Deliverables: system_glossary.md, updated documentation."

echo ""
echo "=== CHECKING IF GEESE STARTED MOVING ==="
echo "Waiting 10 seconds for geese to process instructions..."
sleep 10

echo ""
echo "Current status from watcher:"
cat ~/goose-monitor/status_board.txt | tail -20

echo ""
echo "=== EXPECTED NEXT ==="
echo "Geese should now show:"
echo "- CHECK-IN with new assignment details"
echo "- Progress bars moving"
echo "- New work being done"
echo ""
echo "If still stuck, the goose processes may be dead and need restarting."