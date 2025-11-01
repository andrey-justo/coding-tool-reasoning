<#
<#
.SYNOPSIS
    Start LocalAI + app using Docker Compose and prepare a default CodeGen model in a way
    that follows LocalAI's model guidance.

.DESCRIPTION
    This script prepares a `models/` directory and tries to help place a model that LocalAI
    can load. It follows the guidance in the LocalAI documentation:
    https://localai.io/docs/getting-started/models/

    The script will:
    - Ensure `models/` exists in the repository root (this directory is mounted into the
      LocalAI container by the docker-compose configuration in the repo)
    - Optionally clone a Hugging Face model repository (default: `Salesforce/codegen-350M-mono`)
      but does NOT assume the cloned files are already in a LocalAI-compatible format
      (ggml/gguf). If the clone doesn't contain compatible model files the script prints
      instructions and links for conversion/downloading compatible artifacts.
    - Create a `.env` with a generated `API_KEY` if one does not exist
    - Start the docker-compose stack (tries `docker-compose` then `docker compose`)

.NOTES
    - Many Hugging Face repositories contain checkpoints in PyTorch/transformers formats that
      must be converted to ggml/gguf to be loadable by LocalAI. The LocalAI docs explain
      conversion options and compatible formats; see:
      https://localai.io/docs/getting-started/models/
    - The script purposefully avoids attempting binary model conversion automatically because
      conversions often require toolchains and user decisions (quantization target, format)
      which are environment-specific. Instead the script will detect whether a LocalAI-
      compatible file exists and, if not, provide clear next steps.

.EXAMPLE
    pwsh .\setup\start_docker_localai.ps1
#>

Set-StrictMode -Version Latest

# resolve repository root (parent of this script folder)
$RepoRoot = (Resolve-Path "$PSScriptRoot\..\").Path
Write-Host "Repository root: $RepoRoot"

# configuration - change these variables if you want a different model
$ModelRepo = 'Salesforce/codegen-350M-mono'    # default HF repo to clone (not guaranteed LocalAI-ready)
$ModelName = ($ModelRepo -split '/')[-1]
$ModelsDir = Join-Path $RepoRoot 'models'
$ModelPath = Join-Path $ModelsDir $ModelName

function New-DirectoryIfMissing($path) {
    if (-not (Test-Path $path)) {
        Write-Host "Creating directory: $path"
        New-Item -ItemType Directory -Path $path | Out-Null
    }
}

New-DirectoryIfMissing $ModelsDir

# helper to detect LocalAI-compatible files in a folder
function Has-LocalAICompatibleFile($folder) {
    if (-not (Test-Path $folder)) { return $false }
    $extensions = @('*.gguf','*.ggml','*.bin','*.pt','*.safetensors')
    foreach ($ext in $extensions) {
        $match = Get-ChildItem -Path $folder -Filter $ext -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($match) { return $true }
    }
    return $false
}

# If model already exists and contains a compatible file, skip clone
$modelExists = Test-Path $ModelPath
if ($modelExists -and (Has-LocalAICompatibleFile $ModelPath)) {
    Write-Host "Model directory already exists and contains LocalAI-compatible files: $ModelPath`nSkipping download and conversion."
} else {
    # Attempt to clone the HF repo for convenience (user may still need to convert)
    $git = Get-Command git -ErrorAction SilentlyContinue
    if ($git) {
        Write-Host "Cloning Hugging Face repo (for model assets/weights): $ModelRepo -> $ModelPath"
        try {
            git clone "https://huggingface.co/$ModelRepo" $ModelPath
            if ($LASTEXITCODE -ne 0) {
                Write-Warning "git clone exited with code $LASTEXITCODE. The repo may not have downloaded correctly."
            } else {
                Write-Host "Repository cloned to $ModelPath"
            }
        } catch {
            Write-Warning "Failed to clone model repository: $_"
        }

        # Re-check for LocalAI-compatible files after clone
        if (Has-LocalAICompatibleFile $ModelPath) {
            Write-Host "Found LocalAI-compatible files in $ModelPath"
        } else {
            Write-Warning "No LocalAI-compatible model files were found in the cloned repo."
            Write-Host "Common next steps (see LocalAI docs for details):"
            Write-Host "  - Convert the repo checkpoints to a LocalAI-supported format (ggml/gguf)."
            Write-Host "  - Download a pre-converted gguf/ggml release if the model author provides one."
            Write-Host "Conversion and compatibility guide: https://localai.io/docs/getting-started/models/"
            Write-Host "Example conversion tools and notes are on the LocalAI docs page."
        }
    } else {
        Write-Warning "git not found in PATH; skipping automatic clone of Hugging Face repo."
        Write-Host "If you want to provide a LocalAI-compatible model, either:"
        Write-Host "  - Download a pre-converted gguf/ggml model into the './models' folder, or"
        Write-Host "  - Install git and git-lfs, then run: git lfs install && git clone https://huggingface.co/$ModelRepo $ModelPath"
        Write-Host "For more, see: https://localai.io/docs/getting-started/models/"
    }
}

# Ensure .env with API_KEY exists
$EnvFile = Join-Path $RepoRoot '.env'
if (-not (Test-Path $EnvFile)) {
    $api = [System.Guid]::NewGuid().ToString('N')
    Write-Host "Creating .env with generated API_KEY"
    "API_KEY=$api" | Out-File -FilePath $EnvFile -Encoding utf8
} else {
    Write-Host ".env already exists; leaving it untouched."
}

# Start docker-compose (try docker-compose, then docker compose)
Push-Location $RepoRoot
try {
    if (Get-Command docker-compose -ErrorAction SilentlyContinue) {
        Write-Host "Starting services with docker-compose..."
        docker-compose up -d --build
    } else {
        Write-Host "docker-compose not found; trying 'docker compose'..."
        $composeResult = & docker compose up -d --build 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Failed to start compose using 'docker compose'. Output:`n$composeResult"
            Write-Host "Make sure Docker Desktop is running and 'docker' is in PATH."
        } else {
            Write-Host "Services started with 'docker compose'."
        }
    }
} finally {
    Pop-Location
}

Write-Host "Done. LocalAI should be reachable at http://localhost:8080 (or via service name 'localai' from other containers)."
Write-Host "Important: if the cloned repo does not contain a .gguf/.ggml or other LocalAI-compatible file, follow the LocalAI docs to convert or obtain a compatible model: https://localai.io/docs/getting-started/models/`n"
