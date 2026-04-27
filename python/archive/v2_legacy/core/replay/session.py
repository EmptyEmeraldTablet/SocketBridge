"""
Core Replay Session Manager - 会话管理

提供录制会话的查询和管理功能：
- 列出所有会话
- 按时间/大小排序
- 清理旧会话
- 会话元数据查询
"""

import os
import json
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

from .message import SessionMetadata

logger = logging.getLogger(__name__)

# 默认录制目录
DEFAULT_RECORDINGS_DIR = os.environ.get("SOCKETBRIDGE_RECORDINGS_DIR", "./recordings")


@dataclass
class SessionInfo:
    """会话信息摘要"""

    session_id: str
    path: Path
    start_time: float = 0.0
    duration: float = 0.0
    total_frames: int = 0
    total_messages: int = 0
    size_bytes: int = 0
    protocol_version: str = "2.0"

    @property
    def start_datetime(self) -> datetime:
        """开始时间"""
        return datetime.fromtimestamp(self.start_time) if self.start_time else datetime.now()

    @property
    def duration_formatted(self) -> str:
        """格式化持续时间"""
        mins, secs = divmod(int(self.duration), 60)
        return f"{mins:02d}:{secs:02d}"

    @property
    def size_formatted(self) -> str:
        """格式化大小"""
        if self.size_bytes < 1024:
            return f"{self.size_bytes} B"
        elif self.size_bytes < 1024 * 1024:
            return f"{self.size_bytes / 1024:.1f} KB"
        else:
            return f"{self.size_bytes / (1024 * 1024):.1f} MB"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "path": str(self.path),
            "start_time": self.start_time,
            "duration": self.duration,
            "total_frames": self.total_frames,
            "total_messages": self.total_messages,
            "size_bytes": self.size_bytes,
            "protocol_version": self.protocol_version,
        }


class SessionManager:
    """
    会话管理器

    使用示例：
    ```python
    from core.replay import SessionManager

    manager = SessionManager()

    # 列出所有会话
    for session in manager.list_sessions():
        print(f"{session.session_id}: {session.duration_formatted}")

    # 获取最新会话
    latest = manager.get_latest()

    # 删除旧会话
    manager.cleanup(keep_count=10)
    ```
    """

    def __init__(self, recordings_dir: Optional[str] = None):
        self.recordings_dir = Path(recordings_dir or DEFAULT_RECORDINGS_DIR)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)

    def list_sessions(
        self,
        sort_by: str = "time",
        reverse: bool = True,
    ) -> List[SessionInfo]:
        """
        列出所有会话

        Args:
            sort_by: 排序方式 - "time", "size", "frames", "duration"
            reverse: 是否降序

        Returns:
            会话信息列表
        """
        sessions = []

        for item in self.recordings_dir.iterdir():
            if not item.is_dir():
                continue

            # 跳过特殊目录
            if item.name.startswith(".") or item.name.startswith("_"):
                continue

            session_info = self._load_session_info(item)
            if session_info:
                sessions.append(session_info)

        # 排序
        if sort_by == "time":
            sessions.sort(key=lambda s: s.start_time, reverse=reverse)
        elif sort_by == "size":
            sessions.sort(key=lambda s: s.size_bytes, reverse=reverse)
        elif sort_by == "frames":
            sessions.sort(key=lambda s: s.total_frames, reverse=reverse)
        elif sort_by == "duration":
            sessions.sort(key=lambda s: s.duration, reverse=reverse)

        return sessions

    def _load_session_info(self, session_dir: Path) -> Optional[SessionInfo]:
        """加载会话信息"""
        try:
            session_id = session_dir.name

            # 计算目录大小
            size_bytes = sum(f.stat().st_size for f in session_dir.rglob("*") if f.is_file())

            # 尝试加载元数据
            metadata_path = session_dir / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return SessionInfo(
                    session_id=session_id,
                    path=session_dir,
                    start_time=data.get("start_time", 0),
                    duration=data.get("duration", 0),
                    total_frames=data.get("total_frames", 0),
                    total_messages=data.get("total_messages", 0),
                    size_bytes=size_bytes,
                    protocol_version=data.get("protocol_version", "2.0"),
                )

            # 尝试旧格式元数据
            meta_files = list(session_dir.glob("*_meta.json"))
            if meta_files:
                with open(meta_files[0], "r", encoding="utf-8") as f:
                    data = json.load(f)
                return SessionInfo(
                    session_id=session_id,
                    path=session_dir,
                    start_time=data.get("start_time", 0),
                    duration=data.get("duration", 0),
                    total_frames=data.get("total_frames", 0),
                    total_messages=data.get("total_messages", 0),
                    size_bytes=size_bytes,
                )

            # 尝试从摘要加载
            summary_path = session_dir / "summary.json"
            if summary_path.exists():
                with open(summary_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return SessionInfo(
                    session_id=session_id,
                    path=session_dir,
                    start_time=session_dir.stat().st_ctime,
                    duration=data.get("duration", 0),
                    total_frames=data.get("frames", 0),
                    total_messages=data.get("messages", 0),
                    size_bytes=size_bytes,
                )

            # 无元数据，使用目录信息
            return SessionInfo(
                session_id=session_id,
                path=session_dir,
                start_time=session_dir.stat().st_ctime,
                size_bytes=size_bytes,
            )

        except Exception as e:
            logger.warning(f"加载会话信息失败 {session_dir}: {e}")
            return None

    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """获取指定会话信息"""
        session_dir = self.recordings_dir / session_id

        if not session_dir.exists():
            # 模糊匹配
            matches = list(self.recordings_dir.glob(f"*{session_id}*"))
            if matches:
                session_dir = matches[0]
            else:
                return None

        return self._load_session_info(session_dir)

    def get_latest(self) -> Optional[SessionInfo]:
        """获取最新会话"""
        sessions = self.list_sessions(sort_by="time", reverse=True)
        return sessions[0] if sessions else None

    def get_oldest(self) -> Optional[SessionInfo]:
        """获取最旧会话"""
        sessions = self.list_sessions(sort_by="time", reverse=False)
        return sessions[0] if sessions else None

    def delete_session(self, session_id: str) -> bool:
        """删除会话"""
        session = self.get_session(session_id)
        if not session:
            return False

        try:
            shutil.rmtree(session.path)
            logger.info(f"删除会话: {session_id}")
            return True
        except Exception as e:
            logger.error(f"删除会话失败 {session_id}: {e}")
            return False

    def cleanup(
        self,
        keep_count: int = 10,
        keep_days: Optional[int] = None,
        max_size_mb: Optional[float] = None,
    ) -> int:
        """
        清理旧会话

        Args:
            keep_count: 保留最新的会话数量
            keep_days: 保留最近 N 天的会话
            max_size_mb: 最大总大小（MB）

        Returns:
            删除的会话数量
        """
        sessions = self.list_sessions(sort_by="time", reverse=True)
        deleted = 0

        # 按数量保留
        for session in sessions[keep_count:]:
            if keep_days is not None:
                # 检查时间
                age_days = (datetime.now() - session.start_datetime).days
                if age_days <= keep_days:
                    continue

            if self.delete_session(session.session_id):
                deleted += 1

        # 按大小限制
        if max_size_mb is not None:
            max_size_bytes = max_size_mb * 1024 * 1024
            sessions = self.list_sessions(sort_by="time", reverse=True)
            total_size = 0

            for session in sessions:
                total_size += session.size_bytes
                if total_size > max_size_bytes:
                    if self.delete_session(session.session_id):
                        deleted += 1

        logger.info(f"清理完成，删除 {deleted} 个会话")
        return deleted

    def get_total_size(self) -> int:
        """获取总大小（字节）"""
        sessions = self.list_sessions()
        return sum(s.size_bytes for s in sessions)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        sessions = self.list_sessions()
        return {
            "total_sessions": len(sessions),
            "total_size": self.get_total_size(),
            "total_frames": sum(s.total_frames for s in sessions),
            "total_messages": sum(s.total_messages for s in sessions),
            "total_duration": sum(s.duration for s in sessions),
        }


# 便捷函数
def list_sessions(
    recordings_dir: Optional[str] = None,
    sort_by: str = "time",
) -> List[SessionInfo]:
    """列出所有会话"""
    manager = SessionManager(recordings_dir)
    return manager.list_sessions(sort_by=sort_by)


def get_latest_session(
    recordings_dir: Optional[str] = None,
) -> Optional[SessionInfo]:
    """获取最新会话"""
    manager = SessionManager(recordings_dir)
    return manager.get_latest()
