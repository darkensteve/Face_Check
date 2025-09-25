import sqlite3
from db import get_connection, close_connection

def show_tables_only():
    """Show only the tables in the database"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("��️  ALL TABLES IN DATABASE:")
    print("-" * 40)
    
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        if tables:
            for i, table in enumerate(tables, 1):
                print(f"{i:2d}. {table[0]}")
        else:
            print("No tables found")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        close_connection(conn)

def view_database():
    """View database contents in terminal"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("=" * 60)
    print("🗄️  FACECHECK DATABASE VIEWER")
    print("=" * 60)
    
    try:
        # 1. Show all tables
        print("\n📋 TABLES:")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for table in tables:
            print(f"   • {table[0]}")
        
        # 2. Show users
        print("\n�� USERS:")
        cursor.execute("SELECT user_id, idno, firstname, lastname, role FROM user")
        users = cursor.fetchall()
        for user in users:
            print(f"   ID: {user[0]} | Username: {user[1]} | Name: {user[2]} {user[3]} | Role: {user[4]}")
        
        # 3. Show students
        print("\n🎓 STUDENTS:")
        cursor.execute("""
            SELECT s.student_id, u.firstname, u.lastname, u.idno, s.year_level, c.course_name
            FROM student s
            JOIN user u ON s.user_id = u.user_id
            LEFT JOIN course c ON s.course_id = c.course_id
        """)
        students = cursor.fetchall()
        for student in students:
            print(f"   ID: {student[0]} | Name: {student[1]} {student[2]} | ID No: {student[3]} | Year: {student[4]} | Course: {student[5] or 'Not assigned'}")
        
        # 4. Show departments
        print("\n🏢 DEPARTMENTS:")
        cursor.execute("SELECT dept_id, dept_name FROM department")
        departments = cursor.fetchall()
        for dept in departments:
            print(f"   ID: {dept[0]} | Name: {dept[1]}")
        
        # 5. Show courses
        print("\n📚 COURSES:")
        cursor.execute("SELECT course_id, course_name FROM course")
        courses = cursor.fetchall()
        for course in courses:
            print(f"   ID: {course[0]} | Name: {course[1]}")
        
        # 6. Show today's attendance
        print("\n�� TODAY'S ATTENDANCE:")
        cursor.execute("""
            SELECT u.firstname, u.lastname, a.attendance_date, a.attendance_status
            FROM attendance a
            JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
            JOIN student s ON sc.student_id = s.student_id
            JOIN user u ON s.user_id = u.user_id
            WHERE DATE(a.attendance_date) = DATE('now')
            ORDER BY a.attendance_date DESC
        """)
        attendance = cursor.fetchall()
        if attendance:
            for record in attendance:
                print(f"   {record[0]} {record[1]} | {record[2]} | Status: {record[3]}")
        else:
            print("   No attendance recorded today")
        
        # 7. Show statistics
        print("\n📊 STATISTICS:")
        cursor.execute("SELECT COUNT(*) FROM user WHERE role = 'student'")
        total_students = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM attendance WHERE DATE(attendance_date) = DATE('now') AND attendance_status = 'present'")
        today_present = cursor.fetchone()[0]
        
        attendance_rate = (today_present / total_students * 100) if total_students > 0 else 0
        
        print(f"   Total Students: {total_students}")
        print(f"   Present Today: {today_present}")
        print(f"   Attendance Rate: {attendance_rate:.1f}%")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        close_connection(conn)
    
    print("\n" + "=" * 60)

def show_tables_with_counts():
    """Show all tables with record counts"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print("🗄️  FACECHECK DATABASE - TABLES & RECORD COUNTS")
    print("=" * 60)
    
    try:
        # Get all table names
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        if tables:
            print(f"{'Table Name':<20} {'Records':<10} {'Status'}")
            print("-" * 50)
            
            for table in tables:
                table_name = table[0]
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    status = "✅ Active" if count > 0 else "�� Empty"
                    print(f"{table_name:<20} {count:<10} {status}")
                except Exception as e:
                    print(f"{table_name:<20} {'Error':<10} ❌ {str(e)[:20]}")
        else:
            print("No tables found in database")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        close_connection(conn)

def show_specific_table(table_name):
    """Show data from a specific table"""
    conn = get_connection()
    cursor = conn.cursor()
    
    print(f"��️  TABLE: {table_name.upper()}")
    print("=" * 50)
    
    try:
        # Get table schema
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        if not columns:
            print(f"❌ Table '{table_name}' not found")
            return
        
        print("📋 COLUMNS:")
        for col in columns:
            print(f"   • {col[1]} ({col[2]})")
        
        print(f"\n📊 DATA:")
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        if rows:
            for i, row in enumerate(rows, 1):
                print(f"   Row {i}: {row}")
        else:
            print("   No data found")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        close_connection(conn)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "tables":
            show_tables_only()
        elif command == "counts":
            show_tables_with_counts()
        elif command == "view":
            view_database()
        elif command == "table" and len(sys.argv) > 2:
            show_specific_table(sys.argv[2])
        else:
            print("Usage:")
            print("  python view_db.py tables     - Show all tables")
            print("  python view_db.py counts     - Show tables with record counts")
            print("  python view_db.py view        - Show full database view")
            print("  python view_db.py table <name> - Show specific table data")
    else:
        # Default: show full database view
        view_database()