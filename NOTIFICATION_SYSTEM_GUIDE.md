# Notification System Guide

## 🎯 Overview

The FaceCheck system now includes a comprehensive notification system that automatically alerts students about their attendance status. This guide explains all the new features and how they work.

---

## ✨ New Features

### 1. **Auto-Mark as Absent** ✅

**What it does:**
- Automatically marks students as absent if they don't mark attendance by the end of the day
- Runs as a scheduled task at the end of each day

**How to enable:**
1. Go to **Admin Settings** → **Set Attendance Rules**
2. Check the box for **"Auto-mark as Absent"**
3. Click **"Save All Settings"**

**Example:**
```
End of Day Process:
- Students who marked attendance → Status unchanged
- Students who didn't mark → Automatically marked as "absent" ❌
- Notification sent to each absent student
```

**Running the auto-mark process:**
```python
from notification_system import auto_mark_absent
auto_mark_absent()  # Returns count of students marked absent
```

---

### 2. **Lates to Absent Conversion** ✅

**What it does:**
- Converts multiple late marks into absent marks
- Default: 3 lates = 1 absent (configurable)

**How to configure:**
1. Go to **Admin Settings** → **Set Attendance Rules**
2. Set **"Lates Count as Absent"** (e.g., 3)
3. Click **"Save All Settings"**

**Example:**
```
Student has 9 late marks:
- 9 lates ÷ 3 = 3 absences
- Student receives notification about late conversion
- Status tracked for reporting purposes
```

---

### 3. **Absence Notifications** ✅

**What it does:**
- Automatically sends notifications to students when they reach a certain number of absences
- Default: 5 absences triggers notification (configurable)

**How to configure:**
1. Go to **Admin Settings** → **Set Attendance Rules**
2. Set **"Absence Notification Threshold"** (e.g., 5)
3. Check **"Enable Attendance Notifications"**
4. Click **"Save All Settings"**

**Example:**
```
Student reaches 5 absences:
- ⚠️ Notification sent: "Attendance Alert: You have 5 absences. 
  Please maintain regular attendance to meet the minimum requirement."
- Notification appears in student dashboard
- Badge count updates in real-time
```

---

### 4. **Notification Bell Icons** ✅

**What it does:**
- Shows a bell icon in faculty and student dashboards
- Displays red badge with unread notification count
- Dropdown shows recent notifications

**Location:**
- **Faculty Dashboard**: Top right corner
- **Student Dashboard**: Top right corner

**Features:**
- Real-time badge count updates every 30 seconds
- Click bell to view notification dropdown
- Mark individual notifications as read
- Mark all notifications as read with one click
- Timestamps show "just now", "5m ago", "2h ago", etc.

**Visual:**
```
┌─────────────────────────────────────┐
│  Dashboard              🔔 (3)      │  ← Badge shows unread count
└─────────────────────────────────────┘
                            │
                            ▼
                    ┌───────────────────┐
                    │ Notifications     │
                    │ [Mark all read]   │
                    ├───────────────────┤
                    │ ⚠️ Alert: You     │
                    │ have 5 absences   │
                    │ 2h ago            │
                    ├───────────────────┤
                    │ 📋 Note: 9 lates  │
                    │ equals 3 absences │
                    │ 1d ago            │
                    └───────────────────┘
```

---

## 🎛️ Admin Settings

### Attendance Rules Configuration

All notification settings are located in **Admin Settings** → **Set Attendance Rules**:

| Setting | Description | Default | Range |
|---------|-------------|---------|-------|
| **Late Threshold (minutes)** | Minutes after start time to mark as late | 15 | 1-60 |
| **Minimum Attendance (%)** | Required minimum attendance percentage | 75 | 0-100 |
| **Lates Count as Absent** | Number of lates that equal 1 absent | 3 | 1-10 |
| **Absence Notification Threshold** | Number of absences before notifying student | 5 | 1-20 |
| **Auto-mark as Absent** | Automatically mark absent if not recorded | ✓ Enabled | On/Off |
| **Enable Attendance Notifications** | Send notifications to students | ✓ Enabled | On/Off |

---

## 📊 How It Works

### Notification Flow

```
1. Student marks attendance → Status recorded (present/late/absent)
                             ↓
2. System checks notification rules
                             ↓
3. Count total absences for student
                             ↓
4. Reached threshold? (e.g., 5 absences)
   ├─ YES → Create notification
   │        └─ Send to student's dashboard
   │        └─ Update badge count
   └─ NO → Continue
                             ↓
5. Check late marks
                             ↓
6. Multiple of lates-to-absent? (e.g., 3, 6, 9)
   ├─ YES → Create late conversion notification
   └─ NO → Done
```

### Auto-Mark Absent Flow

```
End of Day (can be scheduled):
                             ↓
1. Get all active student enrollments
                             ↓
2. For each student-class:
   - Check if attendance marked today?
     ├─ YES → Skip
     └─ NO → Mark as absent
             └─ Create notification
             └─ Update badge count
                             ↓
3. Return count of students marked absent
```

---

## 🔧 Setup Instructions

### 1. Add Notifications Table to Database

Run the migration script:
```bash
python add_notifications_table.py
```

**Output:**
```
Adding notifications table to FaceCheck database...
✅ Notifications table created successfully!

Migration complete! You can now use the notification features.
```

### 2. Configure Settings

1. Login as **Admin**
2. Navigate to **Settings** in sidebar
3. Click on **Set Attendance Rules**
4. Configure notification settings:
   - Set late threshold (e.g., 15 minutes)
   - Set lates to absent conversion (e.g., 3)
   - Set absence notification threshold (e.g., 5)
   - Enable auto-mark as absent
   - Enable attendance notifications
5. Click **"Save All Settings"**

### 3. Test Notifications

**Test absence notification:**
1. Create a test student account
2. Mark the student absent 5 times (or your threshold)
3. Check student dashboard for notification bell badge
4. Click bell to view notification

**Test late conversion:**
1. Mark a student as "late" 3 times (or your threshold)
2. Check student dashboard for notification about late conversion

**Test auto-mark absent:**
```python
# In Python terminal or script
from notification_system import auto_mark_absent
count = auto_mark_absent()
print(f"Marked {count} students as absent")
```

---

## 📱 API Endpoints

### Get Notifications
```
GET /api/notifications
GET /api/notifications?unread_only=true

Response:
{
    "success": true,
    "notifications": [
        {
            "notification_id": 1,
            "user_id": 5,
            "message": "⚠️ Attendance Alert: You have 5 absences...",
            "notification_type": "absence_warning",
            "is_read": false,
            "created_at": "2025-11-20 09:30:00"
        }
    ],
    "unread_count": 3
}
```

### Get Unread Count
```
GET /api/notifications/unread-count

Response:
{
    "success": true,
    "count": 3
}
```

### Mark Notification as Read
```
POST /api/notifications/mark-read/<notification_id>

Response:
{
    "success": true
}
```

### Mark All as Read
```
POST /api/notifications/mark-all-read

Response:
{
    "success": true
}
```

---

## 🔍 Notification Types

| Type | Description | Example Message |
|------|-------------|----------------|
| **absence_warning** | Student reached absence threshold | ⚠️ Attendance Alert: You have 5 absences. Please maintain regular attendance... |
| **late_conversion** | Late marks converted to absence | 📋 Note: You have 9 late marks. Every 3 lates count as 1 absence in your record. |
| **auto_absent** | Student automatically marked absent | ❌ You were marked absent for CS101 on 2025-11-20. Please ensure you mark attendance on time. |

---

## 🎨 UI Features

### Notification Bell

**Badge Behavior:**
- Hidden when no unread notifications
- Shows count (e.g., "3") when unread notifications exist
- Red background for visibility
- Updates every 30 seconds automatically

**Dropdown:**
- Shows up to 50 recent notifications
- Unread notifications have full opacity
- Read notifications appear dimmed (60% opacity)
- Click anywhere outside to close
- Scrollable for many notifications

**Timestamps:**
- "Just now" - less than 1 minute
- "5m ago" - minutes
- "2h ago" - hours
- "3d ago" - days

---

## 🚀 Advanced Usage

### Scheduled Auto-Mark Absent

**Option 1: Manual trigger**
```python
from notification_system import auto_mark_absent
auto_mark_absent()
```

**Option 2: Cron job (Linux/Mac)**
```bash
# Run every day at 11:59 PM
59 23 * * * cd /path/to/Face_Check && python -c "from notification_system import auto_mark_absent; auto_mark_absent()"
```

**Option 3: Windows Task Scheduler**
```
1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Daily at 11:59 PM
4. Action: Start a program
   - Program: python
   - Arguments: -c "from notification_system import auto_mark_absent; auto_mark_absent()"
   - Start in: C:\Face_Check
```

### Custom Notifications

```python
from notification_system import create_notification

# Create custom notification
create_notification(
    user_id=5,
    message="📢 Important: Faculty meeting tomorrow at 9 AM",
    notification_type="info"
)
```

---

## 🐛 Troubleshooting

### Notifications not showing?

**Check 1: Database table exists**
```bash
python add_notifications_table.py
```

**Check 2: Notifications enabled in settings**
- Go to Admin Settings
- Check "Enable Attendance Notifications" is checked
- Click "Save All Settings"

**Check 3: Browser console for errors**
- Press F12 to open developer console
- Look for JavaScript errors related to notifications

### Badge count not updating?

**Solution:**
- Refresh the page
- Check browser console for network errors
- Ensure notification API endpoints are accessible

### Auto-mark not working?

**Check:**
- Setting is enabled in Admin Settings
- Run script manually to test: `python -c "from notification_system import auto_mark_absent; auto_mark_absent()"`
- Check database for new attendance records

---

## 📝 Summary

✅ **Auto-mark as absent** - Automatically marks students absent if not recorded
✅ **3 lates = 1 absent** - Configurable late-to-absent conversion
✅ **Absence notifications** - Alerts students at threshold (e.g., 5 absences)
✅ **Notification icons** - Bell icon in faculty and student dashboards
✅ **Real-time updates** - Badge count updates every 30 seconds
✅ **Admin configuration** - All settings in one place

---

## 🎓 Best Practices

1. **Set reasonable thresholds**
   - Late threshold: 10-15 minutes
   - Absence notification: 3-5 absences
   - Lates to absent: 3 lates

2. **Monitor notification effectiveness**
   - Check if students respond to notifications
   - Adjust thresholds based on attendance patterns

3. **Run auto-mark daily**
   - Schedule it at end of day (11:59 PM)
   - Or run manually if needed

4. **Test before deployment**
   - Test with sample students
   - Verify notifications appear correctly
   - Check email notifications (if integrated)

---

## 📞 Support

For issues or questions about the notification system:
1. Check this guide first
2. Review the troubleshooting section
3. Check system logs for errors
4. Contact system administrator

---

**System Version:** 1.0
**Last Updated:** November 20, 2025

