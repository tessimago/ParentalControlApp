import time
import threading

import psutil

from app.config import LIMITER_CHECK_INTERVAL
from app.database import get_app_limits, get_usage_for_process_today, get_setting
from app.warning import send_warning


class AppLimiter:
    def __init__(self, stop_flag: threading.Event):
        self.stop_flag = stop_flag
        self.warned_apps = set()

    def run(self):
        while not self.stop_flag.is_set():
            try:
                self._tick()
            except Exception:
                pass
            self.stop_flag.wait(LIMITER_CHECK_INTERVAL)

    def _tick(self):
        if get_setting("limiter_enabled") != "1":
            return

        limits = get_app_limits()
        for limit in limits:
            process_name = limit["process_name"]
            max_seconds = limit["daily_limit_minutes"] * 60
            action = limit["action"]

            used_seconds = get_usage_for_process_today(process_name)
            if used_seconds < max_seconds:
                self.warned_apps.discard(process_name)
                continue

            if action == "kill":
                if process_name not in self.warned_apps:
                    send_warning(
                        f"Time limit reached for {process_name}! Closing in 10 seconds...",
                        timeout=10
                    )
                    self.warned_apps.add(process_name)
                    self.stop_flag.wait(10)
                    if self.stop_flag.is_set():
                        return
                self._kill_process(process_name)
            elif action == "warn":
                if process_name not in self.warned_apps:
                    send_warning(
                        f"Time limit reached for {process_name}! Please close it.",
                        timeout=60
                    )
                    self.warned_apps.add(process_name)

    def _kill_process(self, process_name):
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"].lower() == process_name.lower():
                    proc.terminate()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
