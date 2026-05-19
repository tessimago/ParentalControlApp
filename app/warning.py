import subprocess
import ctypes
import os


def send_warning(message, timeout=30):
    try:
        subprocess.run(
            ["msg", "*", f"/TIME:{timeout}", message],
            timeout=5,
            capture_output=True
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        _fallback_warning(message, timeout)


def _fallback_warning(message, timeout):
    try:
        # WTSSendMessage via ctypes as fallback
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
            0x00000030,  # MB_ICONWARNING
            timeout,
            ctypes.byref(response),
            False
        )
    except Exception:
        pass


def trigger_shutdown(delay=0):
    os.system(f"shutdown /s /t {delay} /f /c \"Parental Control: Time is up!\"")


def cancel_shutdown():
    os.system("shutdown /a")
