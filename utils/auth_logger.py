from db import get_db_connection
from flask import request

def log_auth_event(username, action, result, reason):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO auth_logs
            (username, action, result, reason, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                username,
                action,
                result,
                reason,
                request.remote_addr,
                request.headers.get("User-Agent")
            )
        )

        conn.commit()
        cursor.close()
        conn.close()
    except:
        pass
