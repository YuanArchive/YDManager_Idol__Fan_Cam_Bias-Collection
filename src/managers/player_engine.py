from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class SlotState(str, Enum):
    EMPTY = "empty"
    PRELOADING = "preloading"
    READY = "ready"
    ACTIVE = "active"
    FAILED = "failed"
    STALE = "stale"


class SlotRole(str, Enum):
    CURRENT = "current"
    NEXT = "next"
    PREVIOUS = "previous"
    SPARE = "spare"


@dataclass(frozen=True)
class PlaybackItem:
    path: str
    start_pos: int = 0


@dataclass
class ActivationResult:
    slot_id: int
    path: str
    reused_source: bool
    waiting_for_media: bool
    fallback_required: bool


@dataclass
class PlayerSlot:
    slot_id: int
    mode: str
    player: Any
    audio: Any
    video_item: Any
    expected_path: str | None = None
    expected_generation: int = 0
    state: SlotState = SlotState.EMPTY
    role: SlotRole = SlotRole.SPARE
    last_error: str | None = None
    last_status: Any = None
    requested_start_pos: int = 0
