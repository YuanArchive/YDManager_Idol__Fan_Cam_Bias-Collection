# consts.py
import os

# --- Application Info ---
APP_NAME = "YDManager"
APP_VERSION = "8.1"
APP_ID = 'mycompany.ydmanager.subproduct.02'

# --- File Paths ---
# Use current working directory or specific logic if needed
BASE_DIR = os.getcwd()

ICON_PATH = os.path.join(BASE_DIR, "assets", "icon.ico")
TAGS_FILE = os.path.join(BASE_DIR, "index", "video_tags.json")
HIGHLIGHTS_FILE = os.path.join(BASE_DIR, "index", "video_highlights.json")
HISTORY_FILE = os.path.join(BASE_DIR, "index", "folder_history.json")
TRASH_CACHE_FILE = os.path.join(BASE_DIR, "index", "trash_cache.json")
GLOBAL_CACHE_FILE = os.path.join(BASE_DIR, "index", "video_global_cache.json")

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
