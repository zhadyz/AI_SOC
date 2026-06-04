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
function Write-ErrorMsg { Write-Host $args -ForegroundColor Red }

function Invoke-OpenSsl {
    param([string[]]$OpenSslArgs)

    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & openssl.exe $OpenSslArgs
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    if ($exitCode -ne 0) {
        throw "openssl failed (exit $exitCode): openssl $($OpenSslArgs -join ' ')"
    }
}

function Initialize-OpenSslEnvironment {
    param([string]$ConfigRoot)

    $gitOpenSsl = Join-Path ${env:ProgramFiles} "Git\usr\bin\openssl.exe"
    if (Test-Path $gitOpenSsl) {
        $gitBin = Split-Path $gitOpenSsl -Parent
        $env:Path = "$gitBin;$env:Path"
        Write-Info "[INFO] Using Git OpenSSL: $gitOpenSsl"
    }

    try {
        $null = Get-Command openssl -ErrorAction Stop
    } catch {
        Write-ErrorMsg "[ERROR] OpenSSL not found. Install: winget install OpenSSL.OpenSSL"
        exit 1
    }

    $opensslExe = (Get-Command openssl).Source
    Write-Info "[INFO] OpenSSL: $(openssl version) ($opensslExe)"

    $configCandidates = @(
        (Join-Path ${env:ProgramFiles} "Git\usr\ssl\openssl.cnf"),
        (Join-Path ${env:ProgramFiles(x86)} "Git\usr\ssl\openssl.cnf"),
        (Join-Path (Split-Path $opensslExe -Parent) "..\ssl\openssl.cnf"),
        (Join-Path (Split-Path $opensslExe -Parent) "cnf\openssl.cnf"),
        (Join-Path (Split-Path $opensslExe -Parent) "openssl.cfg"),
        (Join-Path ${env:ProgramFiles} "OpenSSL-Win64\bin\cnf\openssl.cnf"),
        (Join-Path ${env:ProgramFiles} "OpenSSL-Win64\bin\openssl.cfg"),
        (Join-Path $ConfigRoot "openssl.cnf")
    )

    foreach ($candidate in $configCandidates) {
        try {
            $resolved = Resolve-Path $candidate -ErrorAction Stop
            $env:OPENSSL_CONF = $resolved.Path
            Write-Info "[INFO] OPENSSL_CONF=$($env:OPENSSL_CONF)"
            return
        } catch { }
    }

    $minimalConfig = Join-Path $ConfigRoot "openssl.cnf"
    @"
[req]
default_bits = 2048
default_md = sha256
distinguished_name = req_distinguished_name
prompt = no

[req_distinguished_name]
"@ | Set-Content -Path $minimalConfig -Encoding ASCII
    $env:OPENSSL_CONF = $minimalConfig
    Write-Info "[INFO] Created minimal OPENSSL_CONF=$minimalConfig"
}

function Test-CertPairComplete {
    param(
        [string]$KeyPath,
        [string]$CertPath
    )
    return ((Test-Path $KeyPath) -and (Test-Path $CertPath))
}

function Remove-IncompleteCertPair {
    param(
        [string]$KeyPath,
        [string]$CertPath
    )
    if ((Test-Path $KeyPath) -and -not (Test-Path $CertPath)) {
        Write-Info "[INFO] Removing incomplete key: $KeyPath"
        Remove-Item $KeyPath -Force
    }
}

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

Initialize-OpenSslEnvironment -ConfigRoot $ConfigDir

# ============================================================================
# 1. Generate Root CA
# ============================================================================
Write-Host ""
Write-Success "[1/5] Generating Root CA..."

$RootCADir = Join-Path $ConfigDir "root-ca"
New-Item -ItemType Directory -Force -Path $RootCADir | Out-Null

if (-not (Test-CertPairComplete "$RootCADir\root-ca-key.pem" "$RootCADir\root-ca.pem")) {
    if (Test-Path "$RootCADir\root-ca-key.pem") {
        Write-Info "[INFO] Removing incomplete Root CA key (missing root-ca.pem)"
        Remove-Item "$RootCADir\root-ca-key.pem" -Force
    }
    Invoke-OpenSsl @('genrsa', '-out', "$RootCADir\root-ca-key.pem", '4096')
    Invoke-OpenSsl @(
        'req', '-new', '-x509', '-days', "$DaysValid", '-key', "$RootCADir\root-ca-key.pem",
        '-out', "$RootCADir\root-ca.pem", '-batch',
        '-subj', "/C=$Country/ST=$State/L=$City/O=$Org/OU=$OU/CN=AI-SOC_Root_CA"
    )
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

if (-not (Test-CertPairComplete "$IndexerCertDir\indexer-key.pem" "$IndexerCertDir\indexer.pem")) {
    Remove-IncompleteCertPair "$IndexerCertDir\indexer-key.pem" "$IndexerCertDir\indexer.pem"
    Invoke-OpenSsl @('genrsa', '-out', "$IndexerCertDir\indexer-key.pem", '2048')
    Invoke-OpenSsl @(
        'req', '-new', '-key', "$IndexerCertDir\indexer-key.pem",
        '-out', "$IndexerCertDir\indexer.csr", '-batch',
        '-subj', "/C=$Country/ST=$State/L=$City/O=$Org/OU=$OU/CN=wazuh-indexer"
    )
    Invoke-OpenSsl @(
        'x509', '-req', '-days', "$DaysValid", '-in', "$IndexerCertDir\indexer.csr",
        '-CA', "$RootCADir\root-ca.pem", '-CAkey', "$RootCADir\root-ca-key.pem",
        '-CAcreateserial', '-out', "$IndexerCertDir\indexer.pem"
    )
    Copy-Item "$RootCADir\root-ca.pem" "$IndexerCertDir\root-ca.pem"
    Remove-Item "$IndexerCertDir\indexer.csr" -Force -ErrorAction SilentlyContinue
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

if (-not (Test-CertPairComplete "$ManagerCertDir\filebeat-key.pem" "$ManagerCertDir\filebeat.pem")) {
    Remove-IncompleteCertPair "$ManagerCertDir\filebeat-key.pem" "$ManagerCertDir\filebeat.pem"
    Invoke-OpenSsl @('genrsa', '-out', "$ManagerCertDir\filebeat-key.pem", '2048')
    Invoke-OpenSsl @(
        'req', '-new', '-key', "$ManagerCertDir\filebeat-key.pem",
        '-out', "$ManagerCertDir\filebeat.csr", '-batch',
        '-subj', "/C=$Country/ST=$State/L=$City/O=$Org/OU=$OU/CN=wazuh-manager"
    )
    Invoke-OpenSsl @(
        'x509', '-req', '-days', "$DaysValid", '-in', "$ManagerCertDir\filebeat.csr",
        '-CA', "$RootCADir\root-ca.pem", '-CAkey', "$RootCADir\root-ca-key.pem",
        '-CAcreateserial', '-out', "$ManagerCertDir\filebeat.pem"
    )
    Copy-Item "$RootCADir\root-ca.pem" "$ManagerCertDir\root-ca.pem"
    Remove-Item "$ManagerCertDir\filebeat.csr" -Force -ErrorAction SilentlyContinue
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

if (-not (Test-CertPairComplete "$DashboardCertDir\dashboard-key.pem" "$DashboardCertDir\dashboard.pem")) {
    Remove-IncompleteCertPair "$DashboardCertDir\dashboard-key.pem" "$DashboardCertDir\dashboard.pem"
    Invoke-OpenSsl @('genrsa', '-out', "$DashboardCertDir\dashboard-key.pem", '2048')
    Invoke-OpenSsl @(
        'req', '-new', '-key', "$DashboardCertDir\dashboard-key.pem",
        '-out', "$DashboardCertDir\dashboard.csr", '-batch',
        '-subj', "/C=$Country/ST=$State/L=$City/O=$Org/OU=$OU/CN=wazuh-dashboard"
    )
    Invoke-OpenSsl @(
        'x509', '-req', '-days', "$DaysValid", '-in', "$DashboardCertDir\dashboard.csr",
        '-CA', "$RootCADir\root-ca.pem", '-CAkey', "$RootCADir\root-ca-key.pem",
        '-CAcreateserial', '-out', "$DashboardCertDir\dashboard.pem"
    )
    Copy-Item "$RootCADir\root-ca.pem" "$DashboardCertDir\root-ca.pem"
    Remove-Item "$DashboardCertDir\dashboard.csr" -Force -ErrorAction SilentlyContinue
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

if (-not (Test-CertPairComplete "$FilebeatCertDir\filebeat-key.pem" "$FilebeatCertDir\filebeat.pem")) {
    Remove-IncompleteCertPair "$FilebeatCertDir\filebeat-key.pem" "$FilebeatCertDir\filebeat.pem"
    Invoke-OpenSsl @('genrsa', '-out', "$FilebeatCertDir\filebeat-key.pem", '2048')
    Invoke-OpenSsl @(
        'req', '-new', '-key', "$FilebeatCertDir\filebeat-key.pem",
        '-out', "$FilebeatCertDir\filebeat.csr", '-batch',
        '-subj', "/C=$Country/ST=$State/L=$City/O=$Org/OU=$OU/CN=filebeat"
    )
    Invoke-OpenSsl @(
        'x509', '-req', '-days', "$DaysValid", '-in', "$FilebeatCertDir\filebeat.csr",
        '-CA', "$RootCADir\root-ca.pem", '-CAkey', "$RootCADir\root-ca-key.pem",
        '-CAcreateserial', '-out', "$FilebeatCertDir\filebeat.pem"
    )
    Copy-Item "$RootCADir\root-ca.pem" "$FilebeatCertDir\root-ca.pem"
    Remove-Item "$FilebeatCertDir\filebeat.csr" -Force -ErrorAction SilentlyContinue
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
Write-Success "  [OK] Root CA"
Write-Success "  [OK] Wazuh Indexer"
Write-Success "  [OK] Wazuh Manager"
Write-Success "  [OK] Wazuh Dashboard"
Write-Success "  [OK] Filebeat"
Write-Host ""
$ExpiryDate = (Get-Date).AddDays($DaysValid).ToString("yyyy-MM-dd")
Write-Host "Certificate validity: " -NoNewline
Write-Success "$DaysValid days (expires: $ExpiryDate)"
Write-Host ""
Write-Info "IMPORTANT: These are self-signed certificates for development."
Write-Info "For production, use certificates from a trusted CA."
Write-Host ""
