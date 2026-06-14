import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ProVideoViewStaticTest(unittest.TestCase):
    def test_pro_video_view_has_single_resize_event_handler(self):
        source = (ROOT / "src" / "ui" / "ui_components.py").read_text(encoding="utf-8")
        module = ast.parse(source)
        class_node = next(
            node for node in module.body
            if isinstance(node, ast.ClassDef) and node.name == "ProVideoView"
        )

        resize_handlers = [
            node for node in class_node.body
            if isinstance(node, ast.FunctionDef) and node.name == "resizeEvent"
        ]

        self.assertEqual(len(resize_handlers), 1)


class SignalSetupStaticTest(unittest.TestCase):
    def test_refresh_button_forces_disk_scan_instead_of_cache_only_reload(self):
        source = (ROOT / "src" / "core" / "signal_setup.py").read_text(encoding="utf-8")

        self.assertIn(
            "window.btn_refresh.clicked.connect(lambda: window.load_files(force_scan=True))",
            source,
        )
        self.assertNotIn("window.btn_refresh.clicked.connect(window.load_files)", source)


class ReadmeShortcutStaticTest(unittest.TestCase):
    def test_readme_documents_mode_specific_delete_enter_and_restore_shortcuts(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("<kbd>Delete</kbd> (하이라이트 모드)", readme)
        self.assertIn("하이라이트 항목 삭제", readme)
        self.assertIn("<kbd>Delete</kbd> (휴지통 모드)", readme)
        self.assertIn("영구 삭제", readme)
        self.assertIn("<kbd>Enter</kbd> (하이라이트 모드)", readme)
        self.assertIn("<kbd>Enter</kbd> (휴지통 모드)", readme)
        self.assertIn("<kbd>R</kbd> (휴지통 모드)", readme)


if __name__ == "__main__":
    unittest.main()
