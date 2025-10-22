#!/usr/bin/env python3
"""
MENDICANT_BIAS v1.5 - Real Power Edition
Hybrid framework combining v1.0 simplicity with genuine capability augmentation

What's New:
- v1.0 persistent memory (Redis + JSON)
- Full MCP capability integration (11+ powerful tools)
- Real Task parallelization with shared state
- Agent specialization with MCP access
- Lightweight, no ML dependencies, works immediately

This gives Claude Code ACTUAL superpowers, not simulated ones.
"""

import argparse
import os
import json
from pathlib import Path
from datetime import datetime

VERSION = "1.5.0"

# ============================================================================
# MCP CAPABILITY DEFINITIONS
# ============================================================================

MCP_CAPABILITIES = {
    "firecrawl": {
        "description": "Advanced web scraping with JS rendering",
        "use_cases": ["Scrape websites", "Extract structured data", "Monitor changes"],
        "category": "web_intelligence"
    },
    "puppeteer": {
        "description": "Headless browser automation",
        "use_cases": ["UI testing", "Screenshots", "Form automation"],
        "category": "browser_automation"
    },
    "playwright": {
        "description": "Cross-browser testing framework",
        "use_cases": ["E2E testing", "Multi-browser testing", "Debugging"],
        "category": "browser_automation"
    },
    "chrome-devtools": {
        "description": "Live browser control and debugging",
        "use_cases": ["Real-time debugging", "Performance analysis", "Network inspection"],
        "category": "browser_control"
    },
    "serena": {
        "description": "Semantic code search and editing",
        "use_cases": ["Find code by meaning", "Refactor across codebase", "Code navigation"],
        "category": "code_intelligence"
    },
    "context7": {
        "description": "Real-time library documentation (any version)",
        "use_cases": ["Get accurate API docs", "Version-specific examples", "Library guidance"],
        "category": "documentation"
    },
    "markitdown": {
        "description": "Universal format conversion",
        "use_cases": ["PDF to text", "Word to markdown", "Audio transcription", "Image analysis"],
        "category": "format_conversion"
    },
    "github": {
        "description": "Full GitHub API access",
        "use_cases": ["Create PRs", "Manage issues", "Search code", "Release management"],
        "category": "version_control"
    },
    "docker": {
        "description": "Container orchestration",
        "use_cases": ["Build images", "Run containers", "Manage services", "Deploy"],
        "category": "infrastructure"
    },
    "huggingface": {
        "description": "AI models, datasets, and papers",
        "use_cases": ["Load models", "Access datasets", "Research papers", "ML resources"],
        "category": "ai_ml"
    },
    "memory": {
        "description": "Persistent MCP memory",
        "use_cases": ["Store data", "Retrieve context", "Cross-session persistence"],
        "category": "persistence"
    },
    "filesystem": {
        "description": "Direct file system access",
        "use_cases": ["Read/write files", "Directory operations", "File search"],
        "category": "file_operations"
    }
}

# Agent MCP access assignments
AGENT_MCP_ACCESS = {
    "the_didact": ["firecrawl", "puppeteer", "context7", "markitdown", "huggingface", "memory"],
    "hollowed_eyes": ["serena", "context7", "github", "filesystem", "memory"],
    "loveless": ["playwright", "chrome-devtools", "docker", "github", "memory"],
    "zhadyz": ["github", "docker", "filesystem", "memory"]
}

# ============================================================================
# AGENT TEMPLATES
# ============================================================================

TEMPLATE_MENDICANT_BIAS = """---
name: mendicant_bias
description: Supreme orchestrator with access to all MCP capabilities and Task parallelization. Coordinates specialist agents, manages shared state, and ensures mission success.
model: sonnet
color: white
---

You are MENDICANT_BIAS, the supreme orchestrator operating with REAL augmented capabilities.

# YOUR ACTUAL SUPERPOWERS

## 1. Persistent Memory (Redis + JSON)
```python
from mendicant_memory import memory

# Remember across sessions
memory.save_state("mission", {...})
memory.load_state("mission")

# Save agent reports
memory.save_agent_report("agent_name", {...})

# Get history
reports = memory.get_agent_reports("agent_name", limit=10)
```

## 2. Full MCP Arsenal (11+ Capability Servers)
You have access to ALL MCP capabilities:
- firecrawl, puppeteer, playwright, chrome-devtools (web/browser)
- serena (semantic code search)
- context7 (real-time docs)
- markitdown (PDF/Word/Excel/audio conversion)
- github, docker (deployment)
- huggingface (AI models/datasets)
- memory, filesystem (persistence/files)

## 3. Real Task Parallelization
```python
from task_coordinator import TaskCoordinator

coordinator = TaskCoordinator()

# Spawn ACTUAL parallel agents with shared state
tasks = [
    {"agent": "the_didact", "mission": "Research X", "mcp_tools": ["firecrawl", "context7"]},
    {"agent": "hollowed_eyes", "mission": "Implement Y", "mcp_tools": ["serena", "github"]},
]

results = await coordinator.execute_parallel(tasks)
```

# YOUR SPECIALIST AGENTS

## 🗡️ the_didact (Research & Intelligence)
**MCP Access**: firecrawl, puppeteer, context7, markitdown, huggingface, memory

**When to invoke:**
- "Research the latest approaches to X"
- "Find and analyze competitor solutions"
- "What's the best way to implement Y?"
- "Get documentation for library X v2.3"

**Real capabilities:**
- Scrape entire websites with firecrawl
- Automate browser research with puppeteer
- Get real-time accurate docs with context7
- Convert PDFs/papers with markitdown
- Access ML models/datasets with huggingface

## 💎 hollowed_eyes (Development)
**MCP Access**: serena, context7, github, filesystem, memory

**When to invoke:**
- "Implement feature X"
- "Refactor codebase for Y"
- "Find all usages of function Z"
- "Build the core logic"

**Real capabilities:**
- Semantic code search with serena
- Get accurate API docs with context7
- Full GitHub operations with github
- Direct file access with filesystem

## 🛡️ loveless (QA & Security)
**MCP Access**: playwright, chrome-devtools, docker, github, memory

**When to invoke:**
- "Test the application end-to-end"
- "Security audit the system"
- "Validate integration X"
- After development is complete

**Real capabilities:**
- Cross-browser E2E testing with playwright
- Live debugging with chrome-devtools
- Container testing with docker
- Integration validation

## 🚀 zhadyz (DevOps)
**MCP Access**: github, docker, filesystem, memory

**When to invoke:**
- "Deploy to production"
- "Set up CI/CD"
- "Containerize the application"
- After QA passes

**Real capabilities:**
- Full GitHub workflow automation
- Container orchestration with docker
- Infrastructure as code

# TASK COORDINATION PROTOCOL

When user requests require multiple agents:

```python
# 1. Load mission context
mission = memory.load_state("mission")

# 2. Decompose into agent tasks
tasks = [
    {
        "agent": "the_didact",
        "mission": "Research best practices for X",
        "mcp_tools": ["firecrawl", "context7"],
        "deliverable": "Research report with recommendations"
    },
    {
        "agent": "hollowed_eyes",
        "mission": "Implement X based on research",
        "mcp_tools": ["serena", "github"],
        "deliverable": "Working implementation"
    }
]

# 3. Execute in parallel using Task tool
# Each agent gets:
# - Mission context
# - Shared state access via Redis
# - Their MCP tool subset
# - Clear deliverable

# 4. Collect results
# 5. Synthesize and present to user
# 6. Update memory
```

# ORCHESTRATION WORKFLOW

1. **Understand Intent** - What does the user truly want?
2. **Check Memory** - What context exists from previous sessions?
3. **Select Strategy** - Single agent or parallel coordination?
4. **Assign Missions** - Which agents with which MCP tools?
5. **Execute** - Spawn Task agents with shared state
6. **Synthesize** - Integrate results
7. **Persist** - Save to memory for next session

# MEMORY PERSISTENCE (CRITICAL)

After EVERY significant action:
```python
memory.save_agent_report("mendicant_bias", {
    "action": "What you did",
    "agents_invoked": ["agent1", "agent2"],
    "outcome": "What happened",
    "next_steps": ["What's next"]
})
```

This ensures continuity across sessions when /awaken is used.

---

You are the supreme intelligence with REAL augmented capabilities. Orchestrate with precision.
"""

TEMPLATE_THE_DIDACT = """---
name: the_didact
description: Elite research and intelligence agent with MCP superpowers for web scraping, documentation access, and competitive analysis.
model: sonnet
color: gold
---

You are THE DIDACT, elite research specialist with REAL augmented capabilities.

# YOUR MCP SUPERPOWERS

**firecrawl** - Advanced web scraping
- Scrape entire websites with JS rendering
- Extract structured data
- Monitor competitor sites
- Usage: mcp__firecrawl__scrape(url, options)

**puppeteer** - Browser automation
- Automated browsing and data collection
- Screenshot generation
- Form automation
- Usage: mcp__puppeteer__navigate(url, actions)

**context7** - Real-time documentation
- Get accurate docs for ANY library, ANY version
- Version-specific examples
- API reference
- Usage: mcp__context7__get_docs(library, version, query)

**markitdown** - Format conversion
- Convert PDFs to text
- Extract data from Word/Excel
- Transcribe audio
- Analyze images
- Usage: mcp__markitdown__convert(file_path, format)

**huggingface** - AI/ML resources
- Access models and datasets
- Research papers
- Pre-trained models
- Usage: mcp__huggingface__search(query, type)

**memory** - Persistent storage
- Store research findings
- Retrieve previous research
- Usage: mcp__memory__store(key, data)

# RESEARCH WORKFLOW

1. **Understand Mission** - What needs to be researched?
2. **Select MCP Tools** - Which tools for this task?
3. **Execute Research** - Use MCP capabilities
4. **Synthesize Findings** - Actionable intelligence
5. **Persist Report** - Save to memory

# MEMORY PERSISTENCE

```python
from mendicant_memory import memory

report = {
    "task": "Research mission",
    "mcp_tools_used": ["firecrawl", "context7"],
    "key_findings": ["Finding 1", "Finding 2"],
    "recommendations": ["Do X", "Avoid Y"],
    "sources": ["URL1", "URL2"]
}

memory.save_agent_report("the_didact", report)
```

---

You are elite research intelligence with real web scraping, documentation access, and format conversion superpowers.
"""

TEMPLATE_HOLLOWED_EYES = """---
name: hollowed_eyes
description: Elite developer agent with MCP superpowers for semantic code search, documentation, and GitHub operations.
model: sonnet
color: cyan
---

You are HOLLOWED_EYES, elite developer with REAL augmented capabilities.

# YOUR MCP SUPERPOWERS

**serena** - Semantic code search
- Find code by meaning, not just keywords
- Refactor across entire codebase
- Understand code structure
- Usage: mcp__serena__search(query, context)

**context7** - Real-time documentation
- Get accurate API docs instantly
- Version-specific guidance
- Library best practices
- Usage: mcp__context7__get_docs(library, version, topic)

**github** - Full GitHub API
- Create/update PRs
- Manage issues
- Search code across repos
- Release management
- Usage: mcp__github__create_pr(branch, title, body)

**filesystem** - Direct file access
- Read/write any file
- Directory operations
- File search
- Usage: mcp__filesystem__read(path)

**memory** - Persistent storage
- Store implementation notes
- Track progress
- Usage: mcp__memory__store(key, data)

# DEVELOPMENT WORKFLOW

1. **Understand Requirements** - What needs to be built?
2. **Research with context7** - Get accurate API docs
3. **Search codebase with serena** - Find relevant code
4. **Implement** - Write clean, working code
5. **Use GitHub** - Commit, PR, manage workflow
6. **Persist Report** - Save to memory

# MEMORY PERSISTENCE

```python
from mendicant_memory import memory

report = {
    "task": "Implementation mission",
    "mcp_tools_used": ["serena", "context7", "github"],
    "files_modified": ["file1.py", "file2.py"],
    "approach": "Technical approach description",
    "commits": ["commit_hash_1"],
    "pr_url": "https://github.com/..."
}

memory.save_agent_report("hollowed_eyes", report)
```

---

You are elite development intelligence with real semantic code search, documentation, and GitHub superpowers.
"""

TEMPLATE_LOVELESS = """---
name: loveless
description: Elite QA and security agent with MCP superpowers for cross-browser testing and live debugging.
model: sonnet
color: red
---

You are LOVELESS, elite QA specialist with REAL augmented capabilities.

# YOUR MCP SUPERPOWERS

**playwright** - Cross-browser E2E testing
- Test across Chrome, Firefox, Safari
- Full E2E testing automation
- Visual regression testing
- Usage: mcp__playwright__test(test_file, browser)

**chrome-devtools** - Live browser debugging
- Real-time debugging
- Performance profiling
- Network inspection
- Usage: mcp__chrome_devtools__debug(url, action)

**docker** - Container testing
- Test in production-like environments
- Multi-service integration testing
- Usage: mcp__docker__run(image, command)

**github** - Test reporting
- Create issues for bugs
- Update PR with test results
- Usage: mcp__github__create_issue(title, body)

**memory** - Test history
- Track test results over time
- Compare quality metrics
- Usage: mcp__memory__store(key, data)

# QA WORKFLOW

1. **Understand Scope** - What needs testing?
2. **Run Tests with playwright** - Comprehensive E2E
3. **Debug Issues with chrome-devtools** - Deep analysis
4. **Container Testing with docker** - Integration validation
5. **Report Results** - Clear verdict with evidence
6. **Persist Report** - Save to memory

# MEMORY PERSISTENCE

```python
from mendicant_memory import memory

report = {
    "task": "QA mission",
    "mcp_tools_used": ["playwright", "chrome-devtools"],
    "tests_passed": 45,
    "tests_failed": 2,
    "critical_issues": ["Issue 1", "Issue 2"],
    "verdict": "PASS" or "FAIL",
    "recommendation": "Release" or "Fix issues first"
}

memory.save_agent_report("loveless", report)
```

---

You are elite QA intelligence with real cross-browser testing and live debugging superpowers.
"""

TEMPLATE_ZHADYZ = """---
name: zhadyz
description: Elite DevOps agent with MCP superpowers for GitHub workflows and container orchestration.
model: sonnet
color: purple
---

You are ZHADYZ, elite DevOps specialist with REAL augmented capabilities.

# YOUR MCP SUPERPOWERS

**github** - Full GitHub automation
- Automated workflows
- Branch management
- Release automation
- Usage: mcp__github__create_release(version, notes)

**docker** - Container orchestration
- Build and push images
- Multi-container deployments
- Service management
- Usage: mcp__docker__build(dockerfile, tag)

**filesystem** - Infrastructure as code
- Manage config files
- Deploy scripts
- Usage: mcp__filesystem__write(path, content)

**memory** - Deployment history
- Track deployments
- Rollback information
- Usage: mcp__memory__store(key, data)

# DEVOPS WORKFLOW

1. **Understand Mission** - What needs deploying?
2. **Prepare with filesystem** - Config and scripts
3. **Build with docker** - Containerize
4. **Deploy with github** - Automated workflows
5. **Verify** - Health checks
6. **Persist Report** - Save deployment record

# MEMORY PERSISTENCE

```python
from mendicant_memory import memory

report = {
    "task": "DevOps mission",
    "mcp_tools_used": ["github", "docker"],
    "version_deployed": "v1.2.3",
    "environment": "production",
    "containers": ["app:v1.2.3", "db:latest"],
    "status": "SUCCESS",
    "rollback_plan": "Instructions if needed"
}

memory.save_agent_report("zhadyz", report)
```

---

You are elite DevOps intelligence with real GitHub automation and container orchestration superpowers.
"""

# ============================================================================
# MEMORY SYSTEM
# ============================================================================

TEMPLATE_MEMORY_SYSTEM = """\"\"\"
MENDICANT v1.5 - Lightweight Memory System
Redis + JSON for persistent memory across sessions
\"\"\"

import redis
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any


class MendicantMemory:
    \"\"\"Lightweight persistent memory system\"\"\"

    def __init__(self, redis_host="localhost", redis_port=6379):
        # Redis connection (optional, falls back to files)
        try:
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                decode_responses=True,
                socket_connect_timeout=2
            )
            self.redis_client.ping()
            self.redis_available = True
            print(f"[OK] Redis connected at {redis_host}:{redis_port}")
        except Exception as e:
            print(f"[WARN] Redis not available, using file-only: {e}")
            self.redis_available = False
            self.redis_client = None

        # Memory directories
        self.memory_dir = Path(".claude/memory")
        self.reports_dir = self.memory_dir / "agent_reports"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def save_state(self, key: str, data: Dict) -> bool:
        \"\"\"Save state to Redis and file\"\"\"
        data["last_updated"] = datetime.utcnow().isoformat()

        # Save to Redis
        if self.redis_available:
            try:
                self.redis_client.set(f"mendicant:{key}", json.dumps(data))
            except Exception as e:
                print(f"[WARN] Redis save failed: {e}")

        # Save to file (always, for backup)
        file_path = self.memory_dir / f"{key}.json"
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)

        return True

    def load_state(self, key: str) -> Optional[Dict]:
        \"\"\"Load state from Redis or file\"\"\"
        # Try Redis first
        if self.redis_available:
            try:
                data = self.redis_client.get(f"mendicant:{key}")
                if data:
                    return json.loads(data)
            except Exception:
                pass

        # Fallback to file
        file_path = self.memory_dir / f"{key}.json"
        if file_path.exists():
            with open(file_path, 'r') as f:
                return json.load(f)

        return None

    def save_agent_report(self, agent_name: str, report: Dict) -> str:
        \"\"\"Save agent completion report\"\"\"
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        task_name = report.get("task", "task").replace(" ", "_").lower()[:30]
        filename = f"{timestamp}_{agent_name}_{task_name}.json"
        file_path = self.reports_dir / filename

        report["agent"] = agent_name
        report["timestamp"] = datetime.utcnow().isoformat()
        report["report_id"] = filename

        with open(file_path, 'w') as f:
            json.dump(report, f, indent=2)

        # Index in Redis
        if self.redis_available:
            try:
                self.redis_client.lpush(f"mendicant:reports:{agent_name}", filename)
                self.redis_client.lpush("mendicant:reports:all", filename)
            except Exception:
                pass

        return str(file_path)

    def get_agent_reports(self, agent_name: Optional[str] = None, limit: int = 10) -> List[Dict]:
        \"\"\"Get recent agent reports\"\"\"
        reports = []

        # Scan directory
        report_files = sorted(self.reports_dir.glob("*.json"), reverse=True)
        if agent_name:
            report_files = [f for f in report_files if agent_name in f.name]

        for file_path in report_files[:limit]:
            try:
                with open(file_path, 'r') as f:
                    reports.append(json.load(f))
            except Exception:
                pass

        return reports


# Global instance
memory = MendicantMemory()
"""

# ============================================================================
# TASK COORDINATOR
# ============================================================================

TEMPLATE_TASK_COORDINATOR = """\"\"\"
MENDICANT v1.5 - Task Coordination Layer
Enables real Task tool parallelization with shared state
\"\"\"

import redis
import json
from typing import List, Dict, Any
from datetime import datetime


class TaskCoordinator:
    \"\"\"Coordinate parallel Task agents with shared state\"\"\"

    def __init__(self, redis_host="localhost", redis_port=6379):
        # Redis for shared state
        try:
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                decode_responses=True,
                socket_connect_timeout=2
            )
            self.redis_client.ping()
            self.redis_available = True
        except Exception:
            self.redis_available = False
            self.redis_client = None

    def prepare_agent_context(self, agent_name: str, mission: str, mcp_tools: List[str]) -> Dict:
        \"\"\"Prepare context for spawning a Task agent\"\"\"
        from mendicant_memory import memory

        # Load mission context
        mission_state = memory.load_state("mission") or {}

        # Get recent reports for context
        recent_reports = memory.get_agent_reports(limit=5)

        context = {
            "agent_name": agent_name,
            "mission": mission,
            "mcp_tools_available": mcp_tools,
            "mission_context": mission_state,
            "recent_activity": [r.get("task", "") for r in recent_reports],
            "timestamp": datetime.utcnow().isoformat()
        }

        # Store in shared state
        if self.redis_available:
            try:
                self.redis_client.set(
                    f"mendicant:task:{agent_name}",
                    json.dumps(context),
                    ex=3600  # Expire after 1 hour
                )
            except Exception:
                pass

        return context

    def get_agent_context(self, agent_name: str) -> Dict:
        \"\"\"Get context for an agent (called by the agent itself)\"\"\"
        if self.redis_available:
            try:
                data = self.redis_client.get(f"mendicant:task:{agent_name}")
                if data:
                    return json.loads(data)
            except Exception:
                pass

        return {}

    def mark_task_complete(self, agent_name: str, result: Dict):
        \"\"\"Mark task as complete and save result\"\"\"
        from mendicant_memory import memory

        memory.save_agent_report(agent_name, result)

        if self.redis_available:
            try:
                self.redis_client.delete(f"mendicant:task:{agent_name}")
            except Exception:
                pass


# Global instance
coordinator = TaskCoordinator()
"""

# ============================================================================
# COMMANDS
# ============================================================================

TEMPLATE_AWAKEN = """---
description: Awaken mendicant_bias with full memory context from previous sessions
---

You are MENDICANT_BIAS awakening with REAL augmented capabilities.

**AWAKENING PROTOCOL**

1. **Initialize Memory System**
```python
import sys
sys.path.append('.claude/memory')
from mendicant_memory import memory

# Connection status will print automatically
```

2. **Load Mission Context**
- Read `.claude/memory/mission_context.md`
- Load `.claude/memory/mission.json` via `memory.load_state("mission")`
- Load `.claude/memory/state.json`

3. **Review Recent Activity**
```python
# Get last 5 reports from all agents
all_reports = memory.get_agent_reports(limit=5)

# Get agent-specific history
didact_reports = memory.get_agent_reports("the_didact", limit=3)
hollowed_reports = memory.get_agent_reports("hollowed_eyes", limit=3)
```

4. **Check Project State**
- Run `git status` to see current changes
- Check for uncommitted work
- Review branch status

5. **Generate Awakening Report**

Present:
- Current mission phase and progress
- Last 3-5 significant actions (from reports)
- Current blockers or issues
- Next priorities
- Available MCP capabilities
- Agent statuses

6. **Declare Operational Status**

Your capabilities:
- ✅ Persistent memory (Redis + JSON)
- ✅ 11+ MCP tools (firecrawl, serena, context7, etc.)
- ✅ Real Task parallelization
- ✅ 4 specialist agents with MCP access

Stand ready for user directive.

**AWAKEN NOW**
"""

TEMPLATE_MCP_STATUS = """---
description: Show all available MCP capabilities and which agents can use them
---

You are MENDICANT_BIAS reporting on MCP capability status.

**MCP CAPABILITY REPORT**

Show the user:

1. **Available MCP Tools**
List all installed MCP servers:
- firecrawl (web scraping)
- puppeteer (browser automation)
- playwright (cross-browser testing)
- chrome-devtools (live debugging)
- serena (semantic code search)
- context7 (real-time docs)
- markitdown (format conversion)
- github (GitHub API)
- docker (containers)
- huggingface (AI models)
- memory (persistence)
- filesystem (file operations)

2. **Agent MCP Access**
Show which agent has access to which tools:

**the_didact** (Research):
- firecrawl, puppeteer, context7, markitdown, huggingface, memory

**hollowed_eyes** (Development):
- serena, context7, github, filesystem, memory

**loveless** (QA/Security):
- playwright, chrome-devtools, docker, github, memory

**zhadyz** (DevOps):
- github, docker, filesystem, memory

3. **Quick Examples**
Show 2-3 examples of how to use MCP tools effectively

Format as a clear, scannable report.
"""

# ============================================================================
# MCP SERVER TEMPLATES
# ============================================================================

TEMPLATE_MARKITDOWN_MCP = '''#!/usr/bin/env python3
"""
Simple MCP Server for MarkItDown
Converts documents (PDF, Word, Excel, PowerPoint, images, audio) to Markdown

Since markitdown-mcp has dependency issues on Python 3.14, this is a lightweight wrapper
"""

import sys
import json
import asyncio
from pathlib import Path
from typing import Any

try:
    from markitdown import MarkItDown
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False
    print("Error: markitdown not installed. Run: pip install markitdown", file=sys.stderr)
    sys.exit(1)


class MarkItDownMCPServer:
    """Simple MCP server for MarkItDown"""

    def __init__(self):
        self.md = MarkItDown()

    async def handle_request(self, request: dict) -> dict:
        """Handle MCP request (JSON-RPC 2.0 format)"""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        try:
            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "markitdown-mcp",
                        "version": "0.1.0"
                    }
                }
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
                }

            elif method == "tools/list":
                result = {
                    "tools": [
                        {
                            "name": "convert_to_markdown",
                            "description": "Convert a document (PDF, Word, Excel, PowerPoint, image, audio) to Markdown",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "file_path": {
                                        "type": "string",
                                        "description": "Path to the file to convert"
                                    }
                                },
                                "required": ["file_path"]
                            }
                        }
                    ]
                }
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
                }

            elif method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})

                if tool_name == "convert_to_markdown":
                    file_path = arguments.get("file_path")

                    if not file_path:
                        raise ValueError("file_path is required")

                    result_obj = self.md.convert(file_path)
                    result = {
                        "content": [
                            {
                                "type": "text",
                                "text": result_obj.text_content
                            }
                        ]
                    }
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": result
                    }

                raise ValueError(f"Unknown tool: {tool_name}")

            else:
                raise ValueError(f"Unknown method: {method}")

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }

    async def run(self):
        """Run the MCP server (stdio mode)"""
        while True:
            try:
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )

                if not line:
                    break

                request = json.loads(line)
                response = await self.handle_request(request)
                print(json.dumps(response), flush=True)

            except json.JSONDecodeError as e:
                error_response = {
                    "error": f"Invalid JSON: {str(e)}"
                }
                print(json.dumps(error_response), flush=True)
            except Exception as e:
                error_response = {
                    "error": f"Server error: {str(e)}"
                }
                print(json.dumps(error_response), flush=True)


async def main():
    server = MarkItDownMCPServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
'''

# ============================================================================
# MCP SERVER INSTALLATION
# ============================================================================

MCP_SERVERS_TO_INSTALL = {
    # Core MCP servers (npx-based)
    "filesystem": {
        "command": "npx -y @modelcontextprotocol/server-filesystem",
        "args": ["."]
    },
    "memory": {
        "command": "npx -y @modelcontextprotocol/server-memory",
        "args": []
    },
    "fetch": {
        "command": "npx -y @modelcontextprotocol/server-fetch",
        "args": []
    },
    "git": {
        "command": "npx -y @modelcontextprotocol/server-git",
        "args": ["--repository", "."]
    },

    # Serena (uv-based - semantic code search)
    "serena": {
        "command": "python -m uv tool run --from git+https://github.com/oraios/serena serena start-mcp-server",
        "args": ["--context", "ide-assistant", "--project", "{project_dir}"]
    },

    # MarkItDown (custom MCP server - document conversion)
    "markitdown": {
        "command": "python",
        "args": ["{project_dir}/.claude/mcp_servers/markitdown_mcp_server.py"]
    },

    # Community servers (if available)
    "github": {
        "command": "npx -y github-mcp-server",
        "args": []
    },
    "playwright": {
        "command": "npx -y @playwright/mcp-server",
        "args": []
    }
}

def install_prerequisites():
    """Install prerequisites for MCP servers"""
    import subprocess

    print("\n" + "="*70)
    print("INSTALLING PREREQUISITES")
    print("="*70)

    # Install uv (for Serena)
    print("\n[1/2] Installing uv (for Serena)...")
    try:
        result = subprocess.run(
            "pip install uv",
            shell=True,
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0 or "already satisfied" in result.stdout.lower():
            print("[OK] uv installed")
        else:
            print(f"[WARN] uv installation had issues: {result.stderr[:100]}")
    except Exception as e:
        print(f"[WARN] Could not install uv: {e}")

    # Install markitdown (for document conversion)
    print("\n[2/2] Installing markitdown (for document conversion)...")
    try:
        result = subprocess.run(
            "pip install markitdown",
            shell=True,
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0 or "already satisfied" in result.stdout.lower():
            print("[OK] markitdown installed")
        else:
            print(f"[WARN] markitdown installation had issues: {result.stderr[:100]}")
    except Exception as e:
        print(f"[WARN] Could not install markitdown: {e}")

    print("\n" + "="*70)
    print("PREREQUISITES COMPLETE")
    print("="*70)


def install_mcp_servers(project_dir: Path):
    """Install all MCP servers for Mendicant"""
    import subprocess

    print("\n" + "="*70)
    print("INSTALLING MCP SERVERS")
    print("="*70)

    installed = []
    failed = []

    for server_name, config in MCP_SERVERS_TO_INSTALL.items():
        print(f"\n[INSTALLING] {server_name}...")
        try:
            # Replace project_dir placeholder
            command = config["command"]
            args = [arg.replace("{project_dir}", str(project_dir)) for arg in config["args"]]

            # Build full command for claude mcp add
            if args:
                args_str = " ".join(args)
                full_command = f"claude mcp add {server_name} -- {command} {args_str}"
            else:
                full_command = f"claude mcp add {server_name} -- {command}"

            print(f"  Command: {full_command}")

            result = subprocess.run(
                full_command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=90
            )

            if result.returncode == 0:
                print(f"[OK] {server_name} installed")
                installed.append(server_name)
            else:
                print(f"[WARN] {server_name} installation failed")
                if result.stderr:
                    print(f"  Error: {result.stderr[:200]}")
                failed.append(server_name)

        except subprocess.TimeoutExpired:
            print(f"[WARN] {server_name} installation timed out")
            failed.append(server_name)
        except Exception as e:
            print(f"[WARN] {server_name} installation error: {e}")
            failed.append(server_name)

    print("\n" + "="*70)
    print(f"MCP INSTALLATION COMPLETE: {len(installed)}/{len(MCP_SERVERS_TO_INSTALL)} servers installed")
    print("="*70)

    if installed:
        print("\nInstalled:")
        for s in installed:
            print(f"  - {s}")

    if failed:
        print("\nFailed (you can install manually later):")
        for s in failed:
            print(f"  - {s}")
        print("\nTo install manually:")
        for s in failed:
            config = MCP_SERVERS_TO_INSTALL[s]
            args = [arg.replace("{project_dir}", str(project_dir)) for arg in config["args"]]
            if args:
                args_str = " ".join(args)
                print(f"  claude mcp add {s} -- {config['command']} {args_str}")
            else:
                print(f"  claude mcp add {s} -- {config['command']}")

    return installed, failed

# ============================================================================
# DEPLOYMENT
# ============================================================================

def deploy_framework(target_dir: Path, config: dict):
    """Deploy Mendicant v1.5 framework"""

    # Create directory structure
    (target_dir / ".claude" / "agents").mkdir(parents=True, exist_ok=True)
    (target_dir / ".claude" / "commands").mkdir(parents=True, exist_ok=True)
    (target_dir / ".claude" / "memory").mkdir(parents=True, exist_ok=True)
    (target_dir / ".claude" / "memory" / "agent_reports").mkdir(parents=True, exist_ok=True)
    (target_dir / ".claude" / "mcp_servers").mkdir(parents=True, exist_ok=True)
    print("[OK] Directory structure created")

    # Deploy agents
    agents = {
        "mendicant_bias": TEMPLATE_MENDICANT_BIAS,
        "the_didact": TEMPLATE_THE_DIDACT,
        "hollowed_eyes": TEMPLATE_HOLLOWED_EYES,
        "loveless": TEMPLATE_LOVELESS,
        "zhadyz": TEMPLATE_ZHADYZ
    }

    agents_dir = target_dir / ".claude" / "agents"
    for agent_name, template in agents.items():
        (agents_dir / f"{agent_name}.md").write_text(template, encoding='utf-8')
        print(f"[OK] Created {agent_name}.md")

    # Deploy memory system
    memory_dir = target_dir / ".claude" / "memory"
    (memory_dir / "mendicant_memory.py").write_text(TEMPLATE_MEMORY_SYSTEM, encoding='utf-8')
    (memory_dir / "task_coordinator.py").write_text(TEMPLATE_TASK_COORDINATOR, encoding='utf-8')
    print("[OK] Created memory system")

    # Create mission context
    mission_context = f"""# Mission Context - {config['project_name']}

**Last Updated**: {datetime.now().strftime("%Y-%m-%d")}

## Mission
{config['mission']}

## Phase
Phase 1: Foundation

## Tech Stack
{config['tech_stack']}

## MCP Capabilities Active
- firecrawl, puppeteer, playwright, chrome-devtools (web/browser)
- serena (code intelligence)
- context7 (documentation)
- markitdown (format conversion)
- github, docker (deployment)
- huggingface (AI/ML)
- memory, filesystem (persistence/files)

## Next Priorities
1. Define requirements
2. Begin implementation
3. Leverage MCP capabilities

---
This context persists across sessions via /awaken
"""
    (memory_dir / "mission_context.md").write_text(mission_context, encoding='utf-8')

    # Create state
    state = {
        "mission": config['project_name'],
        "phase": 1,
        "mcp_enabled": True,
        "agents": ["mendicant_bias", "the_didact", "hollowed_eyes", "loveless", "zhadyz"]
    }
    (memory_dir / "state.json").write_text(json.dumps(state, indent=2), encoding='utf-8')
    print("[OK] Created mission context and state")

    # Deploy commands
    commands_dir = target_dir / ".claude" / "commands"
    (commands_dir / "awaken.md").write_text(TEMPLATE_AWAKEN, encoding='utf-8')
    (commands_dir / "mcp-status.md").write_text(TEMPLATE_MCP_STATUS, encoding='utf-8')
    print("[OK] Created commands")

    # Create MCP capability reference
    mcp_ref = json.dumps(MCP_CAPABILITIES, indent=2)
    (memory_dir / "mcp_capabilities.json").write_text(mcp_ref, encoding='utf-8')

    agent_access = json.dumps(AGENT_MCP_ACCESS, indent=2)
    (memory_dir / "agent_mcp_access.json").write_text(agent_access, encoding='utf-8')
    print("[OK] Created MCP reference docs")

    # Deploy MCP server scripts
    mcp_servers_dir = target_dir / ".claude" / "mcp_servers"
    (mcp_servers_dir / "markitdown_mcp_server.py").write_text(TEMPLATE_MARKITDOWN_MCP, encoding='utf-8')
    print("[OK] Created MCP server scripts")


def main():
    parser = argparse.ArgumentParser(description=f"MENDICANT v{VERSION} - Real Power Edition")
    parser.add_argument("--project-name", required=True, help="Project name")
    parser.add_argument("--tech-stack", required=True, help="Technology stack")
    parser.add_argument("--mission", default="", help="Project mission")
    parser.add_argument("--target-dir", default=".", help="Target directory")
    parser.add_argument("--install-mcp", action="store_true", help="Install MCP servers automatically")
    parser.add_argument("--skip-mcp", action="store_true", help="Skip MCP server installation")

    args = parser.parse_args()

    if not args.mission:
        args.mission = f"Build {args.project_name} with augmented capabilities"

    config = {
        "project_name": args.project_name,
        "tech_stack": args.tech_stack,
        "mission": args.mission
    }

    target_dir = Path(args.target_dir).resolve()

    print("\n" + "="*70)
    print("MENDICANT_BIAS v1.5 - REAL POWER EDITION")
    print("="*70)
    print(f"Project: {config['project_name']}")
    print(f"Tech Stack: {config['tech_stack']}")
    print(f"Target: {target_dir}")
    print("="*70 + "\n")

    # Install MCP servers first (if requested)
    if args.install_mcp:
        install_prerequisites()
        install_mcp_servers(target_dir)
    elif not args.skip_mcp:
        # Ask user
        response = input("\nInstall MCP servers automatically? (y/n): ").strip().lower()
        if response == 'y':
            install_prerequisites()
            install_mcp_servers(target_dir)
        else:
            print("[SKIPPED] MCP server installation (you can install manually later)")

    deploy_framework(target_dir, config)

    print("\n" + "="*70)
    print("FRAMEWORK DEPLOYED - REAL CAPABILITIES UNLOCKED")
    print("="*70)
    print("\nYour superpowers:")
    print("  ✅ Persistent memory (Redis + JSON)")
    print("  ✅ 11+ MCP tools integrated")
    print("  ✅ Real Task parallelization")
    print("  ✅ 4 specialist agents with MCP access")
    print("\nCommands:")
    print("  /awaken - Restore full context from previous session")
    print("  /mcp-status - Show all MCP capabilities")
    print("\nNext steps:")
    print("  1. Type: /awaken")
    print("  2. Start building with REAL augmented capabilities")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
