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


def _qurl_from_path(path: str):
    try:
        from PyQt6.QtCore import QUrl

        return QUrl.fromLocalFile(path)
    except Exception:
        class FakeUrl:
            def __init__(self, value):
                self.value = value

            def toLocalFile(self):
                return self.value

        return FakeUrl(path)


class PlayerEngine:
    def __init__(self, slots, fallback_timer, privacy_guard, autoplay_getter, audio_enabled_getter):
        self.slots = slots
        self.fallback_timer = fallback_timer
        self.privacy_guard = privacy_guard
        self.autoplay_getter = autoplay_getter
        self.audio_enabled_getter = audio_enabled_getter
        self.active_slot_id = None
        self.current_generation = 0

    def _normalize_path(self, path: str) -> str:
        return os.path.normpath(path)

    def _find_valid_slot(self, path: str, generation: int):
        norm_path = self._normalize_path(path)
        for slot in self.slots:
            if slot.state in {SlotState.READY, SlotState.PRELOADING, SlotState.ACTIVE}:
                if slot.expected_generation == generation and source_matches_path(slot, norm_path):
                    return slot
        return None

    def _choose_slot(self):
        for slot in self.slots:
            if slot.state in {SlotState.EMPTY, SlotState.STALE, SlotState.FAILED}:
                return slot
        for slot in self.slots:
            if slot.state != SlotState.ACTIVE:
                return slot
        return self.slots[0]

    def _demote_other_active_slots(self, active_slot):
        for slot in self.slots:
            if slot is active_slot:
                continue
            if slot.state == SlotState.ACTIVE:
                slot.video_item.setOpacity(0.0)
                slot.video_item.setZValue(0.0)
                slot.audio.setMuted(True)
                slot.state = SlotState.STALE
                slot.role = SlotRole.SPARE

    def _arm_fallback(self):
        self.fallback_timer.stop()
        self.fallback_timer.start()

    def activate(self, path: str, start_pos: int, generation: int, autoplay: bool) -> ActivationResult:
        norm_path = self._normalize_path(path)
        self.current_generation = generation
        slot = self._find_valid_slot(norm_path, generation)
        reused = slot is not None

        if slot is None:
            slot = self._choose_slot()
            if slot.state != SlotState.EMPTY:
                slot.clear()
            slot.player.setSource(_qurl_from_path(norm_path))
            slot.expected_path = norm_path
            slot.expected_generation = generation
            slot.requested_start_pos = start_pos
            waiting = True
        else:
            waiting = slot.state == SlotState.PRELOADING

        self._demote_other_active_slots(slot)
        slot.state = SlotState.ACTIVE
        slot.role = SlotRole.CURRENT
        slot.requested_start_pos = start_pos
        slot.audio.setMuted(not self.audio_enabled_getter())
        slot.video_item.setZValue(20.0)
        self.active_slot_id = slot.slot_id

        if waiting:
            self._arm_fallback()

        if autoplay:
            slot.player.play()
        else:
            slot.player.setPosition(start_pos)

        return ActivationResult(
            slot_id=slot.slot_id,
            path=norm_path,
            reused_source=reused,
            waiting_for_media=waiting,
            fallback_required=waiting,
        )
