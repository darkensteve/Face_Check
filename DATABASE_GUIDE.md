# Database Management Guide - Face_Check

This guide provides comprehensive instructions for managing the Face_Check database.

## 🗄️ Database Overview

Face_Check uses SQLite as its database backend with the following structure:

### Database File
- **Location**: `facecheck.db`
- **Type**: SQLite 3
- **Size**: Varies (typically 50KB - 5MB depending on usage)

### Table Structure

1. **users** - User accounts (admin, faculty, student)
2. **classes** - Class definitions
3. **students** - Student information
4. **class_students** - Class enrollment relationships
5. **attendance** - Attendance records
6. **events** - Scheduled events
7. **event_attendance** - Event attendance tracking
8. **face_encodings** - Stored face recognition data
9. **login_attempts** - Security tracking
10. **sessions** - Active user sessions
11. **audit_log** - System activity logging
12. **settings** - Application settings
13. **notifications** - System notifications

## 🔧 Database Operations

### 1. Initialize New Database

Create a fresh database with all tables:
```bash
python db.py
```

**What it does:**
- Creates all required tables
- Sets up foreign key constraints
- Creates default admin user
- Initializes security settings

### 2. Check Database Status

Get comprehensive database information:
```bash
python status_report.py
```

**Output includes:**
- Table count and structure
- Record counts per table
- Database file size
- Integrity check results

### 3. View Database Contents

Examine database data in detail:
```bash
python view_db.py
```

**Shows:**
- All tables with record counts
- Sample data from each table
- User account details (passwords hashed)
- Class and enrollment information

### 4. Database Migration

Update database schema and security:
```bash
python migrate_database.py
```

**Functions:**
- Adds missing tables/columns
- Updates security configurations
- Migrates data to new formats
- Preserves existing data

### 5. Reset Database (⚠️ Destructive)

Completely recreate database:
```bash
python recreate_database.py
```

**⚠️ Warning:** This destroys all data!
- Deletes existing database
- Creates new empty database
- Resets to default state

### 6. Create Sample Data

Populate database with test data:
```bash
python create_sample_accounts.py
```

**Creates:**
- Sample faculty accounts
- Sample student accounts
- Sample classes
- Test attendance records

## 🔍 Database Inspection

### Manual Database Access

Using SQLite command line:
```bash
sqlite3 facecheck.db

# Common queries
.tables                          # List all tables
.schema users                    # Show table structure
SELECT COUNT(*) FROM users;      # Count users
SELECT * FROM users LIMIT 5;    # View sample users
.exit                           # Exit SQLite
```

### Python Database Inspection

```python
import sqlite3

# Connect to database
conn = sqlite3.connect('facecheck.db')
cursor = conn.cursor()

# List all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", tables)

# Check user counts by role
cursor.execute("SELECT role, COUNT(*) FROM users GROUP BY role;")
roles = cursor.fetchall()
print("User roles:", roles)

conn.close()
```

## 📊 Database Maintenance

### 1. Database Integrity Check

```bash
python -c "
import sqlite3
conn = sqlite3.connect('facecheck.db')
cursor = conn.cursor()
cursor.execute('PRAGMA integrity_check;')
result = cursor.fetchone()
print('Database integrity:', result[0])
conn.close()
"
```

### 2. Database Size Optimization

```bash
python -c "
import sqlite3
import os
print('Database size before:', os.path.getsize('facecheck.db'), 'bytes')
conn = sqlite3.connect('facecheck.db')
conn.execute('VACUUM;')
conn.close()
print('Database size after:', os.path.getsize('facecheck.db'), 'bytes')
"
```

### 3. Clean Temporary Data

```bash
python -c "
import sqlite3
conn = sqlite3.connect('facecheck.db')
cursor = conn.cursor()

# Clean old sessions (older than 24 hours)
cursor.execute('DELETE FROM sessions WHERE created_at < datetime(\"now\", \"-1 day\");')
deleted_sessions = cursor.rowcount

# Clean old login attempts (older than 7 days)
cursor.execute('DELETE FROM login_attempts WHERE timestamp < datetime(\"now\", \"-7 days\");')
deleted_attempts = cursor.rowcount

conn.commit()
conn.close()

print(f'Cleaned {deleted_sessions} old sessions')
print(f'Cleaned {deleted_attempts} old login attempts')
"
```

## 🔐 Security Management

### 1. Update Admin Password

```bash
python -c "
import sqlite3
import bcrypt

new_password = input('Enter new admin password: ')
hashed = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

conn = sqlite3.connect('facecheck.db')
cursor = conn.cursor()
cursor.execute('UPDATE users SET password = ? WHERE username = \"admin\";', (hashed,))
conn.commit()
conn.close()

print('Admin password updated successfully!')
"
```

### 2. View Security Events

```bash
python -c "
import sqlite3
conn = sqlite3.connect('facecheck.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM login_attempts ORDER BY timestamp DESC LIMIT 10;')
attempts = cursor.fetchall()
for attempt in attempts:
    print(f'User: {attempt[1]}, IP: {attempt[2]}, Success: {attempt[3]}, Time: {attempt[4]}')
conn.close()
"
```

### 3. List Active Sessions

```bash
python -c "
import sqlite3
conn = sqlite3.connect('facecheck.db')
cursor = conn.cursor()
cursor.execute('''
    SELECT s.session_id, u.username, u.role, s.created_at, s.last_accessed 
    FROM sessions s 
    JOIN users u ON s.user_id = u.id 
    ORDER BY s.last_accessed DESC;
''')
sessions = cursor.fetchall()
for session in sessions:
    print(f'User: {session[1]}, Role: {session[2]}, Last Access: {session[4]}')
conn.close()
"
```

## 📋 Backup and Restore

### 1. Create Database Backup

```bash
# Simple copy backup
cp facecheck.db "facecheck_backup_$(date +%Y%m%d_%H%M%S).db"

# Or with compression
sqlite3 facecheck.db ".backup facecheck_backup.db"
gzip facecheck_backup.db
```

### 2. Restore from Backup

```bash
# Restore from uncompressed backup
cp facecheck_backup_20250925_120000.db facecheck.db

# Restore from compressed backup
gunzip facecheck_backup.db.gz
cp facecheck_backup.db facecheck.db
```

### 3. Export Data to CSV

```bash
python -c "
import sqlite3
import csv

conn = sqlite3.connect('facecheck.db')
cursor = conn.cursor()

# Export users
cursor.execute('SELECT id, username, email, role, created_at FROM users;')
with open('users_export.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['ID', 'Username', 'Email', 'Role', 'Created'])
    writer.writerows(cursor.fetchall())

# Export attendance
cursor.execute('SELECT * FROM attendance;')
with open('attendance_export.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['ID', 'Student_ID', 'Class_ID', 'Date', 'Status', 'Method'])
    writer.writerows(cursor.fetchall())

conn.close()
print('Data exported to CSV files')
"
```

## 🚨 Troubleshooting

### Common Database Issues

1. **Database locked error**
   ```bash
   # Check for active connections
   lsof facecheck.db  # Linux/macOS
   # Or restart the application
   ```

2. **Corrupted database**
   ```bash
   # Check integrity
   sqlite3 facecheck.db "PRAGMA integrity_check;"
   
   # Attempt repair
   sqlite3 facecheck.db ".recover" | sqlite3 facecheck_recovered.db
   ```

3. **Missing tables**
   ```bash
   # Run migration
   python migrate_database.py
   ```

4. **Permission errors**
   ```bash
   # Check file permissions
   ls -la facecheck.db
   
   # Fix permissions (Linux/macOS)
   chmod 664 facecheck.db
   ```

### Database Recovery Steps

1. **Stop the application**
2. **Create backup of current database**
3. **Run integrity check**
4. **Apply migration if needed**
5. **Test with status report**
6. **Restart application**

### Data Validation

```bash
python -c "
import sqlite3
conn = sqlite3.connect('facecheck.db')
cursor = conn.cursor()

# Check for orphaned records
cursor.execute('''
    SELECT COUNT(*) FROM class_students cs 
    LEFT JOIN students s ON cs.student_id = s.id 
    WHERE s.id IS NULL;
''')
orphaned_enrollments = cursor.fetchone()[0]

cursor.execute('''
    SELECT COUNT(*) FROM attendance a 
    LEFT JOIN students s ON a.student_id = s.id 
    WHERE s.id IS NULL;
''')
orphaned_attendance = cursor.fetchone()[0]

print(f'Orphaned enrollments: {orphaned_enrollments}')
print(f'Orphaned attendance records: {orphaned_attendance}')

if orphaned_enrollments == 0 and orphaned_attendance == 0:
    print('✅ Database integrity is good')
else:
    print('⚠️ Database has integrity issues')

conn.close()
"
```

## 📈 Performance Optimization

### 1. Add Database Indexes

```bash
python -c "
import sqlite3
conn = sqlite3.connect('facecheck.db')
cursor = conn.cursor()

# Add performance indexes
indexes = [
    'CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);',
    'CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);',
    'CREATE INDEX IF NOT EXISTS idx_attendance_student ON attendance(student_id);',
    'CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);',
    'CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);',
    'CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip_address);'
]

for index in indexes:
    cursor.execute(index)

conn.commit()
conn.close()
print('Database indexes added for better performance')
"
```

### 2. Database Statistics

```bash
python -c "
import sqlite3
conn = sqlite3.connect('facecheck.db')
cursor = conn.cursor()

# Get table sizes
cursor.execute('''
    SELECT name, 
           (SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=m.name) as table_count
    FROM sqlite_master m WHERE type='table';
''')

tables = cursor.fetchall()
for table in tables:
    cursor.execute(f'SELECT COUNT(*) FROM {table[0]};')
    count = cursor.fetchone()[0]
    print(f'{table[0]}: {count} records')

conn.close()
"
```

---

**⚠️ Important Notes:**
- Always backup before making changes
- Test changes in development first  
- Monitor database performance regularly
- Keep Face_Check application updated