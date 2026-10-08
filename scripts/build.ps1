# Builds dist\Gestecho\Gestecho.exe with PyInstaller.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

python -m pip install --quiet pyinstaller
python -m PyInstaller --noconfirm --clean --windowed --name Gestecho `
    --collect-binaries sounddevice `
    scripts\launcher.py

Write-Host "Built dist\Gestecho\Gestecho.exe"
