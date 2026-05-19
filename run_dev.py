"""
Development runner - starts the app without Windows Service.
Use this for testing. Run: python run_dev.py
"""
import threading
from app.database import init_db
from app.monitor import MonitorEngine
from app.scheduler import ScheduleEnforcer
from app.limiter import AppLimiter
from app.screenshots import ScreenshotCapture
from app.updater import AutoUpdater
from app.tunnel import CloudflareTunnel
from app.web import create_app
from app.config import DEFAULT_PORT
from app.database import get_setting


def main():
    init_db()
    port = int(get_setting("port") or DEFAULT_PORT)
    stop_flag = threading.Event()

    monitor = MonitorEngine(stop_flag)
    scheduler = ScheduleEnforcer(stop_flag)
    limiter = AppLimiter(stop_flag)
    screenshots = ScreenshotCapture(stop_flag)
    updater = AutoUpdater(stop_flag)
    tunnel = CloudflareTunnel(stop_flag)

    threads = [
        threading.Thread(target=monitor.run, daemon=True),
        threading.Thread(target=scheduler.run, daemon=True),
        threading.Thread(target=limiter.run, daemon=True),
        threading.Thread(target=screenshots.run, daemon=True),
        threading.Thread(target=updater.run, daemon=True),
        threading.Thread(target=tunnel.run, daemon=True),
    ]

    for t in threads:
        t.start()

    app = create_app()
    print(f"Starting Parental Control on http://0.0.0.0:{port}")
    print("Default password: admin")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()
