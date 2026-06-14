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


if __name__ == "__main__":
    unittest.main()
