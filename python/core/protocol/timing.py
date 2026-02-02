from dataclasses import dataclass, field
from typing import Dict, Optional, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class TimingIssueType(Enum):
    FRAME_GAP = "frame_gap"
    FRAME_JUMP = "frame_jump"
    OUT_OF_ORDER = "out_of_order"
    STALE_DATA = "stale_data"
    CHANNEL_DESYNC = "channel_desync"


@dataclass
class ChannelTimingInfo:
    channel: str
    collect_frame: int
    collect_time: int
    interval: str
    stale_frames: int = 0

    @property
    def is_stale(self) -> bool:
        interval_frames = {
            "HIGH": 1,
            "MEDIUM": 5,
            "LOW": 30,
            "RARE": 90,
            "ON_CHANGE": 60,
        }
        threshold = interval_frames.get(self.interval, 30) * 2
        return self.stale_frames > threshold


@dataclass
class MessageTimingInfo:
    seq: int
    frame: int
    game_time: int
    prev_frame: int
    channel_meta: Dict[str, ChannelTimingInfo] = field(default_factory=dict)

    @classmethod
    def from_message(cls, msg: dict) -> "MessageTimingInfo":
        channel_meta = {}
        for name, meta in msg.get("channel_meta", {}).items():
            channel_meta[name] = ChannelTimingInfo(
                channel=name,
                collect_frame=meta.get("collect_frame", msg.get("frame", 0)),
                collect_time=meta.get("collect_time", msg.get("timestamp", 0)),
                interval=meta.get("interval", "UNKNOWN"),
                stale_frames=meta.get("stale_frames", 0),
            )

        return cls(
            seq=msg.get("seq", 0),
            frame=msg.get("frame", 0),
            game_time=msg.get("game_time", msg.get("timestamp", 0)),
            prev_frame=msg.get("prev_frame", 0),
            channel_meta=channel_meta,
        )


@dataclass
class TimingIssue:
    issue_type: TimingIssueType
    frame: int
    seq: int
    details: Dict
    severity: str = "warning"


class TimingMonitor:
    def __init__(self):
        self.last_seq = 0
        self.last_frame = 0
        self.expected_frame_gap = 1
        self.issues: List[TimingIssue] = []

        self.total_messages = 0
        self.frame_gaps = 0
        self.out_of_order = 0
        self.stale_channels = 0

    def check_message(self, timing: MessageTimingInfo) -> List[TimingIssue]:
        issues = []
        self.total_messages += 1

        if timing.seq > 0 and self.last_seq > 0:
            if timing.seq != self.last_seq + 1:
                if timing.seq <= self.last_seq:
                    issues.append(
                        TimingIssue(
                            issue_type=TimingIssueType.OUT_OF_ORDER,
                            frame=timing.frame,
                            seq=timing.seq,
                            details={
                                "expected_seq": self.last_seq + 1,
                                "actual_seq": timing.seq,
                            },
                            severity="error",
                        )
                    )
                    self.out_of_order += 1
                else:
                    gap = timing.seq - self.last_seq - 1
                    issues.append(
                        TimingIssue(
                            issue_type=TimingIssueType.FRAME_GAP,
                            frame=timing.frame,
                            seq=timing.seq,
                            details={
                                "missing_count": gap,
                                "last_seq": self.last_seq,
                            },
                            severity="warning",
                        )
                    )

        if self.last_frame > 0:
            frame_gap = timing.frame - self.last_frame

            if frame_gap <= 0:
                issues.append(
                    TimingIssue(
                        issue_type=TimingIssueType.OUT_OF_ORDER,
                        frame=timing.frame,
                        seq=timing.seq,
                        details={
                            "last_frame": self.last_frame,
                            "current_frame": timing.frame,
                        },
                        severity="error",
                    )
                )
            elif frame_gap > 5:
                issues.append(
                    TimingIssue(
                        issue_type=TimingIssueType.FRAME_JUMP,
                        frame=timing.frame,
                        seq=timing.seq,
                        details={
                            "frame_gap": frame_gap,
                            "last_frame": self.last_frame,
                        },
                        severity="warning" if frame_gap < 30 else "error",
                    )
                )
                self.frame_gaps += 1

        for channel_name, channel_timing in timing.channel_meta.items():
            if channel_timing.is_stale:
                issues.append(
                    TimingIssue(
                        issue_type=TimingIssueType.STALE_DATA,
                        frame=timing.frame,
                        seq=timing.seq,
                        details={
                            "channel": channel_name,
                            "stale_frames": channel_timing.stale_frames,
                            "collect_frame": channel_timing.collect_frame,
                            "interval": channel_timing.interval,
                        },
                        severity="info",
                    )
                )
                self.stale_channels += 1

        high_freq_channels = [
            (name, meta)
            for name, meta in timing.channel_meta.items()
            if meta.interval == "HIGH"
        ]
        if len(high_freq_channels) > 1:
            frames = [meta.collect_frame for _, meta in high_freq_channels]
            if max(frames) - min(frames) > 1:
                issues.append(
                    TimingIssue(
                        issue_type=TimingIssueType.CHANNEL_DESYNC,
                        frame=timing.frame,
                        seq=timing.seq,
                        details={
                            "channels": {
                                name: meta.collect_frame
                                for name, meta in high_freq_channels
                            },
                        },
                        severity="warning",
                    )
                )

        self.last_seq = timing.seq
        self.last_frame = timing.frame
        self.issues.extend(issues)

        return issues

    def get_stats(self) -> Dict:
        return {
            "total_messages": self.total_messages,
            "frame_gaps": self.frame_gaps,
            "out_of_order": self.out_of_order,
            "stale_channels": self.stale_channels,
            "issue_rate": len(self.issues) / max(self.total_messages, 1),
        }
