import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BINARY_SUFFIXES = {
    ".bmp",
    ".dll",
    ".exe",
    ".ico",
    ".mp4",
    ".png",
    ".pyd",
    ".pyc",
    ".ttf",
}


def _run_git_ls_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]


def _forbidden_text_patterns() -> list[str]:
    root_windows = str(ROOT)
    root_posix = root_windows.replace("\\", "/")
    home_windows = str(Path.home())
    home_posix = home_windows.replace("\\", "/")
    temp_windows = os.environ.get("TEMP", "")
    temp_posix = temp_windows.replace("\\", "/")

    patterns = [
        pattern
        for pattern in {
            root_windows,
            root_posix,
            home_windows,
            home_posix,
            temp_windows,
            temp_posix,
            "ydm-" + "debug-smoke",
        }
        if pattern
    ]
    return sorted(patterns, key=len, reverse=True)


def _is_binary_candidate(path: Path) -> bool:
    return path.suffix.lower() in BINARY_SUFFIXES


def main() -> int:
    candidates = _run_git_ls_files()
    forbidden_generated_roots = ("build/", "dist/", "installer/", "index/", "logs/")
    forbidden_text_patterns = _forbidden_text_patterns()
    failures: list[str] = []

    for relative_path in candidates:
        if relative_path.startswith(forbidden_generated_roots):
            failures.append(f"generated-artifact-candidate:{relative_path}")
            continue

        path = ROOT / relative_path
        if _is_binary_candidate(path) or not path.is_file():
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            failures.append(f"read-failed:{relative_path}:{exc}")
            continue

        for pattern in forbidden_text_patterns:
            if pattern and pattern in content:
                failures.append(f"forbidden-local-text:{relative_path}:{pattern}")
                break

    if failures:
        print("RELEASE_AUDIT_FAILED")
        for failure in failures:
            print(failure)
        return 1

    print(f"RELEASE_AUDIT_OK files={len(candidates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
