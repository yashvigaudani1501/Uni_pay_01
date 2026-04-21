from db import get_db_connection

def log_admin_action(admin, action, target):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO admin_logs (admin, action, target)
            VALUES (%s, %s, %s)
            """,
            (admin, action, target)
        )

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print("ADMIN LOG ERROR:", e)
