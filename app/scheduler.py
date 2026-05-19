import time
import threading
from datetime import datetime

from app.config import SCHEDULE_CHECK_INTERVAL
from app.database import get_schedule_for_day, get_override_for_date
from app.warning import send_warning, trigger_shutdown


class ScheduleEnforcer:
    def __init__(self, stop_flag: threading.Event):
        self.stop_flag = stop_flag
        self.warning_sent = False
        self.shutdown_triggered = False

    def run(self):
        while not self.stop_flag.is_set():
            try:
                self._tick()
            except Exception:
                pass
            self.stop_flag.wait(SCHEDULE_CHECK_INTERVAL)

    def _tick(self):
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        today_str = now.strftime("%Y-%m-%d")
        day_of_week = now.weekday()

        override = get_override_for_date(today_str)
        if override:
            start_time = override["start_time"]
            end_time = override["end_time"]
        else:
            schedule = get_schedule_for_day(day_of_week)
            if not schedule:
                return
            start_time = schedule["start_time"]
            end_time = schedule["end_time"]

        if start_time <= current_time <= end_time:
            self.warning_sent = False
            self.shutdown_triggered = False
            return

        if not self.warning_sent:
            send_warning(
                "Your computer time is over! Shutting down in 30 seconds...",
                timeout=30
            )
            self.warning_sent = True
            self.stop_flag.wait(30)

            if self.stop_flag.is_set():
                return

            if not self.shutdown_triggered:
                trigger_shutdown(delay=0)
                self.shutdown_triggered = True

    def is_within_schedule(self):
        now = datetime.now()
        current_time = now.strftime("%H:%M")
        today_str = now.strftime("%Y-%m-%d")
        day_of_week = now.weekday()

        override = get_override_for_date(today_str)
        if override:
            return override["start_time"] <= current_time <= override["end_time"]

        schedule = get_schedule_for_day(day_of_week)
        if not schedule:
            return True
        return schedule["start_time"] <= current_time <= schedule["end_time"]
