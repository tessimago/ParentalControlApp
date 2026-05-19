import os
import sys
import threading
import time

import servicemanager
import win32event
import win32service
import win32serviceutil

# Ensure the project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import SERVICE_NAME, SERVICE_DISPLAY_NAME, SERVICE_DESCRIPTION


class ParentalControlService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.running = True

    def SvcStop(self):
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.running = False
        win32event.SetEvent(self.stop_event)

    def SvcDoRun(self):
        self.ReportServiceStatus(win32service.SERVICE_START_PENDING)
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, "")
        )
        self.main()

    def main(self):
        import logging
        from app.config import logger, DEFAULT_PORT

        try:
            from app.database import init_db
            from app.monitor import MonitorEngine
            from app.scheduler import ScheduleEnforcer
            from app.limiter import AppLimiter
            from app.screenshots import ScreenshotCapture
            from app.updater import AutoUpdater
            from app.tunnel import CloudflareTunnel
            from app.web import create_app
            from app.database import get_setting

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
            self.ReportServiceStatus(win32service.SERVICE_RUNNING)

            while self.running:
                if win32event.WaitForSingleObject(self.stop_event, 1000) == win32event.WAIT_OBJECT_0:
                    break

            logger.info("Service stopping...")
            stop_flag.set()
            time.sleep(2)
            logger.info("Service stopped")

        except Exception as e:
            logger.exception(f"Service crashed: {e}")
            raise


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(ParentalControlService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(ParentalControlService)
