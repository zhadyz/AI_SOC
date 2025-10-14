# ============================================================================
# AI-SOC SSL Certificate Generation Script (PowerShell)
# ============================================================================
# Generates self-signed certificates for Wazuh components
# Windows-compatible version using PowerShell and OpenSSL
#
# Usage: .\scripts\generate-certs.ps1
# Requirements: OpenSSL (install via: winget install OpenSSL.OpenSSL)
# ============================================================================

$ErrorActionPreference = "Stop"

# Color output functions
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Info { Write-Host $args -ForegroundColor Yellow }
function Write-Error { Write-Host $args -ForegroundColor Red }

Write-Success "================================"
Write-Success "AI-SOC Certificate Generator"
Write-Success "================================"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$ConfigDir = Join-Path $ProjectDir "config"

# Certificate parameters
$DaysValid = 3650  # 10 years
$Country = "US"
$State = "California"
$City = "Los_Angeles"
$Org = "AI-SOC"
$OU = "Security_Operations"

Write-Info "[INFO] Project directory: $ProjectDir"
Write-Info "[INFO] Config directory: $ConfigDir"
Write-Info "[INFO] Certificate validity: $DaysValid days (10 years)"

# Check for OpenSSL
try {
    $null = Get-Command openssl -ErrorAction Stop
    Write-Info "[INFO] OpenSSL found: $(openssl version)"
} catch {
    Write-Error "[ERROR] OpenSSL not found. Install it using: winget install OpenSSL.OpenSSL"
    exit 1
}

# ============================================================================
# 1. Generate Root CA
# ============================================================================
Write-Host ""
Write-Success "[1/5] Generating Root CA..."

$RootCADir = Join-Path $ConfigDir "root-ca"
New-Item -ItemType Directory -Force -Path $RootCADir | Out-Null

if (-not (Test-Path "$RootCADir\root-ca-key.pem")) {
    openssl genrsa -out "$RootCADir\root-ca-key.pem" 4096
    openssl req -new -x509 -days $DaysValid -key "$RootCADir\root-ca-key.pem" `
        -out "$RootCADir\root-ca.pem" `
        -subj "/C=$Country/ST=$State/L=$City/O=$Org/OU=$OU/CN=AI-SOC_Root_CA"
    Write-Success "[OK] Root CA generated"
} else {
    Write-Info "[SKIP] Root CA already exists"
}

# ============================================================================
# 2. Generate Wazuh Indexer Certificates
# ============================================================================
Write-Host ""
Write-Success "[2/5] Generating Wazuh Indexer certificates..."

$IndexerCertDir = Join-Path $ConfigDir "wazuh-indexer\certs"
New-Item -ItemType Directory -Force -Path $IndexerCertDir | Out-Null

if (-not (Test-Path "$IndexerCertDir\indexer-key.pem")) {
    openssl genrsa -out "$IndexerCertDir\indexer-key.pem" 2048

    openssl req -new -key "$IndexerCertDir\indexer-key.pem" `
        -out "$IndexerCertDir\indexer.csr" `
        -subj "/C=$Country/ST=$State/L=$City/O=$Org/OU=$OU/CN=wazuh-indexer"

    openssl x509 -req -days $DaysValid `
        -in "$IndexerCertDir\indexer.csr" `
        -CA "$RootCADir\root-ca.pem" `
        -CAkey "$RootCADir\root-ca-key.pem" `
        -CAcreateserial `
        -out "$IndexerCertDir\indexer.pem"

    Copy-Item "$RootCADir\root-ca.pem" "$IndexerCertDir\root-ca.pem"
    Remove-Item "$IndexerCertDir\indexer.csr" -Force

    Write-Success "[OK] Wazuh Indexer certificates generated"
} else {
    Write-Info "[SKIP] Wazuh Indexer certificates already exist"
}

# ============================================================================
# 3. Generate Wazuh Manager / Filebeat Certificates
# ============================================================================
Write-Host ""
Write-Success "[3/5] Generating Wazuh Manager certificates..."

$ManagerCertDir = Join-Path $ConfigDir "wazuh-manager\certs"
New-Item -ItemType Directory -Force -Path $ManagerCertDir | Out-Null

if (-not (Test-Path "$ManagerCertDir\filebeat-key.pem")) {
    openssl genrsa -out "$ManagerCertDir\filebeat-key.pem" 2048

    openssl req -new -key "$ManagerCertDir\filebeat-key.pem" `
        -out "$ManagerCertDir\filebeat.csr" `
        -subj "/C=$Country/ST=$State/L=$City/O=$Org/OU=$OU/CN=wazuh-manager"

    openssl x509 -req -days $DaysValid `
        -in "$ManagerCertDir\filebeat.csr" `
        -CA "$RootCADir\root-ca.pem" `
        -CAkey "$RootCADir\root-ca-key.pem" `
        -CAcreateserial `
        -out "$ManagerCertDir\filebeat.pem"

    Copy-Item "$RootCADir\root-ca.pem" "$ManagerCertDir\root-ca.pem"
    Remove-Item "$ManagerCertDir\filebeat.csr" -Force

    Write-Success "[OK] Wazuh Manager certificates generated"
} else {
    Write-Info "[SKIP] Wazuh Manager certificates already exist"
}

# ============================================================================
# 4. Generate Wazuh Dashboard Certificates
# ============================================================================
Write-Host ""
Write-Success "[4/5] Generating Wazuh Dashboard certificates..."

$DashboardCertDir = Join-Path $ConfigDir "wazuh-dashboard\certs"
New-Item -ItemType Directory -Force -Path $DashboardCertDir | Out-Null

if (-not (Test-Path "$DashboardCertDir\dashboard-key.pem")) {
    openssl genrsa -out "$DashboardCertDir\dashboard-key.pem" 2048

    openssl req -new -key "$DashboardCertDir\dashboard-key.pem" `
        -out "$DashboardCertDir\dashboard.csr" `
        -subj "/C=$Country/ST=$State/L=$City/O=$Org/OU=$OU/CN=wazuh-dashboard"

    openssl x509 -req -days $DaysValid `
        -in "$DashboardCertDir\dashboard.csr" `
        -CA "$RootCADir\root-ca.pem" `
        -CAkey "$RootCADir\root-ca-key.pem" `
        -CAcreateserial `
        -out "$DashboardCertDir\dashboard.pem"

    Copy-Item "$RootCADir\root-ca.pem" "$DashboardCertDir\root-ca.pem"
    Remove-Item "$DashboardCertDir\dashboard.csr" -Force

    Write-Success "[OK] Wazuh Dashboard certificates generated"
} else {
    Write-Info "[SKIP] Wazuh Dashboard certificates already exist"
}

# ============================================================================
# 5. Generate Filebeat Certificates
# ============================================================================
Write-Host ""
Write-Success "[5/5] Generating Filebeat certificates..."

$FilebeatCertDir = Join-Path $ConfigDir "filebeat\certs"
New-Item -ItemType Directory -Force -Path $FilebeatCertDir | Out-Null

if (-not (Test-Path "$FilebeatCertDir\filebeat-key.pem")) {
    openssl genrsa -out "$FilebeatCertDir\filebeat-key.pem" 2048

    openssl req -new -key "$FilebeatCertDir\filebeat-key.pem" `
        -out "$FilebeatCertDir\filebeat.csr" `
        -subj "/C=$Country/ST=$State/L=$City/O=$Org/OU=$OU/CN=filebeat"

    openssl x509 -req -days $DaysValid `
        -in "$FilebeatCertDir\filebeat.csr" `
        -CA "$RootCADir\root-ca.pem" `
        -CAkey "$RootCADir\root-ca-key.pem" `
        -CAcreateserial `
        -out "$FilebeatCertDir\filebeat.pem"

    Copy-Item "$RootCADir\root-ca.pem" "$FilebeatCertDir\root-ca.pem"
    Remove-Item "$FilebeatCertDir\filebeat.csr" -Force

    Write-Success "[OK] Filebeat certificates generated"
} else {
    Write-Info "[SKIP] Filebeat certificates already exist"
}

# ============================================================================
# Summary
# ============================================================================
Write-Host ""
Write-Success "================================"
Write-Success "Certificate Generation Complete!"
Write-Success "================================"
Write-Host ""
Write-Host "Generated certificates:"
Write-Success "  ✓ Root CA"
Write-Success "  ✓ Wazuh Indexer"
Write-Success "  ✓ Wazuh Manager"
Write-Success "  ✓ Wazuh Dashboard"
Write-Success "  ✓ Filebeat"
Write-Host ""
$ExpiryDate = (Get-Date).AddDays($DaysValid).ToString("yyyy-MM-dd")
Write-Host "Certificate validity: " -NoNewline
Write-Success "$DaysValid days (expires: $ExpiryDate)"
Write-Host ""
Write-Info "IMPORTANT: These are self-signed certificates for development."
Write-Info "For production, use certificates from a trusted CA."
Write-Host ""
