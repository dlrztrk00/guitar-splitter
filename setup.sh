#!/bin/bash
# One-time setup. Run this once, then use GuitarSplit.command from then on.
set -e
cd "$(dirname "$0")"

echo "Checking for Homebrew packages…"
command -v brew >/dev/null || { echo "Install Homebrew first: https://brew.sh"; exit 1; }
brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg
brew list python@3.11 >/dev/null 2>&1 || brew install python@3.11

PY="$(brew --prefix python@3.11)/bin/python3.11"
echo "Creating the environment (this downloads about 800 MB, once)…"
"$PY" -m venv venv
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install --prefer-binary -r requirements.txt

# torch declares these but this code never reaches them. 160 MB saved.
./venv/bin/pip uninstall -y -q sympy networkx 2>/dev/null || true

echo
echo "Done. Double-click GuitarSplit.command to start it."
