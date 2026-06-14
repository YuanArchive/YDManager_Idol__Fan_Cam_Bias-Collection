import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CleanupStaticTest(unittest.TestCase):
    def test_startup_display_log_is_not_duplicated(self):
        main_source = (ROOT / "main.py").read_text(encoding="utf-8")

        self.assertEqual(
            1,
            main_source.count('logger.info(f"Display Detected - DPI: {dpi}, Pixel Ratio: {pixel_ratio}")'),
        )

    def test_import_statements_do_not_repeat_the_same_symbol(self):
        files = [
            ROOT / "main.py",
            ROOT / "src" / "core" / "event_handler.py",
            ROOT / "src" / "core" / "signal_setup.py",
            ROOT / "src" / "ui" / "ui_components.py",
        ]

        for path in files:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    imported_names = [alias.name for alias in node.names]
                    with self.subTest(path=path, line=node.lineno):
                        self.assertEqual(len(imported_names), len(set(imported_names)))

    def test_main_does_not_keep_legacy_direct_preload_pipeline(self):
        main_source = (ROOT / "main.py").read_text(encoding="utf-8")

        legacy_symbols = [
            "preload_timer",
            "_sync_player_layers",
            "_execute_media_load",
            "preload_next_file",
            "_run_preload",
        ]

        for symbol in legacy_symbols:
            with self.subTest(symbol=symbol):
                self.assertNotIn(symbol, main_source)

    def test_file_actions_do_not_reload_media_sources_directly(self):
        source = (ROOT / "src" / "controllers" / "file_action_controller.py").read_text(encoding="utf-8")

        self.assertNotIn("QUrl.fromLocalFile", source)


if __name__ == "__main__":
    unittest.main()
