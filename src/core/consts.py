# consts.py
import os
import shutil
import sys

# --- Application Info ---
APP_NAME = "YDManager"
APP_VERSION = "8.1"
APP_ID = 'mycompany.ydmanager.subproduct.02'

# --- File Paths ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESOURCE_DIR = getattr(sys, "_MEIPASS", BASE_DIR)
USER_DATA_ROOT = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    APP_NAME,
)

def resource_path(*parts):
    return os.path.join(RESOURCE_DIR, *parts)

ICON_PATH = resource_path("assets", "icon.ico")
FONT_DIR = resource_path("assets", "fonts")
FONT_LICENSE_PATH = resource_path("assets", "fonts", "LICENSE_Pretendard.txt")

LEGACY_INDEX_DIR = os.path.join(BASE_DIR, "index")
INDEX_DIR = os.path.join(USER_DATA_ROOT, "index")
TAGS_FILE = os.path.join(INDEX_DIR, "video_tags.json")
HIGHLIGHTS_FILE = os.path.join(INDEX_DIR, "video_highlights.json")
HISTORY_FILE = os.path.join(INDEX_DIR, "folder_history.json")
TRASH_CACHE_FILE = os.path.join(INDEX_DIR, "trash_cache.json")
GLOBAL_CACHE_FILE = os.path.join(INDEX_DIR, "video_global_cache.json")

INDEX_FILE_NAMES = (
    "video_tags.json",
    "video_highlights.json",
    "folder_history.json",
    "trash_cache.json",
    "video_global_cache.json",
)

def migrate_legacy_index_files(legacy_index_dir=None, target_index_dir=None):
    legacy_index_dir = LEGACY_INDEX_DIR if legacy_index_dir is None else legacy_index_dir
    target_index_dir = INDEX_DIR if target_index_dir is None else target_index_dir

    if not os.path.isdir(legacy_index_dir):
        return []

    os.makedirs(target_index_dir, exist_ok=True)
    copied = []
    for filename in INDEX_FILE_NAMES:
        source = os.path.join(legacy_index_dir, filename)
        target = os.path.join(target_index_dir, filename)
        if os.path.exists(source) and not os.path.exists(target):
            shutil.copy2(source, target)
            copied.append(target)
    return copied

# --- UI Layout ---
LEFT_PANEL_WIDTH = 230
MENU_HEIGHT = 30
VIDEO_RATIO_W = 16
VIDEO_RATIO_H = 9

DEFAULT_WIN_W = 1280
DEFAULT_WIN_H = 720

# --- Timers (milliseconds) ---
SCAN_INTERVAL = 500
PRELOAD_DELAY = 50
SEEK_SAFETY_DELAY = 1500
RESIZE_THROTTLE = 100

# --- Defaults ---
DEFAULT_SKIP_RATIO = "10%"
DEFAULT_SEEK_INTERVAL = 2
DEFAULT_WHEEL_INTERVAL = 5
