"""
Migration script to add event_faculty junction table
This allows multiple faculty to be assigned to events (similar to student_class)
"""
import sqlite3
import os
from datetime import datetime

def migrate_database():
    """Add event_faculty table for many-to-many relationship between events and faculty"""
    db_path = 'facecheck.db'
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found. Skipping migration.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Starting migration to add event_faculty table...")
        
        # Check if table already exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='event_faculty'
        """)
        
        if cursor.fetchone():
            print("[OK] event_faculty table already exists. Skipping creation.")
            conn.close()
            return
        
        # Create event_faculty junction table
        print("Creating event_faculty table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_faculty (
                eventfaculty_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                faculty_id INTEGER NOT NULL,
                FOREIGN KEY (event_id) REFERENCES event(event_id) ON DELETE CASCADE,
                FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE CASCADE,
                UNIQUE(event_id, faculty_id)
            )
        """)
        
        # Create index for better query performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_faculty_event 
            ON event_faculty(event_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_faculty_faculty 
            ON event_faculty(faculty_id)
        """)
        
        # Optionally, migrate existing organizer faculty to event_faculty
        # This ensures existing events have at least the organizer as assigned faculty
        print("Migrating existing event organizers to event_faculty...")
        cursor.execute("""
            INSERT INTO event_faculty (event_id, faculty_id)
            SELECT event_id, faculty_id
            FROM event
            WHERE NOT EXISTS (
                SELECT 1 FROM event_faculty ef
                WHERE ef.event_id = event.event_id 
                AND ef.faculty_id = event.faculty_id
            )
        """)
        
        migrated_count = cursor.rowcount
        print(f"[OK] Migrated {migrated_count} existing event organizers to event_faculty table")
        
        conn.commit()
        print("[OK] Migration completed successfully!")
        
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("Face_Check Event-Faculty Migration Tool")
    print("=" * 50)
    print("This migration adds the event_faculty junction table")
    print("to support multiple faculty per event.\n")
    
    migrate_database()
    
    print("\nMigration complete!")
    print("\nNext steps:")
    print("1. Update notification_system.py to use event_faculty table")
    print("2. Create routes for managing event faculty")
    print("3. Update event-related queries to use event_faculty")

