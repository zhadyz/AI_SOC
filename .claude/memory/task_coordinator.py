"""
MENDICANT v1.5 - Task Coordination Layer
Enables real Task tool parallelization with shared state
"""

import redis
import json
from typing import List, Dict, Any
from datetime import datetime


class TaskCoordinator:
    """Coordinate parallel Task agents with shared state"""

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
        """Prepare context for spawning a Task agent"""
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
        """Get context for an agent (called by the agent itself)"""
        if self.redis_available:
            try:
                data = self.redis_client.get(f"mendicant:task:{agent_name}")
                if data:
                    return json.loads(data)
            except Exception:
                pass

        return {}

    def mark_task_complete(self, agent_name: str, result: Dict):
        """Mark task as complete and save result"""
        from mendicant_memory import memory

        memory.save_agent_report(agent_name, result)

        if self.redis_available:
            try:
                self.redis_client.delete(f"mendicant:task:{agent_name}")
            except Exception:
                pass


# Global instance
coordinator = TaskCoordinator()
