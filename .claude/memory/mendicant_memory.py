"""
MENDICANT v1.5 - Lightweight Memory System
Redis + JSON for persistent memory across sessions
"""

import redis
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any


class MendicantMemory:
    """Lightweight persistent memory system"""

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
        """Save state to Redis and file"""
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
        """Load state from Redis or file"""
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
        """Save agent completion report"""
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
        """Get recent agent reports"""
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
