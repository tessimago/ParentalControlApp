"""
Cloudflare Quick Tunnel - fully free, no account needed.
Runs cloudflared with a temporary URL that changes on restart.
Sends the URL via Telegram so you can access it from anywhere.
"""
import os
import re
import subprocess
import threading
import time

from app.config import DATA_DIR, logger
from app.database import get_setting, set_setting

CLOUDFLARED_PATH = os.path.join(DATA_DIR, "cloudflared.exe")
CLOUDFLARED_URL = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"


class CloudflareTunnel:
    def __init__(self, stop_flag: threading.Event):
        self.stop_flag = stop_flag
        self.process = None

    def run(self):
        # Wait a bit for Flask to start
        self.stop_flag.wait(5)

        # Wait for internet connectivity
        self._wait_for_internet()

        while not self.stop_flag.is_set():
            if not os.path.exists(CLOUDFLARED_PATH):
                logger.info("Downloading cloudflared...")
                if not self._download_cloudflared():
                    logger.error("Failed to download cloudflared")
                    self.stop_flag.wait(60)
                    continue

            port = get_setting("port") or "7847"
            logger.info(f"Starting tunnel on port {port}...")
            url = self._start_quick_tunnel(port)

            if url:
                logger.info(f"Tunnel connected: {url}")
                set_setting("tunnel_url", url)
                self._notify_telegram(url)
            else:
                logger.error("Tunnel failed to start")

            while not self.stop_flag.is_set() and self.process and self.process.poll() is None:
                self.stop_flag.wait(10)

            if not self.stop_flag.is_set():
                logger.info("Tunnel process exited, retrying in 15s...")
                self.stop_flag.wait(15)

        self._stop_tunnel()

    def _wait_for_internet(self):
        """Wait until we can reach the internet before starting the tunnel."""
        import urllib.request
        while not self.stop_flag.is_set():
            try:
                urllib.request.urlopen("https://cloudflare.com/cdn-cgi/trace", timeout=5)
                return
            except Exception:
                self.stop_flag.wait(10)

    def _download_cloudflared(self):
        try:
            import urllib.request
            os.makedirs(DATA_DIR, exist_ok=True)
            urllib.request.urlretrieve(CLOUDFLARED_URL, CLOUDFLARED_PATH)
            return True
        except Exception:
            return False

    def _start_quick_tunnel(self, port):
        """Start a quick tunnel and parse the generated URL from stderr."""
        try:
            self.process = subprocess.Popen(
                [CLOUDFLARED_PATH, "tunnel", "--no-autoupdate", "--url", f"http://localhost:{port}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )

            # Read stderr lines to find the URL (cloudflared prints it there)
            url = None
            deadline = time.time() + 30
            while time.time() < deadline:
                if self.stop_flag.is_set():
                    break
                line = self.process.stderr.readline().decode("utf-8", errors="ignore")
                if not line:
                    if self.process.poll() is not None:
                        break
                    continue
                match = re.search(r"(https://[a-zA-Z0-9\-]+\.trycloudflare\.com)", line)
                if match:
                    url = match.group(1)
                    break

            # Keep reading stderr in background so pipe doesn't fill
            if url:
                threading.Thread(target=self._drain_pipe, args=(self.process.stderr,), daemon=True).start()
                threading.Thread(target=self._drain_pipe, args=(self.process.stdout,), daemon=True).start()

            return url
        except Exception:
            return None

    def _drain_pipe(self, pipe):
        try:
            while True:
                line = pipe.readline()
                if not line:
                    break
        except Exception:
            pass

    def _stop_tunnel(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def _notify_telegram(self, url):
        bot_token = get_setting("telegram_bot_token")
        chat_ids_raw = get_setting("telegram_chat_id")

        if not bot_token or not chat_ids_raw:
            return

        from app.telegram_helper import telegram_send

        message = f"\U0001f5a5️ Parental Control is online!\n\n\U0001f517 {url}\n\nAccess from anywhere with this link."

        for chat_id in chat_ids_raw.split(","):
            chat_id = chat_id.strip()
            if not chat_id:
                continue
            try:
                telegram_send(bot_token, chat_id, message)
                logger.info(f"Telegram notification sent to chat {chat_id}")
            except Exception as e:
                logger.error(f"Telegram send failed for chat {chat_id}: {e}")
