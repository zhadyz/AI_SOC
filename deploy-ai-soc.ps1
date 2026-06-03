# =============================================================================
# AI-SOC Master Deployment Script (Windows PowerShell)
# =============================================================================
# Single-command deploy for the entire AI-SOC stack.
#
# Usage:
#   .\deploy-ai-soc.ps1           Deploy all services
#   .\deploy-ai-soc.ps1 -Stop     Tear down all services
#   .\deploy-ai-soc.ps1 -Status   Show service status
#
# Phases:
#   1. SIEM Core   (Wazuh indexer, manager, dashboard)
#   2. AI Services (Ollama, ML Inference, Alert Triage, RAG, Wazuh Integration)
#   3. Monitoring  (Prometheus, Grafana, Alertmanager)
# =============================================================================

[CmdletBinding()]
param(
    [switch]$Stop,
    [switch]$Status,
    [switch]$ResetSiemData,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
$ScriptDir     = $PSScriptRoot
$ComposeDir    = Join-Path $ScriptDir "docker-compose"
$ScriptsDir    = Join-Path $ScriptDir "scripts"
$SiemCompose   = Join-Path $ComposeDir "phase1-siem-core-windows.yml"
$AiCompose     = Join-Path $ComposeDir "ai-services.yml"
$MonCompose    = Join-Path $ComposeDir "monitoring-stack.yml"

# Compose project names (overridden from .env by Import-DeployEnv)
$Script:SiemProject   = "ai-soc-siem"
$Script:AiProject     = "ai-soc-ai"
$Script:MonProject    = "ai-soc-monitoring"
$Script:SiemBackendNetwork = "ai-soc-siem-backend"

$Script:EnvRequiredKeys = @(
    'COMPOSE_PROJECT_SIEM',
    'COMPOSE_PROJECT_AI',
    'COMPOSE_PROJECT_MONITORING',
    'SIEM_BACKEND_NETWORK',
    'SIEM_FRONTEND_NETWORK'
)

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------
function Write-Log    { param($Msg) Write-Host "[AI-SOC] $Msg" -ForegroundColor Cyan }
function Write-Ok     { param($Msg) Write-Host "[  OK  ] $Msg" -ForegroundColor Green }
function Write-Warn   { param($Msg) Write-Host "[ WARN ] $Msg" -ForegroundColor Yellow }
function Write-Err    { param($Msg) Write-Host "[ERROR ] $Msg" -ForegroundColor Red }
function Write-Banner { param($Msg) Write-Host "`n=== $Msg ===`n" -ForegroundColor Blue }

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
if ($Help) {
    Write-Host "Usage: .\deploy-ai-soc.ps1 [-Stop] [-Status] [-ResetSiemData] [-Help]"
    Write-Host "  (no flags)        Deploy full AI-SOC stack"
    Write-Host "  -Stop             Tear down all services"
    Write-Host "  -ResetSiemData    With -Stop: remove Wazuh volumes; alone: reset then deploy"
    Write-Host "  -Status           Show running containers"
    Write-Host ""
    Write-Host "Local lab logins (from .env):"
    Write-Host "  Wazuh Dashboard:  admin / AisocIndexer1.dev"
    Write-Host "  Grafana:          admin / AisocGrafana1-dev"
    exit 0
}

# ---------------------------------------------------------------------------
# Tear down
# ---------------------------------------------------------------------------
function Invoke-ComposeDown {
    param(
        [string]$Project,
        [string]$ComposeFile,
        [string]$Label,
        [switch]$RemoveVolumes
    )

    if (-not (Test-Path $ComposeFile)) { return }

    Write-Log $Label
    $downArgs = @('down')
    if ($RemoveVolumes) { $downArgs += '-v' }

    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & docker compose -p $Project -f $ComposeFile @downArgs 2>&1 | Out-Null
    } finally {
        $ErrorActionPreference = $prevEap
    }
}

function Reset-SiemData {
    Write-Banner "Reset SIEM Data (Wazuh volumes)"
    Write-Warn "Deleting Wazuh indexer/manager volumes so passwords in .env take effect."

    $legacyProject = 'docker-compose'
    foreach ($project in @($Script:SiemProject, $legacyProject)) {
        Invoke-ComposeDown -Project $project -ComposeFile $SiemCompose -RemoveVolumes `
            -Label "Removing SIEM stack and volumes (project: $project)..."
    }
    Remove-StaleSiemNetworks
    Write-Ok "SIEM data reset complete."
}

function Get-SiemNetworkNamesToRemove {
    $frontend = if ($env:SIEM_FRONTEND_NETWORK) { $env:SIEM_FRONTEND_NETWORK } else { 'ai-soc-siem-frontend' }
    @(
        'ai-soc-siem_siem-backend',
        'ai-soc-siem_siem-frontend',
        'docker-compose_siem-backend',
        'docker-compose_siem-frontend',
        $Script:SiemBackendNetwork,
        $frontend
    ) | Where-Object { $_ } | Select-Object -Unique
}

function Remove-StaleSiemNetworks {
    Write-Log "Removing leftover SIEM Docker networks..."

    $known = Get-SiemNetworkNamesToRemove
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'

    foreach ($name in $known) {
        $null = docker network rm $name 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "Removed network: $name"
        }
    }

    $listed = docker network ls --format '{{.Name}}' 2>$null |
        Where-Object { $_ -match 'siem' -and $_ -notin $known }
    foreach ($name in $listed) {
        $null = docker network rm $name 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Ok "Removed network: $name"
        }
    }

    $ErrorActionPreference = $prevEap
}

function Invoke-Teardown {
    Write-Banner "Stopping AI-SOC"

    $legacyProject = 'docker-compose'

    foreach ($project in @($Script:MonProject, $legacyProject)) {
        Invoke-ComposeDown -Project $project -ComposeFile $MonCompose `
            -Label "Stopping monitoring stack (project: $project)..."
    }
    foreach ($project in @($Script:AiProject, $legacyProject)) {
        Invoke-ComposeDown -Project $project -ComposeFile $AiCompose `
            -Label "Stopping AI services (project: $project)..."
    }
    foreach ($project in @($Script:SiemProject, $legacyProject)) {
        Invoke-ComposeDown -Project $project -ComposeFile $SiemCompose -RemoveVolumes:$ResetSiemData `
            -Label $(if ($ResetSiemData) {
                "Stopping SIEM core and removing volumes (project: $project)..."
            } else {
                "Stopping SIEM core (project: $project)..."
            })
    }

    Remove-StaleSiemNetworks
    Write-Ok $(if ($ResetSiemData) { "All services stopped; SIEM volumes removed." } else { "All services stopped." })
}

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
function Show-Status {
    Write-Banner "AI-SOC Service Status"
    docker ps --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"
}

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------
function Test-Prerequisites {
    Write-Banner "Checking Prerequisites"

    # Docker
    try {
        $dockerVer = (docker --version) -replace "Docker version ", ""
        Write-Ok "Docker: $dockerVer"
    } catch {
        Write-Err "Docker is not installed. Install from https://docs.docker.com/desktop/windows/"
        exit 1
    }

    # Docker Compose v2
    try {
        $composeVer = docker compose version --short 2>$null
        Write-Ok "Docker Compose: $composeVer"
    } catch {
        Write-Err "Docker Compose v2 not available. Update Docker Desktop."
        exit 1
    }

    # Docker daemon — docker info writes benign warnings to stderr; only exit code matters
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'SilentlyContinue'
    $null = docker info 2>&1
    $daemonRunning = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prevEap
    if (-not $daemonRunning) {
        Write-Err "Docker daemon is not running. Start Docker Desktop and retry."
        exit 1
    }
    Write-Ok "Docker daemon: running"

    # Disk space (warn if <20 GB)
    $drive = (Get-PSDrive -Name ($ScriptDir.Substring(0,1)))[0]
    if ($drive) {
        $freeGb = [math]::Round($drive.Free / 1GB, 1)
        if ($freeGb -lt 20) {
            Write-Warn "Low disk space: ${freeGb}GB free. Recommend at least 20GB."
        } else {
            Write-Ok "Disk space: ${freeGb}GB free"
        }
    }

    # Memory (warn if <8 GB)
    $totalMem = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
    $totalGb  = [math]::Round($totalMem / 1GB, 1)
    if ($totalGb -lt 8) {
        Write-Warn "Low memory: ${totalGb}GB detected. Recommend at least 8GB."
    } else {
        Write-Ok "Memory: ${totalGb}GB"
    }
}

# ---------------------------------------------------------------------------
# SSL certificates
# ---------------------------------------------------------------------------
function Ensure-Certs {
    Write-Banner "SSL Certificates"

    $caCert = Join-Path $ScriptDir "config\root-ca\root-ca.pem"
    if (Test-Path $caCert) {
        Write-Ok "SSL certificates already exist, skipping generation."
        return
    }

    $certScript = Join-Path $ScriptsDir "generate-certs.ps1"
    if (Test-Path $certScript) {
        Write-Log "Generating SSL certificates..."
        & $certScript
        Write-Ok "SSL certificates generated."
    } else {
        Write-Warn "generate-certs.ps1 not found. Skipping certificate generation."
        Write-Warn "Wazuh TLS may fail without certificates."
    }
}

# ---------------------------------------------------------------------------
# .env file
# ---------------------------------------------------------------------------
function Merge-EnvDefaults {
    param(
        [string]$EnvFile,
        [string]$ExampleFile
    )

    if (-not (Test-Path $ExampleFile)) { return }

    $content = Get-Content $EnvFile -Raw -ErrorAction SilentlyContinue
    if (-not $content) { $content = "" }

    $exampleLines = Get-Content $ExampleFile
    foreach ($key in $Script:EnvRequiredKeys) {
        if ($content -match "(?m)^\s*$([regex]::Escape($key))\s*=") { continue }
        $line = $exampleLines | Where-Object { $_ -match "^\s*$([regex]::Escape($key))\s*=" } | Select-Object -First 1
        if ($line) {
            Add-Content -Path $EnvFile -Value $line
            Write-Log "Added missing $key to .env"
        }
    }
}

function Import-DeployEnv {
    $envFile = Join-Path $ScriptDir ".env"
    if (-not (Test-Path $envFile)) { return }

    Get-Content $envFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq '' -or $line.StartsWith('#')) { return }
        if ($line -match '^([^=]+)=(.*)$') {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim().Trim('"').Trim("'")
            Set-Item -Path "Env:$name" -Value $value
        }
    }

    if ($env:COMPOSE_PROJECT_SIEM)        { $Script:SiemProject = $env:COMPOSE_PROJECT_SIEM }
    if ($env:COMPOSE_PROJECT_AI)          { $Script:AiProject = $env:COMPOSE_PROJECT_AI }
    if ($env:COMPOSE_PROJECT_MONITORING)  { $Script:MonProject = $env:COMPOSE_PROJECT_MONITORING }
    if ($env:SIEM_BACKEND_NETWORK)        { $Script:SiemBackendNetwork = $env:SIEM_BACKEND_NETWORK }

    Write-Ok "Deploy config: SIEM project=$($Script:SiemProject), AI project=$($Script:AiProject), SIEM network=$($Script:SiemBackendNetwork)"
}

function Sync-ComposeEnv {
    $envFile = Join-Path $ScriptDir ".env"
    $composeEnv = Join-Path $ComposeDir ".env"
    $composeExample = Join-Path $ComposeDir ".env.example"

    if (Test-Path $envFile) {
        Copy-Item $envFile $composeEnv -Force
        Write-Ok "Synced .env to docker-compose/.env"
        return
    }

    if (Test-Path $composeExample) {
        Copy-Item $composeExample $composeEnv -Force
        Write-Warn "Root .env missing; created docker-compose/.env from docker-compose/.env.example"
    }
}

function Ensure-Env {
    Write-Banner "Environment Configuration"

    $envFile     = Join-Path $ScriptDir ".env"
    $exampleFile = Join-Path $ScriptDir ".env.example"
    $composeExample = Join-Path $ComposeDir ".env.example"

    if (Test-Path $envFile) {
        Write-Ok ".env file exists."
        Merge-EnvDefaults -EnvFile $envFile -ExampleFile $exampleFile
    } elseif (Test-Path $exampleFile) {
        Write-Log "Creating .env from .env.example..."
        Copy-Item $exampleFile $envFile
        Write-Ok ".env created. Review and update credentials if needed."
    } elseif (Test-Path $composeExample) {
        Write-Log "Creating .env from docker-compose/.env.example..."
        Copy-Item $composeExample $envFile
        Write-Ok ".env created from docker-compose/.env.example"
    } else {
        Write-Warn ".env.example not found. Creating minimal .env..."
        @"
# Auto-generated by deploy-ai-soc.ps1
COMPOSE_PROJECT_SIEM=ai-soc-siem
COMPOSE_PROJECT_AI=ai-soc-ai
COMPOSE_PROJECT_MONITORING=ai-soc-monitoring
SIEM_BACKEND_NETWORK=ai-soc-siem-backend
SIEM_FRONTEND_NETWORK=ai-soc-siem-frontend
INDEXER_USERNAME=admin
INDEXER_PASSWORD=AisocIndexer1.dev
API_USERNAME=wazuh-wui
API_PASSWORD=AisocApiUser1-dev
WAZUH_API_PASSWORD=AisocApiUser1-dev
POSTGRES_PASSWORD=aisoc-postgres-dev
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=AisocGrafana1-dev
"@ | Set-Content $envFile
        Write-Ok "Minimal .env created."
    }

    Sync-ComposeEnv
    Import-DeployEnv
}

function Invoke-Compose {
    param(
        [string]$Project,
        [string]$ComposeFile,
        [string[]]$ComposeArgs,
        [switch]$Stream
    )

    $cmdLabel = "docker compose -p $Project -f $ComposeFile $($ComposeArgs -join ' ')"
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'

    $outputLines = [System.Collections.Generic.List[string]]::new()

    if ($Stream) {
        Write-Log "Running (live output): $cmdLabel"
        & docker compose -p $Project -f $ComposeFile @ComposeArgs 2>&1 | ForEach-Object {
            $line = "$_"
            $outputLines.Add($line)
            Write-Host $line
        }
    } else {
        $result = & docker compose -p $Project -f $ComposeFile @ComposeArgs 2>&1
        foreach ($line in $result) {
            $text = "$line"
            $outputLines.Add($text)
            Write-Host $text
        }
    }

    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $prevEap

    if ($exitCode -ne 0) {
        Write-Err "docker compose failed (exit $exitCode): $cmdLabel"
        $text = ($outputLines -join "`n")
        if ($text -match 'Pool overlaps') {
            Write-Warn "Subnet conflict: another Docker network already uses BACKEND_SUBNET/FRONTEND_SUBNET from .env"
            Write-Warn "  docker network ls | findstr siem"
            Write-Warn "  docker network rm <stale-name>   # only when no containers are attached"
            Write-Warn "  Or set BACKEND_SUBNET/FRONTEND_SUBNET in .env (e.g. 172.52.0.0/24 and 172.53.0.0/24), then redeploy"
        }
        if ($text -match 'ollama.*unhealthy|container ollama is unhealthy') {
            Write-Warn "Ollama failed health check. Recent logs:"
            docker logs ollama --tail 30 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkYellow }
            Write-Warn "Retry: docker compose -p ai-soc-ai -f docker-compose/ai-services.yml up -d ollama"
            Write-Warn "Then: docker logs -f ollama"
        }
        if ($text -match 'rag-service.*unhealthy|container rag-service is unhealthy') {
            Write-Warn "RAG service failed health check (first start downloads embedding model; allow ~3 min). Recent logs:"
            docker logs rag-service --tail 40 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkYellow }
            Write-Warn "Retry: docker compose -p ai-soc-ai -f docker-compose/ai-services.yml up -d rag-service wazuh-integration"
        }
        exit $exitCode
    }
}

function Get-ContainerRuntimeStatus {
    param([string]$ContainerName)

    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $exists = docker inspect $ContainerName 2>$null
    if ($LASTEXITCODE -ne 0) {
        $ErrorActionPreference = $prevEap
        return @{ Exists = $false; Status = 'not created'; Health = 'n/a' }
    }

    $status = (docker inspect --format '{{.State.Status}}' $ContainerName 2>$null).Trim()
    $health = (docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' $ContainerName 2>$null).Trim()
    $ErrorActionPreference = $prevEap
    return @{ Exists = $true; Status = $status; Health = $health }
}

function Show-ContainerStatusTable {
    param(
        [string]$PhaseLabel,
        [string[]]$ContainerNames
    )

    Write-Host ""
    Write-Host "--- $PhaseLabel ---" -ForegroundColor DarkCyan
    foreach ($name in $ContainerNames) {
        $info = Get-ContainerRuntimeStatus -ContainerName $name
        if (-not $info.Exists) {
            Write-Host "  $name : not created yet" -ForegroundColor DarkGray
            continue
        }
        $healthSuffix = if ($info.Health -ne 'none') { " (health: $($info.Health))" } else { '' }
        $color = switch ($info.Status) {
            'running' { 'Green' }
            'created' { 'Yellow' }
            'exited'  { 'Red' }
            default   { 'Gray' }
        }
        Write-Host "  $name : $($info.Status)$healthSuffix" -ForegroundColor $color
    }
    Write-Host ""
}

function Watch-StackStartup {
    param(
        [string]$PhaseLabel,
        [string[]]$ContainerNames,
        [string[]]$RequiredHealthy = @(),
        [int]$MaxWaitSecs = 180,
        [int]$IntervalSecs = 5
    )

    Write-Log "Watching $PhaseLabel startup (poll every ${IntervalSecs}s, max ${MaxWaitSecs}s)..."
    $elapsed = 0

    while ($elapsed -lt $MaxWaitSecs) {
        Show-ContainerStatusTable -PhaseLabel "$PhaseLabel @ ${elapsed}s" -ContainerNames $ContainerNames

        $allRequiredOk = $true
        foreach ($required in $RequiredHealthy) {
            $info = Get-ContainerRuntimeStatus -ContainerName $required
            if (-not $info.Exists) {
                $allRequiredOk = $false
                break
            }
            if ($info.Health -ne 'none') {
                if ($info.Health -ne 'healthy') { $allRequiredOk = $false }
            } elseif ($info.Status -ne 'running') {
                $allRequiredOk = $false
            }
        }

        if ($RequiredHealthy.Count -gt 0 -and $allRequiredOk) {
            Write-Ok "$PhaseLabel required containers are healthy/running."
            return $true
        }

        # Fail fast if a required container is explicitly unhealthy or exited
        foreach ($required in $RequiredHealthy) {
            $info = Get-ContainerRuntimeStatus -ContainerName $required
            if ($info.Health -eq 'unhealthy' -or $info.Status -eq 'exited') {
                Write-Warn "$required is $($info.Status) / $($info.Health). Recent logs:"
                docker logs --tail 15 $required 2>&1 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkYellow }
                return $false
            }
        }

        Start-Sleep -Seconds $IntervalSecs
        $elapsed += $IntervalSecs
    }

    Write-Warn "$PhaseLabel did not reach ready state within ${MaxWaitSecs}s."
    return $false
}

function Test-SiemBackendNetwork {
    $networkName = $Script:SiemBackendNetwork
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $null = docker network inspect $networkName 2>&1
    $exists = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prevEap

    if (-not $exists) {
        Write-Err "SIEM backend network '$networkName' not found. Complete Phase 1 (SIEM) before AI services."
        exit 1
    }
    Write-Ok "SIEM backend network '$networkName' is available."
}

# ---------------------------------------------------------------------------
# Wait for container health
# ---------------------------------------------------------------------------
function Wait-ForHealthy {
    param(
        [string]$ContainerName,
        [int]$MaxWaitSecs = 120,
        [int]$IntervalSecs = 10
    )

    Write-Log "Waiting for $ContainerName to become healthy (max ${MaxWaitSecs}s)..."
    $elapsed = 0

    while ($elapsed -lt $MaxWaitSecs) {
        $state = ""
        try {
            $state = (docker inspect --format="{{.State.Health.Status}}" $ContainerName 2>$null).Trim()
        } catch { }

        switch ($state) {
            "healthy" {
                Write-Ok "$ContainerName is healthy."
                return $true
            }
            "unhealthy" {
                Write-Warn "$ContainerName is unhealthy after ${elapsed}s."
                return $false
            }
            "starting" {
                Write-Log "  $ContainerName is starting... (${elapsed}s)"
            }
        }

        Start-Sleep -Seconds $IntervalSecs
        $elapsed += $IntervalSecs
    }

    Write-Warn "$ContainerName did not become healthy within ${MaxWaitSecs}s. Continuing anyway."
    return $true
}

# ---------------------------------------------------------------------------
# Phase 1: SIEM Core
# ---------------------------------------------------------------------------
function Deploy-Siem {
    Write-Banner "Phase 1: SIEM Core"

    if (-not (Test-Path $SiemCompose)) {
        Write-Warn "SIEM compose file not found: $SiemCompose"
        Write-Warn "Skipping SIEM phase."
        return
    }

    $siemContainers = @('wazuh-indexer', 'wazuh-manager', 'wazuh-dashboard')
    Write-Log "SIEM stack: $($siemContainers -join ', ')"
    Write-Log "Compose project: $($Script:SiemProject)"

    Write-Log "Creating/starting SIEM containers (live compose output)..."
    Invoke-Compose -Project $Script:SiemProject -ComposeFile $SiemCompose -ComposeArgs @('up', '-d', '--remove-orphans') -Stream

    $siemReady = Watch-StackStartup -PhaseLabel 'SIEM' -ContainerNames $siemContainers `
        -RequiredHealthy @('wazuh-indexer', 'wazuh-manager', 'wazuh-dashboard') -MaxWaitSecs 300 -IntervalSecs 5

    if (-not $siemReady) {
        Write-Warn "SIEM startup incomplete. Inspect: docker logs wazuh-manager --tail 50"
    }

    Wait-ForHealthy -ContainerName "wazuh-indexer" -MaxWaitSecs 60 -IntervalSecs 5
    Test-SiemBackendNetwork
    Show-ContainerStatusTable -PhaseLabel 'SIEM final' -ContainerNames $siemContainers
    Write-Ok "SIEM core started."
}

# ---------------------------------------------------------------------------
# Phase 2: AI Services
# ---------------------------------------------------------------------------
function Deploy-AIServices {
    Write-Banner "Phase 2: AI Services"

    if (-not (Test-Path $AiCompose)) {
        Write-Err "AI services compose file not found: $AiCompose"
        exit 1
    }

    Test-SiemBackendNetwork

    $aiContainers = @(
        'ollama', 'chromadb', 'ml-inference', 'alert-triage', 'rag-service',
        'wazuh-integration', 'ai-soc-postgres', 'feedback-service',
        'correlation-engine', 'rule-generator', 'response-orchestrator'
    )
    Write-Log "AI stack containers: $($aiContainers -join ', ')"
    Write-Log "Compose project: $($Script:AiProject)"

    Write-Log "Building AI service images (live build output)..."
    Invoke-Compose -Project $Script:AiProject -ComposeFile $AiCompose -ComposeArgs @('build', '--parallel') -Stream

    Write-Log "Starting core AI infrastructure (ollama, chromadb, postgres, ml-inference)..."
    Invoke-Compose -Project $Script:AiProject -ComposeFile $AiCompose -ComposeArgs @(
        'up', '-d', 'ollama', 'chromadb', 'postgres', 'ml-inference'
    ) -Stream

    Write-Log "Waiting for Ollama to become healthy (up to 3 min on first start)..."
    $ollamaOk = Watch-StackStartup -PhaseLabel 'Ollama' -ContainerNames @('ollama') `
        -RequiredHealthy @('ollama') -MaxWaitSecs 180 -IntervalSecs 5
    if (-not $ollamaOk) {
        Write-Warn "Ollama not healthy yet. Logs:"
        docker logs ollama --tail 40 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkYellow }
    }

    Write-Log "Starting remaining AI services (live compose output)..."
    Invoke-Compose -Project $Script:AiProject -ComposeFile $AiCompose -ComposeArgs @('up', '-d', '--remove-orphans') -Stream

    $aiReady = Watch-StackStartup -PhaseLabel 'AI Services' -ContainerNames $aiContainers `
        -RequiredHealthy @('ollama', 'chromadb', 'ml-inference') -MaxWaitSecs 240 -IntervalSecs 5

    if (-not $aiReady) {
        Write-Warn "Some AI containers still starting; continuing with per-service health checks."
    }

    Wait-ForHealthy -ContainerName "ollama" -MaxWaitSecs 120 -IntervalSecs 5
    Pull-OllamaModel

    foreach ($svc in @("chromadb", "ml-inference", "alert-triage", "rag-service", "wazuh-integration")) {
        Wait-ForHealthy -ContainerName $svc -MaxWaitSecs 120 -IntervalSecs 5
    }

    Show-ContainerStatusTable -PhaseLabel 'AI Services final' -ContainerNames $aiContainers
    Write-Ok "AI services started."
}

# ---------------------------------------------------------------------------
# Pull Ollama model
# ---------------------------------------------------------------------------
function Pull-OllamaModel {
    $model = "llama3.2:3b"
    Write-Log "Pulling Ollama model: $model ..."

    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $ollamaRunning = docker ps --filter "name=^ollama$" --filter "status=running" -q
    if (-not $ollamaRunning) {
        Write-Warn "Ollama container is not running. Skipping model pull."
        $ErrorActionPreference = $prevEap
        return
    }

    $existingModels = docker exec ollama ollama list 2>&1
    if ($existingModels -match "llama3.2") {
        Write-Ok "Ollama model $model already present."
        $ErrorActionPreference = $prevEap
        return
    }

    try {
        docker exec ollama ollama pull $model
        Write-Ok "Ollama model $model pulled successfully."
    } catch {
        Write-Warn "Failed to pull Ollama model $model. Alert Triage will use fallback mode."
    } finally {
        $ErrorActionPreference = $prevEap
    }
}

# ---------------------------------------------------------------------------
# Phase 3: Monitoring
# ---------------------------------------------------------------------------
function Deploy-Monitoring {
    Write-Banner "Phase 3: Monitoring Stack"

    if (-not (Test-Path $MonCompose)) {
        Write-Warn "Monitoring compose file not found: $MonCompose"
        Write-Warn "Skipping monitoring phase."
        return
    }

    Write-Log "Starting monitoring stack (project: $($Script:MonProject))..."
    Invoke-Compose -Project $Script:MonProject -ComposeFile $MonCompose -ComposeArgs @('up', '-d', '--remove-orphans')

    Wait-ForHealthy -ContainerName "monitoring-prometheus" -MaxWaitSecs 60
    Write-Ok "Monitoring stack started."
}

# ---------------------------------------------------------------------------
# Knowledge base ingestion
# ---------------------------------------------------------------------------
function Invoke-KBIngestion {
    Write-Banner "Knowledge Base Ingestion"

    $ragUrl  = "http://localhost:8300"
    $maxWait = 60
    $elapsed = 0

    Write-Log "Waiting for RAG service to be ready..."
    while ($elapsed -lt $maxWait) {
        try {
            $r = Invoke-WebRequest -Uri "$ragUrl/health" -TimeoutSec 3 -UseBasicParsing
            if ($r.StatusCode -eq 200) { break }
        } catch { }
        Start-Sleep -Seconds 5
        $elapsed += 5
    }

    try {
        Invoke-RestMethod -Uri "$ragUrl/health" -TimeoutSec 3 -UseBasicParsing | Out-Null

        Write-Log "Triggering MITRE ATT&CK ingestion..."
        try {
            Invoke-RestMethod -Method Post -Uri "$ragUrl/ingest/mitre" -TimeoutSec 10 -UseBasicParsing | Out-Null
            Write-Ok "MITRE ATT&CK ingestion started (runs in background)."
        } catch {
            Write-Warn "MITRE ingestion trigger failed. Retry: Invoke-RestMethod -Method Post -Uri '$ragUrl/ingest/mitre'"
        }

        Write-Log "Triggering security runbook ingestion..."
        try {
            Invoke-RestMethod -Method Post -Uri "$ragUrl/ingest/runbooks" -TimeoutSec 10 -UseBasicParsing | Out-Null
            Write-Ok "Security runbook ingestion started."
        } catch {
            Write-Warn "Runbook ingestion trigger failed."
        }
    } catch {
        Write-Warn "RAG service not reachable after ${maxWait}s. Skipping knowledge base ingestion."
        Write-Warn "Trigger manually: Invoke-RestMethod -Method Post -Uri 'http://localhost:8300/ingest/mitre'"
    }
}

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------
function Invoke-HealthCheck {
    Write-Banner "Health Check Summary"

    $endpoints = @{
        "ML Inference"     = "http://localhost:8500/health"
        "Alert Triage"     = "http://localhost:8100/health"
        "RAG Service"      = "http://localhost:8300/health"
        "Wazuh Integration"= "http://localhost:8002/health"
        "Prometheus"       = "http://localhost:9090/-/healthy"
        "Grafana"          = "http://localhost:3000/api/health"
    }

    $allOk = $true
    foreach ($name in $endpoints.Keys) {
        $url = $endpoints[$name]
        try {
            $r = Invoke-WebRequest -Uri $url -TimeoutSec 5 -UseBasicParsing
            if ($r.StatusCode -eq 200) {
                Write-Ok "${name}: reachable"
            } else {
                Write-Warn "${name}: HTTP $($r.StatusCode)"
                $allOk = $false
            }
        } catch {
            Write-Warn "${name}: not reachable ($url)"
            $allOk = $false
        }
    }

    if ($allOk) {
        Write-Ok "All services healthy."
    } else {
        Write-Warn "Some services not yet reachable. Run '.\deploy-ai-soc.ps1 -Status' to check container states."
    }
}

# ---------------------------------------------------------------------------
# Print access URLs
# ---------------------------------------------------------------------------
function Print-AccessUrls {
    Write-Banner "Access URLs"
    Write-Host ""
    Write-Host "AI Services:" -ForegroundColor White
    Write-Host "  Alert Triage API:    http://localhost:8100/docs" -ForegroundColor Cyan
    Write-Host "  RAG Service API:     http://localhost:8300/docs" -ForegroundColor Cyan
    Write-Host "  ML Inference API:    http://localhost:8500/docs" -ForegroundColor Cyan
    Write-Host "  Wazuh Integration:   http://localhost:8002/docs" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Monitoring:" -ForegroundColor White
    $grafanaPass = if ($env:GRAFANA_ADMIN_PASSWORD) { $env:GRAFANA_ADMIN_PASSWORD } else { 'AisocGrafana1-dev' }
    Write-Host "  Grafana:             http://localhost:3000  (admin/$grafanaPass)" -ForegroundColor Cyan
    Write-Host "  Prometheus:          http://localhost:9090" -ForegroundColor Cyan
    Write-Host "  Alertmanager:        http://localhost:9093" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "SIEM:" -ForegroundColor White
    $indexerPass = if ($env:INDEXER_PASSWORD) { $env:INDEXER_PASSWORD } else { 'AisocIndexer1.dev' }
    Write-Host "  Wazuh Dashboard:     https://localhost:443  (admin/$indexerPass)" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Infrastructure:" -ForegroundColor White
    Write-Host "  Ollama LLM:          http://localhost:11434" -ForegroundColor Cyan
    Write-Host "  ChromaDB:            http://localhost:8200" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "AI-SOC deployment complete." -ForegroundColor Green
    Write-Host "Run '.\deploy-ai-soc.ps1 -Stop' to tear down all services." -ForegroundColor Gray
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=============================================" -ForegroundColor Blue
Write-Host "   AI Security Operations Center" -ForegroundColor Blue
Write-Host "   Master Deployment Script (Windows)" -ForegroundColor Blue
Write-Host "=============================================" -ForegroundColor Blue
Write-Host ""

if ($Stop) {
    if (Test-Path (Join-Path $ScriptDir ".env")) { Import-DeployEnv }
    Invoke-Teardown
} elseif ($ResetSiemData -and -not $Status) {
    Test-Prerequisites
    Ensure-Certs
    Ensure-Env
    Reset-SiemData
    Deploy-Siem
    Deploy-AIServices
    Deploy-Monitoring
    Invoke-KBIngestion
    Invoke-HealthCheck
    Print-AccessUrls
} elseif ($Status) {
    Show-Status
} else {
    Test-Prerequisites
    Ensure-Certs
    Ensure-Env
    Deploy-Siem
    Deploy-AIServices
    Deploy-Monitoring
    Invoke-KBIngestion
    Invoke-HealthCheck
    Print-AccessUrls
}
