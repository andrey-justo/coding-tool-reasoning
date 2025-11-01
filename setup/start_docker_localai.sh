#!/usr/bin/env bash
set -euo pipefail

# start_docker_localai.sh
# Prepares a models/ directory, optionally clones a Hugging Face model repo
# and starts the docker-compose stack. Follows LocalAI docs guidance:
# https://localai.io/docs/getting-started/models/

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Repository root: $REPO_ROOT"

# Configuration (change as needed)
MODEL_REPO='Salesforce/codegen-350M-mono'
MODEL_NAME="${MODEL_REPO##*/}"
MODELS_DIR="$REPO_ROOT/models"
MODEL_PATH="$MODELS_DIR/$MODEL_NAME"

mkdir -p "$MODELS_DIR"

has_localai_file() {
  local folder="$1"
  if [ ! -d "$folder" ]; then
    return 1
  fi
  # look for common LocalAI-compatible extensions
  if find "$folder" -type f \( -iname "*.gguf" -o -iname "*.ggml" -o -iname "*.bin" -o -iname "*.pt" -o -iname "*.safetensors" \) -print -quit | grep -q .; then
    return 0
  fi
  return 1
}

if [ -d "$MODEL_PATH" ] && has_localai_file "$MODEL_PATH"; then
  echo "Model directory already exists and contains LocalAI-compatible files: $MODEL_PATH"
  echo "Skipping download and conversion."
else
  if command -v git >/dev/null 2>&1; then
    echo "Cloning Hugging Face repo (for model assets/weights): $MODEL_REPO -> $MODEL_PATH"
    if git clone "https://huggingface.co/$MODEL_REPO" "$MODEL_PATH"; then
      echo "Repository cloned to $MODEL_PATH"
    else
      echo "Warning: git clone returned non-zero exit status. The repo may not have downloaded correctly." >&2
    fi

    if has_localai_file "$MODEL_PATH"; then
      echo "Found LocalAI-compatible files in $MODEL_PATH"
    else
      cat <<'EOS'
Warning: No LocalAI-compatible model files were found in the cloned repo.
Common next steps (see LocalAI docs for details):
  - Convert the repository checkpoints to a LocalAI-supported format (ggml/gguf).
  - Download a pre-converted gguf/ggml release if the model author provides one.
Conversion and compatibility guide: https://localai.io/docs/getting-started/models/
EOS
    fi
  else
    cat <<EOF
git is not available on PATH; skipping automatic clone of the Hugging Face repo.
If you want to provide a LocalAI-compatible model, either:
  - Download a pre-converted gguf/ggml model into the './models' folder, or
  - Install git and git-lfs, then run:
      git lfs install && git clone https://huggingface.co/$MODEL_REPO $MODEL_PATH

For more, see: https://localai.io/docs/getting-started/models/
EOF
  fi
fi

# Ensure .env with API_KEY exists
ENV_FILE="$REPO_ROOT/.env"
if [ ! -f "$ENV_FILE" ]; then
  if command -v python3 >/dev/null 2>&1; then
    API_KEY=$(python3 - <<'PY'
import secrets
print(secrets.token_hex(16))
PY
)
  elif command -v openssl >/dev/null 2>&1; then
    API_KEY=$(openssl rand -hex 16)
  else
    # fallback to uuid
    API_KEY=$(cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "$(date +%s)-$RANDOM")
  fi
  echo "API_KEY=$API_KEY" > "$ENV_FILE"
  echo "Created .env with generated API_KEY"
else
  echo ".env already exists; leaving it untouched."
fi

# Start docker-compose (try docker-compose, then 'docker compose')
pushd "$REPO_ROOT" >/dev/null
if command -v docker-compose >/dev/null 2>&1; then
  echo "Starting services with docker-compose..."
  docker-compose up -d --build
else
  echo "docker-compose not found; trying 'docker compose'..."
  if docker compose up -d --build; then
    echo "Services started with 'docker compose'."
  else
    echo "Failed to start compose using 'docker compose'. Ensure Docker is running and 'docker' is in PATH." >&2
  fi
fi
popd >/dev/null

echo "Done. LocalAI should be reachable at http://localhost:8080 (or via service name 'localai' from other containers)."
echo "If the cloned repo does not contain a .gguf/.ggml or other LocalAI-compatible file, follow the LocalAI docs to convert or obtain a compatible model: https://localai.io/docs/getting-started/models/"
