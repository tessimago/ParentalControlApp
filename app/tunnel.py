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

from app.config import DATA_DIR
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

        while not self.stop_flag.is_set():
            if not os.path.exists(CLOUDFLARED_PATH):
                if not self._download_cloudflared():
                    self.stop_flag.wait(60)
                    continue

            port = get_setting("port") or "7847"
            url = self._start_quick_tunnel(port)

            if url:
                set_setting("tunnel_url", url)
                self._notify_telegram(url)

            # Wait for tunnel process to exit or stop signal
            while not self.stop_flag.is_set() and self.process and self.process.poll() is None:
                self.stop_flag.wait(10)

            # Tunnel crashed — retry after delay
            if not self.stop_flag.is_set():
                self.stop_flag.wait(15)

        self._stop_tunnel()

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
        chat_id = get_setting("telegram_chat_id")

        if not bot_token or not chat_id:
            return

        try:
            import urllib.request
            import urllib.parse

            message = f"🖥️ Parental Control is online!\n\n🔗 {url}\n\nAccess from anywhere with this link."
            api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            data = urllib.parse.urlencode({
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }).encode()

            req = urllib.request.Request(api_url, data=data)
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass
