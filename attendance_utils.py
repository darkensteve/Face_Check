import csv, os
from datetime import datetime

ATT_DIR = "attendance"
ATT_FILE = os.path.join(ATT_DIR, "attendance.csv")

def _ensure_file():
    os.makedirs(ATT_DIR, exist_ok=True)
    if not os.path.exists(ATT_FILE):
        with open(ATT_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "time", "name"])

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

def mark_attendance(name: str) -> bool:
    # English: Skip unknown and duplicates (per day).
    # Cebuano: I-skip ang "Unknown" ug ayaw i-duplicate sa parehas nga adlaw.
    if name == "Unknown":
        return False
    _ensure_file()
    today = datetime.now().strftime("%Y-%m-%d")
    if name in load_today_names():
        return False
    now_time = datetime.now().strftime("%H:%M:%S")
    with open(ATT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([today, now_time, name])
    return True