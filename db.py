import sqlite3
from datetime import datetime

def create_database():
    """Create the FaceCheck database with all required tables"""
    
    # Create database connection
    conn = sqlite3.connect("facecheck.db")
    c = conn.cursor()
    
    try:
        # DEPARTMENT table
        c.execute("""
            CREATE TABLE IF NOT EXISTS department (
                dept_id INTEGER PRIMARY KEY AUTOINCREMENT,
                dept_name VARCHAR(50) NOT NULL
            )
        """)
        
        # USER table
        c.execute("""
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
        c.execute("""
            CREATE TABLE IF NOT EXISTS faculty (
                faculty_id INTEGER PRIMARY KEY AUTOINCREMENT,
                position VARCHAR(30) NOT NULL,
                user_id INTEGER NOT NULL,
                FOREIGN KEY (user_id) REFERENCES user(user_id)
            )
        """)
        
        # COURSE table
        c.execute("""
            CREATE TABLE IF NOT EXISTS course (
                course_id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_name VARCHAR(100) NOT NULL
            )
        """)
        
        # STUDENT table
        c.execute("""
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
        c.execute("""
            CREATE TABLE IF NOT EXISTS days (
                day_id INTEGER PRIMARY KEY AUTOINCREMENT,
                day_name VARCHAR(10) NOT NULL UNIQUE
            )
        """)
        
        # CLASS table
        c.execute("""
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
        c.execute("""
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
        c.execute("""
            CREATE TABLE IF NOT EXISTS class_days (
                class_id INTEGER NOT NULL,
                day_id INTEGER NOT NULL,
                PRIMARY KEY (class_id, day_id),
                FOREIGN KEY (class_id) REFERENCES class(class_id),
                FOREIGN KEY (day_id) REFERENCES days(day_id)
            )
        """)
        
        # ATTENDANCE table
        c.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
                attendance_date DATETIME NOT NULL,
                attendance_status VARCHAR(10) NOT NULL CHECK (attendance_status IN ('present', 'absent', 'late')),
                studentclass_id INTEGER NOT NULL,
                FOREIGN KEY (studentclass_id) REFERENCES student_class(studentclass_id)
            )
        """)
        
        # EVENT table
        c.execute("""
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
        c.execute("""
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
        
        # NOTIFICATIONS table
        c.execute("""
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
        
        # Insert default data
        insert_default_data(c)
        
        # Commit changes
        conn.commit()
        print("✅ Database and tables created successfully!")
        
    except Exception as e:
        print(f"❌ Error creating database: {e}")
        conn.rollback()
    finally:
        conn.close()

def insert_default_data(cursor):
    """Insert default data into the database"""
    
    # Insert default departments
    departments = [
        ('Computer Science',),
        ('Information Technology',),
        ('Engineering',),
        ('Business Administration',)
    ]
    cursor.executemany("INSERT OR IGNORE INTO department (dept_name) VALUES (?)", departments)
    
    # Insert default days
    days = [
        ('Monday',),
        ('Tuesday',),
        ('Wednesday',),
        ('Thursday',),
        ('Friday',),
        ('Saturday',),
        ('Sunday',)
    ]
    cursor.executemany("INSERT OR IGNORE INTO days (day_name) VALUES (?)", days)
    
    # Insert default courses
    courses = [
        ('Bachelor of Science in Computer Science',),
        ('Bachelor of Science in Information Technology',),
        ('Bachelor of Science in Engineering',),
        ('Bachelor of Science in Business Administration',)
    ]
    cursor.executemany("INSERT OR IGNORE INTO course (course_name) VALUES (?)", courses)
    
    # Insert default admin user (with hashed password)
    try:
        import bcrypt 
        admin_password = bcrypt.hashpw(b'admin123', bcrypt.gensalt()).decode('utf-8')
    except ImportError:
        admin_password = 'admin123'  # Fallback for initial setup
        
    cursor.execute("""
        INSERT OR IGNORE INTO user (idno, firstname, lastname, role, password, dept_id) 
        VALUES ('admin', 'Admin', 'User', 'admin', ?, 1)
    """, (admin_password,))
    
    print("✅ Default data inserted successfully!")

def get_connection():
    """Get database connection"""
    return sqlite3.connect("facecheck.db")

def close_connection(conn):
    """Close database connection"""
    if conn:
        conn.close()

if __name__ == "__main__":
    create_database()