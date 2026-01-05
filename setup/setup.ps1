# PowerShell script to set up virtual environment and install dependencies

py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python.exe -m pip install --upgrade pip
pip install poetry
poetry install
Write-Host "Virtual environment setup complete. To activate later, run '.venv\Scripts\Activate.ps1'"