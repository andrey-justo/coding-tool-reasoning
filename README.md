# Python Code Reasoning Tools

## Setting up a virtual environment

You can use the provided PowerShell script to set up your environment:

```pwsh
.\setup\setup.ps1
```

This script will:
- Create a virtual environment in `.venv`
- Activate the environment
- Upgrade pip
- Install all dependencies from `requirements.txt`

To activate the environment later, run:
```pwsh
.venv\Scripts\Activate.ps1
```

To deactivate the environment, run:
```pwsh
deactivate
```

## Install PyTorch

### CUDA

pip3 install torch torchvision --index-url https://download.pytorch.org/whl/cu126

### CPU

pip3 install torch torchvision

## Usage

1. Run `python src/main.py`
2. Enter the path to the target code file
3. Enter the path to the migration prompt file

## Structure
- `src/main.py`: Entry point
- `src/migration/`: Migration logic
- `src/utils/`: Utility functions

## Features

This tool reads a target code file and migration prompts, then explains:
- **Why** migration is needed
- **How** migration should be performed
- **Unsafe changes** that may occur