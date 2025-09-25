import sqlite3
from db import get_connection, close_connection
from datetime import datetime

def create_sample_accounts():
    """Create sample student and faculty accounts"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        print("Creating sample accounts...")
        
        # 1. Create a sample student user
        cursor.execute("""
            INSERT OR IGNORE INTO user (idno, firstname, lastname, role, password, dept_id) 
            VALUES ('STU001', 'John', 'Doe', 'student', 'student123', 1)
        """)
        
        # Get the user_id for the student
        cursor.execute("SELECT user_id FROM user WHERE idno = 'STU001'")
        student_user_id = cursor.fetchone()[0]
        
        # Create student record
        cursor.execute("""
            INSERT OR IGNORE INTO student (year_level, user_id, course_id) 
            VALUES ('1st Year', ?, 1)
        """, (student_user_id,))
        
        # 2. Create a sample faculty user
        cursor.execute("""
            INSERT OR IGNORE INTO user (idno, firstname, lastname, role, password, dept_id) 
            VALUES ('FAC001', 'Jane', 'Smith', 'faculty', 'faculty123', 1)
        """)
        
        # Get the user_id for the faculty
        cursor.execute("SELECT user_id FROM user WHERE idno = 'FAC001'")
        faculty_user_id = cursor.fetchone()[0]
        
        # Create faculty record
        cursor.execute("""
            INSERT OR IGNORE INTO faculty (position, user_id) 
            VALUES ('Professor', ?)
        """, (faculty_user_id,))
        
        # 3. Create a sample class
        cursor.execute("""
            INSERT OR IGNORE INTO class (class_name, edpcode, start_time, end_time, room, faculty_id) 
            VALUES ('CS101', 'CS101-001', '08:00', '10:00', 'Room A', ?)
        """, (faculty_user_id,))
        
        # Get class_id
        cursor.execute("SELECT class_id FROM class WHERE edpcode = 'CS101-001'")
        class_id = cursor.fetchone()[0]
        
        # Get student_id
        cursor.execute("SELECT student_id FROM student WHERE user_id = ?", (student_user_id,))
        student_id = cursor.fetchone()[0]
        
        # 4. Enroll student in class
        cursor.execute("""
            INSERT OR IGNORE INTO student_class (student_id, class_id) 
            VALUES (?, ?)
        """, (student_id, class_id))
        
        # 5. Add some sample attendance records
        cursor.execute("""
            INSERT OR IGNORE INTO attendance (attendance_date, attendance_status, studentclass_id) 
            VALUES (datetime('now', '-1 day'), 'present', ?)
        """, (1,))
        
        cursor.execute("""
            INSERT OR IGNORE INTO attendance (attendance_date, attendance_status, studentclass_id) 
            VALUES (datetime('now', '-2 days'), 'present', ?)
        """, (1,))
        
        conn.commit()
        print("✅ Sample accounts created successfully!")
        
        # Display account information
        print("\n" + "="*60)
        print("📋 SAMPLE ACCOUNTS CREATED")
        print("="*60)
        
        print("\n🎓 STUDENT ACCOUNT:")
        print("   Username: STU001")
        print("   Password: student123")
        print("   Name: John Doe")
        print("   Role: Student")
        print("   Year Level: 1st Year")
        print("   Course: Bachelor of Science in Computer Science")
        
        print("\n👨‍🏫 FACULTY ACCOUNT:")
        print("   Username: FAC001")
        print("   Password: faculty123")
        print("   Name: Jane Smith")
        print("   Role: Faculty")
        print("   Position: Professor")
        print("   Department: Computer Science")
        
        print("\n�� ADMIN ACCOUNT:")
        print("   Username: admin")
        print("   Password: admin123")
        print("   Name: Admin User")
        print("   Role: Admin")
        
        print("\n" + "="*60)
        print("🔐 LOGIN CREDENTIALS SUMMARY")
        print("="*60)
        print("Student:  STU001 / student123")
        print("Faculty:  FAC001 / faculty123")
        print("Admin:    admin / admin123")
        
    except Exception as e:
        print(f"❌ Error creating accounts: {e}")
        conn.rollback()
    finally:
        close_connection(conn)

def verify_accounts():
    """Verify that accounts were created"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        print("\n🔍 VERIFYING ACCOUNTS...")
        print("-" * 40)
        
        # Check users
        cursor.execute("SELECT idno, firstname, lastname, role FROM user WHERE role IN ('student', 'faculty', 'admin')")
        users = cursor.fetchall()
        
        for user in users:
            print(f"✅ {user[3].title()}: {user[0]} - {user[1]} {user[2]}")
        
        # Check students
        cursor.execute("""
            SELECT u.idno, u.firstname, u.lastname, s.year_level, c.course_name
            FROM user u
            JOIN student s ON u.user_id = s.user_id
            LEFT JOIN course c ON s.course_id = c.course_id
        """)
        students = cursor.fetchall()
        
        if students:
            print(f"\n📚 STUDENTS ({len(students)}):")
            for student in students:
                print(f"   • {student[0]} - {student[1]} {student[2]} ({student[3]}) - {student[4] or 'No course'}")
        
        # Check faculty
        cursor.execute("""
            SELECT u.idno, u.firstname, u.lastname, f.position, d.dept_name
            FROM user u
            JOIN faculty f ON u.user_id = f.user_id
            LEFT JOIN department d ON u.dept_id = d.dept_id
        """)
        faculty = cursor.fetchall()
        
        if faculty:
            print(f"\n👨‍�� FACULTY ({len(faculty)}):")
            for fac in faculty:
                print(f"   • {fac[0]} - {fac[1]} {fac[2]} ({fac[3]}) - {fac[4] or 'No department'}")
        
        # Check classes
        cursor.execute("""
            SELECT c.class_name, c.edpcode, u.firstname, u.lastname
            FROM class c
            JOIN faculty f ON c.faculty_id = f.faculty_id
            JOIN user u ON f.user_id = u.user_id
        """)
        classes = cursor.fetchall()
        
        if classes:
            print(f"\n�� CLASSES ({len(classes)}):")
            for cls in classes:
                print(f"   • {cls[0]} ({cls[1]}) - {cls[2]} {cls[3]}")
        
    except Exception as e:
        print(f"❌ Error verifying accounts: {e}")
    finally:
        close_connection(conn)

if __name__ == "__main__":
    create_sample_accounts()
    verify_accounts()