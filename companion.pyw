"""
Companion process - runs in the user's desktop session.
Handles screenshot capture and warning display since the Windows Service
runs in Session 0 and cannot access the user's desktop.

This script is launched at user login via Task Scheduler or Startup folder.
It communicates with the main service by watching a command file.
"""
import os
import sys
import time
import json
import threading
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import SCREENSHOTS_DIR, SCREENSHOT_INTERVAL, DATA_DIR
from app.database import get_setting

COMMAND_FILE = os.path.join(DATA_DIR, "companion_cmd.json")
HEARTBEAT_FILE = os.path.join(DATA_DIR, "companion_heartbeat")

try:
    import mss
    from PIL import Image
    import io
except ImportError:
    sys.exit(1)


def capture_screenshot():
    now = datetime.now()
    day_folder = os.path.join(SCREENSHOTS_DIR, now.strftime("%Y-%m-%d"))
    os.makedirs(day_folder, exist_ok=True)

    filename = now.strftime("%H-%M-%S") + ".jpg"
    filepath = os.path.join(day_folder, filename)

    with mss.mss() as sct:
        screenshot = sct.grab(sct.monitors[0])
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        img.save(filepath, "JPEG", quality=70)


def capture_live_frame():
    """Capture a frame and save it to a shared location for the web panel."""
    live_path = os.path.join(DATA_DIR, "live_frame.jpg")
    try:
        with mss.mss() as sct:
            screenshot = sct.grab(sct.monitors[0])
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
            img.save(live_path, "JPEG", quality=60)
    except Exception:
        pass


def write_heartbeat():
    try:
        with open(HEARTBEAT_FILE, "w") as f:
            f.write(datetime.now().isoformat())
    except Exception:
        pass


def check_commands():
    """Check if the service has sent any commands (e.g., take screenshot now)."""
    if not os.path.exists(COMMAND_FILE):
        return None
    try:
        with open(COMMAND_FILE, "r") as f:
            cmd = json.load(f)
        os.remove(COMMAND_FILE)
        return cmd
    except (json.JSONDecodeError, OSError):
        return None


def screenshot_loop():
    last_capture = 0
    while True:
        try:
            interval = int(get_setting("screenshot_interval") or SCREENSHOT_INTERVAL)
        except (TypeError, ValueError):
            interval = SCREENSHOT_INTERVAL

        now = time.time()
        if now - last_capture >= interval:
            capture_screenshot()
            last_capture = now

        # Always update live frame for streaming
        capture_live_frame()
        write_heartbeat()

        time.sleep(1)


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    screenshot_loop()


if __name__ == "__main__":
    main()
