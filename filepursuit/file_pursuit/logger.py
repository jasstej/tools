"""
Activity logging module for FilePursuit.

Maintains append-only JSON log of crawl and search activities.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict
from pathlib import Path


class ActivityLogger:
    """Append-only JSON activity logger."""

    def __init__(self, log_path: str = "data/crawl.log"):
        """Initialize activity logger."""
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)

    def log_crawl_started(self, target_id: str, target_url: str) -> None:
        """Log crawl start event."""
        self._append_log({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": "crawl_started",
            "target_id": target_id,
            "target_url": target_url,
        })

    def log_crawl_completed(self, target_id: str, target_url: str,
                           files_discovered: int, files_indexed: int,
                           errors_count: int, duration_seconds: float) -> None:
        """Log crawl completion event."""
        self._append_log({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": "crawl_completed",
            "target_id": target_id,
            "target_url": target_url,
            "files_discovered": files_discovered,
            "files_indexed": files_indexed,
            "errors": errors_count,
            "duration_seconds": duration_seconds,
            "status": "SUCCESS" if errors_count == 0 else "PARTIAL"
        })

    def log_crawl_error(self, target_id: str, target_url: str,
                       error_message: str, duration_seconds: float) -> None:
        """Log crawl error event."""
        self._append_log({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": "crawl_error",
            "target_id": target_id,
            "target_url": target_url,
            "error_message": error_message,
            "duration_seconds": duration_seconds,
            "status": "FAIL"
        })

    def log_search(self, query: str, filters: Dict[str, Any],
                  result_count: int, execution_ms: float,
                  source_ip: str = "127.0.0.1") -> None:
        """Log search query."""
        self._append_log({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event": "search",
            "query": query,
            "filters": filters,
            "result_count": result_count,
            "execution_ms": execution_ms,
            "source_ip": source_ip
        })

    def _append_log(self, entry: Dict[str, Any]) -> None:
        """Append entry to log file."""
        with open(self.log_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_recent_logs(self, limit: int = 100) -> list:
        """Get most recent log entries."""
        if not os.path.exists(self.log_path):
            return []

        entries = []
        with open(self.log_path, "r") as f:
            for line in f:
                if line.strip():
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        return entries[-limit:]
