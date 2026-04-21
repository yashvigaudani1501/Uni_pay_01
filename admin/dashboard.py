from flask import Blueprint, redirect, url_for, session,render_template,request
from db import get_db_connection
from utils.admin_required import admin_required
from utils.admin_logger import log_admin_action

admin_bp = Blueprint("admin", __name__)

# -------------------------------
# 🔓 UNLOCK USER
# -------------------------------

@admin_bp.route("/admin/users", methods=["GET"])
@admin_required
def manage_users():
    search = request.args.get("q", "").strip()
    status = request.args.get("status", "")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        SELECT username, email, email_verified,
               is_banned, locked_until, otp_fail_count
        FROM users
        WHERE 1=1
    """
    params = []

    if search:
        query += """
            AND (
                LOWER(username) LIKE %s
                OR LOWER(email) LIKE %s
            )
        """
        like = f"%{search.lower()}%"
        params.extend([like, like])

    if status == "banned":
        query += " AND is_banned = 1"
    elif status == "locked":
        query += " AND locked_until IS NOT NULL"
    elif status == "verified":
        query += " AND email_verified = 1"
    elif status == "unverified":
        query += " AND email_verified = 0"

    query += " ORDER BY username"

    print("SEARCH:", search)
    print("QUERY:", query)
    print("PARAMS:", params)

    cursor.execute(query, params)
    users = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        "manage_users.html",
        users=users,
        search=search,
        status=status
    )

@admin_bp.route("/admin/transactions")
@admin_required
def transaction():
    return render_template("transactions.html")


@admin_bp.route("/admin/logs")
@admin_required
def logs():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # 1️⃣ Total log count
    cursor.execute("SELECT COUNT(*) AS total FROM auth_logs")
    total_logs = cursor.fetchone()["total"]

    # 2️⃣ Paginated logs
    cursor.execute("""
        SELECT *
        FROM auth_logs
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """, (per_page, offset))

    logs = cursor.fetchall()

    cursor.close()
    conn.close()

    # 3️⃣ Pagination math
    total_pages = (total_logs + per_page - 1) // per_page

    return render_template(
        "logs.html",
        logs=logs,
        page=page,
        total_pages=total_pages
    )


@admin_bp.route("/admin/settings")
@admin_required
def settings():
    return render_template("settings.html")


@admin_bp.route("/admin/dashboard")
@admin_required
def dashboard():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Total users
    cursor.execute("SELECT COUNT(*) AS total_users FROM users")
    total_users = cursor.fetchone()["total_users"]

    cursor.execute("""
        SELECT 
            *
        FROM transaction_log
        ORDER BY created_at DESC
        LIMIT 3
    """)
    recent_transactions = cursor.fetchall()

    # Transaction-related placeholders (no table yet)
    total_amount = 0
    today_amount = 0
    active_users = 0

    cursor.close()
    conn.close()

    return render_template(
        "dashboard.html",
        total_users=total_users,
        total_amount=total_amount,
        today_amount=today_amount,
        recent_transactions=recent_transactions
    )

@admin_bp.route("/admin/users/<username>/unlock", methods=["POST"])
@admin_required
def unlock_user(username):
    data = request.get_json()
    entered_code = data.get("code")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT mobile FROM users WHERE username=%s",
        (username,)
    )
    user = cursor.fetchone()

    if not user:
        return {"status": "error", "message": "User not found"}, 404

    if entered_code != user["mobile"][-4:]:
        return {"status": "error", "message": "Invalid confirmation code"}, 403

    cursor.execute(
        "UPDATE users SET locked_until=NULL, otp_fail_count=0 WHERE username=%s",
        (username,)
    )
    conn.commit()

    cursor.close()
    conn.close()

    log_admin_action(session.get("admin"), "unlock_user", username)

    return {"status": "success", "message": "User unlocked"}


@admin_bp.route("/admin/users/<username>/ban", methods=["POST"])
@admin_required
def ban_user(username):
    data = request.get_json()
    entered_code = data.get("code")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT mobile FROM users WHERE username=%s",
        (username,)
    )
    user = cursor.fetchone()

    if not user:
        return {"status": "error", "message": "User not found"}, 404

    if entered_code != user["mobile"][-4:]:
        return {"status": "error", "message": "Invalid confirmation code"}, 403

    cursor.execute(
        "UPDATE users SET is_banned=1 WHERE username=%s",
        (username,)
    )
    conn.commit()

    cursor.close()
    conn.close()

    log_admin_action(session.get("admin"), "ban_user", username)

    return {"status": "success", "message": "User banned"}


@admin_bp.route("/admin/users/<username>/reset-otp", methods=["POST"])
@admin_required
def reset_otp(username):
    data = request.get_json()
    entered_code = data.get("code")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT mobile FROM users WHERE username=%s",
        (username,)
    )
    user = cursor.fetchone()

    if not user:
        return {"status": "error", "message": "User not found"}, 404

    if entered_code != user["mobile"][-4:]:
        return {"status": "error", "message": "Invalid confirmation code"}, 403

    cursor.execute(
        "UPDATE users SET otp_fail_count=0 WHERE username=%s",
        (username,)
    )
    conn.commit()

    cursor.close()
    conn.close()

    log_admin_action(session.get("admin"), "reset_otp", username)

    return {"status": "success", "message": "OTP attempts reset"}




@admin_bp.route("/admin/users/<username>/unban", methods=["POST"])
@admin_required
def unban_user(username):
    data = request.get_json()
    entered_code = data.get("code")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT mobile FROM users WHERE username=%s",
        (username,)
    )
    user = cursor.fetchone()

    if not user:
        return {"status": "error", "message": "User not found"}, 404

    if entered_code != user["mobile"][-4:]:
        return {"status": "error", "message": "Invalid confirmation code"}, 403

    cursor.execute(
        "UPDATE users SET is_banned=0 WHERE username=%s",
        (username,)
    )
    conn.commit()

    cursor.close()
    conn.close()

    log_admin_action(session.get("admin"), "unban_user", username)

    return {"status": "success", "message": "User unbanned"}


@admin_bp.route("/admin/users/<username>/lock", methods=["POST"])
@admin_required
def lock_user(username):
    data = request.get_json()
    entered_code = data.get("code")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT mobile FROM users WHERE username=%s",
        (username,)
    )
    user = cursor.fetchone()

    if not user:
        return {"status": "error", "message": "User not found"}, 404

    if entered_code != user["mobile"][-4:]:
        return {"status": "error", "message": "Invalid confirmation code"}, 403

    lock_until = datetime.now() + timedelta(hours=24)

    cursor.execute(
        "UPDATE users SET locked_until=%s WHERE username=%s",
        (lock_until, username)
    )
    conn.commit()

    cursor.close()
    conn.close()

    log_admin_action(session.get("admin"), "lock_user", username)

    return {
        "status": "success",
        "message": "User locked for 24 hours"
    }



@admin_bp.route("/admin/users/<username>/unverify-email", methods=["POST"])
@admin_required
def unverify_email(username):
    data = request.get_json()
    entered_code = data.get("code")

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    cursor.execute(
        "SELECT mobile FROM users WHERE username=%s",
        (username,)
    )
    user = cursor.fetchone()

    if not user:
        return {"status": "error", "message": "User not found"}, 404

    if entered_code != user["mobile"][-4:]:
        return {"status": "error", "message": "Invalid confirmation code"}, 403

    cursor.execute(
        "UPDATE users SET email_verified=0 WHERE username=%s",
        (username,)
    )
    conn.commit()

    cursor.close()
    conn.close()

    log_admin_action(session.get("admin"), "unverify_email", username)

    return {
        "status": "success",
        "message": "Email marked as unverified"
    }
