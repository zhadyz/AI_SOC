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

# Separate project names so --remove-orphans in one stack does not delete other stacks
$SiemProject   = "ai-soc-siem"
$AiProject     = "ai-soc-ai"
$MonProject    = "ai-soc-monitoring"

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
    Write-Host "Usage: .\deploy-ai-soc.ps1 [-Stop] [-Status] [-Help]"
    Write-Host "  (no flags)  Deploy full AI-SOC stack"
    Write-Host "  -Stop       Tear down all services"
    Write-Host "  -Status     Show running containers"
    exit 0
}

# ---------------------------------------------------------------------------
# Tear down
# ---------------------------------------------------------------------------
function Invoke-ComposeDown {
    param(
        [string]$Project,
        [string]$ComposeFile,
        [string]$Label
    )

    if (-not (Test-Path $ComposeFile)) { return }

    Write-Log $Label
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        # Docker Compose logs warnings to stderr; ignore them during teardown.
        & docker compose -p $Project -f $ComposeFile down 2>&1 | Out-Null
    } finally {
        $ErrorActionPreference = $prevEap
    }
}

function Invoke-Teardown {
    Write-Banner "Stopping AI-SOC"

    $legacyProject = 'docker-compose'

    foreach ($project in @($MonProject, $legacyProject)) {
        Invoke-ComposeDown -Project $project -ComposeFile $MonCompose `
            -Label "Stopping monitoring stack (project: $project)..."
    }
    foreach ($project in @($AiProject, $legacyProject)) {
        Invoke-ComposeDown -Project $project -ComposeFile $AiCompose `
            -Label "Stopping AI services (project: $project)..."
    }
    foreach ($project in @($SiemProject, $legacyProject)) {
        Invoke-ComposeDown -Project $project -ComposeFile $SiemCompose `
            -Label "Stopping SIEM core (project: $project)..."
    }

    Write-Ok "All services stopped."
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
function Ensure-Env {
    Write-Banner "Environment Configuration"

    $envFile     = Join-Path $ScriptDir ".env"
    $exampleFile = Join-Path $ScriptDir ".env.example"

    if (Test-Path $envFile) {
        Write-Ok ".env file exists."
    } elseif (Test-Path $exampleFile) {
        Write-Log "Creating .env from .env.example..."
        Copy-Item $exampleFile $envFile
        Write-Ok ".env created. Review and update credentials if needed."
    } else {
        Write-Warn ".env.example not found. Creating minimal .env..."
        @"
# Auto-generated by deploy-ai-soc.ps1
# Update passwords before production use
INDEXER_USERNAME=admin
INDEXER_PASSWORD=SecurePassword1!
API_PASSWORD=SecurePassword1!
WAZUH_API_PASSWORD=SecurePassword1!
KIBANA_PASSWORD=SecurePassword1!
"@ | Set-Content $envFile
        Write-Ok "Minimal .env created."
    }
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

    Write-Log "Starting SIEM core services..."
    docker compose -p $SiemProject -f $SiemCompose up -d --remove-orphans

    Wait-ForHealthy -ContainerName "wazuh-indexer" -MaxWaitSecs 180
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

    Write-Log "Building AI service images..."
    docker compose -p $AiProject -f $AiCompose build --parallel

    Write-Log "Starting AI services..."
    docker compose -p $AiProject -f $AiCompose up -d --remove-orphans

    Wait-ForHealthy -ContainerName "ollama" -MaxWaitSecs 120
    Pull-OllamaModel

    foreach ($svc in @("chromadb", "ml-inference", "alert-triage", "rag-service")) {
        Wait-ForHealthy -ContainerName $svc -MaxWaitSecs 120
    }

    Write-Ok "AI services started."
}

# ---------------------------------------------------------------------------
# Pull Ollama model
# ---------------------------------------------------------------------------
function Pull-OllamaModel {
    $model = "llama3.2:3b"
    Write-Log "Pulling Ollama model: $model ..."

    $existingModels = docker exec ollama ollama list 2>$null
    if ($existingModels -match "llama3.2") {
        Write-Ok "Ollama model $model already present."
        return
    }

    try {
        docker exec ollama ollama pull $model
        Write-Ok "Ollama model $model pulled successfully."
    } catch {
        Write-Warn "Failed to pull Ollama model $model. Alert Triage will use fallback mode."
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

    Write-Log "Starting monitoring stack..."
    docker compose -p $MonProject -f $MonCompose up -d --remove-orphans

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
    Write-Host "  Grafana:             http://localhost:3000  (admin/admin)" -ForegroundColor Cyan
    Write-Host "  Prometheus:          http://localhost:9090" -ForegroundColor Cyan
    Write-Host "  Alertmanager:        http://localhost:9093" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "SIEM:" -ForegroundColor White
    Write-Host "  Wazuh Dashboard:     https://localhost:443  (admin/SecurePassword1!)" -ForegroundColor Cyan
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
    Invoke-Teardown
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
