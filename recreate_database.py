import os
import sqlite3
from db import create_database

def delete_database():
    """Delete the existing database file"""
    db_file = "facecheck.db"
    if os.path.exists(db_file):
        os.remove(db_file)
        print(f"✅ Deleted existing database: {db_file}")
    else:
        print("ℹ️  No existing database found")

def recreate_database():
    """Recreate database with correct departments and courses"""
    print("�� Recreating database...")
    
    # Delete existing database
    delete_database()
    
    # Create new database
    create_database()
    
    # Add correct departments and courses
    add_correct_data()

def add_correct_data():
    """Add the correct departments and courses"""
    conn = sqlite3.connect("facecheck.db")
    cursor = conn.cursor()
    
    try:
        print("�� Adding correct departments and courses...")
        
        # Clear existing data
        cursor.execute("DELETE FROM course")
        cursor.execute("DELETE FROM department")
        
        # Insert correct departments (Colleges)
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
        
        # Insert correct courses with their respective departments
        courses = [
            # College of Engineering
            ('BS Civil Engineering', 1),
            ('BS Mechanical Engineering', 1),
            ('BS Electrical Engineering', 1),
            ('BS Industrial Engineering', 1),
            ('BS Naval Architecture and Marine Engineering', 1),
            ('BS Computer Engineering', 1),
            
            # College of Education
            ('Bachelor of Elementary Education', 2),
            ('Bachelor of Secondary Education', 2),
            
            # College of Criminology
            ('BS Criminology', 3),
            
            # College of Business Administration
            ('BS Business Administration', 4),
            
            # College of Accountancy
            ('BS Accountancy', 5),
            
            # College of Commerce
            ('BS Commerce', 6),
            ('BS Customs Administration', 6),
            
            # College of Hotel and Restaurant Management
            ('BS Hotel and Restaurant Management', 7),
            
            # College of Computer Studies
            ('BS Information Technology', 8),
            ('BS Computer Science', 8),
            
            # College of Liberal Arts
            ('AB Political Science', 9),
            ('AB English', 9),
            
            # College of Maritime Studies
            ('BS Marine Transportation', 10),
            ('BS Marine Engineering', 10),
            
            # College of Nursing
            ('BS Nursing', 11),
            
            # College of Midwifery
            ('BS Midwifery', 12)
        ]
        
        cursor.executemany("INSERT INTO course (course_name, course_id) VALUES (?, ?)", courses)
        print(f"✅ Inserted {len(courses)} courses")
        
        # Update admin user to use College of Engineering
        cursor.execute("UPDATE user SET dept_id = 1 WHERE idno = 'admin'")
        
        conn.commit()
        print("✅ Database recreated successfully!")
        
        # Display the new structure
        print("\n" + "="*80)
        print("📚 NEW DATABASE STRUCTURE")
        print("="*80)
        
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
            JOIN department d ON c.course_id = d.dept_id
            ORDER BY d.dept_name, c.course_name
        """)
        courses = cursor.fetchall()
        
        print(f"\n�� COURSES BY DEPARTMENT:")
        current_dept = None
        for course in courses:
            if course[0] != current_dept:
                current_dept = course[0]
                print(f"\n   {current_dept}:")
            print(f"      • {course[1]}")
        
        # Show statistics
        cursor.execute("SELECT COUNT(*) FROM department")
        dept_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM course")
        course_count = cursor.fetchone()[0]
        
        print(f"\n📊 STATISTICS:")
        print(f"   Departments: {dept_count}")
        print(f"   Courses: {course_count}")
        
    except Exception as e:
        print(f"❌ Error recreating database: {e}")
        conn.rollback()
    finally:
        conn.close()

def verify_new_database():
    """Verify the new database structure"""
    conn = sqlite3.connect("facecheck.db")
    cursor = conn.cursor()
    
    try:
        print("\n🔍 VERIFYING NEW DATABASE...")
        print("-" * 50)
        
        # Check if database exists
        if not os.path.exists("facecheck.db"):
            print("❌ Database file not found!")
            return
        
        # Check departments
        cursor.execute("SELECT COUNT(*) FROM department")
        dept_count = cursor.fetchone()[0]
        print(f"✅ Departments: {dept_count}")
        
        # Check courses
        cursor.execute("SELECT COUNT(*) FROM course")
        course_count = cursor.fetchone()[0]
        print(f"✅ Courses: {course_count}")
        
        # Check admin user
        cursor.execute("SELECT idno, firstname, lastname, role FROM user WHERE role = 'admin'")
        admin = cursor.fetchone()
        if admin:
            print(f"✅ Admin user: {admin[0]} - {admin[1]} {admin[2]} ({admin[3]})")
        else:
            print("❌ Admin user not found")
        
        # Check if all expected departments exist
        expected_departments = [
            'College of Engineering',
            'College of Education',
            'College of Criminology',
            'College of Business Administration',
            'College of Accountancy',
            'College of Commerce',
            'College of Hotel and Restaurant Management',
            'College of Computer Studies',
            'College of Liberal Arts',
            'College of Maritime Studies',
            'College of Nursing',
            'College of Midwifery'
        ]
        
        cursor.execute("SELECT dept_name FROM department")
        existing_departments = [row[0] for row in cursor.fetchall()]
        
        missing_departments = set(expected_departments) - set(existing_departments)
        if missing_departments:
            print(f"⚠️  Missing departments: {missing_departments}")
        else:
            print("✅ All expected departments present")
        
        # Check if all expected courses exist
        expected_courses = [
            'BS Civil Engineering',
            'BS Mechanical Engineering',
            'BS Electrical Engineering',
            'BS Industrial Engineering',
            'BS Naval Architecture and Marine Engineering',
            'BS Computer Engineering',
            'Bachelor of Elementary Education',
            'Bachelor of Secondary Education',
            'BS Criminology',
            'BS Business Administration',
            'BS Accountancy',
            'BS Commerce',
            'BS Customs Administration',
            'BS Hotel and Restaurant Management',
            'BS Information Technology',
            'BS Computer Science',
            'AB Political Science',
            'AB English',
            'BS Marine Transportation',
            'BS Marine Engineering',
            'BS Nursing',
            'BS Midwifery'
        ]
        
        cursor.execute("SELECT course_name FROM course")
        existing_courses = [row[0] for row in cursor.fetchall()]
        
        missing_courses = set(expected_courses) - set(existing_courses)
        if missing_courses:
            print(f"⚠️  Missing courses: {missing_courses}")
        else:
            print("✅ All expected courses present")
        
        print("\n🎉 Database recreation completed successfully!")
        
    except Exception as e:
        print(f"❌ Error verifying database: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    print("🗑️  RECREATING DATABASE...")
    print("=" * 50)
    
    # Ask for confirmation
    response = input("This will DELETE your current database. Continue? (y/N): ")
    if response.lower() in ['y', 'yes']:
        recreate_database()
        verify_new_database()
    else:
        print("❌ Operation cancelled")