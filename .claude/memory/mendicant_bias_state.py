"""
MENDICANT_BIAS State Manager
Persistent memory and state management for the supreme orchestrator
"""

import redis
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


class MendicantBiasMemory:
    """
    Persistent memory system for mendicant_bias orchestrator

    Provides:
    - Redis-backed state storage
    - File-based memory persistence
    - Agent report archival
    - Mission context tracking
    - Roadmap and decision logging
    """

    def __init__(self, redis_host: str = "localhost", redis_port: int = 6379, redis_db: int = 0):
        """Initialize memory system"""

        # Redis connection
        try:
            self.redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                decode_responses=True,
                socket_connect_timeout=2
            )
            # Test connection
            self.redis_client.ping()
            self.redis_available = True
            print(f"[OK] Connected to Redis at {redis_host}:{redis_port}")
        except (redis.ConnectionError, redis.TimeoutError) as e:
            print(f"[WARN] Redis not available: {e}")
            print(f"[WARN] Falling back to file-only storage")
            self.redis_available = False
            self.redis_client = None

        # Memory paths
        self.memory_dir = Path(".claude/memory")
        self.reports_dir = self.memory_dir / "agent_reports"

        # Ensure directories exist
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

        # State keys
        self.MISSION_KEY = "mendicant_bias:mission_context"
        self.PROJECT_KEY = "mendicant_bias:project_state"
        self.ROADMAP_KEY = "mendicant_bias:roadmap"
        self.METRICS_KEY = "mendicant_bias:metrics"
        self.AGENT_STATUS_KEY = "mendicant_bias:agent_status"

    # ==================== CORE STATE OPERATIONS ====================

    def save_state(self, key: str, data: Dict[str, Any]) -> bool:
        """Save state to both Redis and file"""
        timestamp = datetime.utcnow().isoformat()
        data["last_updated"] = timestamp

        success = True

        # Save to Redis
        if self.redis_available:
            try:
                self.redis_client.set(key, json.dumps(data))
            except Exception as e:
                print(f"[WARN] Redis save failed: {e}")
                success = False

        # Save to file (backup)
        file_path = self.memory_dir / f"{key.replace(':', '_')}.json"
        try:
            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[WARN] File save failed: {e}")
            success = False

        return success

    def load_state(self, key: str) -> Optional[Dict[str, Any]]:
        """Load state from Redis or file fallback"""

        # Try Redis first
        if self.redis_available:
            try:
                data = self.redis_client.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                print(f"[WARN] Redis load failed: {e}")

        # Fallback to file
        file_path = self.memory_dir / f"{key.replace(':', '_')}.json"
        if file_path.exists():
            try:
                with open(file_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARN] File load failed: {e}")

        return None

    # ==================== AGENT REPORTS ====================

    def save_agent_report(self, agent_name: str, report: Dict[str, Any]) -> str:
        """
        Save agent completion report to file and index in Redis
        Returns: Report file path
        """
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        task_name = report.get("task", "unknown_task").replace(" ", "_").lower()

        filename = f"{timestamp}_{agent_name}_{task_name}.json"
        file_path = self.reports_dir / filename

        # Add metadata
        report["agent"] = agent_name
        report["timestamp"] = datetime.utcnow().isoformat()
        report["report_id"] = filename

        # Save report file
        with open(file_path, 'w') as f:
            json.dump(report, f, indent=2)

        # Index in Redis
        if self.redis_available:
            try:
                # Add to agent's report list
                self.redis_client.lpush(f"mendicant_bias:reports:{agent_name}", filename)
                # Add to global report list
                self.redis_client.lpush("mendicant_bias:reports:all", filename)
            except Exception as e:
                print(f"[WARN] Redis indexing failed: {e}")

        return str(file_path)

    def get_agent_reports(self, agent_name: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent agent reports"""
        reports = []

        if self.redis_available and agent_name:
            try:
                # Get from Redis index
                report_ids = self.redis_client.lrange(
                    f"mendicant_bias:reports:{agent_name}",
                    0,
                    limit - 1
                )
                for report_id in report_ids:
                    file_path = self.reports_dir / report_id
                    if file_path.exists():
                        with open(file_path, 'r') as f:
                            reports.append(json.load(f))
                return reports
            except Exception as e:
                print(f"[WARN] Redis query failed: {e}")

        # Fallback: scan directory
        report_files = sorted(self.reports_dir.glob("*.json"), reverse=True)

        if agent_name:
            report_files = [f for f in report_files if agent_name in f.name]

        for file_path in report_files[:limit]:
            try:
                with open(file_path, 'r') as f:
                    reports.append(json.load(f))
            except Exception as e:
                print(f"[WARN] Failed to load {file_path}: {e}")

        return reports

    # ==================== AGENT ADAPTATION TRACKING ====================

    def track_adaptation(self, agent_name: str, changes: List[str], trigger: str, rationale: str) -> bool:
        """Track agent adaptation event"""
        adaptation = {
            "agent": agent_name,
            "timestamp": datetime.utcnow().isoformat(),
            "changes": changes,
            "trigger": trigger,
            "rationale": rationale
        }

        # Save as agent report
        report = {
            "task": f"Agent Adaptation: {agent_name}",
            "status": "COMPLETED",
            "summary": {
                "agent_adapted": agent_name,
                "changes": changes,
                "trigger": trigger,
                "rationale": rationale
            }
        }
        self.save_agent_report("mendicant_bias", report)

        # Also store in Redis list for quick queries
        if self.redis_available:
            try:
                self.redis_client.lpush(
                    "mendicant_bias:adaptations",
                    json.dumps(adaptation)
                )
                # Keep only last 50 adaptations
                self.redis_client.ltrim("mendicant_bias:adaptations", 0, 49)
            except Exception as e:
                print(f"[WARN] Redis adaptation tracking failed: {e}")

        return True

    def analyze_agent_patterns(self, agent_name: str, issue_type: str, lookback: int = 10) -> int:
        """Analyze how many times a specific issue type has appeared in agent reports"""
        reports = self.get_agent_reports(agent_name, limit=lookback)
        count = 0

        issue_keywords = {
            "security": ["vulnerability", "security", "auth", "injection", "xss", "csrf"],
            "performance": ["slow", "latency", "timeout", "performance", "bottleneck"],
            "quality": ["bug", "error", "fail", "crash", "exception"],
            "test": ["test fail", "coverage", "assertion"]
        }

        keywords = issue_keywords.get(issue_type.lower(), [issue_type.lower()])

        for report in reports:
            report_text = json.dumps(report).lower()
            if any(keyword in report_text for keyword in keywords):
                count += 1

        return count

    def should_trigger_adaptation(self, agent_name: str, issue_type: str, threshold: int = 3) -> bool:
        """Determine if an agent should be adapted based on pattern analysis"""
        pattern_count = self.analyze_agent_patterns(agent_name, issue_type)
        return pattern_count >= threshold

    # ==================== AWAKENING ====================

    def generate_awakening_report(self) -> str:
        """Generate comprehensive awakening report for mendicant_bias"""
        return "MENDICANT_BIAS READY - Memory system operational"


# Global memory instance
try:
    memory = MendicantBiasMemory(
        redis_host=os.getenv("REDIS_HOST", "localhost"),
        redis_port=int(os.getenv("REDIS_PORT", "6379")),
        redis_db=int(os.getenv("REDIS_DB", "0"))
    )
except Exception as e:
    print(f"[ERROR] Failed to initialize memory: {e}")
    memory = None
