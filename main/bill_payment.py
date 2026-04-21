# main/bill_payment.py
from flask import Blueprint, render_template, request, jsonify, session
from utils.login_required import login_required
from db import get_db_connection
import json
import os
from datetime import datetime
import hashlib
import random

bill_bp = Blueprint('bill', __name__)

def generate_transaction_id():
    """Generate a unique transaction ID for bills"""
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
    return 'BILL' + hashlib.md5(timestamp.encode()).hexdigest()[:10].upper()

def save_bill_to_json(username, bill_data):
    """Save bill payment to user's JSON file"""
    file_path = f"payments_data/{username}_bills.json"
    
    bills = []
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            bills = json.load(f)
    
    bills.append(bill_data)
    
    with open(file_path, 'w') as f:
        json.dump(bills, f, indent=2)
    
    print(f"✅ Saved bill payment to {file_path}")

def save_bill_as_transaction(username, transaction_data):
    """Save bill payment as a transaction in the main transactions JSON file"""
    file_path = f"payments_data/{username}_transactions.json"
    
    transactions = []
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            transactions = json.load(f)
    
    transactions.append(transaction_data)
    
    with open(file_path, 'w') as f:
        json.dump(transactions, f, indent=2)
    
    print(f"✅ Saved bill payment to transactions JSON")

@bill_bp.route('/bill-payment')
@login_required
def bill_payment_page():
    """Render bill payment page"""
    username = session.get('user')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get user balance
    cursor.execute("SELECT balance FROM upi_accounts WHERE username = %s", (username,))
    user = cursor.fetchone()
    
    # Get bill categories
    cursor.execute("SELECT * FROM bill_categories ORDER BY category_name")
    categories = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    # Load bill payment history
    bill_history = []
    history_file = f"payments_data/{username}_bills.json"
    if os.path.exists(history_file):
        with open(history_file, 'r') as f:
            bill_history = json.load(f)
            # Sort by date (newest first)
            bill_history.sort(key=lambda x: x['date'], reverse=True)
    
    return render_template('bill_payment_simplified.html',
                         user=user,
                         balance=user['balance'] if user else 0,
                         categories=categories,
                         bill_history=bill_history[:10])

@bill_bp.route('/api/fetch-bill-simple', methods=['POST'])
@login_required
def fetch_bill_simple():
    """Fetch bill details using customer name (simplified)"""
    try:
        data = request.get_json()
        
        customer_name = data.get('customer_name', '').strip()
        provider = data.get('provider', '')
        category = data.get('category', '')
        
        print(f"📄 Fetching bill - Category: {category}, Provider: {provider}, Customer: {customer_name}")
        
        if not customer_name or not provider:
            return jsonify({
                'success': False,
                'message': 'Please enter customer name and select provider'
            })
        
        # Generate random bill amount based on category
        amounts = {
            'Electricity': random.randint(500, 5000),
            'Water': random.randint(200, 1500),
            'Gas': random.randint(300, 2500),
            'Internet': random.randint(600, 2000),
            'DTH/Cable': random.randint(300, 1200),
            'Credit Card': random.randint(1000, 50000),
            'Education': random.randint(5000, 100000),
            'Municipal Taxes': random.randint(1000, 10000)
        }
        
        amount = amounts.get(category, random.randint(500, 5000))
        
        # Generate due date (15th of current month or next month)
        today = datetime.now()
        if today.day <= 15:
            due_date = today.replace(day=15).strftime('%Y-%m-%d')
        else:
            # Next month
            if today.month == 12:
                due_date = today.replace(year=today.year+1, month=1, day=15).strftime('%Y-%m-%d')
            else:
                due_date = today.replace(month=today.month+1, day=15).strftime('%Y-%m-%d')
        
        return jsonify({
            'success': True,
            'customer_name': customer_name,
            'amount': amount,
            'due_date': due_date,
            'bill_period': today.strftime('%b %Y'),
            'bill_number': f"BILL{random.randint(10000, 99999)}"
        })
        
    except Exception as e:
        print(f"❌ Error fetching bill: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Error fetching bill: {str(e)}'
        })

@bill_bp.route('/api/pay-bill-simple', methods=['POST'])
@login_required
def pay_bill_simple():
    """Process bill payment (simplified version)"""
    conn = None
    cursor = None
    try:
        username = session.get('user')
        data = request.get_json()
        
        category = data.get('category')
        provider = data.get('provider')
        customer_name = data.get('customer_name')
        amount = float(data.get('amount'))
        bill_period = data.get('bill_period')
        
        print(f"📄 Bill Payment - User: {username}, Category: {category}, Provider: {provider}, Amount: {amount}")
        
        if amount <= 0:
            return jsonify({
                'success': False,
                'message': 'Invalid bill amount!'
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
        
        # Insert bill payment record (simplified - no consumer number)
        cursor.execute("""
            INSERT INTO bill_payments 
            (username, bill_category, provider_name, customer_name, amount, bill_period, transaction_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'success')
        """, (username, category, provider, customer_name, amount, bill_period, transaction_id))
        
        # Log transaction
        
        
        conn.commit()
        
        # Create bill record for JSON
        bill_record = {
            'id': transaction_id,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'category': category,
            'provider': provider,
            'customer_name': customer_name,
            'amount': amount,
            'bill_period': bill_period,
            'status': 'success'
        }
        
        # Save to bill JSON file
        save_bill_to_json(username, bill_record)
        
        # Save to transactions JSON for search history
        transaction_record = {
            'id': transaction_id,
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'debit',
            'amount': amount,
            'description': f'{category} Bill - {customer_name}',
            'category': category,
            'status': 'completed'
        }
        save_bill_as_transaction(username, transaction_record)
        
        # Get updated balance
        cursor.execute("SELECT balance FROM upi_accounts WHERE username = %s", (username,))
        new_balance = cursor.fetchone()['balance']
        
        cursor.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'✅ {category} bill of ₹{amount:,.0f} paid successfully!',
            'new_balance': new_balance,
            'transaction_id': transaction_id
        })
        
    except Exception as e:
        print(f"❌ Bill payment error: {str(e)}")
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
            'message': f'Error processing bill payment: {str(e)}'
        }), 500

@bill_bp.route('/api/bill-history', methods=['GET'])
@login_required
def get_bill_history():
    """Get bill payment history"""
    username = session.get('user')
    
    file_path = f"payments_data/{username}_bills.json"
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            history = json.load(f)
            history.sort(key=lambda x: x['date'], reverse=True)
            return jsonify({'success': True, 'history': history[:20]})
    
    return jsonify({'success': True, 'history': []})