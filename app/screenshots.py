import os
import io
import shutil
import threading
from datetime import datetime, timedelta

from app.config import SCREENSHOTS_DIR, SCREENSHOT_INTERVAL, SCREENSHOT_RETENTION_DAYS, DATA_DIR
from app.database import get_setting

LIVE_FRAME_PATH = os.path.join(DATA_DIR, "live_frame.jpg")


class ScreenshotCapture:
    """
    When running as a service (Session 0), screenshots are handled by the
    companion process. This thread only handles cleanup of old screenshots.
    When running in dev mode (run_dev.py), it captures directly.
    """
    def __init__(self, stop_flag: threading.Event):
        self.stop_flag = stop_flag
        self.is_session_0 = self._detect_session_0()

    def _detect_session_0(self):
        try:
            import ctypes
            session_id = ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
            current_session = ctypes.windll.kernel32.ProcessIdToSessionId(
                os.getpid(), ctypes.byref(ctypes.c_ulong())
            )
            # If we can grab a screen, we're not in Session 0
            import mss
            with mss.mss() as sct:
                sct.grab(sct.monitors[0])
            return False
        except Exception:
            return True

    def run(self):
        while not self.stop_flag.is_set():
            try:
                if not self.is_session_0:
                    self._capture_and_save()
                self._cleanup_old()
            except Exception:
                pass
            interval = int(get_setting("screenshot_interval") or SCREENSHOT_INTERVAL)
            self.stop_flag.wait(interval)

    def _capture_and_save(self):
        import mss
        from PIL import Image

        now = datetime.now()
        day_folder = os.path.join(SCREENSHOTS_DIR, now.strftime("%Y-%m-%d"))
        os.makedirs(day_folder, exist_ok=True)

        filename = now.strftime("%H-%M-%S") + ".jpg"
        filepath = os.path.join(day_folder, filename)

        with mss.mss() as sct:
            screenshot = sct.grab(sct.monitors[0])
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            img.save(filepath, "JPEG", quality=70)

    def _cleanup_old(self):
        retention = int(get_setting("screenshot_retention_days") or SCREENSHOT_RETENTION_DAYS)
        cutoff = datetime.now() - timedelta(days=retention)

        if not os.path.exists(SCREENSHOTS_DIR):
            return

        for folder_name in os.listdir(SCREENSHOTS_DIR):
            folder_path = os.path.join(SCREENSHOTS_DIR, folder_name)
            if not os.path.isdir(folder_path):
                continue
            try:
                folder_date = datetime.strptime(folder_name, "%Y-%m-%d")
                if folder_date < cutoff:
                    shutil.rmtree(folder_path)
            except ValueError:
                continue


def capture_frame():
    """
    Get a live frame. First try reading from the companion process's shared file.
    If that's stale or missing, try capturing directly.
    """
    # Try companion's live frame first
    if os.path.exists(LIVE_FRAME_PATH):
        try:
            age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(LIVE_FRAME_PATH))).total_seconds()
            if age < 5:
                with open(LIVE_FRAME_PATH, "rb") as f:
                    return f.read()
        except Exception:
            pass

    # Fallback: try direct capture (works in dev mode)
    try:
        import mss
        from PIL import Image

        with mss.mss() as sct:
            screenshot = sct.grab(sct.monitors[0])
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
            buffer = io.BytesIO()
            img.save(buffer, "JPEG", quality=60)
            return buffer.getvalue()
    except Exception:
        # Return a placeholder
        return b""


def get_screenshot_dates():
    if not os.path.exists(SCREENSHOTS_DIR):
        return []
    dates = []
    for name in sorted(os.listdir(SCREENSHOTS_DIR), reverse=True):
        if os.path.isdir(os.path.join(SCREENSHOTS_DIR, name)):
            dates.append(name)
    return dates


def get_screenshots_for_date(date_str):
    day_folder = os.path.join(SCREENSHOTS_DIR, date_str)
    if not os.path.exists(day_folder):
        return []
    files = sorted(os.listdir(day_folder))
    return [f for f in files if f.endswith(".jpg")]


def get_screenshot_path(date_str, filename):
    return os.path.join(SCREENSHOTS_DIR, date_str, filename)
