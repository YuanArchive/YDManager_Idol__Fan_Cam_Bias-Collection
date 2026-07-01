import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication

from src.ui.thumbnail_rail import (
    PreviewOrientation,
    ThumbnailCell,
    ThumbnailPreviewRailWidget,
)


app = QApplication.instance() or QApplication([])


class ThumbnailPreviewRailWidgetTest(unittest.TestCase):
    def tearDown(self):
        widget = getattr(self, "widget", None)
        if widget is not None:
            widget.close()
            widget.deleteLater()
            app.processEvents()

    def test_widget_defaults_to_vertical_and_twelve_cells(self):
        self.widget = ThumbnailPreviewRailWidget()

        self.assertEqual(self.widget.orientation, PreviewOrientation.VERTICAL)
        self.assertEqual(self.widget.cell_count, 12)

    def test_set_cells_requires_twelve_cells(self):
        self.widget = ThumbnailPreviewRailWidget()
        cells = [
            ThumbnailCell(index=i, timestamp_ms=i * 1000, image_path=None, state="loading")
            for i in range(12)
        ]

        self.widget.set_cells(cells)

        self.assertEqual(len(self.widget.cells), 12)

    def test_orientation_can_switch_to_horizontal(self):
        self.widget = ThumbnailPreviewRailWidget()

        self.widget.set_orientation(PreviewOrientation.HORIZONTAL)

        self.assertEqual(self.widget.orientation, PreviewOrientation.HORIZONTAL)

    def test_click_signal_emits_timestamp(self):
        self.widget = ThumbnailPreviewRailWidget()
        cells = [
            ThumbnailCell(index=i, timestamp_ms=i * 1000, image_path=None, state="ready")
            for i in range(12)
        ]
        emitted = []
        self.widget.thumbnail_clicked.connect(emitted.append)

        self.widget.set_cells(cells)
        self.widget.activate_cell_for_test(3)

        self.assertEqual(emitted, [3000])

    def test_hover_preview_uses_double_scale_without_resizing_rail(self):
        self.widget = ThumbnailPreviewRailWidget()
        self.widget.resize(120, 480)
        self.widget.set_cells([
            ThumbnailCell(index=i, timestamp_ms=i * 1000, image_path=None, state="ready")
            for i in range(12)
        ])
        original_size = self.widget.size()

        self.widget.update_hover_position(QPoint(60, 85))

        cell_rect = self.widget.cell_rect(2)
        preview_rect = self.widget.hover_preview_rect()
        self.assertEqual(self.widget.hovered_cell_index, 2)
        self.assertEqual(preview_rect.width(), cell_rect.width() * 2)
        self.assertEqual(preview_rect.height(), cell_rect.height() * 2)
        self.assertEqual(self.widget.size(), original_size)

    def test_vertical_cells_fill_height_without_bottom_remainder(self):
        self.widget = ThumbnailPreviewRailWidget()
        self.widget.resize(134, 887)

        first_rect = self.widget.cell_rect(0)
        last_rect = self.widget.cell_rect(11)

        self.assertEqual(first_rect.top(), self.widget.grid_margin)
        self.assertEqual(last_rect.bottom(), self.widget.height() - self.widget.grid_margin - 1)

    def test_vertical_width_for_height_preserves_twelve_sixteen_by_nine_cells(self):
        height = 887
        width = ThumbnailPreviewRailWidget.width_for_height(height)
        usable_height = height - ThumbnailPreviewRailWidget.grid_margin * 2
        usable_height -= ThumbnailPreviewRailWidget.grid_gap * 11
        cell_height = usable_height / 12

        self.assertEqual(width, round(cell_height * 16 / 9) + ThumbnailPreviewRailWidget.grid_margin * 2)

    def test_privacy_hidden_clears_hover_preview(self):
        self.widget = ThumbnailPreviewRailWidget()
        self.widget.resize(120, 480)
        self.widget.set_cells([
            ThumbnailCell(index=i, timestamp_ms=i * 1000, image_path=None, state="ready")
            for i in range(12)
        ])
        self.widget.update_hover_position(QPoint(60, 85))

        self.widget.set_privacy_hidden(True)

        self.assertTrue(self.widget.privacy_hidden)
        self.assertIsNone(self.widget.hovered_cell_index)
        self.assertIsNone(self.widget.hover_preview_rect())


class ThumbnailMarkerTest(unittest.TestCase):
    def tearDown(self):
        widget = getattr(self, "widget", None)
        if widget is not None:
            widget.close()
            widget.deleteLater()
            app.processEvents()

    def test_playback_position_marks_nearest_cell(self):
        self.widget = ThumbnailPreviewRailWidget()
        self.widget.set_cells([
            ThumbnailCell(index=i, timestamp_ms=i * 1000, image_path=None, state="ready")
            for i in range(12)
        ])

        self.widget.set_playback_position(3400)

        self.assertEqual(self.widget.current_cell_index, 3)

    def test_highlight_markers_count_nearest_cells(self):
        self.widget = ThumbnailPreviewRailWidget()
        self.widget.set_cells([
            ThumbnailCell(index=i, timestamp_ms=i * 1000, image_path=None, state="ready")
            for i in range(12)
        ])

        self.widget.set_highlights([3100, 3200])

        self.assertEqual(self.widget.highlight_counts[3], 2)
