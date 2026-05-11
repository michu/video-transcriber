#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Installing Video Transcriber..."

python3 -m venv venv
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create virtual environment. Make sure Python 3.12 is installed."
    exit 1
fi

venv/bin/python -m pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies."
    exit 1
fi

echo ""
echo "Installation complete. Run ./start.sh to launch the application."