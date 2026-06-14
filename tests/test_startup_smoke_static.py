from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class StartupSmokeStaticTest(unittest.TestCase):
    def test_startup_smoke_tool_and_docs_are_present(self):
        script_path = ROOT / "tools" / "startup_smoke.py"
        self.assertTrue(script_path.exists())

        script = script_path.read_text(encoding="utf-8")
        run_checks = (ROOT / "tools" / "run_checks.ps1").read_text(encoding="utf-8")
        manual_doc = (ROOT / "docs" / "maintenance" / "manual-smoke-test.md").read_text(encoding="utf-8")

        self.assertIn("STARTUP_SMOKE_OK", script)
        self.assertIn("TemporaryDirectory", script)
        self.assertIn("QTimer", script)
        self.assertIn("VideoSorter", script)
        self.assertIn("logging.shutdown()", script)
        self.assertIn("startup_smoke.py", run_checks)
        self.assertIn("startup_smoke.py", manual_doc)
        self.assertIn("STARTUP_SMOKE_OK", manual_doc)


if __name__ == "__main__":
    unittest.main()
