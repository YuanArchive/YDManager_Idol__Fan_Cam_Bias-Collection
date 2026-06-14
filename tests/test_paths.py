import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from src.core import consts


ROOT = Path(__file__).resolve().parents[1]


class PathResolutionTest(unittest.TestCase):
    def tearDown(self):
        importlib.reload(consts)

    def test_base_dir_is_project_root_not_current_working_directory(self):
        original_cwd = os.getcwd()
        with tempfile.TemporaryDirectory() as other_dir:
            try:
                os.chdir(other_dir)
                importlib.reload(consts)

                self.assertEqual(Path(consts.BASE_DIR), ROOT)
                self.assertEqual(Path(consts.ICON_PATH), ROOT / "assets" / "icon.ico")
            finally:
                os.chdir(original_cwd)

    def test_resource_path_resolves_from_project_root(self):
        self.assertEqual(
            Path(consts.resource_path("assets", "fonts", "Pretendard-Medium.ttf")),
            ROOT / "assets" / "fonts" / "Pretendard-Medium.ttf",
        )

    def test_index_dir_uses_local_app_data_when_available(self):
        original_localappdata = os.environ.get("LOCALAPPDATA")
        with tempfile.TemporaryDirectory() as app_data:
            try:
                os.environ["LOCALAPPDATA"] = app_data
                importlib.reload(consts)

                self.assertEqual(
                    Path(consts.INDEX_DIR),
                    Path(app_data) / "YDManager" / "index",
                )
                self.assertEqual(
                    Path(consts.TAGS_FILE),
                    Path(app_data) / "YDManager" / "index" / "video_tags.json",
                )
            finally:
                if original_localappdata is None:
                    os.environ.pop("LOCALAPPDATA", None)
                else:
                    os.environ["LOCALAPPDATA"] = original_localappdata

    def test_legacy_index_files_are_copied_without_overwriting_app_data(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            legacy_dir = Path(tmp_dir) / "legacy"
            app_index_dir = Path(tmp_dir) / "appdata" / "index"
            legacy_dir.mkdir()
            app_index_dir.mkdir(parents=True)

            legacy_tags = legacy_dir / "video_tags.json"
            app_tags = app_index_dir / "video_tags.json"
            legacy_history = legacy_dir / "folder_history.json"
            legacy_tags.write_text(json.dumps({"legacy.mp4": "A"}), encoding="utf-8")
            app_tags.write_text(json.dumps({"existing.mp4": "B"}), encoding="utf-8")
            legacy_history.write_text(json.dumps(["D:/Videos"]), encoding="utf-8")

            copied = consts.migrate_legacy_index_files(
                legacy_index_dir=str(legacy_dir),
                target_index_dir=str(app_index_dir),
            )

            self.assertEqual(copied, [str(app_index_dir / "folder_history.json")])
            self.assertEqual(json.loads(app_tags.read_text(encoding="utf-8")), {"existing.mp4": "B"})
            self.assertEqual(
                json.loads((app_index_dir / "folder_history.json").read_text(encoding="utf-8")),
                ["D:/Videos"],
            )


if __name__ == "__main__":
    unittest.main()
