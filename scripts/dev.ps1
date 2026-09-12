$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
uv run python scripts/dev.py
exit $LASTEXITCODE
