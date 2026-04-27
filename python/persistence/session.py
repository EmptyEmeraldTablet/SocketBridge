"""
Session Manager — lists, manages, and cleans up recording sessions on disk.
"""

import os
import json
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

DEFAULT_RECORDINGS_DIR = os.environ.get("SOCKETBRIDGE_RECORDINGS_DIR", "./recordings")


@dataclass
class SessionInfo:
    """Lightweight session summary for listing."""
    session_id: str
    path: str
    total_frames: int = 0
    total_messages: int = 0
    duration: float = 0.0
    size_bytes: int = 0

    @property
    def duration_formatted(self) -> str:
        mins, secs = divmod(int(self.duration), 60)
        return f"{mins:02d}:{secs:02d}"

    @property
    def size_formatted(self) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if self.size_bytes < 1024:
                return f"{self.size_bytes:.1f} {unit}"
            self.size_bytes /= 1024
        return f"{self.size_bytes:.1f} TB"


class SessionManager:
    """Manage recording sessions on disk."""

    def __init__(self, directory: str = DEFAULT_RECORDINGS_DIR):
        self.directory = Path(directory)

    def list_sessions(self) -> list[SessionInfo]:
        """List all recording sessions."""
        if not self.directory.exists():
            return []

        sessions = []
        for entry in sorted(self.directory.iterdir(), reverse=True):
            if not entry.is_dir():
                continue
            summary_path = entry / "summary.json"
            if not summary_path.exists():
                continue

            try:
                with open(summary_path, "r") as f:
                    data = json.load(f)
            except Exception:
                continue

            # Calculate total size
            size = sum(
                (entry / f).stat().st_size
                for f in os.listdir(entry)
                if os.path.isfile(entry / f)
            )

            sessions.append(SessionInfo(
                session_id=data.get("session_id", entry.name),
                path=str(entry),
                total_frames=data.get("frames", data.get("total_frames", 0)),
                total_messages=data.get("messages", data.get("total_messages", 0)),
                duration=data.get("duration", 0.0),
                size_bytes=size,
            ))

        return sessions

    def cleanup(self, keep_count: int = 10) -> int:
        """Remove old sessions, keeping the N most recent."""
        sessions = self.list_sessions()
        if len(sessions) <= keep_count:
            return 0

        deleted = 0
        for session in sessions[keep_count:]:
            try:
                import shutil
                shutil.rmtree(session.path)
                deleted += 1
                logger.info("Deleted old session: %s", session.session_id)
            except Exception as e:
                logger.warning("Failed to delete %s: %s", session.session_id, e)

        return deleted

    def get_stats(self) -> dict:
        sessions = self.list_sessions()
        return {
            "total_sessions": len(sessions),
            "total_frames": sum(s.total_frames for s in sessions),
            "total_size": sum(s.size_bytes for s in sessions),
        }


def list_sessions(directory: str = DEFAULT_RECORDINGS_DIR) -> list[SessionInfo]:
    return SessionManager(directory).list_sessions()


def get_latest_session(directory: str = DEFAULT_RECORDINGS_DIR) -> Optional[SessionInfo]:
    sessions = list_sessions(directory)
    return sessions[0] if sessions else None
