"""
Session Recorder — records game data messages to disk with compression.
"""

import gzip
import json
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

from protocol.messages import RawMessage, SessionMetadata

logger = logging.getLogger(__name__)


@dataclass
class RecorderConfig:
    output_dir: str = "./recordings"
    buffer_size: int = 500
    auto_flush_interval: float = 30.0
    compress: bool = True
    include_events: bool = True


@dataclass
class ActiveSession:
    session_id: str
    output_dir: Path
    metadata: SessionMetadata
    start_frame: int = 0
    current_frame: int = 0
    message_buffer: list[RawMessage] = field(default_factory=list)
    messages_recorded: int = 0
    events_recorded: int = 0
    frames_recorded: int = 0
    bytes_written: int = 0


class SessionRecorder:
    """
    Records game data messages to compressed JSONL files.

    Usage:
        recorder = SessionRecorder()
        recorder.start_session()
        recorder.record(msg)    # call for each message
        recorder.stop_session()
    """

    def __init__(self, config: Optional[RecorderConfig] = None):
        self.config = config or RecorderConfig()
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._session: Optional[ActiveSession] = None

    @property
    def is_recording(self) -> bool:
        return self._session is not None

    def start_session(self, session_id: Optional[str] = None,
                      metadata: Optional[dict] = None) -> ActiveSession:
        """Begin a new recording session."""
        if self._session:
            self.stop_session()

        session_id = session_id or datetime.now().strftime("session_%Y%m%d_%H%M%S")
        session_dir = self.output_dir / session_id
        session_dir.mkdir(parents=True, exist_ok=True)

        self._session = ActiveSession(
            session_id=session_id,
            output_dir=session_dir,
            metadata=SessionMetadata(
                session_id=session_id,
                start_time=time.time(),
                metadata=metadata or {},
            ),
        )
        logger.info("Recording started: %s", session_id)
        return self._session

    # Backward compat aliases
    @property
    def current_session(self):
        return self._session

    def record_message(self, message: RawMessage) -> bool:
        """Backward compat: Record a single message."""
        return self.record(message)

    def record(self, message: RawMessage) -> bool:
        """Record a single message."""
        if not self._session:
            return False

        s = self._session
        if message.is_event:
            if self.config.include_events:
                s.events_recorded += 1
            else:
                return True

        s.message_buffer.append(message)
        s.messages_recorded += 1
        if message.frame > s.current_frame:
            s.current_frame = message.frame
            s.frames_recorded += 1

        if len(s.message_buffer) >= self.config.buffer_size:
            self.flush()

        return True

    def flush(self):
        """Write buffered messages to disk."""
        if not self._session or not self._session.message_buffer:
            return

        s = self._session
        ts = int(time.time() * 1000)
        filename = f"messages_{ts}.jsonl"
        if self.config.compress:
            filename += ".gz"
            filepath = s.output_dir / filename
            with gzip.open(filepath, "wt", encoding="utf-8") as f:
                for msg in s.message_buffer:
                    f.write(msg.to_json_line())
        else:
            filepath = s.output_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                for msg in s.message_buffer:
                    f.write(msg.to_json_line())

        s.bytes_written += filepath.stat().st_size
        logger.debug("Flushed %d messages to %s", len(s.message_buffer), filename)
        s.message_buffer.clear()

    def stop_session(self) -> Optional[SessionMetadata]:
        """Stop recording and finalize session."""
        if not self._session:
            return None

        self.flush()
        s = self._session

        s.metadata.end_time = time.time()
        s.metadata.duration = s.metadata.end_time - s.metadata.start_time
        s.metadata.total_frames = s.frames_recorded
        s.metadata.total_messages = s.messages_recorded
        s.metadata.total_events = s.events_recorded

        # Save metadata
        with open(s.output_dir / "metadata.json", "w", encoding="utf-8") as f:
            json.dump(s.metadata.model_dump(), f, indent=2, ensure_ascii=False)

        # Save summary
        summary = {
            "session_id": s.session_id,
            "frames": s.frames_recorded,
            "messages": s.messages_recorded,
            "events": s.events_recorded,
            "bytes": s.bytes_written,
            "duration": s.metadata.duration,
            "start_frame": s.start_frame,
            "end_frame": s.current_frame,
        }
        with open(s.output_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        logger.info(
            "Recording stopped: %s — %d frames, %d msgs, %s",
            s.session_id, s.frames_recorded, s.messages_recorded,
            s.metadata.duration_formatted,
        )

        meta = s.metadata
        self._session = None
        return meta
