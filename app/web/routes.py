import os
import shutil
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
    get_usage_for_date, get_usage_range, get_setting, set_setting
)
from app.screenshots import (
    capture_frame, get_screenshot_dates, get_screenshots_for_date, get_screenshot_path
)
from app.config import SCREENSHOTS_DIR

bp = Blueprint("main", __name__)


# --- Auth ---

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if check_password(password):
            session["authenticated"] = True
            return redirect(url_for("main.dashboard"))
        flash("Invalid password", "error")
    return render_template("login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


# --- Dashboard ---

@bp.route("/")
@login_required
def dashboard():
    from app.monitor import MonitorEngine
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

    return render_template(
        "dashboard.html",
        usage_today=usage_today,
        current_schedule=current_schedule,
        now=now,
        active_users=active_users,
        override=override
    )


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
    for day in range(7):
        start = request.form.get(f"start_{day}")
        end = request.form.get(f"end_{day}")
        if start and end:
            update_schedule(day, start, end)
    flash("Schedule updated", "success")
    return redirect(url_for("main.schedule"))


@bp.route("/schedule/extend", methods=["POST"])
@login_required
def schedule_extend():
    today = datetime.now().strftime("%Y-%m-%d")
    start = request.form.get("start_time", "06:00")
    end = request.form.get("end_time")
    if end:
        set_override(today, start, end)
        flash(f"Today's schedule extended until {end}", "success")
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
    action_type = request.form.get("action_type")

    if action_type == "delete":
        process_name = request.form.get("delete_process")
        if process_name:
            delete_app_limit(process_name)
            flash(f"Removed limit for {process_name}", "success")
    else:
        process_name = request.form.get("process_name", "").strip().lower()
        minutes = request.form.get("daily_limit_minutes")
        action = request.form.get("action", "warn")
        if process_name and minutes:
            set_app_limit(process_name, int(minutes), action)
            flash(f"Limit set for {process_name}", "success")

    return redirect(url_for("main.limits"))


# --- History ---

@bp.route("/history")
@login_required
def history():
    date_str = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    usage = get_usage_for_date(date_str)
    return render_template("history.html", usage=usage, selected_date=date_str)


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
    day_folder = os.path.join(SCREENSHOTS_DIR, date)
    if os.path.exists(day_folder):
        shutil.rmtree(day_folder)
        flash(f"Deleted all screenshots for {date}", "success")
    return redirect(url_for("main.screenshots"))


@bp.route("/screenshots/delete/<date>/<filename>", methods=["POST"])
@login_required
def delete_screenshot(date, filename):
    filepath = get_screenshot_path(date, filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        flash(f"Deleted {filename}", "success")
    return redirect(url_for("main.screenshots_date", date=date))


# --- Settings ---

@bp.route("/settings")
@login_required
def settings():
    current_settings = {
        "port": get_setting("port") or "7847",
        "screenshot_interval": get_setting("screenshot_interval") or "300",
        "screenshot_retention_days": get_setting("screenshot_retention_days") or "30",
        "update_check_interval": get_setting("update_check_interval") or "900",
        "schedule_enabled": get_setting("schedule_enabled") or "0",
        "limiter_enabled": get_setting("limiter_enabled") or "0",
    }
    return render_template("settings.html", settings=current_settings)


@bp.route("/settings", methods=["POST"])
@login_required
def settings_update():
    new_password = request.form.get("new_password")
    if new_password:
        change_password(new_password)
        flash("Password changed", "success")

    for key in ["screenshot_interval", "screenshot_retention_days", "update_check_interval"]:
        value = request.form.get(key)
        if value:
            set_setting(key, value)

    set_setting("schedule_enabled", "1" if request.form.get("schedule_enabled") else "0")
    set_setting("limiter_enabled", "1" if request.form.get("limiter_enabled") else "0")

    flash("Settings updated", "success")
    return redirect(url_for("main.settings"))
