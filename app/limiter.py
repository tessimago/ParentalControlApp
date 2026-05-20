import time
import threading

import psutil

from app.config import LIMITER_CHECK_INTERVAL, logger
from app.database import get_app_limits, get_usage_for_process_today, get_setting
from app.i18n import t
from app.warning import send_warning


class AppLimiter:
    def __init__(self, stop_flag: threading.Event):
        self.stop_flag = stop_flag
        self.warned_apps = set()

    def run(self):
        logger.info("App limiter started")
        while not self.stop_flag.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.error(f"Limiter tick error: {e}")
            self.stop_flag.wait(LIMITER_CHECK_INTERVAL)

    def _tick(self):
        if get_setting("limiter_enabled") != "1":
            return

        running_processes = set()
        for proc in psutil.process_iter(["name"]):
            try:
                running_processes.add(proc.info["name"].lower())
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Clear warned state for apps no longer running — re-triggers on reopen
        for app_name in list(self.warned_apps):
            if app_name.lower() not in running_processes:
                self.warned_apps.discard(app_name)

        limits = get_app_limits()
        for limit in limits:
            process_name = limit["process_name"]
            max_seconds = limit["daily_limit_minutes"] * 60
            action = limit["action"]

            used_seconds = get_usage_for_process_today(process_name)
            if used_seconds < max_seconds:
                continue

            if process_name.lower() not in running_processes:
                continue

            if action == "kill":
                if process_name not in self.warned_apps:
                    logger.info(f"Time limit exceeded for {process_name} ({used_seconds//60}m/{limit['daily_limit_minutes']}m) — killing in 10s")
                    send_warning(
                        t("time_limit_reached_kill", name=process_name),
                        timeout=10
                    )
                    self.warned_apps.add(process_name)
                    self.stop_flag.wait(10)
                    if self.stop_flag.is_set():
                        return
                self._kill_process(process_name)
            elif action == "warn":
                if process_name not in self.warned_apps:
                    logger.info(f"Time limit exceeded for {process_name} ({used_seconds//60}m/{limit['daily_limit_minutes']}m) — warning sent")
                    send_warning(
                        t("time_limit_reached_warn", name=process_name),
                        timeout=60
                    )
                    self.warned_apps.add(process_name)

    def _kill_process(self, process_name):
        killed = 0
        for proc in psutil.process_iter(["name"]):
            try:
                if proc.info["name"].lower() == process_name.lower():
                    proc.terminate()
                    killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if killed:
            logger.info(f"Killed {killed} instance(s) of {process_name}")
