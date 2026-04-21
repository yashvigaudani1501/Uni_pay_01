# main/mobile_recharge.py
from flask import Blueprint, render_template, request, jsonify, session
from utils.login_required import login_required
from db import get_db_connection
import json
import os
from datetime import datetime
import hashlib
import re

mobile_bp = Blueprint('mobile', __name__)

def generate_transaction_id():
    """Generate a unique transaction ID"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
    return 'RCH' + hashlib.md5(timestamp.encode()).hexdigest()[:10].upper()

def save_recharge_to_json(username, recharge_data):
    """Save recharge to user's recharge JSON file"""
    file_path = f"payments_data/{username}_recharges.json"
    
    # Load existing recharges
    recharges = []
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            recharges = json.load(f)
    
    # Add new recharge
    recharges.append(recharge_data)
    
    # Save back to file
    with open(file_path, 'w') as f:
        json.dump(recharges, f, indent=2)
    
    print(f"✅ Saved recharge to {file_path}")

def save_recharge_as_transaction(username, transaction_data):
    """Save recharge as a transaction in the user's transactions JSON file for Search History"""
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
    
    print(f"✅ Saved recharge to transactions JSON: {file_path}")

def validate_mobile_number(mobile):
    """Validate Indian mobile number"""
    pattern = r'^[6-9]\d{9}$'
    return re.match(pattern, mobile) is not None

def check_column_exists(cursor, table, column):
    """Check if a column exists in a table"""
    cursor.execute(f"SHOW COLUMNS FROM {table} LIKE '{column}'")
    return cursor.fetchone() is not None

@mobile_bp.route('/mobile-recharge')
@login_required
def mobile_recharge_page():
    """Render mobile recharge page"""
    username = session.get('user')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get user balance
    cursor.execute("SELECT balance FROM upi_accounts WHERE username = %s", (username,))
    user = cursor.fetchone()
    
    # Get recharge plans
    try:
        cursor.execute("SELECT * FROM recharge_plans ORDER BY operator, amount")
        plans = cursor.fetchall()
    except Exception as e:
        print(f"⚠️ Recharge plans table error: {e}")
        plans = []
    
    cursor.close()
    conn.close()
    
    # Group plans by operator
    grouped_plans = {}
    for plan in plans:
        if plan['operator'] not in grouped_plans:
            grouped_plans[plan['operator']] = []
        grouped_plans[plan['operator']].append(plan)
    
    # Load recharge history
    recharge_history = []
    history_file = f"payments_data/{username}_recharges.json"
    if os.path.exists(history_file):
        with open(history_file, 'r') as f:
            recharge_history = json.load(f)
            # Sort by date (newest first)
            recharge_history.sort(key=lambda x: x['date'], reverse=True)
    
    return render_template('mobile_recharge.html', 
                         user=user,
                         balance=user['balance'] if user else 0,
                         grouped_plans=grouped_plans,
                         recharge_history=recharge_history[:10])  # Last 10 recharges

@mobile_bp.route('/api/recharge', methods=['POST'])
@login_required
def process_recharge():
    """Process mobile recharge"""
    conn = None
    cursor = None
    try:
        username = session.get('user')
        data = request.get_json()
        
        mobile_number = data.get('mobile_number', '').strip()
        operator = data.get('operator')
        amount = float(data.get('amount', 0))
        plan_id = data.get('plan_id')
        
        print(f"📱 Recharge request - User: {username}, Mobile: {mobile_number}, Operator: {operator}, Amount: {amount}")
        
        # Validation using regex (Unit-10 from FSD-1)
        if not validate_mobile_number(mobile_number):
            return jsonify({
                'success': False,
                'message': 'Invalid mobile number! Must be 10 digits starting with 6-9.'
            })
        
        if amount <= 0:
            return jsonify({
                'success': False,
                'message': 'Invalid recharge amount!'
            })
        
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Check balance
        cursor.execute("SELECT balance FROM upi_accounts WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        if not user:
            return jsonify({
                'success': False,
                'message': 'User not found!'
            })
        
        if user['balance'] < amount:
            return jsonify({
                'success': False,
                'message': f'Insufficient balance! Available: ₹{user["balance"]:,.0f}'
            })
        
        # Generate transaction ID
        transaction_id = generate_transaction_id()
        
        # Deduct balance
        cursor.execute(
            "UPDATE upi_accounts SET balance = balance - %s WHERE username = %s",
            (amount, username)
        )
        
        # Check if mobile_recharge table exists and create if needed
        try:
            # Insert recharge record
            cursor.execute("""
                INSERT INTO mobile_recharge 
                (username, mobile_number, operator, amount, plan_type, transaction_id, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'success')
            """, (username, mobile_number, operator, amount, plan_id, transaction_id))
        except Exception as e:
            print(f"⚠️ mobile_recharge table error: {e}")
            # Table might not exist, try to create it
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS mobile_recharge (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) NOT NULL,
                    mobile_number VARCHAR(10) NOT NULL,
                    operator VARCHAR(20) NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    plan_type VARCHAR(50),
                    status ENUM('pending', 'success', 'failed') DEFAULT 'pending',
                    transaction_id VARCHAR(50) UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Retry the insert
            cursor.execute("""
                INSERT INTO mobile_recharge 
                (username, mobile_number, operator, amount, plan_type, transaction_id, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'success')
            """, (username, mobile_number, operator, amount, plan_id, transaction_id))
        
        # Log transaction - Check if description column exists
        try:
            # Check if description column exists in transaction_log
            cursor.execute("SHOW COLUMNS FROM transaction_log LIKE 'description'")
            description_exists = cursor.fetchone()
            
            if description_exists:
                # Description column exists
                cursor.execute(
                    "INSERT INTO transaction_log (type, amount, description) VALUES ('debit', %s, %s)",
                    (amount, f'Mobile Recharge - {operator} {mobile_number}')
                )
            else:
                # Description column doesn't exist - insert without description
                cursor.execute(
                    "INSERT INTO transaction_log (type, amount) VALUES ('debit', %s)",
                    (amount,)
                )
                print("⚠️ Note: description column missing in transaction_log table")
        except Exception as e:
            # transaction_log table might not exist, create it
            print(f"⚠️ transaction_log table error: {e}")
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transaction_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    type ENUM('credit', 'debit') NOT NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    description VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Now insert with description
            cursor.execute(
                "INSERT INTO transaction_log (type, amount, description) VALUES ('debit', %s, %s)",
                (amount, f'Mobile Recharge - {operator} {mobile_number}')
            )
        
        conn.commit()
        
        # Create recharge record for JSON (Recharge history)
        recharge_record = {
            'id': transaction_id,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'mobile': mobile_number,
            'operator': operator,
            'amount': amount,
            'plan': plan_id,
            'status': 'success'
        }
        
        # Save to recharge JSON file
        save_recharge_to_json(username, recharge_record)
        
        # ✅ NEW: Also save to transactions JSON file for Search History
        transaction_record = {
            'id': transaction_id,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'debit',
            'amount': amount,
            'description': f'Mobile Recharge - {operator} {mobile_number}',
            'operator': operator,
            'mobile': mobile_number,
            'status': 'completed'
        }
        
        # Save to transactions JSON
        save_recharge_as_transaction(username, transaction_record)
        
        # Get updated balance
        cursor.execute("SELECT balance FROM upi_accounts WHERE username = %s", (username,))
        new_balance = cursor.fetchone()['balance']
        
        cursor.close()
        conn.close()
        
        print(f"✅ Recharge successful - ID: {transaction_id}")
        
        return jsonify({
            'success': True,
            'message': f'✅ Recharge of ₹{amount:,.0f} for {mobile_number} successful!',
            'new_balance': new_balance,
            'transaction_id': transaction_id
        })
        
    except Exception as e:
        print(f"❌ Recharge error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        if conn:
            try:
                conn.rollback()
            except:
                pass
            if cursor:
                try:
                    cursor.close()
                except:
                    pass
            try:
                conn.close()
            except:
                pass
        
        return jsonify({
            'success': False,
            'message': f'Error processing recharge: {str(e)}'
        }), 500

@mobile_bp.route('/api/recharge/history', methods=['GET'])
@login_required
def get_recharge_history():
    """Get recharge history for the user"""
    username = session.get('user')
    
    file_path = f"payments_data/{username}_recharges.json"
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            history = json.load(f)
            # Sort by date (newest first)
            history.sort(key=lambda x: x['date'], reverse=True)
            return jsonify({'success': True, 'history': history[:20]})
    
    return jsonify({'success': True, 'history': []})

@mobile_bp.route('/api/create-tables', methods=['POST'])
@login_required
def create_tables():
    """Admin endpoint to create required tables"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Create transaction_log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transaction_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                type ENUM('credit', 'debit') NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                description VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create mobile_recharge table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mobile_recharge (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                mobile_number VARCHAR(10) NOT NULL,
                operator VARCHAR(20) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                plan_type VARCHAR(50),
                status ENUM('pending', 'success', 'failed') DEFAULT 'pending',
                transaction_id VARCHAR(50) UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create recharge_plans table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recharge_plans (
                id INT AUTO_INCREMENT PRIMARY KEY,
                operator VARCHAR(20) NOT NULL,
                amount DECIMAL(10,2) NOT NULL,
                description VARCHAR(255),
                validity VARCHAR(50),
                data_benefit VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert sample plans if table is empty
        cursor.execute("SELECT COUNT(*) as count FROM recharge_plans")
        count = cursor.fetchone()[0]
        
        if count == 0:
            cursor.execute("""
                INSERT INTO recharge_plans (operator, amount, description, validity, data_benefit) VALUES
                ('Jio', 299, 'Unlimited calls + 1.5GB/day', '28 days', '1.5GB/day'),
                ('Jio', 499, 'Unlimited calls + 2.5GB/day', '56 days', '2.5GB/day'),
                ('Airtel', 299, 'Unlimited calls + 1GB/day', '28 days', '1GB/day'),
                ('Airtel', 499, 'Unlimited calls + 2GB/day', '56 days', '2GB/day'),
                ('VI', 259, 'Unlimited calls + 1GB/day', '28 days', '1GB/day'),
                ('VI', 459, 'Unlimited calls + 2GB/day', '56 days', '2GB/day'),
                ('BSNL', 199, 'Unlimited calls + 1GB/day', '30 days', '1GB/day'),
                ('BSNL', 399, 'Unlimited calls + 2GB/day', '60 days', '2GB/day')
            """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Tables created successfully!'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500