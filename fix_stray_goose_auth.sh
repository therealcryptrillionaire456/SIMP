#!/bin/bash

# Fix Stray Goose Authentication Error
# This script sets up the environment and starts the proxy server

echo "========================================"
echo "Fixing Stray Goose Authentication Error"
echo "========================================"

# Get the API key from the config file
CONFIG_FILE="$HOME/stray_goose/stray_goose.config.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ ERROR: Config file not found: $CONFIG_FILE"
    exit 1
fi

# Extract API key from config file
API_KEY=$(grep -o '"api_key": *"[^"]*"' "$CONFIG_FILE" | cut -d'"' -f4)
if [ -z "$API_KEY" ]; then
    echo "❌ ERROR: Could not extract API key from config file"
    exit 1
fi

echo "✅ Found API key in config file"
echo ""

# Set the environment variable
echo "Setting X_AI_API_KEY environment variable..."
export X_AI_API_KEY="$API_KEY"
echo "✅ X_AI_API_KEY set to: ${API_KEY:0:10}...${API_KEY: -10}"
echo ""

# Check if proxy is already running
echo "Checking if proxy server is running..."
if curl -s http://localhost:8234/health > /dev/null 2>&1; then
    echo "✅ Proxy server is already running"
else
    echo "🚀 Starting proxy server..."
    cd ~/stray_goose
    python3 zai_proxy.py > /tmp/zai_proxy.log 2>&1 &
    PROXY_PID=$!
    echo $PROXY_PID > /tmp/zai_proxy.pid
    
    # Wait for proxy to start
    echo "⏳ Waiting for proxy to start..."
    sleep 3
    
    if curl -s http://localhost:8234/health > /dev/null 2>&1; then
        echo "✅ Proxy server started successfully (PID: $PROXY_PID)"
        echo "📝 Proxy logs: /tmp/zai_proxy.log"
    else
        echo "❌ Failed to start proxy server"
        echo "Check logs: /tmp/zai_proxy.log"
        cat /tmp/zai_proxy.log | tail -20
        exit 1
    fi
fi

echo ""
echo "========================================"
echo "✅ Setup Complete!"
echo "========================================"
echo ""
echo "To use Stray Goose, run:"
echo "1. cd ~/stray_goose"
echo "2. export X_AI_API_KEY='$API_KEY'"
echo "3. ./start_stray_goose_with_proxy.sh"
echo ""
echo "Or use this one-liner:"
echo "X_AI_API_KEY='$API_KEY' ~/stray_goose/start_stray_goose_with_proxy.sh"
echo ""
echo "The proxy server is now running on http://localhost:8234"
echo "========================================"