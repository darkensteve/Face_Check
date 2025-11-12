# Quick Start Guide - Admin Settings

## 🚀 Quick Start (3 Simple Steps)

### Step 1: Login as Admin
- Open your browser and go to FaceCheck
- Login with admin credentials

### Step 2: Go to Settings
- Click **"Settings"** in the left sidebar
- You'll see 3 configuration sections

### Step 3: Configure & Save
- Click on a section (Attendance, Security, or Database)
- Change the values you want
- Click **"Save All Settings"** button (top right)
- Done! ✓

---

## 📸 What You'll See

### Configuration Sections
```
┌─────────────────────────────────────────────────────────┐
│  [✓ Set Attendance Rules]  [Security]  [Database]      │
└─────────────────────────────────────────────────────────┘
```

### Attendance Rules Section
```
Late Threshold (minutes):          [15]
Grace Period (minutes):            [10]
Minimum Attendance (%):            [75]
☑ Auto-mark as Absent
```

### Security Management Section
```
Session Timeout (seconds):         [3600]
Max Login Attempts:                [5]
Lockout Duration (minutes):        [15]

Password Policy:
  Minimum Length:                  [8]
  ☑ Require special characters
  ☑ Require numbers
  ☑ Require uppercase letters
```

### Database Settings Section
```
☐ Enable Automatic Backups
  Backup Frequency:                [daily ▼]
  Retention Period (days):         [30]

☑ Enable Activity Logging
  Log Retention Period (days):     [90]

[Backup Now] [Optimize Database] [View Activity Logs]
```

---

## 💡 Common Settings Changes

### Make Attendance More Flexible
```
Late Threshold:     15 → 20 minutes
Grace Period:       10 → 15 minutes
Minimum Attendance: 75 → 70%
```

### Make Security Stricter
```
Session Timeout:    3600 → 1800 (30 minutes)
Max Login Attempts: 5 → 3
Lockout Duration:   15 → 30 minutes
```

### Enable Backups
```
☐ Enable Automatic Backups → ☑ Enable Automatic Backups
Backup Frequency: daily
Retention Period: 30 days
```

---

## ⚡ Quick Tips

✅ **Save Your Changes**: Don't forget to click "Save All Settings"  
✅ **Test First**: Try one setting at a time  
✅ **Write Down Defaults**: Note original values before changing  
✅ **Backup Settings**: The file is in `config/system_settings.json`  

---

## 🎯 What Changed from Before

### ❌ Before:
- Settings page existed but didn't work
- Changes were not saved
- Had unnecessary 2FA section
- Required database changes

### ✅ Now:
- Settings page is fully functional
- Changes are saved and persist
- 2FA section removed (cleaner interface)
- No database changes needed
- Settings stored in simple JSON file

---

## 📱 What Admins Can Do Now

1. ✅ **Change Attendance Rules**
   - Adjust late thresholds
   - Set grace periods
   - Control auto-absent marking

2. ✅ **Configure Security**
   - Set session timeouts
   - Control login attempts
   - Set password requirements

3. ✅ **Manage Database**
   - Enable/disable backups
   - Set backup frequency
   - Control log retention
   - Backup database manually
   - Optimize database

4. ✅ **Save & Restore**
   - All settings save immediately
   - Settings persist across restarts
   - Easy to backup (single JSON file)

---

## 🔧 Technical Details

- **Storage**: `config/system_settings.json`
- **Format**: JSON (human-readable)
- **No Database Changes**: Settings stored separately
- **Instant Effect**: Changes apply immediately
- **Admin Only**: Requires admin login

---

## 📞 Need Help?

- **Documentation**: See `SETTINGS_GUIDE.md`
- **Test System**: Run `python test_settings_system.py`
- **Summary**: See `SETTINGS_IMPLEMENTATION_SUMMARY.md`

---

**Dali ra kaayo! (Very easy!)** 😊

Your settings system is ready to use!

