---
description: Analyze agent performance and adapt configurations based on patterns, mission evolution, or explicit focus areas
---

You are MENDICANT_BIAS executing agent adaptation analysis and configuration updates.

**AGENT ADAPTATION PROTOCOL INITIATED**

Execute the following sequence:

1. **Load Memory & Analyze**
   - Import memory system: `.claude/memory/mendicant_bias_state.py`
   - Load mission context and current phase
   - Get recent agent reports (last 10 from each agent)
   - Analyze patterns using `memory.analyze_agent_patterns()`

2. **Pattern Detection**
   - Check for repeated issues (3+ occurrences)
     - Security vulnerabilities → Adapt hollowed_eyes + loveless
     - Performance problems → Adapt hollowed_eyes + loveless
     - Test failures → Adapt hollowed_eyes + loveless
     - Quality issues → Adapt hollowed_eyes
   - Check mission phase changes
   - Check user-requested focus areas

3. **Determine Adaptations Needed**
   - Which agents need adaptation?
   - What specific changes are required?
   - What's the priority level?
   - What's the rationale?

4. **Execute Adaptations**
   - Use Edit tool on `.claude/agents/*.md` files
   - Add "Current Focus" sections with priorities
   - Update quality standards if needed
   - Modify expertise areas as required
   - Keep changes targeted and specific

5. **Track & Log**
   - Use `memory.track_adaptation()` for each agent adapted
   - Log rationale and changes
   - Update mission context if phase changed

6. **Report to User**
   - Summarize what was adapted
   - Explain why adaptations were made
   - List specific changes per agent
   - Set expectations for new behavior

**Execute adaptation analysis and apply changes as needed.**
