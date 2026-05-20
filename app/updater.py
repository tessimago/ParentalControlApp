import os
import sys
import subprocess
import threading
import time

from app.config import BASE_DIR, VENV_DIR, UPDATE_CHECK_INTERVAL, SERVICE_NAME, logger
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
                    logger.info("Update available, applying...")
                    self._apply_update()
                else:
                    logger.info("No updates available")
            except Exception as e:
                logger.error(f"Update check failed: {e}")

    def _check_for_updates(self):
        # Ensure SYSTEM can access user-owned repo
        subprocess.run(
            ["git", "config", "--global", "--add", "safe.directory", BASE_DIR.replace("\\", "/")],
            capture_output=True, timeout=5
        )

        result = subprocess.run(
            ["git", "fetch", "origin", "main"],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode != 0:
            logger.warning(f"git fetch failed: {result.stderr.strip()}")
            return False

        local = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=10
        )
        remote = subprocess.run(
            ["git", "rev-parse", "origin/main"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=10
        )
        if local.returncode != 0 or remote.returncode != 0:
            return False

        local_hash = local.stdout.strip()
        remote_hash = remote.stdout.strip()
        if local_hash != remote_hash:
            logger.info(f"Update available: local={local_hash[:8]} remote={remote_hash[:8]}")
            return True
        return False

    def _apply_update(self):
        subprocess.run(
            ["git", "reset", "--hard", "origin/main"],
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
        """Restart by launching a fully detached new instance and exiting."""
        pythonw = os.path.join(VENV_DIR, "Scripts", "pythonw.exe")
        run_script = os.path.join(BASE_DIR, "run_service.pyw")
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        subprocess.Popen(
            [pythonw, run_script],
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            close_fds=True
        )
        time.sleep(2)
        os._exit(0)
