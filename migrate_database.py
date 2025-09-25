"""
Database migration script to fix security issues and update existing data
Run this script to upgrade your existing database to use secure password hashing
"""

import sqlite3
import os

def migrate_database():
    """Migrate existing database to secure format"""
    
    if not os.path.exists('facecheck.db'):
        print("Database not found. Run create_database.py first.")
        return
    
    conn = sqlite3.connect('facecheck.db')
    c = conn.cursor()
    
    try:
        # Check if migration is needed
        c.execute("PRAGMA table_info(user)")
        columns = [column[1] for column in c.fetchall()]
        
        print("🔄 Starting database migration...")
        
        # Add any missing columns or constraints
        migrations = []
        
        # Add password_reset_token column if not exists
        if 'password_reset_token' not in columns:
            migrations.append("""
                ALTER TABLE user ADD COLUMN password_reset_token TEXT;
            """)
        
        # Add password_reset_expires column if not exists  
        if 'password_reset_expires' not in columns:
            migrations.append("""
                ALTER TABLE user ADD COLUMN password_reset_expires DATETIME;
            """)
        
        # Add last_login column if not exists
        if 'last_login' not in columns:
            migrations.append("""
                ALTER TABLE user ADD COLUMN last_login DATETIME;
            """)
        
        # Execute migrations
        for migration in migrations:
            c.execute(migration)
            print(f"✅ Executed migration: {migration.strip()}")
        
        # Update admin password if it's still the default
        admin_user = c.execute("""
            SELECT password FROM user WHERE idno = 'admin' AND role = 'admin'
        """).fetchone()
        
        if admin_user and admin_user[0] == 'admin123':
            try:
                import bcrypt # type: ignore
                new_password = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode('utf-8')
                c.execute("""
                    UPDATE user SET password = ? WHERE idno = 'admin' AND role = 'admin'
                """, (new_password,))
                print("✅ Updated admin password with secure hash")
            except ImportError:
                print("⚠️ bcrypt not installed. Admin password not updated.")
                print("   Run: pip install bcrypt")
        
        # Enable foreign key constraints
        c.execute("PRAGMA foreign_keys = ON")
        
        conn.commit()
        print("✅ Database migration completed successfully!")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

def backup_database():
    """Create a backup of the current database"""
    import shutil
    from datetime import datetime
    
    if os.path.exists('facecheck.db'):
        backup_name = f"facecheck_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        shutil.copy2('facecheck.db', backup_name)
        print(f"✅ Database backed up as: {backup_name}")
        return backup_name
    return None

if __name__ == "__main__":
    print("🛠️ Face_Check Database Migration Tool")
    print("=" * 40)
    
    # Create backup first
    backup_file = backup_database()
    if backup_file:
        print(f"📋 Backup created: {backup_file}")
    
    # Run migration
    migrate_database()
    
    print("\n🎉 Migration complete!")
    print("\nNext steps:")
    print("1. Install missing packages: pip install -r requirements.txt")
    print("2. Test the application: python app.py")
    print("3. Update your admin password through the web interface")