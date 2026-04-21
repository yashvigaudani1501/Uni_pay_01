# test_stats.py - RUN THIS FIRST
from global_stats import global_stats

print("🧪 Testing stats...")
print(f"Current: {global_stats.get_stats()}")

global_stats.record_transaction(999)
print(f"After +₹999: {global_stats.get_stats()}")

# Check file
import os
if os.path.exists("payments_data/global_stats.json"):
    print("✅ FILE EXISTS!")
else:
    print("❌ FILE MISSING!")
