# Python Code Reasoning Tools

## Setting up the Environment

The project includes setup scripts for both PowerShell (Windows) and bash (Unix-like systems) environments.

### Windows (PowerShell)
```pwsh
.\setup\setup.ps1
```

To activate the environment later:
```pwsh
.venv\Scripts\Activate.ps1
```

### Unix-like Systems (bash)
```bash
# Make scripts executable (one-time)
chmod +x ./setup/*.sh

# Run setup
./setup/setup.sh
```

To activate the environment later:
```bash
source .venv/bin/activate
```

To deactivate the environment (both PowerShell and bash):
```shell
deactivate
```

Both setup scripts will:
- Create a virtual environment in `.venv`
- Activate the environment
- Upgrade pip
- Install all dependencies from `requirements.txt`

## Install PyTorch

### CUDA
```shell
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu126
```

### CPU
```shell
pip install torch torchvision
```

## LocalAI: run a local LLM server and connect the project

This project supports LocalAI as an LLM provider. The LocalAI server runs locally (default HTTP port 8080) and the project will use the `API_KEY` from the project's `.env` file when present.

### Quick Start with Docker Compose

Use the provided script to set up models and start the LocalAI server with Docker Compose:

Windows (PowerShell):
```pwsh
.\setup\start_docker_localai.ps1
```

Unix-like systems (bash):
```bash
./setup/start_docker_localai.sh
```

The script will:
1. Create a `models/` directory in the repository root
2. Try to clone the default CodeGen model (`Salesforce/codegen-350M-mono`) from Hugging Face
3. Generate an `API_KEY` in `.env` if one doesn't exist
4. Start the Docker Compose stack

### Manual Setup (without scripts)

1. Generate an API key and create `.env`:
```shell
# Using Python
echo "API_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(16))')" > .env

# Or using openssl
echo "API_KEY=$(openssl rand -hex 16)" > .env
```

2. Start a LocalAI server (basic Docker example):
```bash
# From repo root, build or pull LocalAI image and run
docker run -p 8080:8080 ghcr.io/go-skynet/localai:latest --http-port 8080
```

For full setup and model installation, refer to the LocalAI docs:
- Getting started: https://localai.io/basics/getting_started/
- Models guide: https://localai.io/docs/getting-started/models/

Authentication note: If you want to enable authentication on the LocalAI server, follow LocalAI docs to pass the auth token/flags to the container and use the same token in `.env` (the client will send `Authorization: Bearer <API_KEY>`).

3. available_models.yaml includes a "localai" entry that points to http://localhost:8080. The local client will use that endpoint automatically.

Docker Compose (local development)
----------------------------------

This repository includes a `docker-compose.yml` (project root) and a top-level `Dockerfile` to run the Python app together with a LocalAI container. The LocalAI Dockerfile lives in `docker/localai/Dockerfile` and exposes the default HTTP port 8080.

Notes and recommended workflow:

- The app service uses an environment variable `LOCALAI_ENDPOINT` set to `http://localai:8080` by default so the app can reach the LocalAI service by service name on the Docker network.
- If you want to supply an API key for LocalAI authentication, put it in a `.env` file as `API_KEY=<your-token>` and the Python client will send it as `Authorization: Bearer <API_KEY>`.
- If you plan to provide model binaries to LocalAI, create a `models/` directory in the repo root and it will be mounted into the LocalAI container (`./models:/models`).

Quick commands (from repo root):

```powershell
# Build images and start services
docker-compose up --build

# Run in background
docker-compose up -d --build

# Stop and remove containers
docker-compose down
```

The app container runs `python src/main.py` by default. You can still run the code locally in a virtualenv — the docker setup is optional and intended for local integration testing with LocalAI.

If you prefer to run LocalAI manually (no docker-compose), you can still follow the previous LocalAI `docker run` example above and point the app to the endpoint using `LOCALAI_ENDPOINT=http://localhost:8080` or by updating `available_models.yaml`.

## Usage

1. Run `python src/main.py`
2. Enter the path to the target code file
3. Enter the path to the migration prompt file

## Structure
- `src/main.py`: Entry point
- `src/migration/`: Migration logic
- `src/utils/`: Utility functions
- `src/llm_client/localai_client.py`: LocalAI HTTP client wrapper
- `available_models.yaml`: Model/provider configuration (add LocalAI)

## Features

This tool reads a target code file and migration prompts, then explains:
- **Why** migration is needed
- **How** migration should be performed
- **Unsafe changes** that may occur

Note: For specific LocalAI model selection and model files, consult https://localai.io/basics/getting_started/. The LocalAI container may require additional flags to load model binaries and/or enable authentication.