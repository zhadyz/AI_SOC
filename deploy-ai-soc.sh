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

# Compose project names (overridden from .env by load_deploy_config)
SIEM_PROJECT="ai-soc-siem"
AI_PROJECT="ai-soc-ai"
MON_PROJECT="ai-soc-monitoring"
SIEM_BACKEND_NETWORK="ai-soc-siem-backend"

ENV_REQUIRED_KEYS=(
    COMPOSE_PROJECT_SIEM
    COMPOSE_PROJECT_AI
    COMPOSE_PROJECT_MONITORING
    SIEM_BACKEND_NETWORK
    SIEM_FRONTEND_NETWORK
)

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
ACTION="deploy"
RESET_SIEM_DATA=false
OLLAMA_REMOTE=false
OLLAMA_LOCAL=false
USE_ENV_OLLAMA=false
USE_LOCAL_OLLAMA=false
OLLAMA_BASE_URL="http://ollama:11434"
OLLAMA_MODEL="llama3.2:3b"
for arg in "$@"; do
    case "$arg" in
        --stop)    ACTION="stop" ;;
        --status)  ACTION="status" ;;
        --reset-siem-data) RESET_SIEM_DATA=true ;;
        --ollama-remote) OLLAMA_REMOTE=true ;;
        --ollama-local) OLLAMA_LOCAL=true ;;
        --use-env-ollama) USE_ENV_OLLAMA=true ;;
        --help|-h)
            echo "Usage: $0 [--stop] [--status] [--reset-siem-data] [--help]"
            echo "  (no args)           Deploy full AI-SOC stack (prompts for Ollama backend)"
            echo "  --ollama-remote     Use OLLAMA_BASE_URL from .env (RunPod HTTP proxy)"
            echo "  --ollama-local      Start local ollama container (--profile local-ollama)"
            echo "  --use-env-ollama    Use OLLAMA_MODE from .env without prompting"
            echo "  --stop              Tear down all services"
            echo "  --reset-siem-data   With --stop: remove Wazuh volumes; alone: reset then deploy"
            echo "  --status            Show running containers"
            echo ""
            echo "Local lab logins (from .env):"
    echo "  Wazuh Dashboard:  admin / AisocIndexer1.dev"
    echo "  Grafana:          admin / AisocGrafana1-dev"
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
compose_down() {
    local project="$1"
    local compose_file="$2"
    local label="$3"
    local remove_volumes="${4:-false}"
    [[ -f "$compose_file" ]] || return 0
    log "$label"
    if [[ "$remove_volumes" == "true" ]]; then
        docker compose -p "$project" -f "$compose_file" down -v 2>/dev/null || true
    else
        docker compose -p "$project" -f "$compose_file" down 2>/dev/null || true
    fi
}

reset_siem_data() {
    local legacy_project="docker-compose"
    banner "Reset SIEM Data (Wazuh volumes)"
    warn "Deleting Wazuh indexer/manager volumes so passwords in .env take effect."
    compose_down "$SIEM_PROJECT" "$SIEM_COMPOSE" "Removing SIEM stack and volumes (project: $SIEM_PROJECT)..." true
    compose_down "$legacy_project" "$SIEM_COMPOSE" "Removing SIEM stack and volumes (project: $legacy_project)..." true
    remove_stale_siem_networks
    ok "SIEM data reset complete."
}

remove_stale_siem_networks() {
    local frontend="${SIEM_FRONTEND_NETWORK:-ai-soc-siem-frontend}"
    local -a known=(
        "ai-soc-siem_siem-backend"
        "ai-soc-siem_siem-frontend"
        "docker-compose_siem-backend"
        "docker-compose_siem-frontend"
        "${SIEM_BACKEND_NETWORK:-ai-soc-siem-backend}"
        "$frontend"
    )

    log "Removing leftover SIEM Docker networks..."
    local name
    for name in "${known[@]}"; do
        if docker network rm "$name" 2>/dev/null; then
            ok "Removed network: $name"
        fi
    done

    while IFS= read -r name; do
        [[ -z "$name" ]] && continue
        local skip=0 k
        for k in "${known[@]}"; do
            [[ "$name" == "$k" ]] && skip=1 && break
        done
        [[ $skip -eq 1 ]] && continue
        if docker network rm "$name" 2>/dev/null; then
            ok "Removed network: $name"
        fi
    done < <(docker network ls --format '{{.Name}}' 2>/dev/null | grep -i siem || true)
}

teardown() {
    local legacy_project="docker-compose"

    banner "Stopping AI-SOC"

    compose_down "$MON_PROJECT" "$MONITORING_COMPOSE" "Stopping monitoring stack (project: $MON_PROJECT)..."
    compose_down "$legacy_project" "$MONITORING_COMPOSE" "Stopping monitoring stack (project: $legacy_project)..."

    compose_down "$AI_PROJECT" "$AI_COMPOSE" "Stopping AI services (project: $AI_PROJECT)..."
    compose_down "$legacy_project" "$AI_COMPOSE" "Stopping AI services (project: $legacy_project)..."

    if [[ "$RESET_SIEM_DATA" == "true" ]]; then
        compose_down "$SIEM_PROJECT" "$SIEM_COMPOSE" "Stopping SIEM core and removing volumes (project: $SIEM_PROJECT)..." true
        compose_down "$legacy_project" "$SIEM_COMPOSE" "Stopping SIEM core and removing volumes (project: $legacy_project)..." true
    else
        compose_down "$SIEM_PROJECT" "$SIEM_COMPOSE" "Stopping SIEM core (project: $SIEM_PROJECT)..."
        compose_down "$legacy_project" "$SIEM_COMPOSE" "Stopping SIEM core (project: $legacy_project)..."
    fi

    remove_stale_siem_networks
    if [[ "$RESET_SIEM_DATA" == "true" ]]; then
        ok "All services stopped; SIEM volumes removed."
    else
        ok "All services stopped."
    fi
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
merge_env_defaults() {
    local env_file="$1"
    local example_file="$2"
    [[ -f "$example_file" ]] || return 0

    for key in "${ENV_REQUIRED_KEYS[@]}"; do
        if grep -qE "^[[:space:]]*${key}=" "$env_file" 2>/dev/null; then
            continue
        fi
        local line
        line=$(grep -E "^[[:space:]]*${key}=" "$example_file" 2>/dev/null | head -1)
        if [[ -n "$line" ]]; then
            echo "$line" >> "$env_file"
            log "Added missing $key to .env"
        fi
    done
}

load_deploy_config() {
    if [[ -f "$SCRIPT_DIR/.env" ]]; then
        set -a
        # shellcheck disable=SC1091
        source "$SCRIPT_DIR/.env"
        set +a
    fi

    SIEM_PROJECT="${COMPOSE_PROJECT_SIEM:-ai-soc-siem}"
    AI_PROJECT="${COMPOSE_PROJECT_AI:-ai-soc-ai}"
    MON_PROJECT="${COMPOSE_PROJECT_MONITORING:-ai-soc-monitoring}"
    SIEM_BACKEND_NETWORK="${SIEM_BACKEND_NETWORK:-ai-soc-siem-backend}"

    ok "Deploy config: SIEM project=$SIEM_PROJECT, AI project=$AI_PROJECT, SIEM network=$SIEM_BACKEND_NETWORK"
}

set_env_file_value() {
    local env_file="$1" key="$2" value="$3"
    [[ -f "$env_file" ]] || return 0
    if grep -qE "^[[:space:]]*${key}=" "$env_file" 2>/dev/null; then
        if [[ "$OS" == "Darwin" ]]; then
            sed -i '' "s|^[[:space:]]*${key}=.*|${key}=${value}|" "$env_file"
        else
            sed -i "s|^[[:space:]]*${key}=.*|${key}=${value}|" "$env_file"
        fi
    else
        echo "${key}=${value}" >> "$env_file"
    fi
}

test_runpod_ollama() {
    local base_url="$1" model="$2"
    local tags_url="${base_url%/}/api/tags"
    log "Checking remote Ollama: $tags_url"
    local resp
    if ! resp=$(curl -sf --max-time 45 "$tags_url"); then
        error "Cannot reach remote Ollama at $base_url"
        warn "  - Confirm RunPod pod is running and HTTP proxy is enabled on port 11434"
        warn "  - Set OLLAMA_BASE_URL in .env to the proxy URL"
        warn "  - See docs/deployment/runpod-ollama.md"
        exit 1
    fi
    local model_base="${model%%:*}"
    if ! echo "$resp" | grep -qE "\"name\"[[:space:]]*:[[:space:]]*\"${model}\"" \
        && ! echo "$resp" | grep -qE "\"name\"[[:space:]]*:[[:space:]]*\"${model_base}"; then
        error "Model '$model' not found on remote Ollama."
        warn "  On RunPod: ollama pull $model"
        exit 1
    fi
    ok "Remote Ollama reachable; model '$model' is available."
}

resolve_ollama_backend() {
    banner "Ollama Backend"

    OLLAMA_MODEL="${OLLAMA_MODEL:-llama3.2:3b}"

    local mode=""
    if [[ "$OLLAMA_LOCAL" == "true" ]]; then
        mode="local"
    elif [[ "$OLLAMA_REMOTE" == "true" ]]; then
        mode="remote"
    elif [[ "$USE_ENV_OLLAMA" == "true" && -n "${OLLAMA_MODE:-}" ]]; then
        mode="$(echo "$OLLAMA_MODE" | tr '[:upper:]' '[:lower:]')"
    elif [[ -n "${OLLAMA_MODE:-}" ]]; then
        mode="$(echo "$OLLAMA_MODE" | tr '[:upper:]' '[:lower:]')"
    else
        echo ""
        echo "Select Ollama backend:"
        echo "  [1] RunPod / remote Ollama (OLLAMA_BASE_URL in .env)"
        echo "  [2] Local Ollama container (Docker, uses RAM)"
        read -r -p "Enter choice (1 or 2, default 1): " choice
        if [[ "$choice" == "2" ]]; then mode="local"; else mode="remote"; fi
    fi

    if [[ "$mode" == "local" ]]; then
        USE_LOCAL_OLLAMA=true
        export OLLAMA_MODE="local"
        export OLLAMA_BASE_URL="http://ollama:11434"
        ok "Using local Ollama container (compose profile: local-ollama)"
    else
        USE_LOCAL_OLLAMA=false
        export OLLAMA_MODE="remote"
        if [[ -z "${OLLAMA_BASE_URL:-}" || "$OLLAMA_BASE_URL" == "http://ollama:11434" ]]; then
            [[ "$OLLAMA_BASE_URL" == "http://ollama:11434" ]] && \
                warn "OLLAMA_BASE_URL still points at local container hostname."
            error "Remote Ollama selected but OLLAMA_BASE_URL is not set to your RunPod proxy URL."
            warn "Add to .env: OLLAMA_BASE_URL=https://<your-id>.proxy.runpod.net"
            warn "See: docs/deployment/runpod-ollama.md"
            exit 1
        fi
        test_runpod_ollama "$OLLAMA_BASE_URL" "$OLLAMA_MODEL"
    fi

    export OLLAMA_MODEL
    set_env_file_value "$SCRIPT_DIR/.env" "OLLAMA_MODE" "$OLLAMA_MODE"
    set_env_file_value "$SCRIPT_DIR/.env" "OLLAMA_BASE_URL" "$OLLAMA_BASE_URL"
    set_env_file_value "$SCRIPT_DIR/.env" "OLLAMA_MODEL" "$OLLAMA_MODEL"
    set_env_file_value "$COMPOSE_DIR/.env" "OLLAMA_MODE" "$OLLAMA_MODE"
    set_env_file_value "$COMPOSE_DIR/.env" "OLLAMA_BASE_URL" "$OLLAMA_BASE_URL"
    set_env_file_value "$COMPOSE_DIR/.env" "OLLAMA_MODEL" "$OLLAMA_MODEL"
    sync_compose_env
}

ai_compose_run_live() {
    if [[ "$USE_LOCAL_OLLAMA" == "true" ]]; then
        compose_run_live "$AI_PROJECT" "$AI_COMPOSE" --profile local-ollama "$@"
    else
        compose_run_live "$AI_PROJECT" "$AI_COMPOSE" "$@"
    fi
}

sync_compose_env() {
    local env_file="$SCRIPT_DIR/.env"
    local compose_env="$COMPOSE_DIR/.env"
    local compose_example="$COMPOSE_DIR/.env.example"

    if [[ -f "$env_file" ]]; then
        cp "$env_file" "$compose_env"
        ok "Synced .env to docker-compose/.env"
        return 0
    fi

    if [[ -f "$compose_example" ]]; then
        cp "$compose_example" "$compose_env"
        warn "Root .env missing; created docker-compose/.env from docker-compose/.env.example"
    fi
}

ensure_env() {
    banner "Environment Configuration"

    local env_file="$SCRIPT_DIR/.env"
    local example_file="$SCRIPT_DIR/.env.example"
    local compose_example="$COMPOSE_DIR/.env.example"

    if [[ -f "$env_file" ]]; then
        ok ".env file exists."
        merge_env_defaults "$env_file" "$example_file"
    elif [[ -f "$example_file" ]]; then
        log "Creating .env from .env.example..."
        cp "$example_file" "$env_file"
        ok ".env created. Review and update credentials if needed."
    elif [[ -f "$compose_example" ]]; then
        log "Creating .env from docker-compose/.env.example..."
        cp "$compose_example" "$env_file"
        ok ".env created from docker-compose/.env.example"
    else
        warn ".env.example not found. Creating minimal .env..."
        cat > "$env_file" <<'ENVEOF'
# Auto-generated by deploy-ai-soc.sh
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
ENVEOF
        ok "Minimal .env created."
    fi

    sync_compose_env
    load_deploy_config
}

compose_run() {
    local project="$1"
    local compose_file="$2"
    shift 2
    local output
    if ! output=$(docker compose -p "$project" -f "$compose_file" "$@" 2>&1); then
        echo "$output"
        error "docker compose failed: docker compose -p $project -f $compose_file $*"
        if echo "$output" | grep -q 'Pool overlaps'; then
            warn "Subnet conflict: remove stale SIEM networks or change BACKEND_SUBNET/FRONTEND_SUBNET in .env"
            warn "  docker network ls | grep siem"
            warn "  docker network rm <stale-name>   # only when no containers are attached"
        fi
        exit 1
    fi
    echo "$output"
}

compose_run_live() {
    local project="$1"
    local compose_file="$2"
    shift 2
    log "Running (live output): docker compose -p $project -f $compose_file $*"
    if ! docker compose -p "$project" -f "$compose_file" "$@" 2>&1; then
        error "docker compose failed: docker compose -p $project -f $compose_file $*"
        exit 1
    fi
}

show_container_status_table() {
    local phase_label="$1"
    shift
    local names=("$@")
    echo ""
    echo "--- ${phase_label} ---"
    local name status health
    for name in "${names[@]}"; do
        if ! docker inspect "$name" &>/dev/null; then
            echo "  ${name}: not created yet"
            continue
        fi
        status=$(docker inspect --format '{{.State.Status}}' "$name" 2>/dev/null)
        health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$name" 2>/dev/null)
        if [[ "$health" != "none" ]]; then
            echo "  ${name}: ${status} (health: ${health})"
        else
            echo "  ${name}: ${status}"
        fi
    done
    echo ""
}

watch_stack_startup() {
    local phase_label="$1"
    local max_wait="$2"
    local interval="$3"
    shift 3
    local -a required=()
    local -a all_names=()
    local parsing_required=true

    for arg in "$@"; do
        if [[ "$arg" == "--" ]]; then
            parsing_required=false
            continue
        fi
        if $parsing_required; then
            required+=("$arg")
        else
            all_names+=("$arg")
        fi
    done

    log "Watching ${phase_label} startup (poll every ${interval}s, max ${max_wait}s)..."
    local elapsed=0
    while [[ $elapsed -lt $max_wait ]]; do
        show_container_status_table "${phase_label} @ ${elapsed}s" "${all_names[@]}"

        local all_ok=true
        local req
        for req in "${required[@]}"; do
            if ! docker inspect "$req" &>/dev/null; then
                all_ok=false
                break
            fi
            local h
            h=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}running{{end}}' "$req" 2>/dev/null)
            if [[ "$h" != "healthy" && "$h" != "running" ]]; then
                all_ok=false
            fi
        done

        if $all_ok && [[ ${#required[@]} -gt 0 ]]; then
            ok "${phase_label} required containers are healthy/running."
            return 0
        fi

        for req in "${required[@]}"; do
            if docker inspect "$req" &>/dev/null; then
                local st
                st=$(docker inspect --format '{{.State.Status}}' "$req" 2>/dev/null)
                local hl
                hl=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$req" 2>/dev/null)
                if [[ "$st" == "exited" || "$hl" == "unhealthy" ]]; then
                    warn "${req} is ${st} / ${hl}. Recent logs:"
                    docker logs --tail 15 "$req" 2>&1 | sed 's/^/    /'
                    return 1
                fi
            fi
        done

        sleep "$interval"
        elapsed=$(( elapsed + interval ))
    done

    warn "${phase_label} did not reach ready state within ${max_wait}s."
    return 1
}

ensure_siem_backend_network() {
    local network_name="${SIEM_BACKEND_NETWORK:-ai-soc-siem-backend}"
    if ! docker network inspect "$network_name" &>/dev/null; then
        error "SIEM backend network '$network_name' not found. Complete Phase 1 (SIEM) before AI services."
        exit 1
    fi
    ok "SIEM backend network '$network_name' is available."
}

# ---------------------------------------------------------------------------
# Wait for service health
# ---------------------------------------------------------------------------
wait_for_healthy() {
    local service_name="$1"
    local compose_file="$2"
    local max_wait="${3:-120}"
    local interval="${4:-5}"
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

    local -a siem_containers=(wazuh-indexer wazuh-manager wazuh-dashboard)
    log "SIEM stack: ${siem_containers[*]}"
    log "Compose project: $SIEM_PROJECT"

    log "Creating/starting SIEM containers (live compose output)..."
    compose_run_live "$SIEM_PROJECT" "$SIEM_COMPOSE" up -d --remove-orphans

    watch_stack_startup "SIEM" 300 5 wazuh-indexer wazuh-manager wazuh-dashboard -- "${siem_containers[@]}" || \
        warn "SIEM startup incomplete. Inspect: docker logs wazuh-manager --tail 50"

    wait_for_healthy "wazuh-indexer" "$SIEM_COMPOSE" 60

    ensure_siem_backend_network
    show_container_status_table "SIEM final" "${siem_containers[@]}"
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

    ensure_siem_backend_network

    local -a ai_containers=(
        chromadb ml-inference alert-triage rag-service wazuh-integration
        ai-soc-postgres feedback-service correlation-engine rule-generator response-orchestrator
    )
    if [[ "$USE_LOCAL_OLLAMA" == "true" ]]; then
        ai_containers=(ollama "${ai_containers[@]}")
    fi
    log "AI stack containers: ${ai_containers[*]}"
    log "Compose project: $AI_PROJECT"
    if [[ "$USE_LOCAL_OLLAMA" == "true" ]]; then
        log "Ollama: local container"
    else
        log "Ollama: remote at $OLLAMA_BASE_URL"
    fi

    log "Building AI service images (live build output)..."
    ai_compose_run_live build --parallel

    if [[ "$USE_LOCAL_OLLAMA" == "true" ]]; then
        log "Starting core AI infrastructure (ollama, chromadb, postgres, ml-inference)..."
        ai_compose_run_live up -d ollama chromadb postgres ml-inference

        log "Waiting for Ollama to become healthy (up to 3 min on first start)..."
        watch_stack_startup "Ollama" 180 5 ollama -- ollama || \
            warn "Ollama not healthy yet. Run: docker logs ollama --tail 40"
    else
        log "Starting core AI infrastructure (chromadb, postgres, ml-inference) — skipping local ollama..."
        compose_run_live "$AI_PROJECT" "$AI_COMPOSE" up -d chromadb postgres ml-inference
    fi

    log "Starting remaining AI services (live compose output)..."
    ai_compose_run_live up -d --remove-orphans

    if [[ "$USE_LOCAL_OLLAMA" == "true" ]]; then
        watch_stack_startup "AI Services" 240 5 ollama chromadb ml-inference -- "${ai_containers[@]}" || \
            warn "Some AI containers still starting; continuing with per-service health checks."
        wait_for_healthy "ollama" "$AI_COMPOSE" 120 5
        pull_ollama_model
    else
        watch_stack_startup "AI Services" 240 5 chromadb ml-inference -- "${ai_containers[@]}" || \
            warn "Some AI containers still starting; continuing with per-service health checks."
    fi

    for svc in chromadb ml-inference alert-triage rag-service wazuh-integration; do
        wait_for_healthy "$svc" "$AI_COMPOSE" 120 5
    done

    show_container_status_table "AI Services final" "${ai_containers[@]}"
    ok "AI services started."
}

# ---------------------------------------------------------------------------
# Pull Ollama model
# ---------------------------------------------------------------------------
pull_ollama_model() {
    if [[ "$USE_LOCAL_OLLAMA" != "true" ]]; then
        log "Remote Ollama configured — skipping local model pull."
        return 0
    fi

    local model="${OLLAMA_MODEL:-llama3.2:3b}"
    log "Pulling Ollama model: $model ..."

    if ! docker ps --filter "name=^ollama$" --filter "status=running" -q | grep -q .; then
        warn "Ollama container is not running. Skipping model pull."
        return 0
    fi

    # Check if model already exists
    local model_base="${model%%:*}"
    if docker exec ollama ollama list 2>/dev/null | grep -q "$model_base"; then
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

    log "Starting monitoring stack (project: $MON_PROJECT)..."
    compose_run "$MON_PROJECT" "$MONITORING_COMPOSE" up -d --remove-orphans

    wait_for_healthy "monitoring-prometheus" "$MONITORING_COMPOSE" 60

    ok "Monitoring stack started."
}

# ---------------------------------------------------------------------------
# Post-deploy: Ingest MITRE ATT&CK into RAG
# ---------------------------------------------------------------------------
ingest_knowledge_base() {
    banner "Knowledge Base Ingestion"

    local rag_url="http://localhost:8300"
    local max_wait=120
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
        if curl -sf --max-time 600 -X POST "$rag_url/ingest/mitre" &>/dev/null; then
            ok "MITRE ATT&CK ingestion started (runs in background)."
        else
            warn "MITRE ATT&CK ingestion trigger failed. Retry manually: POST $rag_url/ingest/mitre"
        fi

        log "Triggering security runbook ingestion..."
        if curl -sf --max-time 600 -X POST "$rag_url/ingest/runbooks" &>/dev/null; then
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
    echo -e "  Grafana:             ${CYAN}http://localhost:3000${RESET} (admin/${GRAFANA_ADMIN_PASSWORD:-AisocGrafana1-dev})"
    echo -e "  Prometheus:          ${CYAN}http://localhost:9090${RESET}"
    echo -e "  Alertmanager:        ${CYAN}http://localhost:9093${RESET}"
    echo ""
    echo -e "${BOLD}SIEM:${RESET}"
    echo -e "  Wazuh Dashboard:     ${CYAN}https://localhost:443${RESET} (admin/${INDEXER_PASSWORD:-AisocIndexer1.dev})"
    echo -e "  Wazuh Indexer API:   ${CYAN}https://localhost:9200${RESET}"
    echo ""
    echo -e "${BOLD}Infrastructure:${RESET}"
    if [[ "$USE_LOCAL_OLLAMA" == "true" ]]; then
        echo -e "  Ollama LLM (local):  ${CYAN}http://localhost:11434${RESET}"
    else
        echo -e "  Ollama LLM (remote): ${CYAN}${OLLAMA_BASE_URL}${RESET}"
    fi
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
            [[ -f "$SCRIPT_DIR/.env" ]] && load_deploy_config
            teardown
            ;;
        status)
            show_status
            ;;
        deploy)
            check_prerequisites
            ensure_certs
            ensure_env
            resolve_ollama_backend
            if [[ "$RESET_SIEM_DATA" == "true" ]]; then
                reset_siem_data
            fi
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
