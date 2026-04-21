from flask import Blueprint, render_template, request, redirect, url_for, session
from db import get_db_connection
from werkzeug.security import check_password_hash
import random, time
from datetime import datetime, timedelta
from utils.auth_logger import log_auth_event

login_bp = Blueprint("login", __name__)

LOGIN_OTP_VALIDITY = 120
MAX_OTP_ATTEMPTS = 5


@login_bp.route("/", methods=["GET", "POST"])
@login_bp.route("/login", methods=["GET", "POST"])
def login():
    alert_message = session.pop("alert_message", None)
    alert_type = session.pop("alert_type", None)

    message = None
    lock_remaining = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            message = "All fields are required."

        else:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            try:
                # 🔐 ADMIN LOGIN
                cursor.execute("SELECT * FROM admins WHERE username=%s", (username,))
                admin = cursor.fetchone()

                if admin and check_password_hash(admin["password"], password):
                    if admin["is_banned"] or (
                        admin["locked_until"] and admin["locked_until"] > datetime.now()
                    ):
                        message = "Invalid username or password."
                    else:
                        session.clear()
                        session["admin"] = admin["username"]
                        session["user_type"] = "admin"
                        log_auth_event(username, "admin_login", "success", "admin_login")
                        return redirect(url_for("admin.dashboard"))

                # 👤 USER LOGIN
                cursor.execute("SELECT * FROM users WHERE username=%s", (username,))
                user = cursor.fetchone()

                if not user or not check_password_hash(user["password"], password):
                    message = "Invalid username or password."
                    log_auth_event(username, "login_password", "failure", "wrong_password")

                elif user["is_banned"]:
                    message = "You are banned."

                elif user["locked_until"] and user["locked_until"] > datetime.now():
                    lock_remaining = int(
                        (user["locked_until"] - datetime.now()).total_seconds()
                    )

                elif not user["email_verified"]:
                    session["email_to_verify"] = user["email"]
                    return render_template(
                        "login.html",
                        show_verify_popup=True,
                        email=user["email"],
                        message="Please verify your email to continue.",
                        alert_message=alert_message,
                        alert_type=alert_type,
                    )

                else:
                    otp = str(random.randint(100000, 999999))
                    session["login_otp"] = otp
                    session["login_otp_time"] = time.time()
                    session["login_otp_user"] = user["username"]
                    session["login_otp_attempts"] = 0

                    print("LOGIN OTP:", otp, flush=True)
                    return redirect(url_for("login.login_otp"))

            finally:
                cursor.close()
                conn.close()

    return render_template(
        "login.html",
        message=message,
        lock_remaining=lock_remaining,
        alert_message=alert_message,
        alert_type=alert_type,
    )


@login_bp.route("/login-otp", methods=["GET", "POST"])
def login_otp():
    if "login_otp" not in session:
        return redirect(url_for("login.login"))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    message = None

    try:
        cursor.execute(
            "SELECT * FROM users WHERE username=%s",
            (session["login_otp_user"],),
        )
        user = cursor.fetchone()

        if time.time() - session["login_otp_time"] > LOGIN_OTP_VALIDITY:
            session["alert_message"] = "OTP expired. Please login again."
            session["alert_type"] = "error"
            session.clear()
            return redirect(url_for("login.login"))

        if request.method == "POST":
            entered_otp = request.form.get("otp")

            if entered_otp != session.get("login_otp"):
                session["login_otp_attempts"] += 1
                attempts = session["login_otp_attempts"]

                if attempts >= MAX_OTP_ATTEMPTS:
                    session.clear()
                    return redirect(url_for("login.login"))

                message = f"Invalid OTP. Attempts left: {MAX_OTP_ATTEMPTS - attempts}"

            else:
                cursor.execute(
                    """
                    UPDATE users
                    SET otp_fail_count=0, locked_until=NULL
                    WHERE username=%s
                    """,
                    (user["username"],),
                )
                conn.commit()

                session.clear()
                session["user"] = user["username"]
                return redirect(url_for("home.home"))

        remaining_seconds = max(
            0, LOGIN_OTP_VALIDITY - int(time.time() - session["login_otp_time"])
        )

        return render_template(
            "login_otp.html",
            message=message,
            remaining_seconds=remaining_seconds,
        )

    finally:
        cursor.close()
        conn.close()
