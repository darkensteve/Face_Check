import os
import sqlite3

def delete_database():
    """Delete the existing database file"""
    db_file = "facecheck.db"
    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"✅ Deleted existing database: {db_file}")
    else:
        print("ℹ️  No existing database found")

def create_fresh_database():
    """Create a completely fresh database with correct data"""
    print(" Creating fresh database...")
    
    # Delete existing database
    delete_database()
    
    # Create new database connection
    conn = sqlite3.connect("facecheck.db")
    cursor = conn.cursor()
    
    try:
        # Create all tables
        create_tables(cursor)
        
        # Insert correct data
        insert_correct_data(cursor)
        
        # Insert sample accounts
        insert_sample_accounts(cursor)
        
        # Commit changes
        conn.commit()
        print("✅ Fresh database created successfully!")
        
        # Verify the data
        verify_database(cursor)
        
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        conn.rollback()
    finally:
        conn.close()

def create_tables(cursor):
    """Create all database tables"""
    print("📋 Creating tables...")
    
    # DEPARTMENT table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS department (
            dept_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dept_name VARCHAR(50) NOT NULL
        )
    """)
    
    # USER table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            idno VARCHAR(20) NOT NULL UNIQUE,
            firstname VARCHAR(50) NOT NULL,
            lastname VARCHAR(50) NOT NULL,
            role VARCHAR(10) NOT NULL CHECK (role IN ('admin', 'faculty', 'student')),
            password VARCHAR(255) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            dept_id INTEGER,
            FOREIGN KEY (dept_id) REFERENCES department(dept_id)
        )
    """)
    
    # FACULTY table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faculty (
            faculty_id INTEGER PRIMARY KEY AUTOINCREMENT,
            position VARCHAR(30) NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES user(user_id)
        )
    """)
    
    # COURSE table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS course (
            course_id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_name VARCHAR(100) NOT NULL,
            dept_id INTEGER,
            FOREIGN KEY (dept_id) REFERENCES department(dept_id)
        )
    """)
    
    # STUDENT table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student (
            student_id INTEGER PRIMARY KEY AUTOINCREMENT,
            year_level VARCHAR(20) NOT NULL,
            attendance_image VARCHAR(255),
            course_id INTEGER,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (course_id) REFERENCES course(course_id),
            FOREIGN KEY (user_id) REFERENCES user(user_id)
        )
    """)
    
    # DAYS table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS days (
            day_id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_name VARCHAR(10) NOT NULL UNIQUE
        )
    """)
    
    # CLASS table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS class (
            class_id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name VARCHAR(20) NOT NULL,
            edpcode VARCHAR(20) NOT NULL UNIQUE,
            start_time TIME,
            end_time TIME,
            room VARCHAR(10),
            faculty_id INTEGER NOT NULL,
            FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id)
        )
    """)
    
    # STUDENT_CLASS table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_class (
            studentclass_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            FOREIGN KEY (student_id) REFERENCES student(student_id),
            FOREIGN KEY (class_id) REFERENCES class(class_id),
            UNIQUE(student_id, class_id)
        )
    """)
    
    # CLASS_DAYS table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS class_days (
            class_id INTEGER NOT NULL,
            day_id INTEGER NOT NULL,
            PRIMARY KEY (class_id, day_id),
            FOREIGN KEY (class_id) REFERENCES class(class_id),
            FOREIGN KEY (day_id) REFERENCES days(day_id)
        )
    """)
    
    # ATTENDANCE table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            attendance_date DATETIME NOT NULL,
            attendance_status VARCHAR(10) NOT NULL CHECK (attendance_status IN ('present', 'absent', 'late')),
            studentclass_id INTEGER NOT NULL,
            FOREIGN KEY (studentclass_id) REFERENCES student_class(studentclass_id)
        )
    """)
    
    # EVENT table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS event (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name VARCHAR(20) NOT NULL,
            description TEXT,
            event_date DATETIME NOT NULL,
            start_time TIME,
            end_time TIME,
            room VARCHAR(20),
            faculty_id INTEGER NOT NULL,
            FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id)
        )
    """)
    
    # EVENT_ATTENDANCE table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_attendance (
            event_attend_id INTEGER PRIMARY KEY AUTOINCREMENT,
            attendance_time DATETIME NOT NULL,
            status VARCHAR(10) NOT NULL CHECK (status IN ('present', 'absent', 'late')),
            event_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            FOREIGN KEY (event_id) REFERENCES event(event_id),
            FOREIGN KEY (user_id) REFERENCES user(user_id)
        )
    """)
    
    print("✅ All tables created successfully!")

def insert_correct_data(cursor):
    """Insert the correct departments and courses"""
    print(" Inserting correct data...")
    
    # Insert departments (Colleges)
    departments = [
        ('College of Engineering',),
        ('College of Education',),
        ('College of Criminology',),
        ('College of Business Administration',),
        ('College of Accountancy',),
        ('College of Commerce',),
        ('College of Hotel and Restaurant Management',),
        ('College of Computer Studies',),
        ('College of Liberal Arts',),
        ('College of Maritime Studies',),
        ('College of Nursing',),
        ('College of Midwifery',)
    ]
    
    cursor.executemany("INSERT INTO department (dept_name) VALUES (?)", departments)
    print(f"✅ Inserted {len(departments)} departments")
    
    # Insert courses with their department IDs
    courses = [
        # College of Engineering (dept_id = 1)
        ('BS Civil Engineering', 1),
        ('BS Mechanical Engineering', 1),
        ('BS Electrical Engineering', 1),
        ('BS Industrial Engineering', 1),
        ('BS Naval Architecture and Marine Engineering', 1),
        ('BS Computer Engineering', 1),
        
        # College of Education (dept_id = 2)
        ('Bachelor of Elementary Education', 2),
        ('Bachelor of Secondary Education', 2),
        
        # College of Criminology (dept_id = 3)
        ('BS Criminology', 3),
        
        # College of Business Administration (dept_id = 4)
        ('BS Business Administration', 4),
        
        # College of Accountancy (dept_id = 5)
        ('BS Accountancy', 5),
        
        # College of Commerce (dept_id = 6)
        ('BS Commerce', 6),
        ('BS Customs Administration', 6),
        
        # College of Hotel and Restaurant Management (dept_id = 7)
        ('BS Hotel and Restaurant Management', 7),
        
        # College of Computer Studies (dept_id = 8)
        ('BS Information Technology', 8),
        ('BS Computer Science', 8),
        
        # College of Liberal Arts (dept_id = 9)
        ('AB Political Science', 9),
        ('AB English', 9),
        
        # College of Maritime Studies (dept_id = 10)
        ('BS Marine Transportation', 10),
        ('BS Marine Engineering', 10),
        
        # College of Nursing (dept_id = 11)
        ('BS Nursing', 11),
        
        # College of Midwifery (dept_id = 12)
        ('BS Midwifery', 12)
    ]
    
    cursor.executemany("INSERT INTO course (course_name, dept_id) VALUES (?, ?)", courses)
    print(f"✅ Inserted {len(courses)} courses")
    
    # Insert days
    days = [
        ('Monday',),
        ('Tuesday',),
        ('Wednesday',),
        ('Thursday',),
        ('Friday',),
        ('Saturday',),
        ('Sunday',)
    ]
    cursor.executemany("INSERT INTO days (day_name) VALUES (?)", days)
    print(f"✅ Inserted {len(days)} days")
    
    # Insert admin user
    cursor.execute("""
        INSERT INTO user (idno, firstname, lastname, role, password, dept_id) 
        VALUES ('admin', 'Admin', 'User', 'admin', 'admin123', 1)
    """)
    print("✅ Inserted admin user")

def insert_sample_accounts(cursor):
    """Insert sample student and faculty accounts"""
    print("👥 Inserting sample accounts...")
    
    # Insert sample student
    cursor.execute("""
        INSERT INTO user (idno, firstname, lastname, role, password, dept_id) 
        VALUES ('STU001', 'John', 'Doe', 'student', 'STU001', 8)
    """)
    
    # Get the student user_id
    cursor.execute("SELECT user_id FROM user WHERE idno = 'STU001'")
    student_user_id = cursor.fetchone()[0]
    
    # Insert student record
    cursor.execute("""
        INSERT INTO student (year_level, course_id, user_id) 
        VALUES ('3rd Year', 1, ?)
    """, (student_user_id,))
    
    print("✅ Inserted sample student: STU001 / STU001")
    
    # Insert sample faculty
    cursor.execute("""
        INSERT INTO user (idno, firstname, lastname, role, password, dept_id) 
        VALUES ('FAC001', 'Jane', 'Smith', 'faculty', 'FAC001', 8)
    """)
    
    # Get the faculty user_id
    cursor.execute("SELECT user_id FROM user WHERE idno = 'FAC001'")
    faculty_user_id = cursor.fetchone()[0]
    
    # Insert faculty record
    cursor.execute("""
        INSERT INTO faculty (position, user_id) 
        VALUES ('Professor', ?)
    """, (faculty_user_id,))
    
    print("✅ Inserted sample faculty: FAC001 / FAC001")
    
    # Create a sample class
    cursor.execute("""
        INSERT INTO class (class_name, edpcode, start_time, end_time, room, faculty_id) 
        VALUES ('CS101', 'CS101-2024', '08:00:00', '10:00:00', 'Room 101', 1)
    """)
    
    # Enroll student in the class
    cursor.execute("""
        INSERT INTO student_class (student_id, class_id) 
        VALUES (1, 1)
    """)
    
    print("✅ Created sample class and enrollment")

def verify_database(cursor):
    """Verify the database was created correctly"""
    print("\n�� VERIFYING DATABASE...")
    print("-" * 50)
    
    # Check departments
    cursor.execute("SELECT COUNT(*) FROM department")
    dept_count = cursor.fetchone()[0]
    print(f"✅ Departments: {dept_count}")
    
    # Check courses
    cursor.execute("SELECT COUNT(*) FROM course")
    course_count = cursor.fetchone()[0]
    print(f"✅ Courses: {course_count}")
    
    # Check users
    cursor.execute("SELECT COUNT(*) FROM user")
    user_count = cursor.fetchone()[0]
    print(f"✅ Users: {user_count}")
    
    # Check students
    cursor.execute("SELECT COUNT(*) FROM student")
    student_count = cursor.fetchone()[0]
    print(f"✅ Students: {student_count}")
    
    # Check faculty
    cursor.execute("SELECT COUNT(*) FROM faculty")
    faculty_count = cursor.fetchone()[0]
    print(f"✅ Faculty: {faculty_count}")
    
    # Show all users
    cursor.execute("SELECT idno, firstname, lastname, role, dept_id FROM user ORDER BY role")
    users = cursor.fetchall()
    
    print(f"\n�� USERS ({len(users)}):")
    for user in users:
        print(f"   {user[0]:8s} - {user[1]} {user[2]} ({user[3]}) - Dept: {user[4]}")
    
    # Show departments
    cursor.execute("SELECT dept_id, dept_name FROM department ORDER BY dept_name")
    departments = cursor.fetchall()
    
    print(f"\n🏢 DEPARTMENTS ({len(departments)}):")
    for dept in departments:
        print(f"   {dept[0]:2d}. {dept[1]}")
    
    # Show courses by department
    cursor.execute("""
        SELECT d.dept_name, c.course_name
        FROM course c
        JOIN department d ON c.dept_id = d.dept_id
        ORDER BY d.dept_name, c.course_name
    """)
    courses = cursor.fetchall()
    
    print(f"\n COURSES BY DEPARTMENT:")
    current_dept = None
    for course in courses:
        if course[0] != current_dept:
            current_dept = course[0]
            print(f"\n   {current_dept}:")
        print(f"      • {course[1]}")
    
    print(f"\n�� STATISTICS:")
    print(f"   Departments: {dept_count}")
    print(f"   Courses: {course_count}")
    print(f"   Users: {user_count}")
    print(f"   Students: {student_count}")
    print(f"   Faculty: {faculty_count}")
    
    print("\n🎉 Database creation completed successfully!")
    print("\n🔑 LOGIN CREDENTIALS:")
    print("   Admin:  admin / admin123")
    print("   Student: STU001 / student123")
    print("   Faculty: FAC001 / faculty123")

if __name__ == "__main__":
    print("🗑️  CREATING FRESH DATABASE...")
    print("=" * 50)
    
    # Ask for confirmation
    response = input("This will DELETE your current database. Continue? (y/N): ")
    if response.lower() in ['y', 'yes']:
        create_fresh_database()
    else:
        print("❌ Operation cancelled")