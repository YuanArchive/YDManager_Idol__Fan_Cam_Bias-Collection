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

    def _slot_matches(self, slot, path: str, generation: int) -> bool:
        return (
            slot.expected_generation == generation
            and slot.expected_path is not None
            and os.path.normcase(os.path.normpath(slot.expected_path)) == os.path.normcase(os.path.normpath(path))
            and slot.state in {SlotState.PRELOADING, SlotState.READY, SlotState.ACTIVE}
            and source_matches_path(slot, path)
        )

    def _find_or_assign_neighbor_slot(self, path: str, generation: int, protected_slot_ids=None):
        protected_slot_ids = protected_slot_ids or set()
        for slot in self.slots:
            if slot.slot_id in protected_slot_ids:
                continue
            if self._slot_matches(slot, path, generation):
                return slot
        for slot in self.slots:
            if slot.slot_id in protected_slot_ids:
                continue
            if slot.state == SlotState.EMPTY:
                return slot
        for slot in self.slots:
            if slot.slot_id in protected_slot_ids:
                continue
            if slot.state not in {SlotState.ACTIVE, SlotState.READY}:
                slot.clear()
                return slot
        return None

    def _prune_invalid_preloads(self, generation: int) -> None:
        for slot in self.slots:
            if slot.state == SlotState.ACTIVE:
                continue
            if slot.state not in {SlotState.PRELOADING, SlotState.READY, SlotState.STALE, SlotState.FAILED}:
                continue
            if (
                slot.expected_generation != generation
                or slot.expected_path is None
                or not source_matches_path(slot, slot.expected_path)
            ):
                slot.clear()

    def _start_preload(self, slot, item: PlaybackItem, generation: int, role: SlotRole) -> None:
        norm_path = self._normalize_path(item.path)
        if self._slot_matches(slot, norm_path, generation):
            slot.role = role
            return
        if slot.state != SlotState.EMPTY:
            slot.clear()
        slot.expected_path = norm_path
        slot.expected_generation = generation
        slot.requested_start_pos = item.start_pos
        slot.role = role
        slot.state = SlotState.PRELOADING
        slot.audio.setMuted(True)
        slot.video_item.setOpacity(0.0)
        slot.video_item.setZValue(0.0)
        slot.player.setSource(_qurl_from_path(norm_path))
        slot.player.pause()
        if item.start_pos > 0:
            slot.player.setPosition(item.start_pos)

    def plan_neighbors(self, current_index: int, playlist: list[PlaybackItem], generation: int) -> None:
        self._prune_invalid_preloads(generation)
        targets = []
        if current_index + 1 < len(playlist):
            targets.append((playlist[current_index + 1], SlotRole.NEXT))
        if current_index - 1 >= 0:
            targets.append((playlist[current_index - 1], SlotRole.PREVIOUS))

        protected_slots = set()
        for item, role in targets:
            slot = self._find_or_assign_neighbor_slot(item.path, generation, protected_slots)
            if slot and slot.state != SlotState.READY:
                self._start_preload(slot, item, generation, role)
            elif slot:
                slot.role = role
            if slot:
                protected_slots.add(slot.slot_id)

        for slot in self.slots:
            if slot.state == SlotState.ACTIVE:
                continue
            if slot.slot_id in protected_slots:
                continue
            if slot.state in {SlotState.PRELOADING, SlotState.READY, SlotState.STALE, SlotState.FAILED}:
                slot.clear()

    def _slot_for_player(self, player):
        for slot in self.slots:
            if slot.player is player:
                return slot
        return None

    def _status_name(self, status) -> str:
        return getattr(status, "name", str(status)).lower()

    def _is_loaded_status(self, status) -> bool:
        name = self._status_name(status)
        return "loaded" in name or "buffered" in name

    def _is_failed_status(self, status) -> bool:
        name = self._status_name(status)
        return "invalid" in name or "nomedia" in name or name == "none"

    def reveal_if_allowed(self, slot, status, fallback_expired: bool = False) -> bool:
        if slot.state != SlotState.ACTIVE:
            return False
        if slot.expected_generation != self.current_generation:
            return False
        if not slot.expected_path or not source_matches_path(slot, slot.expected_path):
            return False
        if self.privacy_guard():
            return False
        if not fallback_expired and not self._is_loaded_status(status):
            return False
        slot.video_item.setOpacity(1.0)
        slot.video_item.setZValue(20.0)
        return True

    def _mark_failed(self, slot, status) -> None:
        slot.last_status = status
        slot.last_error = self._status_name(status)
        slot.player.stop()
        slot.player.setSource(_empty_qurl())
        slot.audio.setMuted(True)
        slot.video_item.setOpacity(0.0)
        slot.video_item.setZValue(0.0)
        slot.expected_path = None
        slot.expected_generation = 0
        slot.requested_start_pos = 0
        slot.state = SlotState.FAILED
        slot.role = SlotRole.SPARE

    def handle_media_status(self, player, status) -> bool:
        slot = self._slot_for_player(player)
        if slot is None:
            return False
        slot.last_status = status
        if self._is_failed_status(status):
            self._mark_failed(slot, status)
            return False
        if slot.state == SlotState.PRELOADING and self._is_loaded_status(status):
            slot.state = SlotState.READY
            return False
        if slot.state == SlotState.ACTIVE:
            revealed = self.reveal_if_allowed(slot, status)
            if revealed:
                self.fallback_timer.stop()
            return revealed
        return False
