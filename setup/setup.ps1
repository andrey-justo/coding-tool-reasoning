# PowerShell script to set up virtual environment and install dependencies

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
Write-Host "Virtual environment setup complete. To activate later, run '.venv\Scripts\Activate.ps1'"