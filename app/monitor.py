import time
import threading

import psutil

from app.config import MONITOR_INTERVAL, IGNORED_PROCESSES
from app.database import log_usage


class MonitorEngine:
    def __init__(self, stop_flag: threading.Event):
        self.stop_flag = stop_flag
        self.active_processes = {}

    def get_active_processes(self):
        return dict(self.active_processes)

    def run(self):
        while not self.stop_flag.is_set():
            try:
                self._tick()
            except Exception:
                pass
            self.stop_flag.wait(MONITOR_INTERVAL)

    def _tick(self):
        current = {}
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = proc.info["name"].lower()
                if name in IGNORED_PROCESSES:
                    continue
                if name not in current:
                    current[name] = proc.info["pid"]
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        for name in current:
            log_usage(name, MONITOR_INTERVAL)

        self.active_processes = current
