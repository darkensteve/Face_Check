# Attendance Timing Logic

## Overview
The Face Check attendance system determines student attendance status (Present, Late, Absent) based on **scheduled class times**, NOT when the faculty starts the camera.

## Key Principles

### 1. Schedule-Based Timing
- All timing decisions are based on the class schedule stored in the database
- The system compares current time against `start_time` and `end_time` from the class schedule
- Faculty camera start time has NO effect on attendance status

### 2. Three Attendance States

#### PRESENT
- **Condition**: Student marks attendance within the late threshold after class start time
- **Default Threshold**: 15 minutes (configurable in settings)
- **Example**: 
  - Class starts: 11:00 AM
  - Late threshold: 15 minutes
  - Student marks at: 11:10 AM
  - **Result**: PRESENT

#### LATE
- **Condition**: Student marks attendance AFTER the late threshold has passed
- **Timestamp**: Records the actual time when student marked attendance
- **Example**:
  - Class starts: 11:00 AM
  - Late threshold: 15 minutes
  - Student marks at: 11:20 AM
  - **Result**: LATE (20 minutes after start)

#### ABSENT
- **Condition**: Student never marks attendance by class end time
- **Timestamp**: Set to the scheduled class end time (not current time)
- **Auto-marking**: Happens automatically when class ends
- **Example**:
  - Class ends: 12:00 PM
  - Current time: 12:05 PM
  - Student never marked attendance
  - **Result**: ABSENT (timestamped at 12:00 PM)

## Implementation Details

### Late Marking Logic (app.py)
```python
# Located in: /api/attendance/mark endpoint
# Lines: 4487-4540

1. Get late_threshold_minutes from settings (default: 15)
2. Retrieve class start_time from database
3. Calculate time difference between current time and scheduled start time
4. If time_diff > late_threshold_minutes:
   - Mark as LATE
   Else:
   - Mark as PRESENT
```

### Auto-Absent Marking (notification_system.py)
```python
# Located in: auto_mark_absent() function
# Lines: 215-400

1. Runs automatically when attendance is fetched
2. For each enrolled student:
   a. Check if class is scheduled today (matches day of week)
   b. Check if class end time has passed
   c. Check if student already has attendance record for today
   d. If no record exists and class has ended:
      - Mark as ABSENT
      - Use scheduled end_time as the timestamp
      - Send notification to student
```

### Real-Time Updates (frontend)
- Attendance list refreshes every 30 seconds
- Shows absent students immediately when class end time passes
- No need for faculty to manually refresh

## Example Scenarios

### Scenario 1: On-Time Student
- **Class Schedule**: Monday 11:00 AM - 12:00 PM
- **Current Time**: 11:05 AM
- **Student Action**: Face detected and recognized
- **Result**: ✅ **PRESENT** (marked at 11:05 AM)

### Scenario 2: Late Student
- **Class Schedule**: Monday 11:00 AM - 12:00 PM
- **Late Threshold**: 15 minutes
- **Current Time**: 11:20 AM
- **Student Action**: Face detected and recognized
- **Result**: ⚠️ **LATE** (marked at 11:20 AM, 20 minutes after start)

### Scenario 3: Absent Student
- **Class Schedule**: Monday 11:00 AM - 12:00 PM
- **Current Time**: 12:05 PM
- **Student Action**: Never appeared for face recognition
- **Result**: ❌ **ABSENT** (auto-marked at 12:00 PM end time)

### Scenario 4: Camera Started Late
- **Class Schedule**: Monday 11:00 AM - 12:00 PM
- **Faculty Action**: Started camera at 11:30 AM (late!)
- **Student Appears**: 11:35 AM
- **Result**: ⚠️ **LATE** (marked at 11:35 AM, 35 minutes after scheduled start)
- **Note**: Student is late based on 11:00 AM start time, NOT 11:30 AM camera start

### Scenario 5: Early Camera Start
- **Class Schedule**: Monday 11:00 AM - 12:00 PM
- **Faculty Action**: Started camera at 10:50 AM (early)
- **Student Appears**: 10:55 AM
- **Result**: ✅ **PRESENT** (marked at 10:55 AM, before class even starts)
- **Note**: Student marked on time, can arrive early

## Configuration

### Late Threshold Setting
Located in: `config/system_settings.json`

```json
{
  "late_threshold_minutes": "15"
}
```

**How to Change:**
1. Go to Admin Dashboard → Settings
2. Navigate to "Attendance Rules"
3. Modify "Late Threshold (minutes)"
4. Save changes

### Auto-Mark Absent Setting
```json
{
  "absent_auto_mark": "true"
}
```

**When Disabled:**
- Students will NOT be automatically marked absent
- Faculty must manually mark absences

## Database Schema

### Class Table
```sql
- start_time: TIME (e.g., "11:00:00")
- end_time: TIME (e.g., "12:00:00")
```

### Attendance Table
```sql
- attendance_date: DATETIME (timestamp when marked)
- attendance_status: TEXT ('present', 'late', 'absent')
- studentclass_id: INTEGER (links to student-class enrollment)
```

## API Endpoints

### Mark Attendance
- **Endpoint**: `POST /api/attendance/mark`
- **Logic**: Determines status based on scheduled start_time
- **Returns**: `{attendance_status: 'present'|'late'}`

### Get Today's Attendance
- **Endpoint**: `GET /api/attendance/today?class_id=X`
- **Triggers**: Calls `auto_mark_absent()` to update absent students
- **Returns**: List of all attendance records for today

## Testing the System

### Test 1: Late Detection
1. Create a test class with start time 15 minutes ago
2. Have a student face recognized
3. Expected: Marked as LATE

### Test 2: Absent Auto-Mark
1. Create a test class with end time 5 minutes ago
2. Don't mark attendance for a student
3. Refresh attendance page
4. Expected: Student appears as ABSENT with end_time timestamp

### Test 3: Camera Start Time Independence
1. Create a class scheduled for 2:00 PM - 3:00 PM
2. Start camera at 2:30 PM
3. Student appears at 2:35 PM
4. Expected: Marked as LATE (35 minutes after scheduled 2:00 PM start)

## Troubleshooting

### Issue: Students marked present even when late
- **Check**: Verify class has correct start_time in database
- **Check**: Confirm late_threshold_minutes setting
- **Check**: System time is correct on server

### Issue: Absent students not appearing
- **Check**: Verify auto_mark_absent setting is enabled
- **Check**: Class has correct end_time in database
- **Check**: Class is scheduled for correct day of week
- **Check**: Frontend is refreshing (30 second interval)

### Issue: Wrong timestamps on absent records
- **Check**: Class end_time in database
- **Cause**: Absent timestamp uses end_time, not current time

## Summary

✅ **DO:**
- Rely on class schedule times for all status decisions
- Mark students late if they arrive after start_time + threshold
- Auto-mark absent at class end_time
- Refresh attendance data periodically

❌ **DON'T:**
- Base timing on when camera starts
- Wait until end of day to mark absences
- Manually mark every absence
- Ignore class schedule in database

---
**Last Updated**: December 16, 2025
**Version**: 1.0

