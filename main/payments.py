from flask import Blueprint, request, jsonify, session
from utils.login_required import login_required
from db import get_db_connection
import json
import os
from datetime import datetime
import hashlib

# main/payments.py
payments_bp = Blueprint('payments', __name__)

def save_transaction_to_json(username, transaction_data):
    """Save transaction to user's JSON file"""
    file_path = f"payments_data/{username}_transactions.json"
    
    # Load existing transactions
    transactions = []
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                transactions = json.load(f)
        except:
            transactions = []
    
    # Add new transaction
    transactions.append(transaction_data)
    
    # Save back to file
    with open(file_path, 'w') as f:
        json.dump(transactions, f, indent=2)
    
    print(f"✅ Saved transaction to {file_path}")

def generate_transaction_id():
    """Generate a unique transaction ID"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
    return hashlib.md5(timestamp.encode()).hexdigest()[:8]

@payments_bp.route("/api/transfer", methods=["POST"])
@login_required
def api_transfer():
    conn = None
    try:
        username = session.get("user")
        print(f"\n💰 Transfer initiated by: {username}")
        
        # 📊 STATS MODE (Anonymous Global Totals)
        if request.form.get("stats") == "1":
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Sum all credits/deposits globally
            cursor.execute("SELECT COALESCE(SUM(amount), 0) as total_credit FROM transaction_log WHERE type = 'credit'")
            credit = float(cursor.fetchone()['total_credit'])
            
            # Sum all debits globally
            cursor.execute("SELECT COALESCE(SUM(amount), 0) as total_debit FROM transaction_log WHERE type = 'debit'")
            debit = float(cursor.fetchone()['total_debit'])
            
            cursor.close()
            conn.close()
            return jsonify({"success": True, "total_credit": credit, "total_debit": debit})

        amount = float(request.form["amount"])
        action = request.form.get("action", "transfer")
        
        # 💳 DEPOSIT MODE
        if action == "deposit":
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            
            # Update user balance
            cursor.execute("UPDATE upi_accounts SET balance = balance + %s WHERE username = %s", (amount, username))
            
            # LOG AS CREDIT (Money entering the system)
            cursor.execute("INSERT INTO transaction_log (type, amount) VALUES ('credit', %s)", (amount,))
            
            # Create transaction record for JSON
            transaction = {
                'id': generate_transaction_id(),
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'type': 'credit',
                'amount': amount,
                'description': 'Fund Deposit',
                'status': 'completed'
            }
            
            # Save to JSON file
            save_transaction_to_json(username, transaction)
            
            conn.commit()
            cursor.execute("SELECT balance FROM upi_accounts WHERE username = %s", (username,))
            new_balance = float(cursor.fetchone()['balance'])
            cursor.close()
            conn.close()
            
            print(f"✅ Deposit of ₹{amount} completed for {username}")
            return jsonify({"success": True, "message": f"✅ ₹{amount:,.0f} deposited!", "new_balance": new_balance})
        
        # 🚀 TRANSFER MODE
        transfer_type = request.form["transfer_type"]
        recipient = request.form["recipient_upi"].strip()
        description = request.form.get("description", "Transfer")
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check sender balance
        cursor.execute("SELECT balance FROM upi_accounts WHERE username = %s", (username,))
        sender = cursor.fetchone()
        if not sender or float(sender['balance']) < amount:
            conn.close()
            return jsonify({"success": False, "message": "❌ Insufficient balance"}), 400
        
        # Find recipient
        if transfer_type == "upi":
            cursor.execute("SELECT username, upi_id FROM upi_accounts WHERE upi_id = %s", (recipient,))
        else:
            cursor.execute("SELECT username FROM users WHERE mobile = %s", (recipient,))
        
        recipient_user = cursor.fetchone()
        if not recipient_user:
            conn.close()
            return jsonify({"success": False, "message": f"❌ '{recipient}' not found"}), 400
        
        recipient_username = recipient_user['username']
        
        # Execute Transfer (Update Balances)
        cursor.execute("UPDATE upi_accounts SET balance = balance - %s WHERE username = %s", (amount, username))
        cursor.execute("UPDATE upi_accounts SET balance = balance + %s WHERE username = %s", (amount, recipient_username))
        
        # LOG AS DEBIT (Money leaving the account)
        cursor.execute("INSERT INTO transaction_log (type, amount) VALUES ('debit', %s)", (amount,))
        
        # Get sender's UPI ID for the recipient's transaction record
        cursor.execute("SELECT upi_id FROM upi_accounts WHERE username = %s", (username,))
        sender_upi = cursor.fetchone()
        sender_upi_id = sender_upi['upi_id'] if sender_upi else f"{username}@unipay"
        
        # Create debit transaction for sender
        sender_transaction = {
            'id': generate_transaction_id(),
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'debit',
            'amount': amount,
            'to_upi': recipient,
            'description': description,
            'status': 'completed'
        }
        
        # Create credit transaction for recipient
        recipient_transaction = {
            'id': generate_transaction_id(),
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'credit',
            'amount': amount,
            'from_upi': sender_upi_id,
            'description': f"From {username}: {description}",
            'status': 'completed'
        }
        
        # Save to JSON files
        save_transaction_to_json(username, sender_transaction)
        save_transaction_to_json(recipient_username, recipient_transaction)
        
        conn.commit()
        new_balance = float(sender['balance']) - amount
        cursor.close()
        conn.close()
        
        print(f"✅ Transfer of ₹{amount} from {username} to {recipient_username} completed")
        return jsonify({"success": True, "message": f"✅ ₹{amount:,.0f} sent!", "new_balance": new_balance})
        
    except Exception as e:
        print(f"❌ Error in transfer: {str(e)}")
        if conn:
            conn.close()
        return jsonify({"success": False, "message": f"❌ Error: {str(e)}"}), 500