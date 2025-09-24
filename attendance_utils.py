import csv, os
from datetime import datetime

ATT_DIR = "attendance"
ATT_FILE = os.path.join(ATT_DIR, "attendance.csv")
STUDENTS_FILE = "students.csv"

def _ensure_file():
    os.makedirs(ATT_DIR, exist_ok=True)
    if not os.path.exists(ATT_FILE):
        with open(ATT_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "name", "student_id"])

def load_today_names() -> set[str]:
    _ensure_file()
    today = datetime.now().strftime("%Y-%m-%d")
    names = set()
    with open(ATT_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row["date"] == today:
                names.add(row["name"])
    return names

def mark_attendance(name: str, student_id: str = None):
    _ensure_file()
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Check if already marked today
    already_marked = load_today_names()
    if name in already_marked:
        return False
    
    # Mark attendance
    with open(ATT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([today, name, student_id or ""])
    
    return True

def load_students():
    """Load existing student database"""
    students = {}
    if os.path.exists(STUDENTS_FILE):
        with open(STUDENTS_FILE, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                students[row["student_id"]] = row
    return students

def save_student(student_id, name, email):
    """Save new student to database"""
    students = load_students()
    students[student_id] = {
        "student_id": student_id,
        "name": name,
        "email": email,
        "registered_date": datetime.now().strftime("%Y-%m-%d")
    }
    
    with open(STUDENTS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["student_id", "name", "email", "registered_date"])
        for student in students.values():
            writer.writerow([student["student_id"], student["name"], student["email"], student["registered_date"]])

def get_attendance_summary():
    """Get attendance summary for web interface"""
    _ensure_file()
    summary = {}
    
    with open(ATT_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row["date"]
            name = row["name"]
            if date not in summary:
                summary[date] = []
            summary[date].append(name)
    
    return summary