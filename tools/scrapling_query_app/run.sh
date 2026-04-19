#!/bin/bash
# Run script for Scrapling Query Tool

set -e

# Change to script directory
cd "$(dirname "$0")"

echo "Starting Scrapling Query Tool..."
echo ""

# Check if Python is available
if ! command -v python3.10 &> /dev/null; then
    echo "Error: python3.10 is required but not found."
    echo "Please install Python 3.10 or update the script to use your Python version."
    exit 1
fi

# Check if required packages are installed
echo "Checking dependencies..."
if ! python3.10 -c "import fastapi" 2>/dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

# Create data directory if it doesn't exist
mkdir -p data/scrapling_query

# Run the server
echo ""
echo "Starting server on http://127.0.0.1:8051"
echo "Press Ctrl+C to stop"
echo ""
python3.10 -m scrapling_query_app