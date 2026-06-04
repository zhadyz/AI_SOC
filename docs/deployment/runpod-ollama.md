# RunPod Ollama (HTTP proxy) for AI-SOC

Use a GPU RunPod pod for fast LLM inference while keeping the rest of the AI-SOC stack on your local machine (Docker Desktop).

## RunPod pod setup

1. Create a pod with an **NVIDIA GPU** (8 GB VRAM minimum; 16 GB recommended).
2. Use an image or template with **Ollama** installed, or install Ollama on the pod.
3. Start Ollama listening on all interfaces:
   ```bash
   OLLAMA_HOST=0.0.0.0:11434 ollama serve
   ```
4. Pull the model used by AI-SOC (must match `OLLAMA_MODEL` in `.env`):
   ```bash
   ollama pull llama3.2:3b
   ```
5. In RunPod, enable **HTTP proxy** (or “Connect”) for port **11434** and copy the public proxy URL (e.g. `https://xxxxx-xxxxx.proxy.runpod.net`).

## Local `.env` configuration

In the repo root [`.env`](../../.env) (synced to `docker-compose/.env` on deploy):

```env
OLLAMA_MODE=remote
OLLAMA_BASE_URL=https://your-id.proxy.runpod.net
OLLAMA_MODEL=llama3.2:3b
```

Do **not** use `http://ollama:11434` for remote mode — that hostname only exists inside the local compose network.

## Deploy

**PowerShell (Windows):**

```powershell
cd AI_SOC
.\deploy-ai-soc.ps1 -OllamaRemote
# or interactive prompt:
.\deploy-ai-soc.ps1
```

**Bash:**

```bash
./deploy-ai-soc.sh --ollama-remote
```

The deploy script will:

- Skip the local `ollama` container (compose profile `local-ollama` is not activated).
- Preflight-check `GET $OLLAMA_BASE_URL/api/tags` and confirm `OLLAMA_MODEL` is present.
- Point alert-triage, correlation-engine, response-orchestrator, and rule-generator at `OLLAMA_BASE_URL`.

## Recreate AI services after changing Ollama URL

```powershell
docker compose -p ai-soc-ai -f docker-compose/ai-services.yml up -d --force-recreate alert-triage correlation-engine response-orchestrator rule-generator
```

## Verify

From the host:

```powershell
Invoke-RestMethod "http://localhost:8100/health"
# Analyze may take several minutes on first call:
Invoke-RestMethod -Method Post -Uri "http://localhost:8100/analyze" -Body (@{ alert_id = "test-1"; severity = 8; description = "test" } | ConvertTo-Json) -ContentType "application/json" -TimeoutSec 600
```

Remote Ollama directly:

```bash
curl -s "${OLLAMA_BASE_URL}/api/tags"
```

## Local Ollama instead

```powershell
.\deploy-ai-soc.ps1 -OllamaLocal
```

Or set `OLLAMA_MODE=local` in `.env` and run with `-UseEnvOllama`.

## Troubleshooting

| Issue | What to check |
|--------|----------------|
| Preflight fails | Pod running, proxy enabled on 11434, URL has no extra path |
| Model not found | `ollama pull` on the pod for `OLLAMA_MODEL` |
| Triage timeout | Increase client timeout; `TRIAGE_LLM_TIMEOUT=300` is set in compose |
| Containers cannot reach RunPod | Use the **public** proxy URL; test from host first with `curl` |

## SSH tunnel (optional)

If you prefer not to use the public HTTP proxy, forward port 11434 over SSH and set:

```env
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

On Windows Docker Desktop, `host.docker.internal` resolves from containers to the host where the tunnel listens.
