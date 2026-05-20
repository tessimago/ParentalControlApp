"""
Background runner for Parental Control.
Launched by scheduled task at system startup. Runs silently (no console window).
Uses .pyw extension + pythonw.exe so no window appears.
"""
import os
import sys
import threading
import time
import traceback

_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _DIR)
os.chdir(_DIR)


def _crash_log(msg):
    try:
        log_dir = os.path.join(_DIR, "data", "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "crash.log"), "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except Exception:
        pass


def _kill_existing():
    """Kill any other instances of the service to avoid duplicates."""
    import psutil
    my_pid = os.getpid()
    for proc in psutil.process_iter(["pid", "cmdline"]):
        try:
            if proc.info["pid"] == my_pid:
                continue
            cmdline = proc.info.get("cmdline") or []
            if any("run_service.pyw" in arg for arg in cmdline):
                proc.terminate()
                proc.wait(timeout=5)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            continue


def main():
    # Small delay to let the old process exit cleanly during updates
    time.sleep(3)
    _kill_existing()

    from app.config import logger, DEFAULT_PORT
    from app.database import init_db, get_setting
    from app.monitor import MonitorEngine
    from app.scheduler import ScheduleEnforcer
    from app.limiter import AppLimiter
    from app.screenshots import ScreenshotCapture
    from app.updater import AutoUpdater
    from app.tunnel import CloudflareTunnel
    from app.web import create_app

    logger.info("Service starting...")
    init_db()
    logger.info("Database initialized")

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

    flask_app = create_app()
    flask_thread = threading.Thread(
        target=lambda: flask_app.run(host="0.0.0.0", port=port, threaded=True),
        daemon=True
    )
    threads.append(flask_thread)

    for t in threads:
        t.start()

    logger.info(f"All threads started. Flask on port {port}")

    # Keep alive forever
    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Service stopping...")
        stop_flag.set()
        time.sleep(2)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _crash_log(f"Service crashed: {e}\n{traceback.format_exc()}")
