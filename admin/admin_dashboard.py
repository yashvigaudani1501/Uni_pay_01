from flask import Blueprint, render_template, session
from utils.admin_required import admin_required

admin_bp = Blueprint("admin", __name__)

@admin_bp.route("/admin")
@admin_required
def dashboard():
    return render_template(
        "dashboard.html",
        admin=session.get("admin")
    )
