from __future__ import annotations

import os
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

    def clear(self) -> None:
        self.player.stop()
        self.player.setSource(_empty_qurl())
        self.audio.setMuted(True)
        self.video_item.setOpacity(0.0)
        self.video_item.setZValue(0.0)
        self.expected_path = None
        self.expected_generation = 0
        self.state = SlotState.EMPTY
        self.role = SlotRole.SPARE
        self.last_error = None
        self.last_status = None
        self.requested_start_pos = 0


def _empty_qurl():
    try:
        from PyQt6.QtCore import QUrl

        return QUrl()
    except Exception:
        return None


def _source_path(player: Any) -> str:
    try:
        source = player.source()
        if source and hasattr(source, "toLocalFile"):
            return os.path.normpath(source.toLocalFile())
    except Exception:
        return ""
    return ""


def source_matches_path(slot: PlayerSlot, path: str) -> bool:
    source_path = _source_path(slot.player)
    if not source_path or not path:
        return False
    return os.path.normcase(source_path) == os.path.normcase(os.path.normpath(path))
