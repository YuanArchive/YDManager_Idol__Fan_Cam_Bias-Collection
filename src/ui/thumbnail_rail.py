from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import os

from PyQt6.QtCore import QPoint, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPixmap
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
        self.hovered_cell_index: int | None = None
        self.privacy_hidden = False
        self.highlight_counts = {index: 0 for index in range(self.cell_count)}
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)

    def sizeHint(self) -> QSize:
        if self.orientation == PreviewOrientation.HORIZONTAL:
            return QSize(720, 70)
        return QSize(105, 420)

    def set_orientation(self, orientation: PreviewOrientation | str) -> None:
        self.orientation = PreviewOrientation(orientation)
        self.updateGeometry()
        self.update()

    def set_cells(self, cells: list[ThumbnailCell]) -> None:
        if len(cells) != self.cell_count:
            raise ValueError("Thumbnail rail requires exactly 12 cells.")
        self.cells = list(cells)
        self.update()

    def set_privacy_hidden(self, hidden: bool) -> None:
        self.privacy_hidden = bool(hidden)
        if self.privacy_hidden:
            self.hovered_cell_index = None
        self.update()

    def activate_cell_for_test(self, index: int) -> None:
        cell = self.cells[index]
        self.thumbnail_clicked.emit(cell.timestamp_ms)

    def cell_rect(self, index: int) -> QRect:
        if not 0 <= index < self.cell_count:
            return QRect()

        margin = 4
        gap = 3
        if self.orientation == PreviewOrientation.HORIZONTAL:
            available = max(1, self.width() - margin * 2 - gap * (self.cell_count - 1))
            cell_w = max(1, available // self.cell_count)
            cell_h = max(1, self.height() - margin * 2)
            return QRect(margin + index * (cell_w + gap), margin, cell_w, cell_h)

        available = max(1, self.height() - margin * 2 - gap * (self.cell_count - 1))
        cell_w = max(1, self.width() - margin * 2)
        cell_h = max(1, available // self.cell_count)
        return QRect(margin, margin + index * (cell_h + gap), cell_w, cell_h)

    def _cell_index_at(self, pos: QPoint) -> int | None:
        for index in range(self.cell_count):
            if self.cell_rect(index).contains(pos):
                return index
        return None

    def update_hover_position(self, pos: QPoint) -> None:
        next_index = None if self.privacy_hidden else self._cell_index_at(pos)
        if self.hovered_cell_index != next_index:
            self.hovered_cell_index = next_index
            self.update()

    def hover_preview_rect(self) -> QRect | None:
        if self.privacy_hidden or self.hovered_cell_index is None:
            return None
        base = self.cell_rect(self.hovered_cell_index)
        if base.isNull():
            return None
        width = int(base.width() * self.hover_scale)
        height = int(base.height() * self.hover_scale)
        if self.orientation == PreviewOrientation.HORIZONTAL:
            x = max(0, base.center().x() - width // 2)
            y = max(0, base.top() - height - 6)
        else:
            x = base.left() - width - 6
            y = max(0, base.center().y() - height // 2)
        return QRect(x, y, width, height)

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

    def mouseMoveEvent(self, event) -> None:
        self.update_hover_position(event.pos())
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self.hovered_cell_index = None
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and not self.privacy_hidden:
            index = self._cell_index_at(event.pos())
            if index is not None and index < len(self.cells):
                self.thumbnail_clicked.emit(self.cells[index].timestamp_ms)
                return
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(20, 24, 32, 120))

        for index in range(self.cell_count):
            cell = self.cells[index] if index < len(self.cells) else None
            self._paint_cell(painter, index, cell, self.cell_rect(index))

        preview_rect = self.hover_preview_rect()
        if preview_rect is not None and self.hovered_cell_index is not None:
            cell = self.cells[self.hovered_cell_index] if self.hovered_cell_index < len(self.cells) else None
            self._paint_cell(painter, self.hovered_cell_index, cell, preview_rect, enlarged=True)

    def _paint_cell(self, painter: QPainter, index: int, cell: ThumbnailCell | None, rect: QRect, enlarged=False) -> None:
        if rect.isNull():
            return

        painter.save()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(35, 42, 55, 220))
        painter.drawRoundedRect(rect, 4, 4)

        if not self.privacy_hidden and cell and cell.image_path and os.path.exists(cell.image_path):
            pixmap = QPixmap(cell.image_path)
            if not pixmap.isNull():
                painter.drawPixmap(rect, pixmap.scaled(
                    rect.size(),
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                ))
        elif self.privacy_hidden:
            painter.setBrush(QColor(50, 55, 65, 230))
            painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 3, 3)
        else:
            painter.setPen(QColor(150, 160, 175, 180))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{index + 1}")

        border_color = QColor(95, 110, 135, 210)
        if index == self.current_cell_index:
            border_color = QColor(136, 192, 208)
        elif index == self.hovered_cell_index:
            border_color = QColor(235, 203, 139)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(border_color, 3 if enlarged else 2))
        painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)

        highlight_count = self.highlight_counts.get(index, 0)
        if highlight_count:
            marker = QRect(rect.right() - 13, rect.top() + 4, 9, 9)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(180, 142, 173))
            painter.drawEllipse(marker)

        painter.restore()
