#!/bin/bash
set -e

# Find a Python 3.11+ interpreter. macOS has no `python` command by default
# (only `python3`), and Apple's built-in python3 may be older than 3.11.
PYTHON=""
for cmd in python3.13 python3.12 python3.11 python3 python; do
    if command -v "$cmd" >/dev/null 2>&1 && \
       "$cmd" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Error: Python 3.11 or newer was not found on your PATH." >&2
    echo "Install Python 3.13 from https://www.python.org/downloads/ or run ./setup-conda.sh instead." >&2
    exit 1
fi

echo "Using $PYTHON ($("$PYTHON" --version))"
"$PYTHON" -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m ipykernel install --user --name=venv --display-name "Python (venv)"
jupyter lab notebooks/1_exploration.ipynb