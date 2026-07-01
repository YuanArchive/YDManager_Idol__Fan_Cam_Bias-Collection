from __future__ import annotations

import os
import shutil
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal

from src.managers.thumbnail_sampling import sample_timestamps


# Upper bounds so a corrupt/streaming/network video cannot hang a worker thread
# forever. A single-frame extraction that exceeds these is treated as a failure.
FFPROBE_TIMEOUT_SEC = 30
FFMPEG_FRAME_TIMEOUT_SEC = 60


class ThumbnailCancelled(Exception):
    """Raised inside the extraction loop when a worker has been asked to stop."""


def _format_timestamp(timestamp_ms: int) -> str:
    total_ms = max(0, int(timestamp_ms))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def _hidden_subprocess_kwargs() -> dict:
    if os.name != "nt":
        return {}
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if not creation_flags:
        return {}
    return {"creationflags": creation_flags}


def probe_duration_ms_ffprobe(path: str) -> int:
    executable = shutil.which("ffprobe")
    if not executable:
        raise RuntimeError("ffprobe executable was not found")

    result = subprocess.run(
        [
            executable,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=FFPROBE_TIMEOUT_SEC,
        **_hidden_subprocess_kwargs(),
    )
    value = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    duration_ms = int(float(value) * 1000)
    if duration_ms <= 0:
        raise RuntimeError("ffprobe returned an invalid duration")
    return duration_ms


def extract_thumbnails_ffmpeg(
    path: str,
    timestamps_ms: list[int],
    output_dir: str,
    size: tuple[int, int] = (160, 90),
    should_cancel=None,
) -> list[str]:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise RuntimeError("ffmpeg executable was not found")

    os.makedirs(output_dir, exist_ok=True)
    width, height = size
    files = []
    for index, timestamp_ms in enumerate(timestamps_ms):
        # Cooperative cancellation checkpoint between frames so a shutdown
        # request does not have to wait for the whole 12-frame extraction.
        if should_cancel is not None and should_cancel():
            raise ThumbnailCancelled("thumbnail extraction cancelled")
        name = f"{index:03d}.jpg"
        output_path = os.path.join(output_dir, name)
        command = [
            executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            _format_timestamp(timestamp_ms),
            "-i",
            path,
            "-frames:v",
            "1",
            "-vf",
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
            "-q:v",
            "5",
            "-y",
            output_path,
        ]
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=FFMPEG_FRAME_TIMEOUT_SEC,
            **_hidden_subprocess_kwargs(),
        )
        files.append(name)
    return files


class ThumbnailWorker(QThread):
    finished_path = pyqtSignal(str, list)
    failed_path = pyqtSignal(str, str)

    def __init__(self, path: str, timestamps_ms: list[int], output_dir: str, extractor=None):
        super().__init__()
        self.path = path
        self.timestamps_ms = list(timestamps_ms)
        self.output_dir = output_dir
        self.extractor = extractor or extract_thumbnails_ffmpeg
        self.duration_ms = None
        self.resolved_duration_ms = None
        self.resolved_timestamps_ms = list(timestamps_ms)
        self._cancel_requested = False

    def set_duration_ms(self, duration_ms: int | None) -> None:
        self.duration_ms = int(duration_ms) if duration_ms and duration_ms > 0 else None

    def cancel(self) -> None:
        """Ask the worker to stop at the next frame checkpoint (safe cross-thread)."""
        self._cancel_requested = True
        # QThread.requestInterruption() is safe to call from any thread.
        self.requestInterruption()

    def _should_cancel(self) -> bool:
        if self._cancel_requested:
            return True
        try:
            return self.isInterruptionRequested()
        except RuntimeError:
            return False

    def run(self) -> None:
        try:
            if self.timestamps_ms:
                timestamps = list(self.timestamps_ms)
                duration_ms = self.duration_ms
            else:
                duration_ms = self.duration_ms or probe_duration_ms_ffprobe(self.path)
                timestamps = sample_timestamps(duration_ms)

            self.resolved_duration_ms = duration_ms
            self.resolved_timestamps_ms = list(timestamps)
            # Only the built-in extractor understands cooperative cancellation;
            # keep the 3-argument contract for injected/test extractors.
            if self.extractor is extract_thumbnails_ffmpeg:
                files = self.extractor(
                    self.path,
                    timestamps,
                    self.output_dir,
                    should_cancel=self._should_cancel,
                )
            else:
                files = self.extractor(self.path, timestamps, self.output_dir)
            self.finished_path.emit(self.path, files)
        except Exception as exc:
            self.failed_path.emit(self.path, str(exc))
