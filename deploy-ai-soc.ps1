$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python scripts/configure_local.py
if ($LASTEXITCODE -ne 0) { throw 'Configuration failed' }
docker compose config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose validation failed' }
docker compose up -d --build --wait --wait-timeout 900
if ($LASTEXITCODE -ne 0) { throw 'Stack failed; inspect docker compose logs' }
Write-Host 'AI-SOC dashboard: http://localhost:5050'
