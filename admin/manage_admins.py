from flask import Blueprint, render_template, request, redirect, url_for, session,jsonify   
from werkzeug.security import generate_password_hash
from db import get_db_connection
from utils.admin_required import admin_required
from utils.admin_logger import log_admin_action

manage_bp = Blueprint("admin_manage", __name__)

@manage_bp.route("/admin/manage-admins", methods=["GET", "POST"])
@admin_required
def manage_admins():
    message = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        mobile = request.form.get("mobile", "").strip()
        password = request.form.get("password", "")

        if not username or not email or not mobile or not password:
            message = "All fields are required."
        elif len(username) < 5 or len(username) > 20:
            message = "Username must be 5–20 characters."
        else:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()

                cursor.execute(
                    """
                    INSERT INTO admins (username, password, email, mobile)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        username,
                        generate_password_hash(password),
                        email,
                        mobile
                    )
                )

                cursor.execute("""
        SELECT 
            *
        FROM admins
    """)
                admins = cursor.fetchall()

                conn.commit()
                cursor.close()
                conn.close()

                log_admin_action(
                    admin=session.get("admin"),
                    action="add_admin",
                    target=username
                )

                return redirect(url_for("admin_manage.manage_admins"))

            except Exception:
                message = "Admin already exists."

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute("""
        SELECT username, email, mobile, created_at
        FROM admins
        ORDER BY created_at DESC
    """)
    admins = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "manage_admins.html",
        admins=admins,
        message=message
    )



@manage_bp.route("/api/admin/stats")
@admin_required
def admin_stats():
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Calculate All Time Total
        cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM transaction_log")
        all_time = float(cursor.fetchone()['total'])
        
        # 2. Calculate Today's Total
        cursor.execute("""
            SELECT COALESCE(SUM(amount), 0) as total 
            FROM transaction_log 
            WHERE DATE(created_at) = CURDATE()
        """)
        today = float(cursor.fetchone()['total'])
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "success": True,
            "all_time": all_time,
            "today": today
        })
    except Exception as e:
        if conn: conn.close()
        return jsonify({"success": False, "message": str(e)}), 500