from __future__ import annotations

import random


THUMBNAIL_CELL_COUNT = 12


def sample_timestamps(duration_ms: int | None, count: int = THUMBNAIL_CELL_COUNT) -> list[int]:
    if count <= 0:
        return []
    if not duration_ms or duration_ms <= 0:
        return [0 for _ in range(count)]

    safe_start = int(duration_ms * 0.05)
    safe_end = int(duration_ms * 0.95)
    if safe_end <= safe_start:
        safe_start = 0
        safe_end = max(0, duration_ms)

    if count == 1:
        return [min(duration_ms, max(0, (safe_start + safe_end) // 2))]

    span = max(0, safe_end - safe_start)
    values = []
    for index in range(count):
        ratio = index / (count - 1)
        timestamp = safe_start + int(span * ratio)
        values.append(min(duration_ms, max(0, timestamp)))
    return values


def choose_random_start_candidate(
    timestamps_ms: list[int],
    quality_scores: list[float],
    duration_ms: int,
    seed: int | None = None,
) -> int | None:
    if not timestamps_ms or not quality_scores:
        return None

    safe_start = int(duration_ms * 0.05)
    safe_end = int(duration_ms * 0.95)
    candidates = [
        (timestamp, score)
        for timestamp, score in zip(timestamps_ms, quality_scores)
        if safe_start <= timestamp <= safe_end and score >= 0.5
    ]
    if not candidates:
        return None

    max_score = max(score for _, score in candidates)
    best = [timestamp for timestamp, score in candidates if score == max_score]
    rng = random.Random(seed)
    return rng.choice(best)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def frame_quality_score(
    brightness: float,
    contrast: float,
    blur: float,
    similarity: float,
) -> float:
    brightness_score = _clamp((brightness - 8.0) / 100.0)
    contrast_score = _clamp(contrast / 45.0)
    blur_score = _clamp(blur / 160.0)
    distinct_score = _clamp(1.0 - similarity)
    return round(
        brightness_score * 0.35
        + contrast_score * 0.25
        + blur_score * 0.20
        + distinct_score * 0.20,
        4,
    )


def choose_replacement_timestamp(
    original_ms: int,
    duration_ms: int,
    attempt_index: int,
) -> int:
    offsets = [1500, -1500, 3000, -3000, 5000, -5000]
    offset = offsets[attempt_index % len(offsets)]
    return max(0, min(duration_ms, original_ms + offset))
