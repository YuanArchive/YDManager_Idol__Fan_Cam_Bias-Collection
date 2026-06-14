from __future__ import annotations

from PyQt6.QtCore import QThread, pyqtSignal


class ThumbnailWorker(QThread):
    finished_path = pyqtSignal(str, list)
    failed_path = pyqtSignal(str, str)

    def __init__(self, path: str, timestamps_ms: list[int], output_dir: str):
        super().__init__()
        self.path = path
        self.timestamps_ms = list(timestamps_ms)
        self.output_dir = output_dir

    def run(self) -> None:
        try:
            self.finished_path.emit(self.path, [])
        except Exception as exc:
            self.failed_path.emit(self.path, str(exc))
