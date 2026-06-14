import argparse
import os
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _create_placeholder_library(root: Path, file_count: int, folder_count: int) -> None:
    folder_count = max(1, folder_count)
    for index in range(file_count):
        folder = root / f"group_{index % folder_count:03d}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"clip_{index:05d}.mp4").write_bytes(b"")

        if index % 10 == 0:
            (folder / f"note_{index:05d}.txt").write_text("not a video", encoding="utf-8")


def _cache_items(file_items):
    for item in file_items:
        path = item["path"]
        yield {
            "path": path,
            "name": os.path.basename(path),
            "folder": os.path.dirname(path),
        }


def run_perf_smoke(file_count: int, folder_count: int, max_scan_seconds: float, max_cache_seconds: float) -> None:
    with tempfile.TemporaryDirectory(prefix="ydm-perf-smoke-") as temp_root:
        temp_path = Path(temp_root)
        os.environ["LOCALAPPDATA"] = str(temp_path / "appdata")

        from src.managers.file_manager import FileManager

        library_root = temp_path / "library"
        _create_placeholder_library(library_root, file_count, folder_count)

        manager = FileManager()
        manager.global_files = []
        manager.trash_files = []

        scan_started = time.perf_counter()
        manager.scan_folder(str(library_root))
        scan_seconds = time.perf_counter() - scan_started

        scanned_count = len(manager.main_files)
        if scanned_count != file_count:
            raise RuntimeError(f"scan_folder found {scanned_count} videos, expected {file_count}")
        if scan_seconds > max_scan_seconds:
            raise RuntimeError(
                f"scan_folder took {scan_seconds:.3f}s, above {max_scan_seconds:.3f}s smoke threshold"
            )

        manager.update_global_cache(list(_cache_items(manager.main_files)))
        manager.main_files = []

        cache_started = time.perf_counter()
        cache_loaded = manager.load_main_files_from_cache(str(library_root))
        cache_seconds = time.perf_counter() - cache_started

        cached_count = len(manager.main_files)
        if not cache_loaded or cached_count != file_count:
            raise RuntimeError(f"cache reload returned {cached_count} videos, expected {file_count}")
        if cache_seconds > max_cache_seconds:
            raise RuntimeError(
                f"cache reload took {cache_seconds:.3f}s, above {max_cache_seconds:.3f}s smoke threshold"
            )

        print(
            "PERF_SCAN_SMOKE_OK "
            f"files={file_count} folders={folder_count} "
            f"scan_seconds={scan_seconds:.3f} cache_seconds={cache_seconds:.3f}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Synthetic large-library smoke for folder scan and cache reload paths."
    )
    parser.add_argument("--files", type=int, default=800)
    parser.add_argument("--folders", type=int, default=32)
    parser.add_argument("--max-scan-seconds", type=float, default=20.0)
    parser.add_argument("--max-cache-seconds", type=float, default=8.0)
    args = parser.parse_args()

    run_perf_smoke(
        file_count=args.files,
        folder_count=args.folders,
        max_scan_seconds=args.max_scan_seconds,
        max_cache_seconds=args.max_cache_seconds,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
