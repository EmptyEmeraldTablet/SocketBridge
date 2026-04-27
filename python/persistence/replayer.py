"""
Session Replayer — replays recorded sessions with frame-accurate seeking.
"""

import gzip
import json
import logging
from pathlib import Path
from typing import Optional, Iterator
from dataclasses import dataclass, field

from protocol.messages import RawMessage, SessionMetadata

logger = logging.getLogger(__name__)


@dataclass
class ReplayerConfig:
    recordings_dir: str = "./recordings"
    session_id: Optional[str] = None


@dataclass
class LoadedSession:
    session_id: str
    metadata: SessionMetadata
    message_files: list[Path] = field(default_factory=list)
    total_messages: int = 0


class SessionReplayer:
    """
    Replays recorded sessions with streaming message iteration.

    Usage:
        replayer = SessionReplayer()
        session = replayer.load_session("session_20260202_234038")
        for msg in replayer.iter_messages():
            print(msg.frame, msg.type)
    """

    def __init__(self, config: Optional[ReplayerConfig] = None):
        self.config = config or ReplayerConfig()
        self.recordings_dir = Path(self.config.recordings_dir)
        self._session: Optional[LoadedSession] = None

    def load_session(self, session_id: str) -> LoadedSession:
        session_dir = self.recordings_dir / session_id
        if not session_dir.exists():
            raise FileNotFoundError(f"Session not found: {session_dir}")

        # Load metadata
        meta_path = session_dir / "metadata.json"
        if meta_path.exists():
            with open(meta_path, "r") as f:
                metadata = SessionMetadata(**json.load(f))
        else:
            metadata = SessionMetadata(session_id=session_id)

        # Find message files
        message_files = sorted(
            [f for f in session_dir.iterdir()
             if f.name.startswith("messages_") and f.name.endswith((".jsonl", ".jsonl.gz"))],
            key=lambda f: f.name,
        )

        # Count total messages
        total = 0
        for fp in message_files:
            try:
                total += sum(1 for _ in self._read_file(fp))
            except Exception:
                pass

        self._session = LoadedSession(
            session_id=session_id,
            metadata=metadata,
            message_files=message_files,
            total_messages=total,
        )
        logger.info("Loaded session %s: %d messages in %d files",
                     session_id, total, len(message_files))
        return self._session

    def iter_messages(self) -> Iterator[RawMessage]:
        """Iterate all messages in frame order."""
        if not self._session:
            raise RuntimeError("No session loaded")
        for fp in self._session.message_files:
            for msg in self._read_file(fp):
                yield msg

    def iter_frames(self) -> Iterator[list[RawMessage]]:
        """Iterate messages grouped by frame."""
        current_frame = -1
        buffer: list[RawMessage] = []
        for msg in self.iter_messages():
            if msg.frame != current_frame:
                if buffer:
                    yield buffer
                buffer = []
                current_frame = msg.frame
            buffer.append(msg)
        if buffer:
            yield buffer

    def get_frame_range(self) -> tuple[int, int]:
        """Get first and last frame numbers."""
        if not self._session:
            return (0, 0)
        first = None
        last = 0
        for msg in self.iter_messages():
            if first is None:
                first = msg.frame
            last = msg.frame
        return (first or 0, last)

    def _read_file(self, path: Path) -> Iterator[RawMessage]:
        """Read messages from a single file."""
        if path.suffix == ".gz":
            opener = gzip.open
        else:
            opener = open

        with opener(path, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield RawMessage.from_json_line(line)
                except Exception as e:
                    logger.warning("Parse error in %s: %s", path.name, e)
