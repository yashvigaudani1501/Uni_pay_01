from flask import Flask, request, session, jsonify
from utils.login_required import login_required

from auth.login import login_bp
from auth.register import register_bp
from auth.otp import otp_bp
from auth.logout import logout_bp
from main.balance import txn_bp
from global_stats import global_stats

from main.home import home_bp

from admin.dashboard import admin_bp
from admin.manage_admins import manage_bp
from main.payments import payments_bp
from main.mobile_recharge import mobile_bp
from main.bill_payment import bill_bp  

app = Flask(__name__)
app.secret_key = "super_secret_key"

# Auth
app.register_blueprint(login_bp)
app.register_blueprint(register_bp)
app.register_blueprint(otp_bp)
app.register_blueprint(logout_bp)

# User
app.register_blueprint(home_bp)
app.register_blueprint(txn_bp)

# Admin
app.register_blueprint(admin_bp)
app.register_blueprint(manage_bp)
app.register_blueprint(payments_bp)

# Mobile Recharge
app.register_blueprint(mobile_bp)

# Bill Payment
app.register_blueprint(bill_bp)

if __name__ == "__main__":
    app.run(debug=True)

@app.route("/api/transfer", methods=["POST"])
@login_required
def api_transfer():
    print("🚀 TRANSFER STARTED")
    
    amount = float(request.form["amount"])
    print(f"💰 Amount: ₹{amount}")
    
    # 🔥 TEST STATS FIRST
    print(f"📊 Before: {global_stats.get_stats()}")
    global_stats.record_transaction(amount)
    print(f"📊 After: {global_stats.get_stats()}")

    username = session.get("user")
    amount = float(request.form["amount"])
    transfer_type = request.form["transfer_type"]  # "upi" or "mobile"
    recipient = request.form["recipient_upi"].strip()
    description = request.form.get("description", "Transfer")
    
    print(f"TRANSFER: {username} → {recipient} ({transfer_type}) ₹{amount}")
    
    # 🚀 UPDATE ADMIN STATS FIRST (global counter)
    global_stats.record_transaction(amount)
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Sender check
    cursor.execute("SELECT balance FROM upi_accounts WHERE username = %s", (username,))
    sender = cursor.fetchone()
    if not sender or sender['balance'] < amount:
        conn.close()
        return jsonify({"success": False, "message": "❌ Insufficient balance"}), 400
    
    # MOBILE NUMBER → Find user
    recipient_username = None
    if transfer_type == "upi":
        cursor.execute("SELECT username FROM upi_accounts WHERE upi_id = %s", (recipient,))
    else:  # mobile
        cursor.execute("SELECT username FROM users WHERE mobile = %s", (recipient,))
    
    recipient_user = cursor.fetchone()
    if not recipient_user:
        conn.close()
        return jsonify({"success": False, "message": f"❌ '{recipient}' not found"}), 400
    
    recipient_username = recipient_user['username']
    
    # TRANSFER MONEY
    cursor.execute("UPDATE upi_accounts SET balance = balance - %s WHERE username = %s", (amount, username))
    cursor.execute("UPDATE upi_accounts SET balance = balance + %s WHERE username = %s", (amount, recipient_username))
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "message": f"✅ ₹{amount:,.0f} sent to {recipient} ({transfer_type.upper()})",
        "new_balance": sender['balance'] - amount
    })

import logging
logging.getLogger('mysql.connector').setLevel(logging.WARNING)  