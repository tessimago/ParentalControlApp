from functools import wraps

import bcrypt
from flask import session, redirect, url_for

from app.database import get_setting, set_setting


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("main.login"))
        return f(*args, **kwargs)
    return decorated


def check_password(password):
    stored_hash = get_setting("password_hash")
    if not stored_hash:
        return False
    return bcrypt.checkpw(password.encode(), stored_hash.encode())


def change_password(new_password):
    new_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    set_setting("password_hash", new_hash)
