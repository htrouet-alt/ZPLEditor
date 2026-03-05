#!/bin/bash
# ZPL Visual Editor Launcher

cd "$(dirname "$0")"

# Check if .venv exists
if [ -f ".venv/bin/python" ]; then
    echo "Starting ZPL Visual Editor..."
    .venv/bin/python main.py
    exit 0
fi

# No venv found - create one
echo "Virtual environment not found. Setting up..."
echo

# Check if python3 is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed."
    echo "Install with:"
    echo "  Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
    echo "  Fedora:        sudo dnf install python3 python3-pip"
    echo "  Arch:          sudo pacman -S python python-pip"
    exit 1
fi

echo "Creating virtual environment..."
python3 -m venv .venv
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to create virtual environment."
    echo "You may need: sudo apt install python3-venv"
    exit 1
fi

echo "Installing dependencies..."
.venv/bin/pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies."
    exit 1
fi

echo
echo "Setup complete! Starting ZPL Visual Editor..."
.venv/bin/python main.py
