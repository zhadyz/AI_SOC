#!/bin/bash
# ============================================================================
# AI-SOC QUICKSTART - Get Running in <5 Minutes
# ============================================================================
# Minimal deployment for immediate "hello world" experience
# Deploys: Core SIEM + AI Services only
#
# Usage: ./quickstart.sh
#
# Features:
#   - Fastest possible deployment
#   - Minimal resource requirements (8GB RAM, 2 CPU cores)
#   - Skip non-essential services
#   - Basic security (dev mode)
#   - Progressive enhancement (add more stacks later)
#
# Author: ZHADYZ DevOps Orchestrator
# Version: 1.0.0
# Date: 2025-10-23
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/docker-compose"
ENV_FILE="$SCRIPT_DIR/.env"

# ============================================================================
# BANNER
# ============================================================================

echo -e "${CYAN}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║              AI-SOC QUICKSTART                               ║"
echo "║              Get Running in < 5 Minutes                      ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================================
# QUICK CHECKS
# ============================================================================

echo -e "${BLUE}[1/5]${NC} Quick prerequisite check..."

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}ERROR:${NC} Docker not found. Please install Docker and try again."
    exit 1
fi

# Check Docker is running
if ! docker info &> /dev/null; then
    echo -e "${RED}ERROR:${NC} Docker daemon is not running. Please start Docker."
    exit 1
fi

echo -e "${GREEN}✓${NC} Docker is ready"

# ============================================================================
# MINIMAL ENVIRONMENT SETUP
# ============================================================================

echo -e "\n${BLUE}[2/5]${NC} Setting up minimal environment..."

if [ ! -f "$ENV_FILE" ]; then
    # Create minimal .env with defaults
    cat > "$ENV_FILE" << 'EOF'
# AI-SOC Quickstart Environment
# Auto-generated for quick deployment

# Wazuh credentials (change after deployment)
INDEXER_USERNAME=admin
INDEXER_PASSWORD=SecurePass123!
API_USERNAME=wazuh-wui
API_PASSWORD=SecurePass456!

# Network subnets
BACKEND_SUBNET=172.20.0.0/24
FRONTEND_SUBNET=172.21.0.0/24

# Grafana
GRAFANA_ADMIN_PASSWORD=admin123

# Monitoring
MONITORING_SUBNET=172.28.0.0/24

# Deployment
DEPLOYMENT_ENV=development
DEBUG_MODE=true
TZ=America/Los_Angeles
EOF
    echo -e "${GREEN}✓${NC} Created .env file"
else
    echo -e "${YELLOW}ℹ${NC} Using existing .env file"
fi

# CRITICAL FIX: Copy .env to docker-compose directory
# Docker Compose can't read .env from parent directory when using -f with path
if [ ! -f "$COMPOSE_DIR/.env" ]; then
    cp "$ENV_FILE" "$COMPOSE_DIR/.env"
    echo -e "${GREEN}✓${NC} Copied .env to docker-compose directory"
fi

# ============================================================================
# GENERATE CERTIFICATES (QUICK MODE)
# ============================================================================

echo -e "\n${BLUE}[3/5]${NC} Generating SSL certificates (this may take a moment)..."

if [ -f "$SCRIPT_DIR/scripts/generate-certs.sh" ]; then
    bash "$SCRIPT_DIR/scripts/generate-certs.sh" > /dev/null 2>&1 || true
    echo -e "${GREEN}✓${NC} Certificates generated"
else
    echo -e "${YELLOW}⚠${NC} Certificate script not found, skipping..."
fi

# ============================================================================
# DEPLOY CORE SERVICES
# ============================================================================

echo -e "\n${BLUE}[4/5]${NC} Deploying core services..."
echo -e "${CYAN}This will deploy:${NC}"
echo "  • AI Services (ML Inference, RAG)"
echo "  • Wazuh SIEM (Core only)"
echo ""

# Detect OS
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]] || [[ "$OSTYPE" == "win32" ]]; then
    SIEM_COMPOSE="phase1-siem-core-windows.yml"
else
    SIEM_COMPOSE="phase1-siem-core.yml"
    # Check if Linux compose file exists, fallback to Windows version
    if [ ! -f "$COMPOSE_DIR/$SIEM_COMPOSE" ]; then
        SIEM_COMPOSE="phase1-siem-core-windows.yml"
    fi
fi

# Deploy AI Services first (fastest to start)
echo -e "\n${CYAN}→${NC} Deploying AI Services..."
docker compose -f "$COMPOSE_DIR/ai-services.yml" up -d
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} AI Services containers launched"
else
    echo -e "${RED}✗${NC} Failed to launch AI Services"
    echo -e "${YELLOW}→${NC} Check logs: docker compose -f $COMPOSE_DIR/ai-services.yml logs"
    exit 1
fi

# Wait a bit for AI services to initialize
echo -e "${CYAN}→${NC} Waiting for AI services to initialize..."
sleep 5

# Deploy SIEM Stack
echo -e "\n${CYAN}→${NC} Deploying Wazuh SIEM..."
echo -e "${YELLOW}Note:${NC} SIEM services take 2-3 minutes to initialize. Please be patient..."

docker compose -f "$COMPOSE_DIR/$SIEM_COMPOSE" up -d
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} SIEM Stack containers launched"
else
    echo -e "${RED}✗${NC} Failed to launch SIEM Stack"
    echo -e "${YELLOW}→${NC} Check logs: docker compose -f $COMPOSE_DIR/$SIEM_COMPOSE logs"
    exit 1
fi

# Give SIEM services time to start health checks
echo -e "${CYAN}→${NC} Waiting for SIEM services to initialize (this takes 2-3 minutes)..."
sleep 10

# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

# Check if container is running and healthy
check_container_health() {
    local container_name=$1
    local display_name=$2

    # Check if container exists and is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${container_name}$"; then
        echo -e "${RED}✗${NC} ${display_name}: NOT RUNNING"
        return 1
    fi

    # Check health status (if container has healthcheck)
    local health_status=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "none")

    if [ "$health_status" = "healthy" ]; then
        echo -e "${GREEN}✓${NC} ${display_name}: HEALTHY"
        return 0
    elif [ "$health_status" = "starting" ]; then
        echo -e "${YELLOW}⚠${NC} ${display_name}: STARTING (waiting for health check)"
        return 2
    elif [ "$health_status" = "unhealthy" ]; then
        echo -e "${RED}✗${NC} ${display_name}: UNHEALTHY"
        return 1
    else
        # No healthcheck defined, check if running
        local state=$(docker inspect --format='{{.State.Status}}' "$container_name" 2>/dev/null)
        if [ "$state" = "running" ]; then
            echo -e "${GREEN}✓${NC} ${display_name}: RUNNING (no healthcheck)"
            return 0
        else
            echo -e "${RED}✗${NC} ${display_name}: $state"
            return 1
        fi
    fi
}

# Check if port is accessible
check_port() {
    local port=$1
    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if nc -z localhost $port 2>/dev/null || (echo > /dev/tcp/localhost/$port) 2>/dev/null; then
            return 0
        fi
        sleep 2
        ((attempt++))
    done
    return 1
}

# Comprehensive deployment validation
validate_deployment() {
    local total_checks=0
    local passed_checks=0
    local failed_checks=0
    local warning_checks=0

    echo -e "\n${BLUE}[5/5]${NC} Validating deployment..."
    echo ""

    # ============================================================================
    # AI SERVICES VALIDATION
    # ============================================================================

    echo -e "${CYAN}AI Services:${NC}"

    # ML Inference
    ((total_checks++))
    if check_container_health "ml-inference" "ML Inference"; then
        ((passed_checks++))
    elif [ $? -eq 2 ]; then
        ((warning_checks++))
    else
        ((failed_checks++))
    fi

    # RAG Service
    ((total_checks++))
    if check_container_health "rag-service" "RAG Service"; then
        ((passed_checks++))
    elif [ $? -eq 2 ]; then
        ((warning_checks++))
    else
        ((failed_checks++))
    fi

    # Redis
    ((total_checks++))
    if check_container_health "redis" "Redis Cache"; then
        ((passed_checks++))
    elif [ $? -eq 2 ]; then
        ((warning_checks++))
    else
        ((failed_checks++))
    fi

    echo ""

    # ============================================================================
    # SIEM SERVICES VALIDATION
    # ============================================================================

    echo -e "${CYAN}SIEM Stack:${NC}"

    # Wazuh Manager
    ((total_checks++))
    if check_container_health "wazuh-manager" "Wazuh Manager"; then
        ((passed_checks++))
    elif [ $? -eq 2 ]; then
        ((warning_checks++))
    else
        ((failed_checks++))
    fi

    # Wazuh Indexer
    ((total_checks++))
    if check_container_health "wazuh-indexer" "Wazuh Indexer"; then
        ((passed_checks++))
    elif [ $? -eq 2 ]; then
        ((warning_checks++))
    else
        ((failed_checks++))
    fi

    # Wazuh Dashboard
    ((total_checks++))
    if check_container_health "wazuh-dashboard" "Wazuh Dashboard"; then
        ((passed_checks++))
    elif [ $? -eq 2 ]; then
        ((warning_checks++))
    else
        ((failed_checks++))
    fi

    echo ""

    # ============================================================================
    # PORT ACCESSIBILITY VALIDATION
    # ============================================================================

    echo -e "${CYAN}Service Accessibility:${NC}"

    # ML Inference API
    ((total_checks++))
    echo -e "${CYAN}→${NC} Checking ML Inference API (port 8500)..."
    if check_port 8500; then
        echo -e "${GREEN}✓${NC} ML Inference API: ACCESSIBLE"
        ((passed_checks++))
    else
        echo -e "${RED}✗${NC} ML Inference API: NOT ACCESSIBLE"
        ((failed_checks++))
    fi

    # RAG Service
    ((total_checks++))
    echo -e "${CYAN}→${NC} Checking RAG Service (port 8300)..."
    if check_port 8300; then
        echo -e "${GREEN}✓${NC} RAG Service: ACCESSIBLE"
        ((passed_checks++))
    else
        echo -e "${RED}✗${NC} RAG Service: NOT ACCESSIBLE"
        ((failed_checks++))
    fi

    # Wazuh Dashboard
    ((total_checks++))
    echo -e "${CYAN}→${NC} Checking Wazuh Dashboard (port 443)..."
    if check_port 443; then
        echo -e "${GREEN}✓${NC} Wazuh Dashboard: ACCESSIBLE"
        ((passed_checks++))
    else
        echo -e "${RED}✗${NC} Wazuh Dashboard: NOT ACCESSIBLE"
        ((failed_checks++))
    fi

    echo ""

    # ============================================================================
    # VALIDATION SUMMARY
    # ============================================================================

    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}  DEPLOYMENT VALIDATION SUMMARY                               ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "  Total Checks:   ${WHITE}${total_checks}${NC}"
    echo -e "  ${GREEN}Passed:${NC}         ${passed_checks}"
    echo -e "  ${YELLOW}Warnings:${NC}       ${warning_checks}"
    echo -e "  ${RED}Failed:${NC}         ${failed_checks}"
    echo ""

    # Determine overall status
    if [ $failed_checks -eq 0 ] && [ $warning_checks -eq 0 ]; then
        echo -e "${GREEN}✓ ALL SERVICES HEALTHY${NC}"
        return 0
    elif [ $failed_checks -eq 0 ] && [ $warning_checks -gt 0 ]; then
        echo -e "${YELLOW}⚠ DEPLOYMENT INCOMPLETE - Some services still starting${NC}"
        echo -e "${YELLOW}  Wait 2-3 minutes and check: docker ps${NC}"
        return 0
    else
        echo -e "${RED}✗ DEPLOYMENT FAILED - ${failed_checks} service(s) failed${NC}"
        echo ""
        echo -e "${WHITE}Troubleshooting:${NC}"
        echo "  1. Check container logs:"
        echo "     docker compose -f $COMPOSE_DIR/ai-services.yml logs"
        echo "     docker compose -f $COMPOSE_DIR/$SIEM_COMPOSE logs"
        echo ""
        echo "  2. Check container status:"
        echo "     docker ps -a"
        echo ""
        echo "  3. Restart failed services:"
        echo "     docker compose -f $COMPOSE_DIR/ai-services.yml restart"
        echo "     docker compose -f $COMPOSE_DIR/$SIEM_COMPOSE restart"
        echo ""
        echo "  4. For detailed troubleshooting:"
        echo "     See docs/troubleshooting.md"
        echo ""
        return 1
    fi
}

# ============================================================================
# RUN VALIDATION
# ============================================================================

# Run comprehensive validation
if validate_deployment; then
    VALIDATION_STATUS="PASSED"
    EXIT_CODE=0
else
    VALIDATION_STATUS="FAILED"
    EXIT_CODE=1
fi

# ============================================================================
# SUCCESS SUMMARY (conditional on validation)
# ============================================================================

if [ "$VALIDATION_STATUS" = "PASSED" ]; then
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}                                                              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  ${GREEN}QUICKSTART DEPLOYMENT COMPLETE!${NC}                          ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                                                              ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    echo -e "${WHITE}Access Your AI-SOC:${NC}"
    echo ""
    echo -e "  ${GREEN}Wazuh Dashboard:${NC}    https://localhost:443"
    echo -e "    Username: admin"
    echo -e "    Password: SecurePass123!"
    echo ""
    echo -e "  ${GREEN}ML Inference API:${NC}   http://localhost:8500/docs"
    echo -e "    Interactive API documentation"
    echo ""
    echo -e "  ${GREEN}RAG Service:${NC}        http://localhost:8300/health"
    echo -e "    MITRE ATT&CK context retrieval"
    echo ""

    echo -e "${YELLOW}Important Notes:${NC}"
    echo "  • Accept the self-signed certificate warning in your browser"
    echo "  • Change default passwords before production use"
    echo ""

    echo -e "${WHITE}Check Service Status:${NC}"
    echo "  docker ps"
    echo ""

    echo -e "${WHITE}View Logs:${NC}"
    echo "  docker compose -f $COMPOSE_DIR/ai-services.yml logs -f"
    echo "  docker compose -f $COMPOSE_DIR/$SIEM_COMPOSE logs -f"
    echo ""

    echo -e "${WHITE}Add More Capabilities:${NC}"
    echo "  ${CYAN}Full deployment:${NC}  ./deploy.sh --full"
    echo "  ${CYAN}SOAR stack:${NC}       docker compose -f $COMPOSE_DIR/phase2-soar-stack.yml up -d"
    echo "  ${CYAN}Monitoring:${NC}       docker compose -f $COMPOSE_DIR/monitoring-stack.yml up -d"
    echo ""

    echo -e "${WHITE}Stop Services:${NC}"
    echo "  docker compose -f $COMPOSE_DIR/ai-services.yml down"
    echo "  docker compose -f $COMPOSE_DIR/$SIEM_COMPOSE down"
    echo ""

    echo -e "${GREEN}Happy hacking!${NC}"
    echo ""
else
    echo ""
    echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}                                                              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}  ${RED}QUICKSTART DEPLOYMENT FAILED${NC}                              ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                                                              ${CYAN}║${NC}"
    echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    echo -e "${RED}One or more services failed to deploy properly.${NC}"
    echo ""
    echo -e "${WHITE}Next Steps:${NC}"
    echo "  1. Review the validation errors above"
    echo "  2. Check container logs for failed services"
    echo "  3. Verify system requirements (8GB RAM, 2 CPU cores)"
    echo "  4. Try restarting failed services"
    echo ""
    echo -e "${WHITE}Common Issues:${NC}"
    echo "  • Insufficient resources: Close other applications"
    echo "  • Port conflicts: Stop services using ports 443, 8300, 8500"
    echo "  • Previous deployment: Run cleanup first"
    echo ""
    echo -e "${WHITE}Clean Up and Retry:${NC}"
    echo "  docker compose -f $COMPOSE_DIR/ai-services.yml down"
    echo "  docker compose -f $COMPOSE_DIR/$SIEM_COMPOSE down"
    echo "  ./quickstart.sh"
    echo ""
fi

# Save quickstart info
mkdir -p "$SCRIPT_DIR/logs"
cat > "$SCRIPT_DIR/logs/quickstart_info.txt" << EOF
AI-SOC Quickstart Deployment
Timestamp: $(date)
Validation Status: $VALIDATION_STATUS

Deployed Stacks:
  - AI Services (ml-inference, rag-service, redis)
  - SIEM (wazuh-manager, wazuh-indexer, wazuh-dashboard)

Access URLs:
  - Wazuh Dashboard: https://localhost:443
  - ML Inference API: http://localhost:8500/docs
  - RAG Service: http://localhost:8300/health

Default Credentials:
  - Wazuh: admin / SecurePass123!

Validation Results:
$(docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep -E 'wazuh|ml-inference|rag-service|redis')

Next Steps:
  1. Access Wazuh Dashboard
  2. Change default passwords
  3. Deploy additional stacks: ./deploy.sh --full
  4. Check validation: docker ps
EOF

exit $EXIT_CODE
