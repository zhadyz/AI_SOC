$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
python scripts/container_stack.py up @args
if ($LASTEXITCODE -ne 0) { throw 'Stack failed; inspect docker compose logs' }
Write-Host 'AI-SOC dashboard: http://localhost:5050'
