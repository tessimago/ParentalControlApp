import subprocess
import ctypes
import json
import os
import sys
import time

from app.config import BASE_DIR, VENV_DIR, DATA_DIR, logger
from app.i18n import t

COMMAND_FILE = os.path.join(DATA_DIR, "companion_cmd.json")


def send_warning(message, timeout=30):
    """Show a fullscreen popup for system warnings (schedule, limits)."""
    logger.info(f"Warning popup: \"{message}\" (timeout={timeout}s)")
    _launch_popup(message, timeout, header="PARENTAL CONTROL")


def send_popup(message, timeout=60, parent_name="Parent"):
    """Show a fullscreen popup with custom parent name."""
    _launch_popup(message, timeout, header=parent_name)


def _launch_popup(message, timeout, header="PARENTAL CONTROL"):
    msg_from = t("message_from")
    closes_in = t("closes_in", seconds="{seconds}")
    click_ok = t("click_ok")

    # Try routing through the companion process (works from Session 0)
    if _send_to_companion(message, timeout, header, msg_from, closes_in, click_ok):
        return

    # Direct launch (works if we're in the user session)
    popup_script = os.path.join(BASE_DIR, "app", "popup.py")
    python_exe = os.path.join(VENV_DIR, "Scripts", "pythonw.exe")

    if not os.path.exists(python_exe):
        python_exe = sys.executable

    try:
        subprocess.Popen(
            [python_exe, popup_script, message, str(timeout), header, msg_from, closes_in, click_ok],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        )
    except Exception:
        _fallback_msg(message, timeout)


def _send_to_companion(message, timeout, header, msg_from, closes_in, click_ok):
    """Write a command file for the companion to pick up and display."""
    try:
        cmd = {
            "action": "popup",
            "message": message,
            "timeout": timeout,
            "header": header,
            "msg_from": msg_from,
            "closes_in": closes_in,
            "click_ok": click_ok,
            "timestamp": time.time(),
        }
        with open(COMMAND_FILE, "w") as f:
            json.dump(cmd, f)
        return True
    except Exception:
        return False


def _fallback_msg(message, timeout):
    """Fallback to Windows msg command if popup fails."""
    try:
        subprocess.run(
            ["msg", "*", f"/TIME:{timeout}", message],
            timeout=5,
            capture_output=True
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        _fallback_wts(message, timeout)


def _fallback_wts(message, timeout):
    try:
        wtsapi = ctypes.windll.wtsapi32
        kernel32 = ctypes.windll.kernel32
        WTS_CURRENT_SERVER_HANDLE = 0

        session_id = kernel32.WTSGetActiveConsoleSessionId()
        if session_id == 0xFFFFFFFF:
            return

        response = ctypes.c_ulong()
        wtsapi.WTSSendMessageW(
            WTS_CURRENT_SERVER_HANDLE,
            session_id,
            "Parental Control",
            len("Parental Control") * 2,
            message,
            len(message) * 2,
            0x00000030,
            timeout,
            ctypes.byref(response),
            False
        )
    except Exception:
        pass


def trigger_shutdown(delay=0):
    logger.info(f"Triggering system shutdown (delay={delay}s)")
    os.system(f"shutdown /s /t {delay} /f /c \"Parental Control: Time is up!\"")


def cancel_shutdown():
    os.system("shutdown /a")
