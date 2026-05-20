import os
import sys
import subprocess
import threading
import time

from app.config import BASE_DIR, VENV_DIR, UPDATE_CHECK_INTERVAL, SERVICE_NAME
from app.database import get_setting


class AutoUpdater:
    def __init__(self, stop_flag: threading.Event):
        self.stop_flag = stop_flag

    def run(self):
        while not self.stop_flag.is_set():
            try:
                interval = int(get_setting("update_check_interval") or UPDATE_CHECK_INTERVAL)
            except (TypeError, ValueError):
                interval = UPDATE_CHECK_INTERVAL
            self.stop_flag.wait(interval)
            if self.stop_flag.is_set():
                break
            try:
                if self._check_for_updates():
                    self._apply_update()
            except Exception:
                pass

    def _check_for_updates(self):
        result = subprocess.run(
            ["git", "fetch"],
            cwd=BASE_DIR,
            capture_output=True,
            timeout=30
        )
        if result.returncode != 0:
            return False

        result = subprocess.run(
            ["git", "status", "-uno"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=10
        )
        return "behind" in result.stdout.lower()

    def _apply_update(self):
        subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=BASE_DIR,
            capture_output=True,
            timeout=60
        )

        python_path = os.path.join(VENV_DIR, "Scripts", "python.exe")
        requirements_path = os.path.join(BASE_DIR, "requirements.txt")
        subprocess.run(
            [python_path, "-m", "pip", "install", "-r", requirements_path, "--quiet"],
            capture_output=True,
            timeout=120
        )

        self._restart()

    def _restart(self):
        """Restart by launching a new instance and exiting this one."""
        pythonw = os.path.join(VENV_DIR, "Scripts", "pythonw.exe")
        run_script = os.path.join(BASE_DIR, "run_service.pyw")
        subprocess.Popen([pythonw, run_script])
        time.sleep(1)
        os._exit(0)
