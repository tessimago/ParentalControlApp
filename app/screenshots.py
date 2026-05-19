import os
import io
import time
import shutil
import threading
from datetime import datetime, timedelta

import mss
from PIL import Image

from app.config import SCREENSHOTS_DIR, SCREENSHOT_INTERVAL, SCREENSHOT_RETENTION_DAYS
from app.database import get_setting


class ScreenshotCapture:
    def __init__(self, stop_flag: threading.Event):
        self.stop_flag = stop_flag

    def run(self):
        while not self.stop_flag.is_set():
            try:
                self._capture_and_save()
                self._cleanup_old()
            except Exception:
                pass
            interval = int(get_setting("screenshot_interval") or SCREENSHOT_INTERVAL)
            self.stop_flag.wait(interval)

    def _capture_and_save(self):
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
    with mss.mss() as sct:
        screenshot = sct.grab(sct.monitors[0])
        img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        img = img.resize((img.width // 2, img.height // 2), Image.LANCZOS)
        buffer = io.BytesIO()
        img.save(buffer, "JPEG", quality=60)
        return buffer.getvalue()


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
