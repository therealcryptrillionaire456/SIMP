#!/bin/bash
# 🧪 VERIFY AGENT LIGHTNING BRP INTEGRATION

echo "================================================================"
echo "🧪 VERIFYING AGENT LIGHTNING BRP INTEGRATION"
echo "================================================================"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

BRP_CONFIG="config/brp"
SIGMA_RULES="$BRP_CONFIG/sigma_rules"
PROJECTX_CONFIG="$BRP_CONFIG/projectx_agent_lightning.json"

echo -e "${YELLOW}🔍 Step 1: Check BRP Configuration${NC}"
echo ""

if [ -f "$BRP_CONFIG/config.yaml" ]; then
    echo -e "${GREEN}✅ BRP config file exists${NC}"
    
    # Check for Agent Lightning section
    if grep -q "agent_lightning" "$BRP_CONFIG/config.yaml"; then
        echo -e "${GREEN}✅ Agent Lightning section found in BRP config${NC}"
    else
        echo -e "${RED}❌ Agent Lightning section NOT found in BRP config${NC}"
    fi
else
    echo -e "${RED}❌ BRP config file not found${NC}"
fi

echo ""
echo -e "${YELLOW}🔍 Step 2: Check Sigma Rules${NC}"
echo ""

if [ -d "$SIGMA_RULES" ]; then
    RULE_COUNT=$(find "$SIGMA_RULES" -name "agent_lightning_*.yml" | wc -l)
    echo -e "${GREEN}✅ Sigma rules directory exists${NC}"
    echo -e "${BLUE}📊 Found $RULE_COUNT Agent Lightning Sigma rules${NC}"
    
    if [ $RULE_COUNT -gt 0 ]; then
        echo "   Sample rules:"
        find "$SIGMA_RULES" -name "agent_lightning_*.yml" | head -3 | while read rule; do
            rule_name=$(basename "$rule")
            echo -e "   • $rule_name"
        done
    fi
else
    echo -e "${RED}❌ Sigma rules directory not found${NC}"
fi

echo ""
echo -e "${YELLOW}🔍 Step 3: Check ProjectX Integration${NC}"
echo ""

if [ -f "$PROJECTX_CONFIG" ]; then
    echo -e "${GREEN}✅ ProjectX configuration exists${NC}"
    
    MONITOR_COUNT=$(python3 -c "
import json
try:
    with open('$PROJECTX_CONFIG', 'r') as f:
        data = json.load(f)
    monitors = data.get('agent_lightning_monitors', {}).get('monitors', [])
    print(len(monitors))
except:
    print(0)
")
    
    echo -e "${BLUE}📊 Found $MONITOR_COUNT ProjectX monitors${NC}"
else
    echo -e "${RED}❌ ProjectX configuration not found${NC}"
fi

echo ""
echo -e "${YELLOW}🔍 Step 4: System Integration Status${NC}"
echo ""

echo -e "${BLUE}📋 INTEGRATION SUMMARY:${NC}"
echo "   • BRP Configuration: $( [ -f "$BRP_CONFIG/config.yaml" ] && echo "✅" || echo "❌" )"
echo "   • Sigma Rules: $( [ $RULE_COUNT -gt 0 ] && echo "✅ ($RULE_COUNT rules)" || echo "❌" )"
echo "   • ProjectX Monitors: $( [ -f "$PROJECTX_CONFIG" ] && echo "✅ ($MONITOR_COUNT monitors)" || echo "❌" )"

echo ""
echo -e "${YELLOW}🎯 NEXT STEPS:${NC}"
echo "1. Restart BRP service to load new rules"
echo "2. Test Sigma rules with simulated agent behavior"
echo "3. Integrate ProjectX monitors with ProjectX server"
echo "4. Monitor system for safety rule effectiveness"

echo ""
echo -e "${GREEN}================================================================"
echo "🧪 VERIFICATION COMPLETE"
echo "================================================================"
echo -e "${NC}"
