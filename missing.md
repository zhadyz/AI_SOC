# Agentic AI Security Gaps (OWASP ASI 2026)

AI-SOC uses **autonomous agents**: LLM triage, RAG, multi-service tool calls, feedback memory, auto-defense. This file is only **agentic** risks—not general SIEM/network issues.

**Wired** = works today · **Exists** = in code/docs, not connected · **Missing** = not built

---

## What we have vs what we lack

| | Wired | Exists, not wired | Missing |
|---|-------|-------------------|---------|
| **Auth between agents** | Wazuh API JWT | `common/auth.py`, API docs | Tokens on triage/RAG/correlation/webhook calls |
| **Prompt / goal safety** | “Use evidence only” in prompt | `detect_prompt_injection()` | Block bad input before LLM; isolate untrusted logs/RAG |
| **Tool limits** | Fixed pipeline; caps on defense actions | Timeouts | Budget per alert; stop runaway plans |
| **Memory safety** | Feedback/history in prompts | 5-alert history cap | Detect poisoned analyst labels |
| **Human before autonomy** | Approve risky defense actions | — | Analyst must confirm LLM severity before auto-defend |
| **Stop rogue behavior** | Turn off `AUTO_DEFEND_ENABLED` | Plan limits | Kill switch; limit repeat auto-defend |

---

## OWASP ASI — open gaps on default lab

| ID | Risk | Problem here |
|----|------|----------------|
| **01** | Goal hijack | Malicious log/RAG text can steer the LLM |
| **02** | Tool misuse | Many tool calls per alert, no hard budget |
| **03** | Identity abuse | AI services accept HTTP with no agent auth |
| **04** | Supply chain | RAG/model trusted without integrity checks |
| **05** | Bad execution | Auto-defense can hit Wazuh AR with weak target checks |
| **06** | Memory poison | Bad feedback changes future triage for an IP |
| **07** | Bad agent comms | Internal `http://`, no signed messages |
| **08** | Cascading failure | Slow LLM blocks whole webhook |
| **09** | Over-trust LLM | LLM severity triggers defense without human check |
| **10** | Rogue agent | Auto-defend can fire again on each high alert |

---

## What actually protects us (agentic)

- Defense actions need approval for risky tiers (`safety.py`)
- Auto-defend only if LLM severity ≥ configured level
- Defense can be disabled via env
- Tool chain is fixed (not free-form agent tools)

---

## Fix first (use code already in repo)

1. Turn on API auth on all services; send Bearer from integration.
2. Run injection checks before Ollama.
3. Require human/policy OK on triage severity before auto-defend.
4. Validate targets before active response; add webhook timeout/breaker.

**Out of scope:** Wazuh dashboard AI fields, SOAR, indexer, correlation IPs.
