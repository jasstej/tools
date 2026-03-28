#!/bin/bash

# Run campp - Social Engineering Demo Tool

set -e

# Activate venv
source venv/bin/activate

# Set ngrok token (replace with your own)
# export NGROK_AUTH_TOKEN="your_token_here"

echo "[*] Starting campp (SecureNote)..."
python3 app.py
