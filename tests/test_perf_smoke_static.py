from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PerfSmokeStaticTest(unittest.TestCase):
    def test_large_library_perf_smoke_tool_and_docs_are_present(self):
        script_path = ROOT / "tools" / "perf_scan_smoke.py"
        self.assertTrue(script_path.exists())

        script = script_path.read_text(encoding="utf-8")
        run_checks = (ROOT / "tools" / "run_checks.ps1").read_text(encoding="utf-8")
        manual_doc = (ROOT / "docs" / "maintenance" / "manual-smoke-test.md").read_text(encoding="utf-8")

        self.assertIn("PERF_SCAN_SMOKE_OK", script)
        self.assertIn("TemporaryDirectory", script)
        self.assertIn("FileManager", script)
        self.assertIn("scan_folder", script)
        self.assertIn("load_main_files_from_cache", script)
        self.assertIn("perf_scan_smoke.py", run_checks)
        self.assertIn("perf_scan_smoke.py", manual_doc)
        self.assertIn("PERF_SCAN_SMOKE_OK", manual_doc)


if __name__ == "__main__":
    unittest.main()
