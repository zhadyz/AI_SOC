#!/bin/bash
# ============================================================================
# AI-SOC SSL Certificate Generation Script
# ============================================================================
# Generates self-signed certificates for Wazuh components
# Based on: https://documentation.wazuh.com/current/deployment-options/docker/certificates.html
#
# Usage: ./scripts/generate-certs.sh
# Requirements: openssl
# ============================================================================

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}================================${NC}"
echo -e "${GREEN}AI-SOC Certificate Generator${NC}"
echo -e "${GREEN}================================${NC}"

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_DIR="$PROJECT_DIR/config"

# Certificate parameters
DAYS_VALID=3650  # 10 years
COUNTRY="US"
STATE="California"
CITY="Los Angeles"
ORG="AI-SOC"
OU="Security Operations"

echo -e "${YELLOW}[INFO]${NC} Project directory: $PROJECT_DIR"
echo -e "${YELLOW}[INFO]${NC} Config directory: $CONFIG_DIR"
echo -e "${YELLOW}[INFO]${NC} Certificate validity: $DAYS_VALID days (10 years)"

# ============================================================================
# 1. Generate Root CA
# ============================================================================
echo -e "\n${GREEN}[1/5] Generating Root CA...${NC}"

ROOT_CA_DIR="$CONFIG_DIR/root-ca"
mkdir -p "$ROOT_CA_DIR"

if [ ! -f "$ROOT_CA_DIR/root-ca-key.pem" ]; then
    openssl genrsa -out "$ROOT_CA_DIR/root-ca-key.pem" 4096
    openssl req -new -x509 -days $DAYS_VALID -key "$ROOT_CA_DIR/root-ca-key.pem" \
        -out "$ROOT_CA_DIR/root-ca.pem" \
        -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/OU=$OU/CN=AI-SOC Root CA"
    echo -e "${GREEN}[OK]${NC} Root CA generated"
else
    echo -e "${YELLOW}[SKIP]${NC} Root CA already exists"
fi

# ============================================================================
# 2. Generate Wazuh Indexer Certificates
# ============================================================================
echo -e "\n${GREEN}[2/5] Generating Wazuh Indexer certificates...${NC}"

INDEXER_CERT_DIR="$CONFIG_DIR/wazuh-indexer/certs"
mkdir -p "$INDEXER_CERT_DIR"

# Generate indexer private key
if [ ! -f "$INDEXER_CERT_DIR/indexer-key.pem" ]; then
    openssl genrsa -out "$INDEXER_CERT_DIR/indexer-key.pem" 2048

    # Generate CSR
    openssl req -new -key "$INDEXER_CERT_DIR/indexer-key.pem" \
        -out "$INDEXER_CERT_DIR/indexer.csr" \
        -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/OU=$OU/CN=wazuh-indexer"

    # Sign with Root CA
    openssl x509 -req -days $DAYS_VALID \
        -in "$INDEXER_CERT_DIR/indexer.csr" \
        -CA "$ROOT_CA_DIR/root-ca.pem" \
        -CAkey "$ROOT_CA_DIR/root-ca-key.pem" \
        -CAcreateserial \
        -out "$INDEXER_CERT_DIR/indexer.pem"

    # Copy Root CA
    cp "$ROOT_CA_DIR/root-ca.pem" "$INDEXER_CERT_DIR/root-ca.pem"

    # Cleanup CSR
    rm "$INDEXER_CERT_DIR/indexer.csr"

    echo -e "${GREEN}[OK]${NC} Wazuh Indexer certificates generated"
else
    echo -e "${YELLOW}[SKIP]${NC} Wazuh Indexer certificates already exist"
fi

# ============================================================================
# 3. Generate Wazuh Manager / Filebeat Certificates
# ============================================================================
echo -e "\n${GREEN}[3/5] Generating Wazuh Manager certificates...${NC}"

MANAGER_CERT_DIR="$CONFIG_DIR/wazuh-manager/certs"
mkdir -p "$MANAGER_CERT_DIR"

if [ ! -f "$MANAGER_CERT_DIR/filebeat-key.pem" ]; then
    openssl genrsa -out "$MANAGER_CERT_DIR/filebeat-key.pem" 2048

    openssl req -new -key "$MANAGER_CERT_DIR/filebeat-key.pem" \
        -out "$MANAGER_CERT_DIR/filebeat.csr" \
        -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/OU=$OU/CN=wazuh-manager"

    openssl x509 -req -days $DAYS_VALID \
        -in "$MANAGER_CERT_DIR/filebeat.csr" \
        -CA "$ROOT_CA_DIR/root-ca.pem" \
        -CAkey "$ROOT_CA_DIR/root-ca-key.pem" \
        -CAcreateserial \
        -out "$MANAGER_CERT_DIR/filebeat.pem"

    cp "$ROOT_CA_DIR/root-ca.pem" "$MANAGER_CERT_DIR/root-ca.pem"
    rm "$MANAGER_CERT_DIR/filebeat.csr"

    echo -e "${GREEN}[OK]${NC} Wazuh Manager certificates generated"
else
    echo -e "${YELLOW}[SKIP]${NC} Wazuh Manager certificates already exist"
fi

# ============================================================================
# 4. Generate Wazuh Dashboard Certificates
# ============================================================================
echo -e "\n${GREEN}[4/5] Generating Wazuh Dashboard certificates...${NC}"

DASHBOARD_CERT_DIR="$CONFIG_DIR/wazuh-dashboard/certs"
mkdir -p "$DASHBOARD_CERT_DIR"

if [ ! -f "$DASHBOARD_CERT_DIR/dashboard-key.pem" ]; then
    openssl genrsa -out "$DASHBOARD_CERT_DIR/dashboard-key.pem" 2048

    openssl req -new -key "$DASHBOARD_CERT_DIR/dashboard-key.pem" \
        -out "$DASHBOARD_CERT_DIR/dashboard.csr" \
        -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/OU=$OU/CN=wazuh-dashboard"

    openssl x509 -req -days $DAYS_VALID \
        -in "$DASHBOARD_CERT_DIR/dashboard.csr" \
        -CA "$ROOT_CA_DIR/root-ca.pem" \
        -CAkey "$ROOT_CA_DIR/root-ca-key.pem" \
        -CAcreateserial \
        -out "$DASHBOARD_CERT_DIR/dashboard.pem"

    cp "$ROOT_CA_DIR/root-ca.pem" "$DASHBOARD_CERT_DIR/root-ca.pem"
    rm "$DASHBOARD_CERT_DIR/dashboard.csr"

    echo -e "${GREEN}[OK]${NC} Wazuh Dashboard certificates generated"
else
    echo -e "${YELLOW}[SKIP]${NC} Wazuh Dashboard certificates already exist"
fi

# ============================================================================
# 5. Generate Filebeat Certificates
# ============================================================================
echo -e "\n${GREEN}[5/5] Generating Filebeat certificates...${NC}"

FILEBEAT_CERT_DIR="$CONFIG_DIR/filebeat/certs"
mkdir -p "$FILEBEAT_CERT_DIR"

if [ ! -f "$FILEBEAT_CERT_DIR/filebeat-key.pem" ]; then
    openssl genrsa -out "$FILEBEAT_CERT_DIR/filebeat-key.pem" 2048

    openssl req -new -key "$FILEBEAT_CERT_DIR/filebeat-key.pem" \
        -out "$FILEBEAT_CERT_DIR/filebeat.csr" \
        -subj "/C=$COUNTRY/ST=$STATE/L=$CITY/O=$ORG/OU=$OU/CN=filebeat"

    openssl x509 -req -days $DAYS_VALID \
        -in "$FILEBEAT_CERT_DIR/filebeat.csr" \
        -CA "$ROOT_CA_DIR/root-ca.pem" \
        -CAkey "$ROOT_CA_DIR/root-ca-key.pem" \
        -CAcreateserial \
        -out "$FILEBEAT_CERT_DIR/filebeat.pem"

    cp "$ROOT_CA_DIR/root-ca.pem" "$FILEBEAT_CERT_DIR/root-ca.pem"
    rm "$FILEBEAT_CERT_DIR/filebeat.csr"

    echo -e "${GREEN}[OK]${NC} Filebeat certificates generated"
else
    echo -e "${YELLOW}[SKIP]${NC} Filebeat certificates already exist"
fi

# ============================================================================
# Verify and Set Permissions
# ============================================================================
echo -e "\n${GREEN}Setting certificate permissions...${NC}"

# Set secure permissions
chmod 600 "$ROOT_CA_DIR"/*-key.pem 2>/dev/null || true
chmod 644 "$ROOT_CA_DIR"/*.pem 2>/dev/null || true
chmod 600 "$INDEXER_CERT_DIR"/*-key.pem 2>/dev/null || true
chmod 644 "$INDEXER_CERT_DIR"/*.pem 2>/dev/null || true
chmod 600 "$MANAGER_CERT_DIR"/*-key.pem 2>/dev/null || true
chmod 644 "$MANAGER_CERT_DIR"/*.pem 2>/dev/null || true
chmod 600 "$DASHBOARD_CERT_DIR"/*-key.pem 2>/dev/null || true
chmod 644 "$DASHBOARD_CERT_DIR"/*.pem 2>/dev/null || true
chmod 600 "$FILEBEAT_CERT_DIR"/*-key.pem 2>/dev/null || true
chmod 644 "$FILEBEAT_CERT_DIR"/*.pem 2>/dev/null || true

echo -e "${GREEN}[OK]${NC} Permissions set"

# ============================================================================
# Summary
# ============================================================================
echo -e "\n${GREEN}================================${NC}"
echo -e "${GREEN}Certificate Generation Complete!${NC}"
echo -e "${GREEN}================================${NC}"
echo -e "\nGenerated certificates:"
echo -e "  ${GREEN}✓${NC} Root CA"
echo -e "  ${GREEN}✓${NC} Wazuh Indexer"
echo -e "  ${GREEN}✓${NC} Wazuh Manager"
echo -e "  ${GREEN}✓${NC} Wazuh Dashboard"
echo -e "  ${GREEN}✓${NC} Filebeat"
echo -e "\nCertificate validity: ${GREEN}$DAYS_VALID days${NC} (expires: $(date -d "+$DAYS_VALID days" +%Y-%m-%d 2>/dev/null || date -v+${DAYS_VALID}d +%Y-%m-%d 2>/dev/null || echo "N/A"))"
echo -e "\n${YELLOW}IMPORTANT:${NC} These are self-signed certificates for development."
echo -e "For production, use certificates from a trusted CA.\n"
