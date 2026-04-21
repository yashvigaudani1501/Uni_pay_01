# main/home.py
import json
import os
from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify
from db import get_db_connection
from utils.login_required import login_required
from mysql.connector import IntegrityError
from utils.Tree import TransactionBST, TransactionHashTable, TransactionAnalyzer

home_bp = Blueprint("home", __name__)

# Store hash tables in memory for better performance
user_hash_tables = {}

def clear_user_hash_table(username):
    """Clear cached hash table for a user when transactions change"""
    if username in user_hash_tables:
        del user_hash_tables[username]
        print(f"🧹 Cleared hash table cache for {username}")
        return True
    return False

@home_bp.route("/home")
@login_required
def home():
    username = session.get("user")
    print(f"\n🔍 User logged in: {username}")  # Debug: Check which user is logged in
    
    all_transactions = []
    
    # Load transactions from JSON file - CHANGED FROM 'transactions' TO 'payments_data'
    file_path = f"payments_data/{username}_transactions.json"
    print(f"📁 Looking for transactions at: {file_path}")  # Debug: Check file path
    
    if os.path.exists(file_path):
        print(f"✅ File found: {file_path}")  # Debug: File exists
        try:
            with open(file_path, 'r') as f:
                all_transactions = json.load(f)
            print(f"📊 Loaded {len(all_transactions)} transactions")  # Debug: Number of transactions loaded
            if all_transactions:
                print(f"📝 First transaction: {all_transactions[0]}")  # Debug: Sample transaction
        except Exception as e:
            print(f"❌ Error loading transactions: {e}")  # Debug: Error if any
            all_transactions = []
    else:
        print(f"❌ File NOT found at: {file_path}")  # Debug: File missing
        print(f"Current working directory: {os.getcwd()}")  # Debug: Show current directory
        
        # List contents of payments_data folder if it exists
        if os.path.exists('payments_data'):
            print("📁 Contents of payments_data folder:")
            for f in os.listdir('payments_data'):
                if f.endswith('.json'):
                    print(f"   - {f}")
        else:
            print("📁 'payments_data' folder does not exist")
    
    # Build hash table for this user if not exists
    if all_transactions and username not in user_hash_tables:
        print(f"🔨 Building hash table for user: {username}")  # Debug
        hash_table = TransactionHashTable()
        hash_table.build_from_list(all_transactions)
        user_hash_tables[username] = hash_table
        print(f"✅ Hash table built with {len(user_hash_tables[username].id_table)} entries")  # Debug
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Fetch user + UPI with LEFT JOIN
    cursor.execute("""
        SELECT u.username, u.email, u.mobile, u.created_at,
               COALESCE(ua.balance, 5000) as balance, 
               ua.upi_id 
        FROM users u 
        LEFT JOIN upi_accounts ua ON u.username = ua.username 
        WHERE u.username = %s
    """, (username,))
    user = cursor.fetchone()
    print(f"👤 User data retrieved: {user['username'] if user else 'None'}")  # Debug
    
    # Auto-create UPI if missing
    if user and not user.get('upi_id'):
        print(f"🔄 Creating UPI ID for user: {username}")  # Debug
        name = user['username'].title()
        mobile = user['mobile'] if user['mobile'] else "0000000000"
        first2 = mobile[:2]
        last2 = mobile[-2:]
        default_upiid = f"{name}{first2}{last2}@unipay"

        try:
            cursor.execute(
                "INSERT INTO upi_accounts (username, upi_id, balance) VALUES (%s, %s, 5000)", 
                (username, default_upiid)
            )
            conn.commit()
            print(f"✅ UPI ID created: {default_upiid}")  # Debug
            
            # Refresh data after creation
            cursor.execute("""
                SELECT u.username, u.email, u.mobile, u.created_at,
                       COALESCE(ua.balance, 5000) as balance, 
                       ua.upi_id 
                FROM users u 
                LEFT JOIN upi_accounts ua ON u.username = ua.username 
                WHERE u.username = %s
            """, (username,))
            user = cursor.fetchone()
        
        except IntegrityError as e:
            print(f"⚠️ IntegrityError creating UPI: {e}")  # Debug
            conn.rollback()
            cursor.execute("""
                SELECT u.username, u.email, u.mobile, u.created_at,
                       COALESCE(ua.balance, 0.00) as balance, 
                       ua.upi_id 
                FROM users u 
                LEFT JOIN upi_accounts ua ON u.username = ua.username 
                WHERE u.username = %s
            """, (username,))
            user = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    if not user:
        print("❌ No user found, redirecting to login")  # Debug
        return redirect(url_for("login.login"))
    
    # Get monthly summary and top transactions for analytics
    print("📊 Generating analytics...")  # Debug
    monthly_summary = TransactionAnalyzer.get_monthly_summary(all_transactions)
    top_transactions = TransactionAnalyzer.get_top_transactions(all_transactions, 5)
    
    print(f"✅ Rendering template with {len(all_transactions)} transactions")  # Debug
    print(f"📈 Total transactions count: {len(all_transactions)}")  # Debug
    
    return render_template("home.html", 
                          user=user, 
                          transactions=all_transactions,
                          monthly_summary=monthly_summary,
                          top_transactions=top_transactions,
                          total_transactions=len(all_transactions))

@home_bp.route("/api/search-transactions", methods=["POST"])
@login_required
def api_search_transactions():
    """API endpoint for AJAX search with DSA"""
    username = session.get("user")
    data = request.get_json()
    
    search_term = data.get('term', '').strip()
    search_type = data.get('type', 'id')  # 'id', 'amount', or 'date'
    
    print(f"🔍 API Search - User: {username}, Type: {search_type}, Term: {search_term}")  # Debug
    
    # CHANGED FROM 'transactions' TO 'payments_data'
    file_path = f"payments_data/{username}_transactions.json"
    if not os.path.exists(file_path):
        print(f"❌ Transaction file not found: {file_path}")  # Debug
        return jsonify({'results': []})
    
    with open(file_path, 'r') as f:
        transactions = json.load(f)
    
    print(f"📊 Loaded {len(transactions)} transactions for search")  # Debug
    
    # Rebuild hash table if it doesn't exist (in case of new transactions)
    if username not in user_hash_tables:
        print(f"🔨 Building hash table for user: {username}")
        hash_table = TransactionHashTable()
        hash_table.build_from_list(transactions)
        user_hash_tables[username] = hash_table
        print(f"✅ Hash table built with {len(user_hash_tables[username].id_table)} entries")
    
    results = []
    search_time = 0
    import time
    
    if search_type == 'id':
        # Binary Search Tree Search - O(log n)
        print("🌲 Using Binary Search Tree")  # Debug
        start_time = time.time()
        bst = TransactionBST()
        for tx in transactions:
            bst.insert(tx)
        result = bst.search(search_term)
        search_time = time.time() - start_time
        if result:
            results = [result]
            print(f"✅ Found result: {result['id']}")  # Debug
        else:
            print("❌ No result found")  # Debug
    
    elif search_type == 'amount':
        # Hash Table Search - O(1) average - Using the new exact match method
        print("⚡ Using Hash Table for exact amount match")  # Debug
        start_time = time.time()
        try:
            amount = float(search_term)
            hash_table = user_hash_tables.get(username)
            if hash_table:
                # Use the new exact match method from Tree.py
                results = hash_table.search_exact_amount(amount)
                print(f"✅ Found {len(results)} results for exact amount {amount}")  # Debug
            else:
                # Fallback to linear search if hash table not available
                results = [tx for tx in transactions if abs(tx['amount'] - amount) < 0.01]
        except ValueError:
            print("❌ Invalid amount format")  # Debug
        search_time = time.time() - start_time
    
    elif search_type == 'date':
        # Linear Search - O(n) with date range support
        print("📊 Using Linear Search")  # Debug
        start_time = time.time()
        
        # Check if it's a date range (e.g., "2026-02-01 to 2026-02-19")
        if ' to ' in search_term:
            try:
                start_date, end_date = search_term.split(' to ')
                results = [
                    tx for tx in transactions 
                    if start_date <= tx.get('date', '')[:10] <= end_date
                ]
                print(f"✅ Found {len(results)} results in date range")
            except:
                results = []
        else:
            # Single date search
            results = [tx for tx in transactions if search_term.lower() in tx.get('date', '').lower()]
            print(f"✅ Found {len(results)} results by date")
        
        search_time = time.time() - start_time
    
    print(f"⏱️ Search took {round(search_time * 1000, 2)}ms")  # Debug
    
    return jsonify({
        'results': results[:20],  # Limit to 20 results
        'search_time': round(search_time * 1000, 2),  # Return in milliseconds
        'algorithm': search_type
    })

# Optional: Add an endpoint to manually clear cache if needed
@home_bp.route("/api/clear-cache", methods=["POST"])
@login_required
def clear_cache():
    """Clear the hash table cache for the current user"""
    username = session.get("user")
    if clear_user_hash_table(username):
        return jsonify({"success": True, "message": "Cache cleared"})
    return jsonify({"success": False, "message": "No cache found"})

# Optional: Add endpoint for advanced search with filters
@home_bp.route("/api/advanced-search", methods=["POST"])
@login_required
def advanced_search():
    """Advanced search with filters (type, date range, etc.)"""
    username = session.get("user")
    data = request.get_json()
    
    search_term = data.get('term', '').strip()
    filter_type = data.get('filter', 'all')  # 'all', 'credit', 'debit'
    sort_order = data.get('sort', 'desc')  # 'asc' or 'desc'
    
    file_path = f"payments_data/{username}_transactions.json"
    if not os.path.exists(file_path):
        return jsonify({'results': []})
    
    with open(file_path, 'r') as f:
        transactions = json.load(f)
    
    results = transactions
    
    # Apply search term filter
    if search_term:
        results = [
            tx for tx in results 
            if search_term.lower() in tx.get('id', '').lower() or
               search_term.lower() in tx.get('description', '').lower() or
               str(tx.get('amount', '')).startswith(search_term)
        ]
    
    # Apply type filter
    if filter_type != 'all':
        results = [tx for tx in results if tx.get('type') == filter_type]
    
    # Apply sorting
    results.sort(key=lambda x: x.get('date', ''), reverse=(sort_order == 'desc'))
    
    return jsonify({
        'results': results[:50],
        'total': len(results)
    })