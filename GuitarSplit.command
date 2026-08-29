#!/bin/bash
# Double-click to start GuitarSplit.
cd "$(dirname "$0")" || exit 1

if [ ! -x ./venv/bin/python ]; then
  echo "GuitarSplit is not set up yet."
  echo "Run ./setup.sh once, then use this again."
  read -r -p "Press return to close."
  exit 1
fi

exec ./venv/bin/python app.py
