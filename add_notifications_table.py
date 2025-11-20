"""
Migration script to add notifications table to existing FaceCheck database
Run this script to add notification support to your database
"""

import sqlite3

def add_notifications_table():
    """Add notifications table to the database"""
    try:
        conn = sqlite3.connect('facecheck.db')
        cursor = conn.cursor()
        
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='notifications'
        """)
        
        if cursor.fetchone():
            print("[OK] Notifications table already exists")
            conn.close()
            return True
        
        # Create notifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                notification_type VARCHAR(20) NOT NULL,
                is_read BOOLEAN DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES user(user_id)
            )
        """)
        
        conn.commit()
        conn.close()
        
        print("[SUCCESS] Notifications table created successfully!")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error adding notifications table: {e}")
        return False

if __name__ == "__main__":
    print("Adding notifications table to FaceCheck database...")
    add_notifications_table()
    print("\nMigration complete! You can now use the notification features.")

