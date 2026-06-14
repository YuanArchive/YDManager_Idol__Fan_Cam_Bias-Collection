from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QWidget


class PreviewOrientation(str, Enum):
    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"


@dataclass(frozen=True)
class ThumbnailCell:
    index: int
    timestamp_ms: int
    image_path: str | None
    state: str
    quality_score: float = 0.0
    is_current: bool = False
    highlight_count: int = 0


class ThumbnailPreviewRailWidget(QWidget):
    thumbnail_clicked = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cell_count = 12
        self.orientation = PreviewOrientation.VERTICAL
        self.cells: list[ThumbnailCell] = []
        self.hover_scale = 2.0
        self.current_cell_index: int | None = None
        self.highlight_counts = {index: 0 for index in range(self.cell_count)}
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)

    def set_orientation(self, orientation: PreviewOrientation | str) -> None:
        self.orientation = PreviewOrientation(orientation)
        self.updateGeometry()
        self.update()

    def set_cells(self, cells: list[ThumbnailCell]) -> None:
        if len(cells) != self.cell_count:
            raise ValueError("Thumbnail rail requires exactly 12 cells.")
        self.cells = list(cells)
        self.update()

    def activate_cell_for_test(self, index: int) -> None:
        cell = self.cells[index]
        self.thumbnail_clicked.emit(cell.timestamp_ms)

    def _nearest_cell_index(self, timestamp_ms: int) -> int | None:
        if not self.cells:
            return None
        distances = [
            (abs(cell.timestamp_ms - timestamp_ms), cell.index)
            for cell in self.cells
        ]
        return min(distances)[1]

    def set_playback_position(self, timestamp_ms: int) -> None:
        self.current_cell_index = self._nearest_cell_index(timestamp_ms)
        self.update()

    def set_highlights(self, timestamps_ms: list[int]) -> None:
        counts = {index: 0 for index in range(self.cell_count)}
        for timestamp_ms in timestamps_ms:
            index = self._nearest_cell_index(timestamp_ms)
            if index is not None:
                counts[index] += 1
        self.highlight_counts = counts
        self.update()
