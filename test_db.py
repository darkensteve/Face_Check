import sqlite3
from db import get_connection, close_connection

def test_database():
    """Test database connection and tables"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Test connection
        print("✅ Database connection successful!")
        
        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"✅ Found {len(tables)} tables:")
        for table in tables:
            print(f"   - {table[0]}")
        
        # Test default data
        cursor.execute("SELECT COUNT(*) FROM user WHERE role='admin'")
        admin_count = cursor.fetchone()[0]
        print(f"✅ Admin users: {admin_count}")
        
        cursor.execute("SELECT COUNT(*) FROM department")
        dept_count = cursor.fetchone()[0]
        print(f"✅ Departments: {dept_count}")
        
        cursor.execute("SELECT COUNT(*) FROM course")
        course_count = cursor.fetchone()[0]
        print(f"✅ Courses: {course_count}")
        
        print("✅ Database is ready to use!")
        
    except Exception as e:
        print(f"❌ Database error: {e}")
    finally:
        close_connection(conn)

if __name__ == "__main__":
    test_database()