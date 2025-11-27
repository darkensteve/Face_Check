"""
Migration script to remove organizers from event_faculty table
Organizers should NOT be in event_faculty - they take attendance, not mark it
"""
import sqlite3
import os

def migrate_database():
    """Remove organizers from event_faculty table"""
    db_path = 'facecheck.db'
    
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found. Skipping migration.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Starting migration to remove organizers from event_faculty...")
        
        # Check if event_faculty table exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='event_faculty'
        """)
        
        if not cursor.fetchone():
            print("[OK] event_faculty table does not exist. Nothing to migrate.")
            conn.close()
            return
        
        # Remove organizers from event_faculty table
        # Organizers are identified by matching event.faculty_id with event_faculty.faculty_id
        print("Removing organizers from event_faculty table...")
        cursor.execute("""
            DELETE FROM event_faculty
            WHERE EXISTS (
                SELECT 1 FROM event e
                WHERE e.event_id = event_faculty.event_id
                AND e.faculty_id = event_faculty.faculty_id
            )
        """)
        
        removed_count = cursor.rowcount
        print(f"[OK] Removed {removed_count} organizer(s) from event_faculty table")
        
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
    print("Face_Check Remove Organizer from Event_Faculty Migration Tool")
    print("=" * 60)
    print("This migration removes organizers from event_faculty table")
    print("Organizers take attendance, they don't need to mark it.\n")
    
    migrate_database()
    
    print("\nMigration complete!")
    print("\nNote: Organizers should only be in the event.faculty_id field,")
    print("not in the event_faculty junction table.")

