#!/usr/bin/env bash
set -euo pipefail

# Setup script (bash) - create virtualenv and install dependencies
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Repository root: $REPO_ROOT"

VENV_DIR="$REPO_ROOT/.venv"

if [ -d "$VENV_DIR" ]; then
  echo "Virtual environment already exists at $VENV_DIR"
else
  echo "Creating virtual environment at $VENV_DIR"
  python3 -m venv "$VENV_DIR"
fi

# Use the venv's pip for installation so system pip is not required
PIP="$VENV_DIR/bin/pip"
"$PIP" install --upgrade pip
"$PIP" install -r "$REPO_ROOT/requirements.txt"

cat <<'EOS'
Virtual environment setup complete.
To activate later (bash / WSL / macOS):
  source .venv/bin/activate
To deactivate:
  deactivate
EOS
