#!/usr/bin/env bash
# =============================================================================
# AI-SOC Master Deployment Script (Linux/macOS)
# =============================================================================
# Single-command deploy for the entire AI-SOC stack.
#
# Usage:
#   ./deploy-ai-soc.sh           Deploy all services
#   ./deploy-ai-soc.sh --stop    Tear down all services
#   ./deploy-ai-soc.sh --status  Show service status
#
# Phases:
#   1. SIEM Core (Wazuh indexer, manager, dashboard)
#   2. AI Services (Ollama, ML Inference, Alert Triage, RAG, Wazuh Integration)
#   3. Monitoring Stack (Prometheus, Grafana, Alertmanager)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Colours
# ---------------------------------------------------------------------------
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
RESET='\033[0m'

log()    { echo -e "${CYAN}[AI-SOC]${RESET} $*"; }
ok()     { echo -e "${GREEN}[  OK  ]${RESET} $*"; }
warn()   { echo -e "${YELLOW}[ WARN ]${RESET} $*"; }
error()  { echo -e "${RED}[ERROR ]${RESET} $*" >&2; }
banner() { echo -e "\n${BOLD}${BLUE}=== $* ===${RESET}\n"; }

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_DIR="$SCRIPT_DIR/docker-compose"
SCRIPTS_DIR="$SCRIPT_DIR/scripts"

# Pick SIEM compose: full Linux stack needs native Docker + host networking.
# Docker Desktop (incl. WSL) cannot run Suricata/Zeek bind mounts reliably.
OS="$(uname -s)"
IS_DOCKER_DESKTOP=false
if docker info 2>/dev/null | grep -q 'Operating System: Docker Desktop'; then
    IS_DOCKER_DESKTOP=true
fi

if [[ "$OS" == "Linux" && "$IS_DOCKER_DESKTOP" == "false" ]]; then
    SIEM_COMPOSE="$COMPOSE_DIR/phase1-siem-core.yml"
else
    SIEM_COMPOSE="$COMPOSE_DIR/phase1-siem-core-windows.yml"
fi

AI_COMPOSE="$COMPOSE_DIR/ai-services.yml"
MONITORING_COMPOSE="$COMPOSE_DIR/monitoring-stack.yml"

# Separate project names so --remove-orphans in one stack does not delete other stacks
SIEM_PROJECT="ai-soc-siem"
AI_PROJECT="ai-soc-ai"
MON_PROJECT="ai-soc-monitoring"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
ACTION="deploy"
for arg in "$@"; do
    case "$arg" in
        --stop)    ACTION="stop" ;;
        --status)  ACTION="status" ;;
        --help|-h)
            echo "Usage: $0 [--stop|--status|--help]"
            echo "  (no args)  Deploy full AI-SOC stack"
            echo "  --stop     Tear down all services"
            echo "  --status   Show running containers"
            exit 0
            ;;
        *)
            error "Unknown argument: $arg"
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Tear down
# ---------------------------------------------------------------------------
teardown() {
    banner "Stopping AI-SOC"
    log "Stopping monitoring stack..."
    docker compose -p "$MON_PROJECT" -f "$MONITORING_COMPOSE" down 2>/dev/null || true
    log "Stopping AI services..."
    docker compose -p "$AI_PROJECT" -f "$AI_COMPOSE" down 2>/dev/null || true
    log "Stopping SIEM core..."
    docker compose -p "$SIEM_PROJECT" -f "$SIEM_COMPOSE" down 2>/dev/null || true
    ok "All services stopped."
}

# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
show_status() {
    banner "AI-SOC Service Status"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || true
}

# ---------------------------------------------------------------------------
# Prerequisite checks
# ---------------------------------------------------------------------------
check_prerequisites() {
    banner "Checking Prerequisites"

    # Docker
    if ! command -v docker &>/dev/null; then
        error "Docker is not installed. Install from https://docs.docker.com/get-docker/"
        exit 1
    fi
    ok "Docker: $(docker --version | cut -d' ' -f3 | tr -d ',')"

    # Docker Compose (v2 plugin or standalone)
    if ! docker compose version &>/dev/null 2>&1; then
        error "Docker Compose v2 is not available. Update Docker Desktop or install the plugin."
        exit 1
    fi
    ok "Docker Compose: $(docker compose version --short 2>/dev/null || echo 'v2')"

    # Docker daemon running
    if ! docker info &>/dev/null; then
        error "Docker daemon is not running. Start Docker and retry."
        exit 1
    fi
    ok "Docker daemon: running"

    # Disk space (need at least 20 GB free)
    local free_gb
    if [[ "$OS" == "Darwin" ]]; then
        free_gb=$(df -g / | awk 'NR==2 {print $4}')
    else
        free_gb=$(df -BG / | awk 'NR==2 {print $4}' | tr -d 'G')
    fi
    if [[ "${free_gb:-0}" -lt 20 ]]; then
        warn "Low disk space: ${free_gb}GB free. Recommend at least 20GB."
    else
        ok "Disk space: ${free_gb}GB free"
    fi

    # Memory (need at least 8 GB)
    local mem_gb=0
    if [[ "$OS" == "Darwin" ]]; then
        mem_gb=$(( $(sysctl -n hw.memsize) / 1073741824 ))
    elif [[ -f /proc/meminfo ]]; then
        mem_gb=$(( $(grep MemTotal /proc/meminfo | awk '{print $2}') / 1048576 ))
    fi
    if [[ "$mem_gb" -gt 0 && "$mem_gb" -lt 8 ]]; then
        warn "Low memory: ${mem_gb}GB detected. Recommend at least 8GB for full stack."
    elif [[ "$mem_gb" -gt 0 ]]; then
        ok "Memory: ${mem_gb}GB"
    fi
}

# ---------------------------------------------------------------------------
# SSL certificates
# ---------------------------------------------------------------------------
ensure_certs() {
    banner "SSL Certificates"

    local ca_cert="$SCRIPT_DIR/config/root-ca/root-ca.pem"
    if [[ -f "$ca_cert" ]]; then
        ok "SSL certificates already exist, skipping generation."
        return
    fi

    if [[ -f "$SCRIPTS_DIR/generate-certs.sh" ]]; then
        log "Generating SSL certificates..."
        bash "$SCRIPTS_DIR/generate-certs.sh"
        ok "SSL certificates generated."
    else
        warn "generate-certs.sh not found. Skipping certificate generation."
        warn "Wazuh TLS may fail without certificates."
    fi
}

# ---------------------------------------------------------------------------
# .env file
# ---------------------------------------------------------------------------
ensure_env() {
    banner "Environment Configuration"

    local env_file="$SCRIPT_DIR/.env"
    local example_file="$SCRIPT_DIR/.env.example"

    if [[ -f "$env_file" ]]; then
        ok ".env file exists."
    elif [[ -f "$example_file" ]]; then
        log "Creating .env from .env.example..."
        cp "$example_file" "$env_file"
        ok ".env created. Review and update credentials if needed."
    else
        warn ".env.example not found. Creating minimal .env..."
        cat > "$env_file" <<'ENVEOF'
# Auto-generated by deploy-ai-soc.sh
# Update passwords before production use
INDEXER_USERNAME=admin
INDEXER_PASSWORD=SecurePassword1!
API_PASSWORD=SecurePassword1!
WAZUH_API_PASSWORD=SecurePassword1!
KIBANA_PASSWORD=SecurePassword1!
ENVEOF
        ok "Minimal .env created."
    fi

    # Compose resolves .env from the compose file directory, not repo root.
    local compose_env="$COMPOSE_DIR/.env"
    cp "$env_file" "$compose_env"
    ok "Synced .env to docker-compose/.env"
}

# ---------------------------------------------------------------------------
# Wait for service health
# ---------------------------------------------------------------------------
wait_for_healthy() {
    local service_name="$1"
    local compose_file="$2"
    local max_wait="${3:-120}"
    local interval=10
    local elapsed=0

    log "Waiting for $service_name to become healthy (max ${max_wait}s)..."

    while [[ $elapsed -lt $max_wait ]]; do
        local state
        state=$(docker inspect --format='{{.State.Health.Status}}' "$service_name" 2>/dev/null || echo "not_found")

        case "$state" in
            healthy)
                ok "$service_name is healthy."
                return 0
                ;;
            not_found)
                # Container not started yet
                ;;
            starting)
                log "  $service_name is starting... (${elapsed}s elapsed)"
                ;;
            unhealthy)
                warn "$service_name is unhealthy after ${elapsed}s."
                return 1
                ;;
        esac

        sleep $interval
        elapsed=$(( elapsed + interval ))
    done

    warn "$service_name did not become healthy within ${max_wait}s. Continuing anyway."
    return 0
}

# ---------------------------------------------------------------------------
# Phase 1: SIEM Core
# ---------------------------------------------------------------------------
deploy_siem() {
    banner "Phase 1: SIEM Core"
    log "Using compose file: $SIEM_COMPOSE"
    if [[ "$IS_DOCKER_DESKTOP" == "true" ]]; then
        warn "Docker Desktop detected: using Wazuh-only SIEM (no Suricata/Zeek)."
    fi

    if [[ ! -f "$SIEM_COMPOSE" ]]; then
        warn "SIEM compose file not found: $SIEM_COMPOSE"
        warn "Skipping SIEM phase."
        return 0
    fi

    log "Starting SIEM core services..."
    docker compose -p "$SIEM_PROJECT" -f "$SIEM_COMPOSE" up -d --remove-orphans

    # Wait for wazuh-indexer (most critical dependency)
    wait_for_healthy "wazuh-indexer" "$SIEM_COMPOSE" 180

    ok "SIEM core started."
}

# ---------------------------------------------------------------------------
# Phase 2: AI Services
# ---------------------------------------------------------------------------
deploy_ai_services() {
    banner "Phase 2: AI Services"

    if [[ ! -f "$AI_COMPOSE" ]]; then
        error "AI services compose file not found: $AI_COMPOSE"
        exit 1
    fi

    log "Building AI service images..."
    docker compose -p "$AI_PROJECT" -f "$AI_COMPOSE" build --parallel

    log "Starting AI services..."
    docker compose -p "$AI_PROJECT" -f "$AI_COMPOSE" up -d --remove-orphans

    # Wait for Ollama - it needs time to initialise
    wait_for_healthy "ollama" "$AI_COMPOSE" 120

    # Pull LLM model if Ollama is running
    pull_ollama_model

    # Wait for critical AI services
    for svc in chromadb ml-inference alert-triage rag-service; do
        wait_for_healthy "$svc" "$AI_COMPOSE" 120
    done

    ok "AI services started."
}

# ---------------------------------------------------------------------------
# Pull Ollama model
# ---------------------------------------------------------------------------
pull_ollama_model() {
    local model="llama3.2:3b"
    log "Pulling Ollama model: $model ..."

    # Check if model already exists
    if docker exec ollama ollama list 2>/dev/null | grep -q "llama3.2"; then
        ok "Ollama model $model already present."
        return 0
    fi

    if docker exec ollama ollama pull "$model" 2>&1; then
        ok "Ollama model $model pulled successfully."
    else
        warn "Failed to pull Ollama model $model. Alert Triage will use fallback mode."
    fi
}

# ---------------------------------------------------------------------------
# Phase 3: Monitoring
# ---------------------------------------------------------------------------
deploy_monitoring() {
    banner "Phase 3: Monitoring Stack"

    if [[ ! -f "$MONITORING_COMPOSE" ]]; then
        warn "Monitoring compose file not found: $MONITORING_COMPOSE"
        warn "Skipping monitoring phase."
        return 0
    fi

    log "Starting monitoring stack..."
    docker compose -p "$MON_PROJECT" -f "$MONITORING_COMPOSE" up -d --remove-orphans

    wait_for_healthy "monitoring-prometheus" "$MONITORING_COMPOSE" 60

    ok "Monitoring stack started."
}

# ---------------------------------------------------------------------------
# Post-deploy: Ingest MITRE ATT&CK into RAG
# ---------------------------------------------------------------------------
ingest_knowledge_base() {
    banner "Knowledge Base Ingestion"

    local rag_url="http://localhost:8300"
    local max_wait=60
    local elapsed=0

    log "Waiting for RAG service to be ready..."
    while [[ $elapsed -lt $max_wait ]]; do
        if curl -sf "$rag_url/health" &>/dev/null; then
            break
        fi
        sleep 5
        elapsed=$(( elapsed + 5 ))
    done

    if curl -sf "$rag_url/health" &>/dev/null; then
        log "Triggering MITRE ATT&CK ingestion..."
        if curl -sf -X POST "$rag_url/ingest/mitre" &>/dev/null; then
            ok "MITRE ATT&CK ingestion started (runs in background)."
        else
            warn "MITRE ATT&CK ingestion trigger failed. Retry manually: POST $rag_url/ingest/mitre"
        fi

        log "Triggering security runbook ingestion..."
        if curl -sf -X POST "$rag_url/ingest/runbooks" &>/dev/null; then
            ok "Security runbook ingestion started."
        else
            warn "Runbook ingestion trigger failed. Retry manually: POST $rag_url/ingest/runbooks"
        fi
    else
        warn "RAG service not reachable after ${max_wait}s. Skipping knowledge base ingestion."
        warn "Trigger manually: curl -X POST http://localhost:8300/ingest/mitre"
    fi
}

# ---------------------------------------------------------------------------
# Health check summary
# ---------------------------------------------------------------------------
health_check() {
    banner "Health Check Summary"

    declare -A ENDPOINTS=(
        ["ML Inference"]="http://localhost:8500/health"
        ["Alert Triage"]="http://localhost:8100/health"
        ["RAG Service"]="http://localhost:8300/health"
        ["Wazuh Integration"]="http://localhost:8002/health"
        ["Prometheus"]="http://localhost:9090/-/healthy"
        ["Grafana"]="http://localhost:3000/api/health"
    )

    local all_ok=true
    for name in "${!ENDPOINTS[@]}"; do
        local url="${ENDPOINTS[$name]}"
        if curl -sf --max-time 5 "$url" &>/dev/null; then
            ok "$name: reachable"
        else
            warn "$name: not reachable ($url)"
            all_ok=false
        fi
    done

    if $all_ok; then
        ok "All services healthy."
    else
        warn "Some services are not yet reachable. They may still be starting up."
        warn "Run './deploy-ai-soc.sh --status' to check container states."
    fi
}

# ---------------------------------------------------------------------------
# Print access URLs
# ---------------------------------------------------------------------------
print_access_urls() {
    banner "Access URLs"
    echo -e "${BOLD}AI Services:${RESET}"
    echo -e "  Alert Triage API:    ${CYAN}http://localhost:8100/docs${RESET}"
    echo -e "  RAG Service API:     ${CYAN}http://localhost:8300/docs${RESET}"
    echo -e "  ML Inference API:    ${CYAN}http://localhost:8500/docs${RESET}"
    echo -e "  Wazuh Integration:   ${CYAN}http://localhost:8002/docs${RESET}"
    echo ""
    echo -e "${BOLD}Monitoring:${RESET}"
    echo -e "  Grafana:             ${CYAN}http://localhost:3000${RESET} (admin/admin)"
    echo -e "  Prometheus:          ${CYAN}http://localhost:9090${RESET}"
    echo -e "  Alertmanager:        ${CYAN}http://localhost:9093${RESET}"
    echo ""
    echo -e "${BOLD}SIEM:${RESET}"
    echo -e "  Wazuh Dashboard:     ${CYAN}https://localhost:443${RESET} (admin/SecurePassword1!)"
    echo -e "  Wazuh Indexer API:   ${CYAN}https://localhost:9200${RESET}"
    echo ""
    echo -e "${BOLD}Infrastructure:${RESET}"
    echo -e "  Ollama LLM:          ${CYAN}http://localhost:11434${RESET}"
    echo -e "  ChromaDB:            ${CYAN}http://localhost:8200${RESET}"
    echo ""
    echo -e "${GREEN}${BOLD}AI-SOC deployment complete.${RESET}"
    echo -e "Run '${CYAN}./deploy-ai-soc.sh --stop${RESET}' to tear down all services."
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    echo -e "\n${BOLD}${BLUE}============================================="
    echo -e "   AI Security Operations Center"
    echo -e "   Master Deployment Script"
    echo -e "=============================================${RESET}\n"

    case "$ACTION" in
        stop)
            teardown
            ;;
        status)
            show_status
            ;;
        deploy)
            check_prerequisites
            ensure_certs
            ensure_env
            deploy_siem
            deploy_ai_services
            deploy_monitoring
            ingest_knowledge_base
            health_check
            print_access_urls
            ;;
    esac
}

main
