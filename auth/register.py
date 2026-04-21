from flask import Blueprint, render_template, request, redirect, url_for
from werkzeug.security import generate_password_hash
from db import get_db_connection
from auth.otp import send_email_verification_otp
import re

register_bp = Blueprint("register", __name__)

@register_bp.route("/register", methods=["GET", "POST"])
def register():
    message = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        mobile = request.form.get("mobile", "").strip()
        raw_password = request.form.get("password", "")


        raw_password = request.form.get("password", "")

        password_pattern = r"^(?=.*[A-Z])(?=.*[a-z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,20}$"

        if not re.match(password_pattern, raw_password):
            return render_template(
                "register.html",
                message=(
                "Password must be 8–20 characters long and include "
                "an uppercase letter, a lowercase letter, a number, "
                "and a special character."
                )
            )


        # ---------- VALIDATIONS ----------
        if not username or len(username) < 5 or len(username) > 20:
            return render_template("register.html",
                message="Username must be between 5 and 20 characters.")

        if not re.match(r"^[a-zA-Z0-9_]+$", username):
            return render_template("register.html",
                message="Username can contain only letters, numbers, and underscore.")

        if username in ("admin", "root"):
            return render_template("register.html",
                message="This username is reserved.")

        if not mobile.isdigit() or len(mobile) != 10:
            return render_template("register.html",
                message="Mobile number must be exactly 10 digits.")

        if not email:
            return render_template("register.html",
                message="Email address is required.")

        if not raw_password:
            return render_template("register.html",
                message="Password is required.")

        password = generate_password_hash(raw_password)



        # ---------- DATABASE INSERT ----------
        try:
            conn = get_db_connection()
            cursor = conn.cursor()


            cursor.execute("SELECT id FROM users WHERE mobile = %s", (mobile,))
            existing_mobile = cursor.fetchone()

            if existing_mobile:
                cursor.close()
                conn.close()
                return render_template(
        "register.html",
        message="This mobile number is already registered."
    )

            cursor.execute(
                """
                INSERT INTO users (username, email, mobile, password, email_verified)
                VALUES (%s, %s, %s, %s, 0)
                """,
                (username, email, mobile, password)
            )

            conn.commit()

        except Exception as e:
            print("MYSQL ERROR >>>", e)
            return render_template(
                "register.html",
                message="Username, email, or mobile already exists."
            )

        finally:
            try:
                cursor.close()
                conn.close()
            except:
                pass

        # ---------- SEND EMAIL OTP (SEPARATE TRY) ----------
        try:
            send_email_verification_otp(email)
        except Exception as e:
            print("EMAIL ERROR >>>", e)
            # user already registered, so still allow OTP page
            message = "Account created, but OTP email failed. Contact support."

        return redirect(url_for("otp.verify_email"))

    return render_template("register.html", message=message)
