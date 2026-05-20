"""
Parental Control - Service management.
Registers a scheduled task that runs at system startup with SYSTEM privileges.
This is more reliable than pywin32 services with venvs.
"""
import os
import sys
import subprocess
import time

_SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
TASK_NAME = "ParentalControlService"
VENV_PYTHONW = os.path.join(_SERVICE_DIR, ".venv", "Scripts", "pythonw.exe")
RUN_SCRIPT = os.path.join(_SERVICE_DIR, "run_service.pyw")


def install():
    """Register the app to run at system startup as SYSTEM."""
    # Remove existing task if any
    subprocess.run(
        ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
        capture_output=True
    )

    result = subprocess.run(
        ["schtasks", "/create",
         "/tn", TASK_NAME,
         "/tr", f'"{VENV_PYTHONW}" "{RUN_SCRIPT}"',
         "/sc", "onstart",
         "/ru", "SYSTEM",
         "/rl", "HIGHEST",
         "/f"],
        capture_output=True, text=True
    )

    if result.returncode == 0:
        print("Service installed (runs at system startup).")
    else:
        print(f"Failed to install: {result.stderr.strip()}")
        return False
    return True


def start():
    """Start the task immediately."""
    result = subprocess.run(
        ["schtasks", "/run", "/tn", TASK_NAME],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print("Service started.")
    else:
        print(f"Failed to start: {result.stderr.strip()}")


def stop():
    """Stop the running task."""
    subprocess.run(
        ["taskkill", "/f", "/im", "pythonw.exe", "/fi", f"WINDOWTITLE eq {TASK_NAME}"],
        capture_output=True
    )
    # Also kill by finding our specific process
    subprocess.run(
        ["schtasks", "/end", "/tn", TASK_NAME],
        capture_output=True
    )
    print("Service stopped.")


def remove():
    """Remove the scheduled task."""
    stop()
    subprocess.run(
        ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
        capture_output=True
    )
    print("Service removed.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: service.py [install|start|stop|remove]")
        sys.exit(1)

    cmd = sys.argv[1].lower().replace("-", "")
    # Handle pywin32-style args like "--startup auto install"
    if "install" in " ".join(sys.argv[1:]).lower():
        install()
    elif cmd == "start":
        start()
    elif cmd == "stop":
        stop()
    elif cmd in ("remove", "uninstall", "delete"):
        remove()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: service.py [install|start|stop|remove]")
