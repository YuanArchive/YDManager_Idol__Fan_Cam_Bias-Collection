import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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
