# Defense plan snapshots

Written by **response-orchestrator** when `ORCHESTRATOR_DEFENSE_PLANS_ENABLED=true` (default).

- Path in container: `/data/defense-plans`
- Host path: `AI_SOC/data/defense-plans/`
- Filename: `defense-{plan_id}.json` (updated when the plan is created and again after verification completes)

Includes full plan JSON: actions, status, and `verification` block when that step has run.
