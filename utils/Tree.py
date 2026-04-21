# utils/Tree.py
import json
from datetime import datetime

class TransactionNode:
    def __init__(self, transaction):
        self.transaction = transaction
        self.left = None
        self.right = None

class TransactionBST:
    """Binary Search Tree for transaction search by ID"""
    
    def __init__(self):
        self.root = None
    
    def insert(self, transaction):
        """Insert transaction into BST"""
        if not self.root:
            self.root = TransactionNode(transaction)
        else:
            self._insert_recursive(self.root, transaction)
    
    def _insert_recursive(self, node, transaction):
        try:
            if int(transaction['id'], 16) < int(node.transaction['id'], 16):
                if node.left:
                    self._insert_recursive(node.left, transaction)
                else:
                    node.left = TransactionNode(transaction)
            else:
                if node.right:
                    self._insert_recursive(node.right, transaction)
                else:
                    node.right = TransactionNode(transaction)
        except:
            # Fallback for non-hex IDs
            if transaction['id'] < node.transaction['id']:
                if node.left:
                    self._insert_recursive(node.left, transaction)
                else:
                    node.left = TransactionNode(transaction)
            else:
                if node.right:
                    self._insert_recursive(node.right, transaction)
                else:
                    node.right = TransactionNode(transaction)
    
    def search(self, target_id):
        """Search transaction by ID (BST search - O(log n))"""
        return self._search_recursive(self.root, str(target_id))
    
    def _search_recursive(self, node, target_id):
        if not node:
            return None
        
        node_id = node.transaction['id']
        if node_id == target_id:
            return node.transaction
        elif target_id < node_id:
            return self._search_recursive(node.left, target_id)
        else:
            return self._search_recursive(node.right, target_id)

class TransactionHashTable:
    """Hash Table for fast transaction lookup by ID or amount"""
    
    def __init__(self):
        self.id_table = {}  # O(1) lookup by ID
        self.amount_buckets = {}  # For amount-based search
        self.exact_amount_map = {}  # For exact amount matching
    
    def build_from_list(self, transactions):
        """Build hash table from transaction list"""
        for tx in transactions:
            # Store by ID
            self.id_table[tx['id']] = tx
            
            # Store in amount buckets (for amount range queries) - bucket by 100s
            range_key = round(tx['amount'] / 100) * 100
            if range_key not in self.amount_buckets:
                self.amount_buckets[range_key] = []
            self.amount_buckets[range_key].append(tx)
            
            # Store for exact amount matching - bucket by actual amount
            # Use string key to avoid floating point issues
            exact_key = str(tx['amount'])
            if exact_key not in self.exact_amount_map:
                self.exact_amount_map[exact_key] = []
            self.exact_amount_map[exact_key].append(tx)
    
    def search_by_id(self, tx_id):
        """O(1) search by transaction ID"""
        return self.id_table.get(str(tx_id))
    
    def search_by_amount_range(self, min_amount, max_amount):
        """Search transactions within amount range"""
        results = []
        min_bucket = round(min_amount / 100) * 100
        max_bucket = round(max_amount / 100) * 100
        
        for bucket in range(min_bucket, max_bucket + 100, 100):
            if bucket in self.amount_buckets:
                for tx in self.amount_buckets[bucket]:
                    if min_amount <= tx['amount'] <= max_amount:
                        results.append(tx)
        return sorted(results, key=lambda x: x['date'], reverse=True)
    
    def search_exact_amount(self, amount):
        """Search for exact amount match - O(1) average"""
        # Use string key to handle floating point precision
        exact_key = str(amount)
        results = self.exact_amount_map.get(exact_key, [])
        return sorted(results, key=lambda x: x['date'], reverse=True)
    
    def search_by_amount_precise(self, amount, tolerance=0.01):
        """Search for amount with small tolerance - useful for floating point"""
        results = []
        for tx_list in self.exact_amount_map.values():
            for tx in tx_list:
                if abs(tx['amount'] - amount) <= tolerance:
                    results.append(tx)
        return sorted(results, key=lambda x: x['date'], reverse=True)

class TransactionAnalyzer:
    """Advanced transaction analysis using DSA"""
    
    @staticmethod
    def get_monthly_summary(transactions):
        """Group transactions by month"""
        summary = {}
        for tx in transactions:
            try:
                date = datetime.strptime(tx['date'], '%Y-%m-%d %H:%M:%S')
                month_key = date.strftime('%Y-%m')
                
                if month_key not in summary:
                    summary[month_key] = {'credit': 0, 'debit': 0, 'count': 0}
                
                summary[month_key][tx['type']] += tx['amount']
                summary[month_key]['count'] += 1
            except:
                pass
        
        return summary
    
    @staticmethod
    def get_top_transactions(transactions, n=5):
        """Get top N transactions by amount (using sorting algorithm)"""
        return sorted(transactions, key=lambda x: x['amount'], reverse=True)[:n]
    
    @staticmethod
    def get_transactions_by_type(transactions, tx_type):
        """Filter transactions by type (credit/debit)"""
        return [tx for tx in transactions if tx.get('type') == tx_type]
    
    @staticmethod
    def get_transactions_by_date_range(transactions, start_date, end_date):
        """Get transactions within a date range"""
        results = []
        for tx in transactions:
            try:
                tx_date = datetime.strptime(tx['date'], '%Y-%m-%d %H:%M:%S')
                start = datetime.strptime(start_date, '%Y-%m-%d')
                end = datetime.strptime(end_date, '%Y-%m-%d')
                if start <= tx_date <= end:
                    results.append(tx)
            except:
                pass
        return sorted(results, key=lambda x: x['date'], reverse=True)
    
    @staticmethod
    def get_total_credit(transactions):
        """Calculate total credit amount"""
        return sum(tx['amount'] for tx in transactions if tx.get('type') == 'credit')
    
    @staticmethod
    def get_total_debit(transactions):
        """Calculate total debit amount"""
        return sum(tx['amount'] for tx in transactions if tx.get('type') == 'debit')
    
    @staticmethod
    def get_average_transaction(transactions):
        """Calculate average transaction amount"""
        if not transactions:
            return 0
        return sum(tx['amount'] for tx in transactions) / len(transactions)