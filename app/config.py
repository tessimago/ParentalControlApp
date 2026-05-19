import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "parental_control.db")
SCREENSHOTS_DIR = r"C:\ProgramData\ParentalControl\.screenshots"
VENV_DIR = os.path.join(BASE_DIR, ".venv")

DEFAULT_PORT = 7847
DEFAULT_PASSWORD = "admin"
SERVICE_NAME = "ParentalControl"
SERVICE_DISPLAY_NAME = "Parental Control Service"
SERVICE_DESCRIPTION = "Monitors and controls child PC usage"

MONITOR_INTERVAL = 5
SCHEDULE_CHECK_INTERVAL = 30
LIMITER_CHECK_INTERVAL = 30
SCREENSHOT_INTERVAL = 300
UPDATE_CHECK_INTERVAL = 900
SCREENSHOT_RETENTION_DAYS = 30

IGNORED_PROCESSES = {
    "system", "system idle process", "registry", "smss.exe", "csrss.exe",
    "wininit.exe", "services.exe", "lsass.exe", "svchost.exe", "dwm.exe",
    "winlogon.exe", "fontdrvhost.exe", "spoolsv.exe", "sihost.exe",
    "taskhostw.exe", "ctfmon.exe", "runtimebroker.exe", "searchhost.exe",
    "startmenuexperiencehost.exe", "shellexperiencehost.exe", "textinputhost.exe",
    "dllhost.exe", "conhost.exe", "securityhealthservice.exe",
    "securityhealthsystray.exe", "sgrmbroker.exe", "dashost.exe",
    "gameinputsvc.exe", "audiodg.exe", "searchindexer.exe",
    "microsoftedgeupdate.exe", "msedgewebview2.exe", "widgetservice.exe",
    "widgets.exe", "lockapp.exe", "smartscreen.exe", "crashpad_handler.exe",
    "parentalcontrol.exe", "python.exe", "pythonservice.exe",
}
