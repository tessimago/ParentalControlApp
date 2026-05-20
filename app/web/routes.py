import os
import shutil
import threading
import time
from datetime import datetime, timedelta

from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, jsonify, Response, send_file
)

from app.web.auth import login_required, check_password, change_password
from app.database import (
    get_schedules, update_schedule, set_override, get_override_for_date,
    get_app_limits, set_app_limit, delete_app_limit,
    get_usage_for_date, get_usage_for_process_today, get_usage_range,
    get_setting, set_setting,
    get_tracked_apps, add_tracked_app, remove_tracked_app,
    get_hidden_apps, hide_app, unhide_app
)
from app.screenshots import (
    capture_frame, get_screenshot_dates, get_screenshots_for_date, get_screenshot_path
)
from app.config import SCREENSHOTS_DIR, LOG_DIR, logger

bp = Blueprint("main", __name__)


# --- Auth ---

@bp.route("/login", methods=["GET", "POST"])
def login():
    from app.i18n import t
    if request.method == "POST":
        password = request.form.get("password", "")
        if check_password(password):
            session["authenticated"] = True
            logger.info(f"Parent logged in from {request.remote_addr}")
            return redirect(url_for("main.dashboard"))
        logger.warning(f"Failed login attempt from {request.remote_addr}")
        flash(t("invalid_password"), "error")
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


# --- Dashboard ---

@bp.route("/")
@login_required
def dashboard():
    import psutil

    today = datetime.now().strftime("%Y-%m-%d")
    usage_today = get_usage_for_date(today)
    schedules = get_schedules()
    now = datetime.now()
    day_of_week = now.weekday()

    override = get_override_for_date(today)
    current_schedule = None
    for s in schedules:
        if s["day_of_week"] == day_of_week:
            current_schedule = s
            break
    if override:
        current_schedule = override

    active_users = len(psutil.users()) > 0

    # Get tracked apps and check which are currently running
    tracked = get_tracked_apps()
    running_processes = set()
    for proc in psutil.process_iter(["name"]):
        try:
            running_processes.add(proc.info["name"].lower())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    tracked_status = []
    for app in tracked:
        tracked_status.append({
            "process_name": app["process_name"],
            "display_name": app["display_name"],
            "is_running": app["process_name"].lower() in running_processes,
            "time_today": get_usage_for_process_today(app["process_name"]),
        })

    hidden = get_hidden_apps()
    usage_today = [u for u in usage_today if u["process_name"] not in hidden]

    return render_template(
        "dashboard.html",
        usage_today=usage_today,
        current_schedule=current_schedule,
        now=now,
        active_users=active_users,
        override=override,
        tracked_status=tracked_status
    )


@bp.route("/api/dashboard")
@login_required
def api_dashboard():
    import psutil

    today = datetime.now().strftime("%Y-%m-%d")
    usage_today = get_usage_for_date(today)
    active_users = len(psutil.users()) > 0

    running_processes = set()
    for proc in psutil.process_iter(["name"]):
        try:
            running_processes.add(proc.info["name"].lower())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    tracked = get_tracked_apps()
    tracked_status = []
    for app in tracked:
        tracked_status.append({
            "process_name": app["process_name"],
            "display_name": app["display_name"],
            "is_running": app["process_name"].lower() in running_processes,
            "time_today": get_usage_for_process_today(app["process_name"]),
        })

    hidden = get_hidden_apps()
    usage_today = [u for u in usage_today if u["process_name"] not in hidden]

    return jsonify({
        "active_users": active_users,
        "time": datetime.now().strftime("%H:%M:%S"),
        "tracked": tracked_status,
        "usage": usage_today
    })


# --- Send Message ---

@bp.route("/message", methods=["POST"])
@login_required
def send_message():
    from app.warning import send_popup
    from app.i18n import t
    message = request.form.get("message", "").strip()
    timeout = int(request.form.get("timeout", 60))
    if message:
        parent_name = get_setting("parent_name") or "Parent"
        send_popup(message, timeout=timeout, parent_name=parent_name)
        logger.info(f"Message sent to child: \"{message}\"")
        flash(t("message_sent"), "success")
    return redirect(url_for("main.dashboard"))


# --- Kill Process ---

@bp.route("/kill", methods=["POST"])
@login_required
def kill_process():
    import psutil
    from app.i18n import t
    process_name = request.form.get("process_name", "").lower()
    killed = 0
    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"].lower() == process_name:
                proc.kill()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    if killed:
        logger.info(f"Parent killed {killed} instance(s) of {process_name}")
        flash(t("killed_instances", count=killed, name=process_name), "success")
    else:
        flash(t("not_running_error", name=process_name), "error")
    return redirect(url_for("main.dashboard"))


# --- Tracked Apps ---

@bp.route("/tracked")
@login_required
def tracked():
    import psutil
    from app.config import IGNORED_PROCESSES

    tracked_apps = get_tracked_apps()
    today = datetime.now().strftime("%Y-%m-%d")

    # Get all currently running non-system processes
    running = set()
    for proc in psutil.process_iter(["name"]):
        try:
            name = proc.info["name"].lower()
            if name not in IGNORED_PROCESSES:
                running.add(name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Also include processes from today's usage that aren't running now
    usage_today = get_usage_for_date(today)
    all_processes = sorted(running | {u["process_name"] for u in usage_today})

    tracked_names = {a["process_name"] for a in tracked_apps}

    return render_template(
        "tracked.html",
        tracked_apps=tracked_apps,
        all_processes=all_processes,
        tracked_names=tracked_names
    )


@bp.route("/tracked", methods=["POST"])
@login_required
def tracked_update():
    from app.i18n import t
    action_type = request.form.get("action_type")

    if action_type == "remove":
        process_name = request.form.get("process_name")
        if process_name:
            remove_tracked_app(process_name)
            logger.info(f"Removed {process_name} from watchlist")
            flash(t("removed_watchlist", name=process_name), "success")
    else:
        process_name = request.form.get("process_name", "").strip().lower()
        display_name = request.form.get("display_name", "").strip()
        if process_name:
            if not display_name:
                display_name = process_name.replace(".exe", "").title()
            add_tracked_app(process_name, display_name)
            logger.info(f"Added {display_name} ({process_name}) to watchlist")
            flash(t("added_watchlist", name=display_name), "success")

    return redirect(url_for("main.tracked"))


# --- Schedule ---

@bp.route("/schedule")
@login_required
def schedule():
    schedules = get_schedules()
    today = datetime.now().strftime("%Y-%m-%d")
    override = get_override_for_date(today)
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return render_template("schedule.html", schedules=schedules, override=override, day_names=day_names)


@bp.route("/schedule", methods=["POST"])
@login_required
def schedule_update():
    from app.i18n import t
    for day in range(7):
        start = request.form.get(f"start_{day}")
        end = request.form.get(f"end_{day}")
        if start and end:
            update_schedule(day, start, end)
    logger.info("Weekly schedule updated")
    flash(t("schedule_updated"), "success")
    return redirect(url_for("main.schedule"))


@bp.route("/schedule/extend", methods=["POST"])
@login_required
def schedule_extend():
    from app.i18n import t
    today = datetime.now().strftime("%Y-%m-%d")
    start = request.form.get("start_time", "06:00")
    end = request.form.get("end_time")
    if end:
        set_override(today, start, end)
        logger.info(f"Today's schedule extended until {end}")
        flash(t("extended_until", time=end), "success")
    return redirect(url_for("main.schedule"))


# --- App Limits ---

@bp.route("/limits")
@login_required
def limits():
    app_limits = get_app_limits()
    return render_template("limits.html", app_limits=app_limits)


@bp.route("/limits", methods=["POST"])
@login_required
def limits_update():
    from app.i18n import t
    action_type = request.form.get("action_type")

    if action_type == "delete":
        process_name = request.form.get("delete_process")
        if process_name:
            delete_app_limit(process_name)
            logger.info(f"Limit removed for {process_name}")
            flash(t("limit_removed", name=process_name), "success")
    else:
        process_name = request.form.get("process_name", "").strip().lower()
        minutes = request.form.get("daily_limit_minutes")
        action = request.form.get("action", "warn")
        if process_name and minutes:
            set_app_limit(process_name, int(minutes), action)
            logger.info(f"Limit set for {process_name}: {minutes}min, action={action}")
            flash(t("limit_set", name=process_name), "success")

    return redirect(url_for("main.limits"))


# --- History ---

@bp.route("/history")
@login_required
def history():
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    show_hidden = request.args.get("show_hidden", "0") == "1"
    usage = get_usage_for_date(date_str)
    tracked = {a["process_name"] for a in get_tracked_apps()}
    hidden = get_hidden_apps()

    tracked_usage = [u for u in usage if u["process_name"] in tracked]
    other_usage = [u for u in usage if u["process_name"] not in tracked and u["process_name"] not in hidden]
    hidden_usage = [u for u in usage if u["process_name"] in hidden]

    return render_template(
        "history.html",
        tracked_usage=tracked_usage,
        other_usage=other_usage,
        hidden_usage=hidden_usage,
        show_hidden=show_hidden,
        selected_date=date_str,
        usage=usage
    )


@bp.route("/api/hide", methods=["POST"])
@login_required
def api_hide():
    process_name = request.form.get("process_name")
    if process_name:
        hide_app(process_name)
    return jsonify({"ok": True})


@bp.route("/api/unhide", methods=["POST"])
@login_required
def api_unhide():
    process_name = request.form.get("process_name")
    if process_name:
        unhide_app(process_name)
    return jsonify({"ok": True})


@bp.route("/api/history")
@login_required
def api_history():
    days = int(request.args.get("days", 7))
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days - 1)).strftime("%Y-%m-%d")
    data = get_usage_range(start_date, end_date)
    return jsonify(data)


# --- Screenshots ---

@bp.route("/screenshots")
@login_required
def screenshots():
    dates = get_screenshot_dates()
    return render_template("screenshots.html", dates=dates, selected_date=None, images=[])


@bp.route("/screenshots/<date>")
@login_required
def screenshots_date(date):
    dates = get_screenshot_dates()
    images = get_screenshots_for_date(date)
    return render_template("screenshots.html", dates=dates, selected_date=date, images=images)


@bp.route("/screenshots/image/<date>/<filename>")
@login_required
def screenshot_image(date, filename):
    path = get_screenshot_path(date, filename)
    return send_file(path, mimetype="image/jpeg")


@bp.route("/screenshots/live")
@login_required
def live_view():
    return render_template("live.html")


@bp.route("/api/live/stream")
@login_required
def live_stream():
    def generate():
        while True:
            try:
                frame = capture_frame()
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
            except Exception:
                pass
            time.sleep(1)

    return Response(generate(), mimetype="multipart/x-mixed-replace; boundary=frame")


@bp.route("/screenshots/delete/<date>", methods=["POST"])
@login_required
def delete_screenshot_day(date):
    from app.i18n import t
    day_folder = os.path.join(SCREENSHOTS_DIR, date)
    if os.path.exists(day_folder):
        shutil.rmtree(day_folder)
        logger.info(f"Deleted all screenshots for {date}")
        flash(t("deleted_screenshots", date=date), "success")
    return redirect(url_for("main.screenshots"))


@bp.route("/screenshots/delete/<date>/<filename>", methods=["POST"])
@login_required
def delete_screenshot(date, filename):
    from app.i18n import t
    filepath = get_screenshot_path(date, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        flash(t("deleted_file", name=filename), "success")
    return redirect(url_for("main.screenshots_date", date=date))


# --- Settings ---

@bp.route("/settings")
@login_required
def settings():
    import subprocess
    from app.config import BASE_DIR

    current_settings = {
        "port": get_setting("port") or "7847",
        "screenshot_interval": get_setting("screenshot_interval") or "300",
        "screenshot_retention_days": get_setting("screenshot_retention_days") or "30",
        "update_check_interval": get_setting("update_check_interval") or "900",
        "schedule_enabled": get_setting("schedule_enabled") or "0",
        "limiter_enabled": get_setting("limiter_enabled") or "0",
        "parent_name": get_setting("parent_name") or "Parent",
        "language": get_setting("language") or "en",
        "telegram_bot_token": get_setting("telegram_bot_token") or "",
        "telegram_chat_id": get_setting("telegram_chat_id") or "",
        "tunnel_url": get_setting("tunnel_url") or "",
    }

    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-1"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=5
        )
        current_settings["version"] = result.stdout.strip() if result.returncode == 0 else "unknown"
    except Exception:
        current_settings["version"] = "unknown"

    return render_template("settings.html", settings=current_settings)


@bp.route("/settings", methods=["POST"])
@login_required
def settings_update():
    from app.i18n import t

    new_password = request.form.get("new_password")
    if new_password:
        change_password(new_password)
        logger.info("Password changed")
        flash(t("password_changed"), "success")

    for key in ["screenshot_interval", "screenshot_retention_days", "update_check_interval"]:
        value = request.form.get(key)
        if value:
            set_setting(key, value)

    parent_name = request.form.get("parent_name", "").strip()
    if parent_name:
        set_setting("parent_name", parent_name)

    language = request.form.get("language", "en")
    set_setting("language", language)

    for key in ["telegram_bot_token", "telegram_chat_id"]:
        value = request.form.get(key, "").strip()
        set_setting(key, value)

    set_setting("schedule_enabled", "1" if request.form.get("schedule_enabled") else "0")
    set_setting("limiter_enabled", "1" if request.form.get("limiter_enabled") else "0")

    # Auto-fetch chat ID if token is set but chat ID is empty
    bot_token = get_setting("telegram_bot_token")
    chat_id = get_setting("telegram_chat_id")
    if bot_token and not chat_id:
        fetched_id = _fetch_telegram_chat_id(bot_token)
        if fetched_id:
            set_setting("telegram_chat_id", fetched_id)
            flash(t("telegram_auto_detected", id=fetched_id), "success")
        else:
            flash(t("telegram_send_message"), "error")

    logger.info("Settings updated")
    flash(t("settings_updated"), "success")
    return redirect(url_for("main.settings"))


def _fetch_telegram_chat_id(bot_token):
    try:
        from app.telegram_helper import telegram_get_updates
        chat_ids = telegram_get_updates(bot_token)
        if chat_ids:
            return ", ".join(sorted(chat_ids))
    except Exception:
        pass
    return None


@bp.route("/api/telegram/detect", methods=["POST"])
@login_required
def api_telegram_detect():
    from app.i18n import t
    bot_token = get_setting("telegram_bot_token")
    if not bot_token:
        return jsonify({"ok": False, "error": "No bot token configured"})

    fetched_id = _fetch_telegram_chat_id(bot_token)
    if fetched_id:
        existing = get_setting("telegram_chat_id") or ""
        # Merge with any existing IDs
        all_ids = set(i.strip() for i in existing.split(",") if i.strip())
        all_ids.update(i.strip() for i in fetched_id.split(",") if i.strip())
        merged = ", ".join(sorted(all_ids))
        set_setting("telegram_chat_id", merged)
        return jsonify({"ok": True, "chat_ids": merged})
    else:
        return jsonify({"ok": False, "error": t("telegram_send_message")})


@bp.route("/api/telegram/test", methods=["POST"])
@login_required
def api_telegram_test():
    from app.telegram_helper import telegram_send

    bot_token = get_setting("telegram_bot_token")
    chat_ids_raw = get_setting("telegram_chat_id")

    if not bot_token:
        return jsonify({"ok": False, "error": "No bot token configured"})
    if not chat_ids_raw:
        return jsonify({"ok": False, "error": "No chat IDs configured"})

    message = "✅ Parental Control test — Telegram is working!"
    sent = 0
    errors = []

    for chat_id in chat_ids_raw.split(","):
        chat_id = chat_id.strip()
        if not chat_id:
            continue
        try:
            telegram_send(bot_token, chat_id, message)
            sent += 1
        except Exception as e:
            errors.append(f"{chat_id}: {str(e)}")

    if sent > 0:
        return jsonify({"ok": True, "sent": sent})
    else:
        return jsonify({"ok": False, "error": "; ".join(errors)})


# --- Logs ---

@bp.route("/logs")
@login_required
def logs():
    return render_template("logs.html")


@bp.route("/api/logs")
@login_required
def api_logs():
    log_file = os.path.join(LOG_DIR, "service.log")
    lines = []
    if os.path.exists(log_file):
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-100:]
    crash_file = os.path.join(LOG_DIR, "crash.log")
    crash_lines = []
    if os.path.exists(crash_file):
        with open(crash_file, "r", encoding="utf-8", errors="ignore") as f:
            crash_lines = f.readlines()[-20:]
    return jsonify({"logs": lines, "crashes": crash_lines})


# --- Remove Control ---

@bp.route("/api/remove-control", methods=["POST"])
@login_required
def api_remove_control():
    import subprocess
    import signal

    logger.info("REMOVE CONTROL triggered by parent")

    errors = []

    # 1. Delete the startup scheduled task
    try:
        subprocess.run(
            ["schtasks", "/delete", "/tn", "ParentalControl", "/f"],
            capture_output=True, timeout=10
        )
        logger.info("Removed ParentalControl scheduled task")
    except Exception as e:
        errors.append(f"Task removal: {e}")

    # 2. Delete the companion scheduled task
    try:
        subprocess.run(
            ["schtasks", "/delete", "/tn", "ParentalControlCompanion", "/f"],
            capture_output=True, timeout=10
        )
        logger.info("Removed ParentalControlCompanion scheduled task")
    except Exception as e:
        errors.append(f"Companion task removal: {e}")

    # 3. Kill companion and tunnel processes
    try:
        subprocess.run(
            ["taskkill", "/f", "/im", "pythonw.exe", "/fi", "WINDOWTITLE eq ParentalControlCompanion"],
            capture_output=True, timeout=10
        )
    except Exception:
        pass
    try:
        subprocess.run(
            ["taskkill", "/f", "/im", "cloudflared.exe"],
            capture_output=True, timeout=10
        )
    except Exception:
        pass

    if errors:
        return jsonify({"ok": False, "error": "; ".join(errors)})

    # 4. Schedule self-termination (give time for the response to reach the browser)
    def _shutdown():
        time.sleep(2)
        logger.info("Service shutting down after Remove Control")
        os._exit(0)

    threading.Thread(target=_shutdown, daemon=True).start()

    return jsonify({"ok": True})


# --- Update ---

@bp.route("/api/update", methods=["POST"])
@login_required
def api_update():
    import subprocess
    from app.config import BASE_DIR

    try:
        result = subprocess.run(
            ["git", "fetch", "origin", "main"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            logger.warning(f"Manual update: git fetch failed — {result.stderr.strip()}")
            return jsonify({"ok": False, "error": "git fetch failed", "status": "no_git"})

        local = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=10
        )
        remote = subprocess.run(
            ["git", "rev-parse", "origin/main"],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=10
        )
        if local.returncode != 0 or remote.returncode != 0:
            return jsonify({"ok": False, "error": "git rev-parse failed", "status": "no_git"})

        if local.stdout.strip() == remote.stdout.strip():
            logger.info("Manual update check: already up to date")
            return jsonify({"ok": True, "status": "up_to_date"})

        logger.info(f"Manual update: applying (local={local.stdout.strip()[:8]} remote={remote.stdout.strip()[:8]})")
        from app.updater import AutoUpdater
        updater = AutoUpdater(None)
        updater._apply_update()
        return jsonify({"ok": True, "status": "updated"})
    except Exception as e:
        logger.error(f"Manual update failed: {e}")
        return jsonify({"ok": False, "error": str(e)})
