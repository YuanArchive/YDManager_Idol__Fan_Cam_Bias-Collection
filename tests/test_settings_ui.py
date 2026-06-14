import unittest
from unittest.mock import patch

from PyQt6.QtWidgets import QMessageBox

from src.ui.settings_ui import SettingsDialog


class FakeParent:
    def __init__(self):
        self.reset_count = 0

    def reset_all_ui(self):
        self.reset_count += 1


class FakeSettingsDialog:
    def __init__(self, reset_result):
        self.file_manager = self
        self.reset_result = reset_result
        self.parent_widget = FakeParent()
        self.accepted = False

    def reset_all_data(self):
        return self.reset_result

    def parent(self):
        return self.parent_widget

    def accept(self):
        self.accepted = True


class SettingsDialogTest(unittest.TestCase):
    def test_reset_click_does_not_report_success_when_data_reset_aborts(self):
        dialog = FakeSettingsDialog(reset_result=False)

        with patch(
            "src.ui.settings_ui.ThemeMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ), patch("src.ui.settings_ui.ThemeMessageBox.information") as information, patch(
            "src.ui.settings_ui.ThemeMessageBox.warning"
        ) as warning:
            SettingsDialog.on_reset_clicked(dialog)

        warning.assert_called_once()
        information.assert_not_called()
        self.assertFalse(dialog.accepted)
        self.assertEqual(dialog.parent_widget.reset_count, 0)


if __name__ == "__main__":
    unittest.main()
