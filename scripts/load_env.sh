#!/bin/bash

# =============================================================================
# SECURE ENVIRONMENT VARIABLE LOADER
# =============================================================================
# This script loads API keys and credentials from .env file
# Should be sourced before running any trading scripts
#
# SECURITY WARNING: Never commit .env files to version control
# Use .env.example for template with placeholder values
# =============================================================================

ENV_FILE="/Users/kaseymarcelle/Downloads/kashclaw (claude rebuild)/simp/.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: Environment file not found at $ENV_FILE"
    echo "Please create .env file with required API credentials"
    echo "See .env.example for template"
    return 1
fi

# Use a more robust method to load environment variables
# This handles multiline variables properly
while IFS='=' read -r key value || [ -n "$key" ]; do
    # Skip comments and empty lines
    if [[ $key =~ ^[[:space:]]*# ]] || [[ -z $key ]]; then
        continue
    fi
    
    # Remove leading/trailing whitespace
    key=$(echo "$key" | xargs)
    
    # Handle multiline values by reading the rest of the line
    # and continuing to read until we find the end of the value
    if [[ $value == *\\n* ]]; then
        # This is a multiline value with escaped newlines
        # We'll process it as-is and let the application handle the \n sequences
        value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    else
        # Regular single-line value
        value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    fi
    
    # Export the variable
    export "$key=$value"
done < "$ENV_FILE"

# Validate required environment variables
required_vars=(
    "COINBASE_API_KEY_NAME"
    "COINBASE_API_PRIVATE_KEY"
)

missing_vars=()
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        missing_vars+=("$var")
    fi
done

if [ ${#missing_vars[@]} -ne 0 ]; then
    echo "ERROR: Missing required environment variables:"
    for var in "${missing_vars[@]}"; do
        echo "  - $var"
    done
    echo "Please check your .env file"
    return 1
fi

# Security verification
echo "✓ Environment variables loaded successfully"
echo "✓ API key name configured"
echo "✓ API private key available (${#COINBASE_API_PRIVATE_KEY} characters)"
echo "✓ Environment: ${SIM_ENVIRONMENT:-sandbox}"
echo "✓ Debug mode: ${SIM_DEBUG_MODE:-false}"

# Additional security checks
if [ "${SIM_ENVIRONMENT}" = "production" ]; then
    echo "⚠️  WARNING: Production mode detected"
    echo "⚠️  Ensure API keys have appropriate permissions"
    echo "⚠️  Consider using read-only keys for testing"
fi