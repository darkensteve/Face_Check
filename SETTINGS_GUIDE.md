# Admin Settings Guide

## Overview

The FaceCheck system now has a fully functional settings management system that allows administrators to configure system behavior without modifying the database. All settings are stored in a JSON configuration file.

---

## 📍 How to Access Settings

1. **Login as Admin**
2. **Navigate to:** Settings (from the sidebar)
3. **Configure Settings:** Choose from three configuration sections
4. **Save Changes:** Click "Save All Settings" button

---

## ⚙️ Configuration Sections

### 1. Set Attendance Rules

Configure how the system handles attendance tracking:

- **Late Threshold (minutes)**: Minutes after start time to mark student as late
  - Default: `15 minutes`
  - Example: If class starts at 8:00 AM, student arriving at 8:16 AM is marked late

- **Grace Period (minutes)**: Grace period before class starts for early check-ins
  - Default: `10 minutes`
  - Example: Student can mark attendance 10 minutes before class starts

- **Minimum Attendance (%)**: Required minimum attendance percentage
  - Default: `75%`
  - Used for reporting and alerts

- **Auto-mark as Absent**: Automatically mark students as absent if not recorded
  - Default: `Enabled`
  - When enabled, students who don't mark attendance are automatically marked absent

---

### 2. Security Management

Configure security policies and authentication:

#### Session Management
- **Session Timeout (seconds)**: Idle time before automatic logout
  - Default: `3600` (1 hour)
  - Note: 3600 = 1 hour, 7200 = 2 hours

#### Login Security
- **Max Login Attempts**: Maximum failed login attempts before lockout
  - Default: `5`
  - Helps prevent brute force attacks

- **Lockout Duration (minutes)**: How long user is locked out after max attempts
  - Default: `15 minutes`
  - User must wait before trying again

#### Password Policy
- **Minimum Length**: Minimum password length
  - Default: `8 characters`
  - Recommended: 8-12 characters

- **Require Special Characters**: Passwords must include special characters (@, #, $, etc.)
  - Default: `Enabled`

- **Require Numbers**: Passwords must include numbers (0-9)
  - Default: `Enabled`

- **Require Uppercase Letters**: Passwords must include uppercase letters (A-Z)
  - Default: `Enabled`

---

### 3. Manage Database Settings

Configure database backup and logging:

#### Automatic Backup
- **Enable Automatic Backups**: Turn on/off automatic database backups
  - Default: `Disabled`
  - Recommended: Enable for production use

- **Backup Frequency**: How often to backup
  - Options: Hourly, Daily, Weekly, Monthly
  - Default: `Daily`

- **Retention Period (days)**: How long to keep old backups
  - Default: `30 days`
  - Old backups are automatically deleted

#### Activity Logging
- **Enable Activity Logging**: Turn on/off system activity logging
  - Default: `Enabled`
  - Logs user actions, attendance marks, etc.

- **Log Retention Period (days)**: How long to keep logs
  - Default: `90 days`
  - Helps with auditing and troubleshooting

#### Database Actions
- **Backup Now**: Create an immediate backup of the database
- **Optimize Database**: Optimize database performance (cleanup, reindex)
- **View Activity Logs**: View system activity logs

---

## 💾 How Settings are Stored

- **Storage Location**: `config/system_settings.json`
- **Format**: JSON (human-readable text file)
- **Backup**: Settings file should be backed up regularly
- **No Database Changes**: Settings do NOT modify database tables

---

## 🔄 Default Settings

If settings file is deleted or corrupted, the system will automatically recreate it with these defaults:

```json
{
    "late_threshold_minutes": "15",
    "attendance_grace_period": "10",
    "minimum_attendance_percentage": "75",
    "absent_auto_mark": "true",
    "session_timeout": "3600",
    "max_login_attempts": "5",
    "lockout_duration": "15",
    "password_min_length": "8",
    "password_require_special": "true",
    "password_require_number": "true",
    "password_require_uppercase": "true",
    "auto_backup": "false",
    "backup_frequency": "daily",
    "backup_retention_days": "30",
    "database_path": "facecheck.db",
    "enable_logging": "true",
    "log_retention_days": "90"
}
```

---

## 🛠️ For Developers

### Accessing Settings in Code

Use the settings helper functions:

```python
from settings_helper import (
    get_late_threshold,
    get_grace_period,
    is_auto_mark_absent_enabled,
    get_session_timeout
)

# Get specific settings
late_threshold = get_late_threshold()  # Returns int
grace_period = get_grace_period()      # Returns int
auto_absent = is_auto_mark_absent_enabled()  # Returns bool

# Or use general function
from config_settings import settings_manager

value = settings_manager.get_setting('late_threshold_minutes', '15')
```

### Updating Settings Programmatically

```python
from config_settings import settings_manager

# Update single setting
settings_manager.update_setting('late_threshold_minutes', '20')

# Update multiple settings
settings_manager.update_settings({
    'late_threshold_minutes': '20',
    'grace_period': '15'
})
```

---

## 🔒 Security Notes

1. **File Permissions**: Ensure `config/system_settings.json` has appropriate file permissions
2. **Backup Settings**: Include settings file in your backup strategy
3. **Version Control**: Consider keeping settings template in version control (but not actual settings with sensitive data)
4. **Password Policy**: Stronger password requirements = better security
5. **Session Timeout**: Shorter timeout = more secure but less convenient

---

## 📝 Common Use Cases

### Scenario 1: School with Flexible Schedule
```
Late Threshold: 20 minutes (flexible)
Grace Period: 15 minutes (allow early arrivals)
Minimum Attendance: 70% (less strict)
```

### Scenario 2: Corporate Office (Strict)
```
Late Threshold: 5 minutes (strict)
Grace Period: 5 minutes (limited early check-in)
Minimum Attendance: 90% (strict)
Session Timeout: 1800 seconds (30 minutes)
```

### Scenario 3: Remote/Hybrid Work
```
Late Threshold: 30 minutes (flexible)
Grace Period: 30 minutes (flexible)
Auto-mark Absent: Disabled (manual review)
```

---

## ❓ Troubleshooting

### Settings Not Saving
1. Check file permissions on `config/` directory
2. Ensure `config/system_settings.json` is writable
3. Check browser console for JavaScript errors
4. Verify you're logged in as admin

### Settings Reset to Defaults
1. Check if `config/system_settings.json` file exists
2. Verify file is valid JSON format
3. Check for file corruption
4. Restore from backup if available

### Settings Not Taking Effect
1. Some settings require logout/login to take effect
2. Clear browser cache and cookies
3. Restart the application server
4. Check application logs for errors

---

## 📞 Support

For additional help with settings configuration:
1. Check application logs
2. Refer to this guide
3. Contact system administrator

---

## ✨ Key Benefits

✅ **No Database Changes** - Settings stored in JSON file  
✅ **Easy to Backup** - Single file to backup  
✅ **Human Readable** - JSON format is easy to read/edit  
✅ **Instant Updates** - Changes take effect immediately  
✅ **Version Control Friendly** - Easy to track changes  
✅ **Portable** - Easy to transfer between systems  

---

**Note:** Always backup your settings before making major changes!

