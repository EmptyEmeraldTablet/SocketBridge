from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from collections import deque
import time
import logging

from ..core.protocol.timing import ChannelTimingInfo, MessageTimingInfo

logger = logging.getLogger(__name__)


@dataclass
class ChannelState:
    data: Any
    collect_frame: int
    collect_time: int
    receive_frame: int
    receive_time: float
    is_stale: bool = False


class TimingAwareStateManager:
    def __init__(self, max_history: int = 300):
        self.channels: Dict[str, ChannelState] = {}
        self.history: Dict[str, deque] = {}
        self.max_history = max_history
        self.current_frame = 0

    def update_channel(
        self, channel: str, data: Any, timing: ChannelTimingInfo, current_frame: int
    ):
        state = ChannelState(
            data=data,
            collect_frame=timing.collect_frame,
            collect_time=timing.collect_time,
            receive_frame=current_frame,
            receive_time=time.time(),
            is_stale=timing.is_stale,
        )

        if channel not in self.history:
            self.history[channel] = deque(maxlen=self.max_history)
        self.history[channel].append(state)

        self.channels[channel] = state
        self.current_frame = max(self.current_frame, current_frame)

    def get_channel(self, channel: str) -> Optional[ChannelState]:
        return self.channels.get(channel)

    def get_channel_data(self, channel: str) -> Optional[Any]:
        state = self.channels.get(channel)
        return state.data if state else None

    def is_channel_fresh(self, channel: str, max_stale_frames: int = 5) -> bool:
        state = self.channels.get(channel)
        if not state:
            return False
        return (self.current_frame - state.collect_frame) <= max_stale_frames

    def get_channel_age(self, channel: str) -> int:
        state = self.channels.get(channel)
        if not state:
            return -1
        return self.current_frame - state.collect_frame

    def get_synchronized_snapshot(
        self, channels: List[str], max_frame_diff: int = 5
    ) -> Optional[Dict[str, Any]]:
        states = []
        for channel in channels:
            state = self.channels.get(channel)
            if not state:
                return None
            states.append((channel, state))

        frames = [s.collect_frame for _, s in states]
        if max(frames) - min(frames) > max_frame_diff:
            logger.warning(f"Channels not synchronized: {dict(zip(channels, frames))}")
            return None

        return {channel: state.data for channel, state in states}

    def get_state_at_frame(self, channel: str, target_frame: int) -> Optional[Any]:
        history = self.history.get(channel, [])

        best_match = None
        best_diff = float("inf")

        for state in history:
            diff = abs(state.collect_frame - target_frame)
            if diff < best_diff:
                best_diff = diff
                best_match = state

        return best_match.data if best_match else None
