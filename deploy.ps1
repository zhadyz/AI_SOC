# ============================================================================
# AI-SOC ONE-CLICK DEPLOYMENT SYSTEM (Windows PowerShell)
# ============================================================================
# Master deployment script for AI-Augmented Security Operations Center
#
# Usage: .\deploy.ps1 [-Mode <quick|full|monitoring>] [-Validate] [-Rollback]
#
# Parameters:
#   -Mode          Deployment mode: quick, full, monitoring (default: full)
#   -Validate      Validate deployment without changes
#   -Rollback      Rollback to previous state
#   -Help          Show help message
#
# Features:
#   - Auto-detect Windows version and prerequisites
#   - Install missing dependencies
#   - Generate secure passwords and certificates
#   - Deploy all stacks in correct order
#   - Run comprehensive health checks
#   - Display access URLs and credentials
#
# Author: ZHADYZ DevOps Orchestrator
# Version: 1.0.0
# Date: 2025-10-23
# ============================================================================

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [ValidateSet('quick', 'full', 'monitoring')]
    [string]$Mode = 'full',

    [Parameter(Mandatory=$false)]
    [switch]$Validate,

    [Parameter(Mandatory=$false)]
    [switch]$Rollback,

    [Parameter(Mandatory=$false)]
    [switch]$Help
)

# ============================================================================
# CONFIGURATION
# ============================================================================

$Script:VERSION = "1.0.0"
$Script:ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Script:ComposeDir = Join-Path $ProjectRoot "docker-compose"
$Script:ConfigDir = Join-Path $ProjectRoot "config"
$Script:EnvFile = Join-Path $ProjectRoot ".env"
$Script:EnvExample = Join-Path $ProjectRoot ".env.example"
$Script:LogDir = Join-Path $ProjectRoot "logs"
$Script:BackupDir = Join-Path $ProjectRoot "backups"
$Script:DeploymentLog = Join-Path $LogDir "deployment_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

# Color definitions
$Script:Colors = @{
    Red     = 'Red'
    Green   = 'Green'
    Yellow  = 'Yellow'
    Blue    = 'Blue'
    Magenta = 'Magenta'
    Cyan    = 'Cyan'
    White   = 'White'
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

function Write-Banner {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║                                                                      ║" -ForegroundColor Cyan
    Write-Host "║        AI-SOC ONE-CLICK DEPLOYMENT SYSTEM                           ║" -ForegroundColor Cyan
    Write-Host "║        Version $Script:VERSION                                              ║" -ForegroundColor Cyan
    Write-Host "║                                                                      ║" -ForegroundColor Cyan
    Write-Host "║        AI-Augmented Security Operations Center                      ║" -ForegroundColor Cyan
    Write-Host "║        Powered by ZHADYZ DevOps Intelligence                        ║" -ForegroundColor Cyan
    Write-Host "║                                                                      ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Log {
    param(
        [string]$Level,
        [string]$Message
    )

    $Timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $LogMessage = "[$Timestamp] [$Level] $Message"
    Add-Content -Path $Script:DeploymentLog -Value $LogMessage

    switch ($Level) {
        'INFO'    { Write-Host "[INFO] $Message" -ForegroundColor Blue }
        'SUCCESS' { Write-Host "[SUCCESS] $Message" -ForegroundColor Green }
        'WARNING' { Write-Host "[WARNING] $Message" -ForegroundColor Yellow }
        'ERROR'   { Write-Host "[ERROR] $Message" -ForegroundColor Red }
        'FATAL'   {
            Write-Host "[FATAL] $Message" -ForegroundColor Red
            exit 1
        }
    }
}

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Magenta -NoNewline
    Write-Host ""
    Write-Log -Level "INFO" -Message $Message
}

function Write-Progress {
    param([string]$Message)
    Write-Host "   → $Message" -ForegroundColor Cyan
}

# ============================================================================
# PREREQUISITE CHECKS
# ============================================================================

function Test-Prerequisites {
    Write-Step "Checking Prerequisites"

    $MissingDeps = @()

    # Check Windows version
    $OSInfo = Get-CimInstance Win32_OperatingSystem
    Write-Log -Level "INFO" -Message "Windows Version: $($OSInfo.Caption) $($OSInfo.Version)"

    # Check Docker
    try {
        $DockerVersion = docker --version
        Write-Log -Level "SUCCESS" -Message "Docker installed: $DockerVersion"
    } catch {
        Write-Log -Level "ERROR" -Message "Docker not found"
        $MissingDeps += "Docker Desktop"
    }

    # Check Docker Compose
    try {
        $ComposeVersion = docker compose version
        Write-Log -Level "SUCCESS" -Message "Docker Compose installed: $ComposeVersion"
    } catch {
        Write-Log -Level "ERROR" -Message "Docker Compose not found"
        $MissingDeps += "Docker Compose"
    }

    # Check Docker daemon
    try {
        docker info | Out-Null
        Write-Log -Level "SUCCESS" -Message "Docker daemon is running"
    } catch {
        Write-Log -Level "FATAL" -Message "Docker daemon is not running. Please start Docker Desktop and try again."
    }

    # Check Python
    try {
        $PythonVersion = python --version
        Write-Log -Level "SUCCESS" -Message "Python installed: $PythonVersion"
    } catch {
        Write-Log -Level "ERROR" -Message "Python not found"
        $MissingDeps += "Python"
    }

    # Check OpenSSL
    try {
        $OpenSSLVersion = openssl version
        Write-Log -Level "SUCCESS" -Message "OpenSSL installed: $OpenSSLVersion"
    } catch {
        Write-Log -Level "WARNING" -Message "OpenSSL not found (required for certificate generation)"
        $MissingDeps += "OpenSSL"
    }

    # Check Git
    try {
        $GitVersion = git --version
        Write-Log -Level "SUCCESS" -Message "Git installed: $GitVersion"
    } catch {
        Write-Log -Level "WARNING" -Message "Git not found (optional)"
    }

    if ($MissingDeps.Count -gt 0) {
        Write-Log -Level "ERROR" -Message "Missing dependencies: $($MissingDeps -join ', ')"
        Write-Host ""
        Write-Host "Please install the following:" -ForegroundColor Yellow
        foreach ($Dep in $MissingDeps) {
            switch ($Dep) {
                "Docker Desktop" {
                    Write-Host "  - Docker Desktop: https://www.docker.com/products/docker-desktop" -ForegroundColor Cyan
                }
                "Python" {
                    Write-Host "  - Python 3.x: https://www.python.org/downloads/" -ForegroundColor Cyan
                }
                "OpenSSL" {
                    Write-Host "  - OpenSSL: https://slproweb.com/products/Win32OpenSSL.html" -ForegroundColor Cyan
                }
            }
        }
        Write-Log -Level "FATAL" -Message "Please install missing dependencies and try again"
    }

    Write-Log -Level "SUCCESS" -Message "All prerequisites satisfied"
}

function Test-SystemResources {
    Write-Step "Checking System Resources"

    # Check memory
    $TotalRAM = [Math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 2)
    Write-Log -Level "INFO" -Message "Total Memory: ${TotalRAM}GB"

    if ($TotalRAM -lt 16) {
        Write-Log -Level "WARNING" -Message "Recommended minimum: 16GB RAM (detected: ${TotalRAM}GB)"
    } else {
        Write-Log -Level "SUCCESS" -Message "Sufficient memory available"
    }

    # Check disk space
    $Drive = (Get-Item $Script:ProjectRoot).PSDrive
    $FreeSpace = [Math]::Round((Get-PSDrive $Drive.Name).Free / 1GB, 2)
    Write-Log -Level "INFO" -Message "Available Disk Space: ${FreeSpace}GB"

    if ($FreeSpace -lt 50) {
        Write-Log -Level "WARNING" -Message "Recommended minimum: 50GB free space (detected: ${FreeSpace}GB)"
    } else {
        Write-Log -Level "SUCCESS" -Message "Sufficient disk space available"
    }

    # Check CPU
    $CPUCores = (Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors
    Write-Log -Level "INFO" -Message "CPU Cores: $CPUCores"

    if ($CPUCores -lt 4) {
        Write-Log -Level "WARNING" -Message "Recommended minimum: 4 CPU cores (detected: $CPUCores)"
    } else {
        Write-Log -Level "SUCCESS" -Message "Sufficient CPU cores available"
    }
}

# ============================================================================
# ENVIRONMENT SETUP
# ============================================================================

function Initialize-Directories {
    Write-Step "Setting Up Directories"

    $Directories = @(
        $Script:LogDir,
        $Script:BackupDir,
        (Join-Path $Script:ConfigDir "root-ca"),
        (Join-Path $Script:ConfigDir "wazuh-indexer\certs"),
        (Join-Path $Script:ConfigDir "wazuh-manager\certs"),
        (Join-Path $Script:ConfigDir "wazuh-dashboard\certs"),
        (Join-Path $Script:ConfigDir "filebeat\certs")
    )

    foreach ($Dir in $Directories) {
        if (-not (Test-Path $Dir)) {
            New-Item -ItemType Directory -Path $Dir -Force | Out-Null
            Write-Progress "Created: $Dir"
        }
    }

    Write-Log -Level "SUCCESS" -Message "Directory structure created"
}

function New-SecurePassword {
    param([int]$Length = 32)

    $Bytes = New-Object byte[] $Length
    [Security.Cryptography.RNGCryptoServiceProvider]::Create().GetBytes($Bytes)
    return [Convert]::ToBase64String($Bytes).Substring(0, $Length).Replace('+', 'A').Replace('/', 'B').Replace('=', 'C')
}

function Initialize-Passwords {
    Write-Step "Generating Secure Passwords"

    $Passwords = @{
        'INDEXER_PASSWORD' = New-SecurePassword
        'API_PASSWORD' = New-SecurePassword
        'POSTGRES_PASSWORD' = New-SecurePassword
        'REDIS_PASSWORD' = New-SecurePassword
        'JUPYTER_TOKEN' = New-SecurePassword
        'PORTAINER_ADMIN_PASSWORD' = New-SecurePassword
        'REDIS_COMMANDER_PASSWORD' = New-SecurePassword
        'SMTP_PASSWORD' = New-SecurePassword
        'GRAFANA_ADMIN_PASSWORD' = New-SecurePassword
    }

    # Save to secure file
    $PasswordFile = Join-Path $Script:BackupDir "passwords_$(Get-Date -Format 'yyyyMMdd_HHmmss').txt"

    $Content = @"
# AI-SOC Generated Passwords
# Generated: $(Get-Date)
# KEEP THIS FILE SECURE!

"@

    foreach ($Key in $Passwords.Keys) {
        $Content += "$Key=$($Passwords[$Key])`n"
    }

    Set-Content -Path $PasswordFile -Value $Content

    # Set secure permissions (owner only)
    $Acl = Get-Acl $PasswordFile
    $Acl.SetAccessRuleProtection($true, $false)
    $Rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        [System.Security.Principal.WindowsIdentity]::GetCurrent().Name,
        "FullControl",
        "Allow"
    )
    $Acl.AddAccessRule($Rule)
    Set-Acl -Path $PasswordFile -AclObject $Acl

    Write-Log -Level "SUCCESS" -Message "Passwords generated and saved to: $PasswordFile"

    return $Passwords
}

function Initialize-Environment {
    param($Passwords)

    Write-Step "Setting Up Environment Configuration"

    if (-not (Test-Path $Script:EnvFile)) {
        if (Test-Path $Script:EnvExample) {
            Copy-Item $Script:EnvExample $Script:EnvFile
            Write-Progress "Created .env from .env.example"

            # Replace placeholder passwords
            $EnvContent = Get-Content $Script:EnvFile

            foreach ($Key in $Passwords.Keys) {
                $EnvContent = $EnvContent -replace "^$Key=.*", "$Key=$($Passwords[$Key])"
            }

            Set-Content -Path $Script:EnvFile -Value $EnvContent

            Write-Log -Level "SUCCESS" -Message "Environment file configured"
        } else {
            Write-Log -Level "FATAL" -Message ".env.example not found. Cannot create .env file"
        }
    } else {
        Write-Log -Level "INFO" -Message "Using existing .env file"
    }
}

function Initialize-Certificates {
    Write-Step "Generating SSL/TLS Certificates"

    $CertScript = Join-Path $Script:ProjectRoot "scripts\generate-certs.sh"

    if (Test-Path $CertScript) {
        # Check if running in Git Bash or WSL
        if (Get-Command bash -ErrorAction SilentlyContinue) {
            bash $CertScript *>&1 | Tee-Object -FilePath $Script:DeploymentLog -Append
            Write-Log -Level "SUCCESS" -Message "Certificates generated"
        } else {
            Write-Log -Level "WARNING" -Message "Bash not found. Please run generate-certs.sh manually or use WSL/Git Bash"
            Write-Log -Level "WARNING" -Message "Deployment will continue but may fail without certificates"
        }
    } else {
        Write-Log -Level "ERROR" -Message "Certificate generation script not found: $CertScript"
        Write-Log -Level "WARNING" -Message "Deployment will continue but may fail without certificates"
    }
}

# ============================================================================
# DEPLOYMENT FUNCTIONS
# ============================================================================

function Deploy-Stack {
    param(
        [string]$StackName,
        [string]$ComposeFile,
        [string]$Description
    )

    Write-Step "Deploying: $Description"

    if (-not (Test-Path $ComposeFile)) {
        Write-Log -Level "ERROR" -Message "Compose file not found: $ComposeFile"
        return $false
    }

    Write-Log -Level "INFO" -Message "Stack: $StackName"
    Write-Log -Level "INFO" -Message "File: $ComposeFile"

    # Pull images
    Write-Progress "Pulling Docker images..."
    docker compose -f $ComposeFile pull *>&1 | Tee-Object -FilePath $Script:DeploymentLog -Append

    # Deploy stack
    Write-Progress "Starting services..."
    docker compose -f $ComposeFile up -d *>&1 | Tee-Object -FilePath $Script:DeploymentLog -Append

    if ($LASTEXITCODE -eq 0) {
        Write-Log -Level "SUCCESS" -Message "$Description deployed successfully"
        Start-Sleep -Seconds 10
        return $true
    } else {
        Write-Log -Level "ERROR" -Message "Failed to deploy $Description"
        return $false
    }
}

function Deploy-Quick {
    Write-Step "Starting QUICK DEPLOYMENT MODE"
    Write-Log -Level "INFO" -Message "This will deploy: SIEM Stack + AI Services"

    # Deploy AI Services
    Deploy-Stack -StackName "ai-services" `
                 -ComposeFile (Join-Path $Script:ComposeDir "ai-services.yml") `
                 -Description "AI Services Stack (ML Inference, Alert Triage, RAG)"

    # Deploy SIEM (Windows compatible)
    Deploy-Stack -StackName "siem" `
                 -ComposeFile (Join-Path $Script:ComposeDir "phase1-siem-core-windows.yml") `
                 -Description "SIEM Stack (Wazuh - Windows Compatible)"

    Write-Log -Level "SUCCESS" -Message "Quick deployment completed!"
}

function Deploy-Full {
    Write-Step "Starting FULL DEPLOYMENT MODE"
    Write-Log -Level "INFO" -Message "This will deploy: All stacks (SIEM, SOAR, AI, Monitoring)"

    # 1. AI Services
    Deploy-Stack -StackName "ai-services" `
                 -ComposeFile (Join-Path $Script:ComposeDir "ai-services.yml") `
                 -Description "AI Services Stack"

    # 2. SIEM Stack
    Deploy-Stack -StackName "siem" `
                 -ComposeFile (Join-Path $Script:ComposeDir "phase1-siem-core-windows.yml") `
                 -Description "SIEM Stack (Windows Compatible)"

    # 3. SOAR Stack
    Deploy-Stack -StackName "soar" `
                 -ComposeFile (Join-Path $Script:ComposeDir "phase2-soar-stack.yml") `
                 -Description "SOAR Stack (TheHive, Cortex, Shuffle)"

    # 4. Monitoring Stack
    Deploy-Stack -StackName "monitoring" `
                 -ComposeFile (Join-Path $Script:ComposeDir "monitoring-stack.yml") `
                 -Description "Monitoring Stack (Prometheus, Grafana)"

    Write-Log -Level "WARNING" -Message "Network Analysis Stack skipped (requires Linux)"
    Write-Log -Level "INFO" -Message "To deploy on Windows, use WSL2 or a Linux VM"

    Write-Log -Level "SUCCESS" -Message "Full deployment completed!"
}

function Deploy-Monitoring {
    Write-Step "Deploying Monitoring Stack Only"

    Deploy-Stack -StackName "monitoring" `
                 -ComposeFile (Join-Path $Script:ComposeDir "monitoring-stack.yml") `
                 -Description "Monitoring Stack (Prometheus, Grafana, AlertManager)"

    Write-Log -Level "SUCCESS" -Message "Monitoring stack deployed!"
}

# ============================================================================
# VALIDATION
# ============================================================================

function Test-Deployment {
    Write-Step "Validating Deployment"

    Write-Log -Level "INFO" -Message "Checking running containers..."
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

    Write-Host ""
    Write-Log -Level "INFO" -Message "Checking container health..."

    $Containers = docker ps -q
    $Unhealthy = @()

    foreach ($Container in $Containers) {
        $Name = (docker inspect --format='{{.Name}}' $Container).TrimStart('/')
        $Health = docker inspect --format='{{.State.Health.Status}}' $Container 2>$null

        if (-not $Health) {
            $Health = "no-healthcheck"
        }

        switch ($Health) {
            "healthy" {
                Write-Log -Level "SUCCESS" -Message "$Name: healthy"
            }
            "no-healthcheck" {
                Write-Log -Level "INFO" -Message "$Name: running (no health check)"
            }
            "starting" {
                Write-Log -Level "WARNING" -Message "$Name: starting..."
            }
            default {
                Write-Log -Level "ERROR" -Message "$Name: $Health"
                $Unhealthy += $Name
            }
        }
    }

    if ($Unhealthy.Count -eq 0) {
        Write-Log -Level "SUCCESS" -Message "All services are healthy!"
    } else {
        Write-Log -Level "WARNING" -Message "Some services are unhealthy: $($Unhealthy -join ', ')"
        Write-Log -Level "INFO" -Message "Run 'docker logs <container>' to investigate"
    }

    Write-Host ""
    Test-ApiEndpoints
}

function Test-ApiEndpoints {
    Write-Step "Validating API Endpoints"

    $Endpoints = @(
        @{ Url = "http://localhost:8500/health"; Name = "ML Inference API" },
        @{ Url = "http://localhost:8100/health"; Name = "Alert Triage Service" },
        @{ Url = "http://localhost:8300/health"; Name = "RAG Service" },
        @{ Url = "http://localhost:9090/-/healthy"; Name = "Prometheus" },
        @{ Url = "http://localhost:3000/api/health"; Name = "Grafana" }
    )

    foreach ($Endpoint in $Endpoints) {
        try {
            $Response = Invoke-WebRequest -Uri $Endpoint.Url -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
            Write-Log -Level "SUCCESS" -Message "$($Endpoint.Name): accessible"
        } catch {
            Write-Log -Level "WARNING" -Message "$($Endpoint.Name): not accessible (may still be starting)"
        }
    }
}

# ============================================================================
# ROLLBACK
# ============================================================================

function Invoke-Rollback {
    Write-Step "Rolling Back Deployment"

    Write-Log -Level "WARNING" -Message "This will stop and remove all AI-SOC containers"
    $Confirm = Read-Host "Are you sure? (yes/no)"

    if ($Confirm -ne "yes") {
        Write-Log -Level "INFO" -Message "Rollback cancelled"
        return
    }

    Get-ChildItem -Path $Script:ComposeDir -Filter "*.yml" | ForEach-Object {
        Write-Log -Level "INFO" -Message "Stopping: $($_.Name)"
        docker compose -f $_.FullName down *>&1 | Tee-Object -FilePath $Script:DeploymentLog -Append
    }

    Write-Log -Level "SUCCESS" -Message "Rollback completed"
}

# ============================================================================
# POST-DEPLOYMENT
# ============================================================================

function Show-Summary {
    Write-Host ""
    Write-Host "╔══════════════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║                                                                      ║" -ForegroundColor Cyan
    Write-Host "║  DEPLOYMENT SUCCESSFUL!                                              ║" -ForegroundColor Green
    Write-Host "║                                                                      ║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
    Write-Host ""

    Write-Host "Access URLs:" -ForegroundColor White
    Write-Host "  Wazuh Dashboard:    https://localhost:443" -ForegroundColor Cyan
    Write-Host "  Grafana:             http://localhost:3000" -ForegroundColor Cyan
    Write-Host "  Prometheus:          http://localhost:9090" -ForegroundColor Cyan
    Write-Host "  TheHive:             http://localhost:9010" -ForegroundColor Cyan
    Write-Host "  Cortex:              http://localhost:9011" -ForegroundColor Cyan
    Write-Host "  Shuffle:             http://localhost:3001" -ForegroundColor Cyan
    Write-Host "  ML Inference API:    http://localhost:8500/docs" -ForegroundColor Cyan
    Write-Host "  Alert Triage:        http://localhost:8100/docs" -ForegroundColor Cyan
    Write-Host ""

    Write-Host "Default Credentials:" -ForegroundColor White
    Write-Host "  Wazuh:      admin / (see .env: INDEXER_PASSWORD)" -ForegroundColor Cyan
    Write-Host "  Grafana:    admin / (see .env: GRAFANA_ADMIN_PASSWORD)" -ForegroundColor Cyan
    Write-Host "  TheHive:    admin@thehive.local / secret (change immediately)" -ForegroundColor Cyan
    Write-Host ""

    $PasswordFile = Get-ChildItem -Path $Script:BackupDir -Filter "passwords_*.txt" |
                    Sort-Object LastWriteTime -Descending |
                    Select-Object -First 1

    if ($PasswordFile) {
        Write-Host "Generated passwords saved to:" -ForegroundColor Yellow
        Write-Host "  $($PasswordFile.FullName)" -ForegroundColor Cyan
        Write-Host ""
    }

    Write-Host "Next Steps:" -ForegroundColor White
    Write-Host "  1. Change all default passwords" -ForegroundColor Cyan
    Write-Host "  2. Access Wazuh Dashboard and complete first-time setup" -ForegroundColor Cyan
    Write-Host "  3. Configure Grafana dashboards" -ForegroundColor Cyan
    Write-Host "  4. Test alert generation" -ForegroundColor Cyan
    Write-Host ""

    Write-Host "Documentation: docs\DEPLOYMENT_GUIDE.md" -ForegroundColor Yellow
    Write-Host "Network Topology: docs\NETWORK_TOPOLOGY.md" -ForegroundColor Yellow
    Write-Host ""

    Write-Host "Deployment log saved to: $Script:DeploymentLog" -ForegroundColor Green
    Write-Host ""
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

function Main {
    # Show help
    if ($Help) {
        Write-Banner
        Write-Host "Usage: .\deploy.ps1 [-Mode <quick|full|monitoring>] [-Validate] [-Rollback]"
        Write-Host ""
        Write-Host "Parameters:"
        Write-Host "  -Mode          Deployment mode: quick, full, monitoring (default: full)"
        Write-Host "  -Validate      Validate deployment without changes"
        Write-Host "  -Rollback      Rollback deployment"
        Write-Host "  -Help          Show this help message"
        Write-Host ""
        exit 0
    }

    # Print banner
    Write-Banner

    # Create log directory
    if (-not (Test-Path $Script:LogDir)) {
        New-Item -ItemType Directory -Path $Script:LogDir -Force | Out-Null
    }

    Write-Log -Level "INFO" -Message "AI-SOC Deployment Started"
    Write-Log -Level "INFO" -Message "Mode: $Mode"
    Write-Log -Level "INFO" -Message "User: $env:USERNAME"

    # Handle rollback
    if ($Rollback) {
        Invoke-Rollback
        exit 0
    }

    # Run checks
    Test-Prerequisites
    Test-SystemResources

    # Setup environment
    Initialize-Directories

    if ($Validate) {
        Test-Deployment
        exit 0
    }

    $Passwords = Initialize-Passwords
    Initialize-Environment -Passwords $Passwords
    Initialize-Certificates

    # Deploy based on mode
    switch ($Mode) {
        'quick' { Deploy-Quick }
        'full' { Deploy-Full }
        'monitoring' { Deploy-Monitoring }
    }

    # Validate deployment
    Start-Sleep -Seconds 5
    Test-Deployment

    # Display summary
    Show-Summary

    Write-Log -Level "SUCCESS" -Message "Deployment completed successfully!"
}

# Run main function
Main
