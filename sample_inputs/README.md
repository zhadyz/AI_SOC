# Sample API inputs

Ready-to-use JSON for manual testing. Run commands from the `AI_SOC` directory.

## Alert Triage (`POST /analyze`)

Required fields: `alert_id`, `rule_description`, `rule_level` (0–15).

**PowerShell:**

```powershell
$body = Get-Content .\sample_inputs\alert-triage-analyze-ssh-bruteforce.json -Raw
Invoke-RestMethod -Method Post -Uri "http://localhost:8100/analyze" -Body $body -ContentType "application/json" -TimeoutSec 600
```

**curl + jq:**

```powershell
curl.exe -s -X POST "http://localhost:8100/analyze" -H "Content-Type: application/json" --data-binary "@sample_inputs/alert-triage-analyze-ssh-bruteforce.json" | jq .
```

| File | Purpose |
|------|---------|
| `alert-triage-analyze-minimal.json` | Smallest valid payload |
| `alert-triage-analyze-ssh-bruteforce.json` | Realistic SSH brute-force example |

## Alert Triage batch (`POST /batch`)

```powershell
$body = Get-Content .\sample_inputs\alert-triage-batch.json -Raw
Invoke-RestMethod -Method Post -Uri "http://localhost:8100/batch" -Body $body -ContentType "application/json" -TimeoutSec 600
```

## RunPod Ollama (`POST /api/generate`)

Set URL from `.env` (`OLLAMA_BASE_URL`), e.g. `https://oqcq84huq8ydey-11434.proxy.runpod.net`.

```powershell
$body = Get-Content .\sample_inputs\ollama-generate.json -Raw
Invoke-RestMethod -Method Post -Uri "https://oqcq84huq8ydey-11434.proxy.runpod.net/api/generate" -Body $body -ContentType "application/json"
```

```powershell
curl.exe -s -X POST "https://oqcq84huq8ydey-11434.proxy.runpod.net/api/generate" -H "Content-Type: application/json" --data-binary "@sample_inputs/ollama-generate.json" | jq .
```

Interactive API docs: http://localhost:8100/docs
