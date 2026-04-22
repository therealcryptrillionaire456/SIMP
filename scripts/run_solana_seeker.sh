#!/bin/bash

# Solana Seeker Phone Integration - Universal Trading System
# ==========================================================
# This script runs the Solana Seeker integration with full Web3 capabilities

echo "📱 SOLANA SEEKER PHONE INTEGRATION - WEB3 TRADING SYSTEM"
echo "======================================================"
echo ""

# Set up environment
cd "/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp"

# Load environment
if [ -f ".env.solana_seeker" ]; then
    echo "🔐 Loading Solana Seeker environment..."
    source .env.solana_seeker
else
    echo "❌ Solana Seeker environment file not found!"
    echo "Please copy .env.solana_seeker to .env and configure your API credentials"
    exit 1
fi

# Check if required environment variables are set
if [ -z "$SOLANA_SEEKER_API_KEY" ] || [ -z "$SOLANA_WALLET_ADDRESS" ]; then
    echo "❌ Required Solana Seeker API credentials not set!"
    echo "Please configure your .env file with SOLANA_SEEKER_API_KEY and SOLANA_WALLET_ADDRESS"
    exit 1
fi

echo "✅ Environment loaded successfully"
echo "📱 Wallet Address: $SOLANA_WALLET_ADDRESS"
echo "🌐 Trading Mode: $TRADING_MODE"
echo "💰 Position Size: $POSITION_SIZE"
echo "🛡️ Risk Level: $RISK_LEVEL"
echo ""

# Show available features
echo "🚀 AVAILABLE FEATURES:"
echo "   ✅ Solana Native Trading (SOL/USD, SOL/USDC)"
echo "   ✅ Solana Token Trading (RAY, SRM, PYTH, JUP, ORCA, RAYDIUM)"
echo "   ✅ NFT Marketplace Integration (Magic Eden, Tensor, Alpha)"
echo "   ✅ DeFi Yield Farming (Orca, Raydium, Serum, Jupiter)"
echo "   ✅ Token Launch Detection (Raydium, Pump Fun, Jupiter)"
echo "   ✅ On-Chain Analytics (Network Volume, Exchange Flow, Holder Distribution)"
echo "   ✅ Cross-Exchange Arbitrage (Solana Seeker vs Coinbase)"
echo "   ✅ Mobile Push Notifications"
echo "   ✅ Real-Time Market Data"
echo ""

# Run the integration
MODE="${1:-dry-run}"
SEEKER_ARGS=(--config solana_seeker_config.json)

case "$MODE" in
    "dry-run")
        echo "🎯 RUNNING DRY-RUN TEST..."
        SEEKER_ARGS+=(--dry-run --once)
        ;;
    "once")
        if [ "${SOLANA_SEEKER_LIVE:-false}" = "true" ]; then
            echo "🎯 RUNNING LIVE TRADING (ONCE)..."
            SEEKER_ARGS+=(--live --once)
        else
            echo "🎯 RUNNING DRY-RUN (ONCE)... set SOLANA_SEEKER_LIVE=true for live mode"
            SEEKER_ARGS+=(--dry-run --once)
        fi
        ;;
    "daemon")
        if [ "${SOLANA_SEEKER_LIVE:-false}" = "true" ]; then
            echo "🎯 RUNNING LIVE DAEMON MODE..."
            echo "⚠️  This will run continuously with live orders. Press Ctrl+C to stop."
            SEEKER_ARGS+=(--live --daemon)
        else
            echo "🎯 RUNNING DRY-RUN DAEMON MODE..."
            SEEKER_ARGS+=(--dry-run --daemon)
        fi
        ;;
    *)
        echo "❌ Invalid mode: $1"
        echo "Usage: $0 [dry-run|once|daemon]"
        echo ""
        echo "Modes:"
        echo "  dry-run  - Test without real trades (default)"
        echo "  once     - Process signals once and exit"
        echo "  daemon   - Run continuously in background"
        exit 1
        ;;
esac

python3.10 scripts/solana_seeker_integration.py "${SEEKER_ARGS[@]}"

echo ""
echo "✅ SOLANA SEEKER INTEGRATION COMPLETED"
echo "📊 Check logs/solana_seeker.log for detailed output"
echo "📱 Ready to profit from Solana ecosystem!"
