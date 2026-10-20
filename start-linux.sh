#!/bin/bash
# Chair Forecast launcher for Linux. Run with: ./start-linux.sh
# First run sets up a private Python environment in .venv (needs internet once).
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3.10 or newer is needed. Install it from https://www.python.org/downloads/ and try again."
  read -r -p "Press Return to close."
  exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Setting up for the first time. This takes a few minutes and only happens once."
  python3 -m venv .venv || { echo "Could not create the environment."; read -r; exit 1; }
fi

if [ ! -f ".venv/.installed" ]; then
  .venv/bin/python -m pip install --upgrade pip >/dev/null
  .venv/bin/python -m pip install -r requirements.txt || { echo "Setup did not finish. Check the internet connection."; read -r; exit 1; }
  touch .venv/.installed
fi

exec .venv/bin/python run.py
