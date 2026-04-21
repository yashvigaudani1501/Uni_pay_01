from functools import wraps
from flask import session, redirect, url_for, request

def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login.login", next=request.url))
        return f(*args, **kwargs)
    return wrapped
