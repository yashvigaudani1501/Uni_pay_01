# db.py - ADD CONNECTION POOL + TIMEOUT
import mysql.connector
from mysql.connector import pooling
import time

# CONNECTION POOL (fixes lost connection)
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '',
    'database': 'unipay',
    'pool_name': 'mypool',
    'pool_size': 5,
    'pool_reset_session': True,
    'connect_timeout': 10
}

try:
    cnxpool = mysql.connector.pooling.MySQLConnectionPool(**db_config)
    print("✅ MySQL Pool created")
except Exception as e:
    print(f"❌ MySQL Error: {e}")

def get_db_connection():
    try:
        conn = cnxpool.get_connection()
        conn.ping(reconnect=True)  # Auto-reconnect
        return conn
    except Exception as e:
        print(f"❌ DB Connection failed: {e}")
        # Fallback single connection
        return mysql.connector.connect(**db_config, connect_timeout=10)
