"""
Migration script to add is_active field to class and event tables.
This allows classes and events to be deactivated instead of deleted.
"""

import sqlite3
import sys

def migrate():
    """Add is_active column to class and event tables"""
    try:
        # Reconfigure stdout to handle Unicode characters
        sys.stdout.reconfigure(encoding='utf-8')
        
        conn = sqlite3.connect("facecheck.db")
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        print("🔄 Starting migration: Adding is_active field to class and event tables...")
        
        # Check if is_active column already exists in class table
        cursor.execute("PRAGMA table_info(class)")
        class_columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_active' not in class_columns:
            print("  ➕ Adding is_active column to class table...")
            cursor.execute("ALTER TABLE class ADD COLUMN is_active BOOLEAN DEFAULT 1")
            # Set all existing classes as active
            cursor.execute("UPDATE class SET is_active = 1 WHERE is_active IS NULL")
            print("  ✅ is_active column added to class table")
        else:
            print("  ⏭️  is_active column already exists in class table")
        
        # Check if is_active column already exists in event table
        cursor.execute("PRAGMA table_info(event)")
        event_columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_active' not in event_columns:
            print("  ➕ Adding is_active column to event table...")
            cursor.execute("ALTER TABLE event ADD COLUMN is_active BOOLEAN DEFAULT 1")
            # Set all existing events as active
            cursor.execute("UPDATE event SET is_active = 1 WHERE is_active IS NULL")
            print("  ✅ is_active column added to event table")
        else:
            print("  ⏭️  is_active column already exists in event table")
        
        conn.commit()
        conn.close()
        
        print("✅ Migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Error during migration: {e}")
        if conn:
            conn.rollback()
            conn.close()
        sys.exit(1)

if __name__ == "__main__":
    migrate()

