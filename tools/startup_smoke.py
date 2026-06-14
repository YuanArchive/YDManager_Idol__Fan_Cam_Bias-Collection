import logging
import os
import sys
import tempfile
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="ydm-startup-smoke-") as temp_root:
        os.environ["LOCALAPPDATA"] = str(Path(temp_root) / "appdata")

        from src.utils.utils_logger import setup_logging
        from main import VideoSorter

        setup_logging()
        app = QApplication(sys.argv[:1])
        window = VideoSorter()
        window.show()

        QTimer.singleShot(500, window.close)
        QTimer.singleShot(1500, app.quit)

        try:
            exit_code = app.exec()
            if exit_code != 0:
                raise RuntimeError(f"QApplication exited with code {exit_code}")
        finally:
            window.close()
            app.processEvents()
            logging.shutdown()

        print(f"STARTUP_SMOKE_OK exit_code={exit_code}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
