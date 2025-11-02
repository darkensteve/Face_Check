import sqlite3

conn = sqlite3.connect('facecheck.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Check all records
all_records = cursor.execute('SELECT attendance_id, attendance_date FROM attendance').fetchall()
print(f"Total records: {len(all_records)}")
print("\nRecords with microseconds (.):")
print("-" * 60)

has_microseconds = []
no_microseconds = []

for r in all_records:
    date_str = str(r['attendance_date'])
    if '.' in date_str:
        has_microseconds.append((r['attendance_id'], date_str))
        print(f"ID: {r['attendance_id']}, Date: {date_str}")
    else:
        no_microseconds.append(r['attendance_id'])

print(f"\nSummary:")
print(f"Records WITH microseconds: {len(has_microseconds)}")
print(f"Records WITHOUT microseconds: {len(no_microseconds)}")

conn.close()

