# global_stats.py
import json
import os
import threading
from datetime import datetime

class GlobalStats:
    def __init__(self):
        self.stats_file = "payments_data/global_stats.json"
        os.makedirs(os.path.dirname(self.stats_file), exist_ok=True)
        self.lock = threading.Lock()
        self.total_amount = 0
        self.total_transactions = 0
        self.load_stats()
    
    def load_stats(self):
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    data = json.load(f)
                    self.total_amount = data.get('total_amount', 0)
                    self.total_transactions = data.get('total_transactions', 0)
        except:
            pass
    
    def save_stats(self):
        with self.lock:
            data = {
                'total_amount': self.total_amount,
                'total_transactions': self.total_transactions,
                'last_updated': datetime.now().isoformat()
            }
            with open(self.stats_file, 'w') as f:
                json.dump(data, f)
    
    def record_transaction(self, amount):
        print("📊 STATS RECORDING...")
        with self.lock:
            self.total_amount += amount
            self.total_transactions += 1
            self.save_stats()
        print("📊 STATS UPDATED!")

global_stats = GlobalStats()
