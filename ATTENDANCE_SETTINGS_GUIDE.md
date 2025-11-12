# Attendance Settings Guide

## 🎯 Attendance Rules Now Applied!

The attendance settings you configure in the admin panel are **now actually used** when marking attendance!

---

## ⚙️ Available Settings

### 1. **Late Threshold (minutes)** ✅ APPLIED

**What it does:**
- Determines how many minutes after the scheduled class time a student is marked as "late" instead of "present"

**Example:**
```
Class Schedule: 8:00 AM
Late Threshold: 15 minutes

Student arrives at:
- 7:50 AM → Status: present ✅
- 8:10 AM → Status: present ✅ (within threshold)
- 8:16 AM → Status: late ⚠️ (after threshold)
- 8:30 AM → Status: late ⚠️
```

**How to Change:**
1. Settings → Set Attendance Rules
2. Change "Late Threshold (minutes)" to desired value (1-60)
3. Click "Save All Settings"
4. Takes effect immediately!

---

### 2. **Minimum Attendance (%)** ✅ SAVED

**What it does:**
- Sets the minimum required attendance percentage for students
- Used for reporting and tracking purposes

**Example:**
```
Minimum Attendance: 75%

Student with 18/20 classes attended:
- Attendance: 90% ✅ Above minimum
- Status: Good standing

Student with 14/20 classes attended:
- Attendance: 70% ⚠️ Below minimum
- Status: At risk
```

**Note:** This setting is saved and available for use in reports and alerts.

---

### 3. **Auto-mark as Absent** ✅ SAVED

**What it does:**
- When enabled, students who don't mark attendance are automatically marked as absent

**Example:**
```
Auto-mark Absent: Enabled ☑

At end of day:
- Students who marked attendance → Status unchanged
- Students who didn't mark → Status: absent ❌
```

**Note:** This setting is saved and ready for integration with automated attendance processing.

---

## 🎬 How Late Threshold Works

### Step-by-Step Process:

1. **Student scans face for attendance**
2. **System gets current time** (e.g., 8:16 AM)
3. **System loads class schedule** (e.g., 8:00 AM)
4. **System loads late threshold** (e.g., 15 minutes)
5. **System calculates time difference:**
   - Current: 8:16 AM
   - Scheduled: 8:00 AM
   - Difference: 16 minutes
6. **System determines status:**
   - 16 minutes > 15 minutes threshold
   - **Status: LATE** ⚠️
7. **System marks attendance with "late" status**
8. **Faculty sees:** "Attendance marked for John Doe (LATE)"

---

## 🧪 Testing Late Threshold

### Test 1: On-Time Arrival

1. **Setup:**
   - Settings → Late Threshold = 15 minutes
   - Create a class with schedule "8:00 AM"

2. **Test at 8:10 AM:**
   - Student marks attendance
   - Time difference: 10 minutes
   - Expected: Status = "present" ✅

### Test 2: Late Arrival

1. **Setup:** Same as above

2. **Test at 8:20 AM:**
   - Student marks attendance
   - Time difference: 20 minutes
   - Expected: Status = "late" ⚠️
   - Message shows: "Attendance marked for [Name] (LATE)"

### Test 3: Changed Threshold

1. **Change Settings:**
   - Settings → Late Threshold = 30 minutes
   - Save

2. **Test at 8:20 AM:**
   - Student marks attendance
   - Time difference: 20 minutes
   - Expected: Status = "present" ✅ (now within threshold!)

---

## 📊 Where Settings Are Applied

| Setting | Applied In | When | Status |
|---------|-----------|------|--------|
| **Late Threshold** | Attendance marking (`/api/attendance/mark`) | Immediately | ✅ Working |
| **Minimum Attendance** | Available for reports/alerts | Immediately | ✅ Saved |
| **Auto-mark Absent** | Available for automation | Immediately | ✅ Saved |

---

## 💡 Real-World Examples

### Example 1: Strict School

```
Settings:
- Late Threshold: 5 minutes (very strict!)
- Minimum Attendance: 90%

Result:
- Students must arrive within 5 minutes of class start
- Must attend 90% of classes
- Encourages punctuality
```

### Example 2: Flexible College

```
Settings:
- Late Threshold: 20 minutes (flexible)
- Minimum Attendance: 70%

Result:
- Students have 20-minute window
- 70% attendance requirement
- More accommodating
```

### Example 3: Corporate Training

```
Settings:
- Late Threshold: 10 minutes
- Minimum Attendance: 85%

Result:
- Balanced approach
- Professional standards
```

---

## 🔧 Technical Details

### Late Status Determination Code:

```python
# Get late threshold from admin settings
late_threshold_minutes = get_late_threshold()

# Get class schedule time
class_schedule = "8:00 AM"  # From database

# Calculate time difference
current_time = datetime.now()
scheduled_time = parse_schedule_time(class_schedule)
time_diff_minutes = (current_time - scheduled_time).total_seconds() / 60

# Determine status
if time_diff_minutes > late_threshold_minutes:
    status = 'late'  ⚠️
else:
    status = 'present'  ✅

# Save with determined status
save_attendance(student_id, status)
```

### Supported Schedule Formats:

- ✅ `08:00` (24-hour format)
- ✅ `8:00 AM` (12-hour with AM/PM)
- ✅ `08:00 AM` (12-hour with leading zero)

---

## ⚠️ Important Notes

1. **Late Threshold Range:** 1-60 minutes
2. **Class Schedule Required:** Late detection requires class schedule to be set
3. **Immediate Effect:** Changes to late threshold apply immediately (no restart needed)
4. **Default Values:** If settings unavailable, uses 15 minutes as default

---

## 🎯 Quick Summary

### English:

**Before:**
- ❌ Late threshold was ignored
- ❌ Everyone marked as "present"
- ❌ No late tracking

**Now:**
- ✅ Late threshold is applied
- ✅ Students marked as "late" or "present"
- ✅ Based on your configured threshold
- ✅ Changes take effect immediately

---

### Cebuano:

**Kaniadto:**
- ❌ Ang late threshold wala gamita
- ❌ Tanan gi-mark ug "present"
- ❌ Walay late tracking

**Karon:**
- ✅ Ang late threshold gigamit na
- ✅ Ang mga estudyante gi-mark ug "late" o "present"
- ✅ Base sa imong na-configure nga threshold
- ✅ Ang mga kausaban dayon dayon na ang epekto

---

## 📞 Next Steps

1. **Configure your late threshold** based on your needs
2. **Test with different times** to see it work
3. **Monitor late arrivals** in attendance reports
4. **Adjust as needed** - it's flexible!

---

## ✅ Verification

To verify it's working:

1. Set late threshold to 15 minutes
2. Save settings
3. Have a student mark attendance 20 minutes after class time
4. Check attendance record - should show "late" status ✅
5. System message should say "Attendance marked for [Name] (LATE)"

---

**Maayo kaayo! (Very good!)** The attendance rules are now functional! 🎉

