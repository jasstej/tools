"""Structured activity logging."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional


class ActivityLogger:
    """Structured JSON activity logging."""

    def __init__(self, log_file: Path):
        """
        Initialize activity logger.

        Args:
            log_file: Path to append-only activity log
        """
        self.log_file = Path(log_file)
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def log(
        self,
        action: str,
        user_token: str,
        source_ip: str,
        file: str = None,
        status: str = "SUCCESS",
        details: dict = None,
    ) -> None:
        """
        Log an activity.

        Args:
            action: Action type (download, upload, list_dir, etc)
            user_token: User's access token
            source_ip: Source IP address
            file: File or path involved
            status: SUCCESS, FAIL, or WARNING
            details: Additional JSON data
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": action,
            "user_token": user_token[:8] + "..." if user_token else "unknown",
            "source_ip": source_ip,
            "file": file,
            "status": status,
            "details": details or {},
        }

        try:
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logging.warning(f"Could not write activity log: {e}")

    def download(
        self, user_token: str, source_ip: str, file_path: str, size: int
    ) -> None:
        """Log a file download."""
        self.log(
            "download",
            user_token,
            source_ip,
            file_path,
            "SUCCESS",
            {"size_bytes": size},
        )

    def upload(
        self, user_token: str, source_ip: str, file_path: str, size: int
    ) -> None:
        """Log a file upload."""
        self.log(
            "upload",
            user_token,
            source_ip,
            file_path,
            "SUCCESS",
            {"size_bytes": size},
        )

    def list_dir(self, user_token: str, source_ip: str, dir_path: str) -> None:
        """Log directory listing."""
        self.log("list_dir", user_token, source_ip, dir_path, "SUCCESS")

    def auth_fail(self, source_ip: str, reason: str) -> None:
        """Log authentication failure."""
        self.log("auth", None, source_ip, None, "FAIL", {"reason": reason})

    def create_folder(self, user_token: str, source_ip: str, folder_path: str) -> None:
        """Log folder creation."""
        self.log("create_folder", user_token, source_ip, folder_path, "SUCCESS")

    def get_logs(self, limit: int = 100) -> list[dict]:
        """
        Get recent activity logs.

        Args:
            limit: Number of recent entries to return

        Returns:
            List of log entries
        """
        if not self.log_file.exists():
            return []

        logs = []
        try:
            with open(self.log_file) as f:
                lines = f.readlines()
                for line in lines[-limit:]:
                    try:
                        entry = json.loads(line)
                        logs.append(entry)
                    except json.JSONDecodeError:
                        pass
        except Exception:
            pass

        return logs
