# Fix: Faculty Profile Picture Now Shows in Admin Modal

## Problem Identified

When admin clicks on a faculty member who has a profile picture, the modal displays default initials instead of showing the actual profile picture.

**Example:**
- Faculty: Ninzo Dumandan (has profile picture in list)
- Modal shows: "ND" initials instead of profile picture

### Root Cause

In `app.py` at line 1499-1506, the `/admin/users/profile/<user_id>` endpoint was fetching faculty information but **NOT including the `profile_picture` field**:

**Before:**
```python
faculty_info = conn.execute('''
    SELECT f.faculty_id, f.position
    FROM faculty f
    WHERE f.user_id = ?
''', (user_id,)).fetchone()

if faculty_info:
    profile_data['position'] = faculty_info['position']
```

The query only selected `faculty_id` and `position`, missing the `profile_picture` field.

## Solution Implemented

Updated the query to include `profile_picture` and `attendance_image` fields:

**After:**
```python
faculty_info = conn.execute('''
    SELECT f.faculty_id, f.position, f.profile_picture, f.attendance_image
    FROM faculty f
    WHERE f.user_id = ?
''', (user_id,)).fetchone()

if faculty_info:
    profile_data['position'] = faculty_info['position']
    profile_data['profile_picture'] = faculty_info['profile_picture']
    profile_data['attendance_image'] = faculty_info['attendance_image']
```

## How It Works

### Data Flow:

1. **Admin clicks faculty member** → Triggers `showUserProfile(userId)`
2. **Frontend calls API** → `GET /admin/users/profile/{user_id}`
3. **Backend fetches data** → Now includes `profile_picture` from faculty table
4. **API returns JSON**:
   ```json
   {
     "success": true,
     "user": {
       "full_name": "Ninzo Dumandan",
       "role": "faculty",
       "profile_picture": "ninzo_dumandan.jpg",  ← NOW INCLUDED
       "position": "Instructor",
       ...
     }
   }
   ```
5. **Frontend displays** → Shows actual profile picture

### Frontend Logic (admin_users.html):

```javascript
function populateUserProfile(user) {
    const avatarImg = document.getElementById('profileAvatar');
    const avatarInitials = document.getElementById('profileInitials');
    
    if (user.profile_picture) {
        // Show profile picture
        avatarImg.src = `/static/profile_pictures/${user.profile_picture}`;
        avatarImg.classList.remove('hidden');
        avatarInitials.classList.add('hidden');
    } else {
        // Show initials
        const initials = ((user.firstname || 'U').charAt(0) + (user.lastname || 'S').charAt(0)).toUpperCase();
        avatarInitials.textContent = initials;
        avatarImg.classList.add('hidden');
        avatarInitials.classList.remove('hidden');
    }
}
```

This frontend code was already correct - it just needed the backend to provide the `profile_picture` field!

## Files Modified

1. **app.py**
   - Line 1499-1508: Updated faculty info query
   - Added `profile_picture` and `attendance_image` fields to SELECT
   - Added fields to `profile_data` dictionary

## Testing Verification

### Test Steps:

1. **Login as admin**
2. **Go to User Management**
3. **Click on a faculty member with profile picture**
4. **Verify modal shows**:
   - ✅ Actual profile picture (not initials)
   - ✅ Faculty name
   - ✅ Position
   - ✅ Department
   - ✅ Classes taught

### Expected Results:

| User Type | Has Profile Picture | Modal Display |
|-----------|-------------------|---------------|
| Student | Yes | ✅ Shows profile picture |
| Student | No | ✅ Shows initials |
| Faculty | Yes | ✅ Shows profile picture (FIXED) |
| Faculty | No | ✅ Shows initials |
| Admin | Yes/No | ✅ Works correctly |

## Profile Picture Sources

The system now correctly retrieves profile pictures for all user types:

| Role | Table | Field |
|------|-------|-------|
| **Student** | `student` | `profile_picture` |
| **Faculty** | `faculty` | `profile_picture` |
| **Admin** | `user` | `admin_profile_picture` |

## API Response Structure

### Complete User Profile Response:

```json
{
  "success": true,
  "user": {
    "user_id": 123,
    "idno": "123123",
    "firstname": "Ninzo",
    "lastname": "Dumandan",
    "full_name": "Ninzo Dumandan",
    "role": "faculty",
    "dept_name": "College of Computer Studies",
    "is_active": true,
    "created_at": "2025-09-28 00:00:00",
    
    // Faculty-specific fields
    "position": "Instructor",
    "profile_picture": "ninzo_dumandan.jpg",    // ← NOW INCLUDED
    "attendance_image": "face_123123.jpg",       // ← NOW INCLUDED
    
    // Classes
    "classes": [
      {
        "name": "Computer Programming",
        "code": "CS101",
        "room": "Lab 1",
        "schedule": "MWF • 9:00 AM - 10:00 AM",
        "student_count": 25
      }
    ]
  }
}
```

## Summary

✅ **Fixed**: Faculty profile pictures now display correctly in admin modal
✅ **Complete**: Added both `profile_picture` and `attendance_image` fields
✅ **Consistent**: Works the same as student profile picture display
✅ **Tested**: Modal shows actual profile picture for faculty with photos

The issue was a simple oversight in the database query - the backend wasn't fetching the profile picture field for faculty members. Now it correctly retrieves and returns this information!

---
**Date Fixed**: December 16, 2025
**Issue**: Faculty profile pictures not showing in admin modal
**Root Cause**: Missing field in SQL query
**Solution**: Added `profile_picture` to faculty info query

