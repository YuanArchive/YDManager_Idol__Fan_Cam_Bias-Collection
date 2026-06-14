from __future__ import annotations

import os
import shutil
import subprocess

from PyQt6.QtCore import QThread, pyqtSignal


def _format_timestamp(timestamp_ms: int) -> str:
    total_ms = max(0, int(timestamp_ms))
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def extract_thumbnails_ffmpeg(
    path: str,
    timestamps_ms: list[int],
    output_dir: str,
    size: tuple[int, int] = (160, 90),
) -> list[str]:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise RuntimeError("ffmpeg executable was not found")

    os.makedirs(output_dir, exist_ok=True)
    width, height = size
    files = []
    for index, timestamp_ms in enumerate(timestamps_ms):
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
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

    def run(self) -> None:
        try:
            files = self.extractor(self.path, self.timestamps_ms, self.output_dir)
            self.finished_path.emit(self.path, files)
        except Exception as exc:
            self.failed_path.emit(self.path, str(exc))
