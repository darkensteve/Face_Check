"""
Migration script to add 'excuse' status to attendance tables
This script updates the CHECK constraints to include 'excuse' status
"""
import sqlite3
import os
from datetime import datetime

def migrate_database():
    """Add 'excuse' status to attendance and event_attendance tables"""
    db_path = 'facecheck.db'
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found. Skipping migration.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Starting migration to add 'excuse' status...")
        
        # SQLite doesn't support ALTER TABLE to modify CHECK constraints
        # So we need to recreate the tables
        
        # ========== MIGRATE ATTENDANCE TABLE ==========
        print("Migrating attendance table...")
        
        # Create new attendance table with updated constraint
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance_new (
                attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                attendance_date DATETIME NOT NULL,
                attendance_status VARCHAR(10) NOT NULL CHECK (attendance_status IN ('present', 'absent', 'late', 'excuse')),
                studentclass_id INTEGER NOT NULL,
                FOREIGN KEY (studentclass_id) REFERENCES student_class(studentclass_id)
            )
        """)
        
        # Copy data from old table to new table
        cursor.execute("""
            INSERT INTO attendance_new (attendance_id, attendance_date, attendance_status, studentclass_id)
            SELECT attendance_id, attendance_date, attendance_status, studentclass_id
            FROM attendance
        """)
        
        # Drop old table
        cursor.execute("DROP TABLE attendance")
        
        # Rename new table
        cursor.execute("ALTER TABLE attendance_new RENAME TO attendance")
        
        print("[OK] Attendance table migrated successfully")
        
        # ========== MIGRATE EVENT_ATTENDANCE TABLE ==========
        print("Migrating event_attendance table...")
        
        # Create new event_attendance table with updated constraint
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_attendance_new (
                event_attend_id INTEGER PRIMARY KEY AUTOINCREMENT,
                attendance_time DATETIME NOT NULL,
                status VARCHAR(10) NOT NULL CHECK (status IN ('present', 'absent', 'late', 'excuse')),
                event_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                FOREIGN KEY (event_id) REFERENCES event(event_id),
                FOREIGN KEY (user_id) REFERENCES user(user_id)
            )
        """)
        
        # Copy data from old table to new table
        cursor.execute("""
            INSERT INTO event_attendance_new (event_attend_id, attendance_time, status, event_id, user_id)
            SELECT event_attend_id, attendance_time, status, event_id, user_id
            FROM event_attendance
        """)
        
        # Drop old table
        cursor.execute("DROP TABLE event_attendance")
        
        # Rename new table
        cursor.execute("ALTER TABLE event_attendance_new RENAME TO event_attendance")
        
        print("[OK] Event_attendance table migrated successfully")
        
        # Commit changes
        conn.commit()
        print("\n[SUCCESS] Migration completed successfully!")
        print("'excuse' status is now available for both class and event attendance.")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Migration failed: {e}")
        print("Rolling back changes...")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_database()

