# Settings Applied Guide
## Where Admin Settings Are Actually Used

This document shows exactly where each admin setting is applied in the system.

---

## 🔐 Password Policy Settings

### Applied In:

#### 1. **User Creation** (`/admin/users/create`)
When admin creates a new user, the password must meet the configured requirements.

**Settings Used:**
- `password_min_length` - Minimum password length
- `password_require_special` - Require special characters (!@#$%^&*, etc.)
- `password_require_number` - Require at least one number (0-9)
- `password_require_uppercase` - Require at least one uppercase letter (A-Z)

**Code Location:** `app.py` line ~412, function `create_user()`

```python
# Validate password strength using admin settings
from security_config import validate_password_strength
is_valid_password, password_message = validate_password_strength(password)
if not is_valid_password:
    flash(password_message, 'error')
```

#### 2. **Password Reset** (`/admin/users/<id>/reset-password`)
When admin resets a user's password, the new password must meet the requirements.

**Settings Used:** Same as User Creation

**Code Location:** `app.py` line ~577, function `reset_password()`

```python
# Validate password strength using admin settings
from security_config import validate_password_strength
is_valid_password, password_message = validate_password_strength(new_password)
if not is_valid_password:
    flash(password_message, 'error')
```

#### 3. **Validation Function** (`security_config.py`)
The core validation function that checks all password requirements.

**Code Location:** `security_config.py` line ~36, function `validate_password_strength()`

---

## 🔒 Security Management Settings

### Applied In:

#### 1. **Login Rate Limiting** (`/login`)
When users attempt to login, the system tracks failed attempts and locks them out.

**Settings Used:**
- `max_login_attempts` - Maximum failed login attempts before lockout (default: 5)
- `lockout_duration` - How long user is locked out in minutes (default: 15)

**Code Location:** `app.py` line ~59, function `is_rate_limited()`

```python
# Get settings from admin configuration
max_attempts = get_max_login_attempts()  # Uses admin setting
window_minutes = get_lockout_duration()  # Uses admin setting
```

**How It Works:**
- User tries to login with wrong password
- System records the attempt
- After N failed attempts (from settings), user is locked out
- Lockout lasts for X minutes (from settings)

#### 2. **Session Timeout** (All authenticated pages)
How long a user can be idle before being automatically logged out.

**Settings Used:**
- `session_timeout` - Idle time in seconds before automatic logout (default: 3600 = 1 hour)

**Code Location:** `app.py` line ~47-59, Flask configuration

```python
# Get session timeout from settings
session_timeout_seconds = get_session_timeout()  # Uses admin setting

app.config.update(
    PERMANENT_SESSION_LIFETIME=session_timeout_seconds  # Uses admin setting
)
```

**How It Works:**
- User logs in successfully
- Session timer starts
- If user is inactive for X seconds (from settings), they're logged out
- Each request refreshes the timer

---

## 📊 Attendance Rules Settings

### Status: **Ready for Integration**

These settings are saved and accessible, but need to be integrated into the attendance system.

**Settings Available:**
- `late_threshold_minutes` - Minutes after start time to mark as late (default: 15)
- `attendance_grace_period` - Minutes before class for early check-in (default: 10)
- `minimum_attendance_percentage` - Required attendance % (default: 75)
- `absent_auto_mark` - Auto-mark students as absent (default: true)

**Where They Should Be Applied:**
- Attendance marking logic
- Class schedule checks
- Attendance reports
- Late/absent calculations

**To Use These Settings:**
```python
from settings_helper import (
    get_late_threshold,
    get_grace_period,
    get_minimum_attendance,
    is_auto_mark_absent_enabled
)

late_threshold = get_late_threshold()  # Returns int (minutes)
grace_period = get_grace_period()      # Returns int (minutes)
min_attendance = get_minimum_attendance()  # Returns int (percentage)
auto_absent = is_auto_mark_absent_enabled()  # Returns bool
```

---

## 💾 Database Settings

### Status: **Ready for Integration**

These settings are saved and can be used for database operations.

**Settings Available:**
- `auto_backup` - Enable automatic backups (default: false)
- `backup_frequency` - Backup frequency: hourly, daily, weekly, monthly (default: daily)
- `backup_retention_days` - Days to keep backups (default: 30)
- `enable_logging` - Enable activity logging (default: true)
- `log_retention_days` - Days to keep logs (default: 90)

**To Use These Settings:**
```python
from settings_helper import (
    is_auto_backup_enabled,
    get_backup_frequency,
    get_backup_retention_days,
    is_logging_enabled,
    get_log_retention_days
)
```

---

## 🎯 Testing the Applied Settings

### Test 1: Password Policy

1. **Change Settings:**
   - Go to Settings → Security Management
   - Set "Minimum Length" to `10`
   - Uncheck "Require special characters"
   - Click "Save All Settings"

2. **Test User Creation:**
   - Go to User Management → Create User
   - Try password: `Password12` (10 chars, no special)
   - Should **PASS** ✓

3. **Test with Old Settings:**
   - Change "Minimum Length" back to `8`
   - Check "Require special characters"
   - Click "Save All Settings"

4. **Test Again:**
   - Try password: `Password12` (no special char)
   - Should **FAIL** ✗ - "Password must contain at least one special character"
   - Try password: `Pass12!` (only 7 chars)
   - Should **FAIL** ✗ - "Password must be at least 8 characters long"
   - Try password: `Password12!` (8 chars, has special)
   - Should **PASS** ✓

---

### Test 2: Login Rate Limiting

1. **Change Settings:**
   - Go to Settings → Security Management
   - Set "Max Login Attempts" to `3`
   - Set "Lockout Duration" to `5` minutes
   - Click "Save All Settings"

2. **Test Login:**
   - Go to Login page
   - Try login with wrong password 3 times
   - 4th attempt should show: "Too many failed login attempts. Please try again in 5 minutes"

3. **Change Settings:**
   - Set "Max Login Attempts" to `10`
   - Click "Save All Settings"

4. **Test Again:**
   - Wait 5 minutes for lockout to expire (or restart app)
   - Now you can try 10 times before lockout

---

### Test 3: Session Timeout

1. **Change Settings:**
   - Go to Settings → Security Management
   - Set "Session Timeout" to `300` (5 minutes)
   - Click "Save All Settings"
   - **Restart the application** (session config loads on startup)

2. **Test Session:**
   - Login to the system
   - Wait 6 minutes without doing anything
   - Try to click something
   - Should be redirected to login (session expired)

3. **Change Settings:**
   - Set "Session Timeout" back to `3600` (1 hour)
   - Click "Save All Settings"
   - Restart the application

---

## 📝 Summary Table

| Setting | Where Applied | When It Takes Effect |
|---------|---------------|----------------------|
| **Password Min Length** | User creation, Password reset | Immediately |
| **Require Special Chars** | User creation, Password reset | Immediately |
| **Require Numbers** | User creation, Password reset | Immediately |
| **Require Uppercase** | User creation, Password reset | Immediately |
| **Max Login Attempts** | Login page | Immediately |
| **Lockout Duration** | Login page | Immediately |
| **Session Timeout** | All authenticated pages | After app restart |
| Late Threshold | *Not yet integrated* | N/A |
| Grace Period | *Not yet integrated* | N/A |
| Minimum Attendance % | *Not yet integrated* | N/A |
| Auto-mark Absent | *Not yet integrated* | N/A |
| Auto Backup | *Not yet integrated* | N/A |
| Backup Frequency | *Not yet integrated* | N/A |
| Enable Logging | *Not yet integrated* | N/A |

---

## ✅ What's Working Now

### ✓ Password Policy
- ✅ Enforced on user creation
- ✅ Enforced on password reset
- ✅ Uses dynamic settings from admin
- ✅ Fallback to defaults if settings unavailable
- ✅ Clear error messages to users

### ✓ Login Security
- ✅ Rate limiting uses admin settings
- ✅ Lockout duration uses admin settings
- ✅ Tracks attempts per IP address
- ✅ Auto-cleans old attempts

### ✓ Session Management
- ✅ Timeout uses admin setting
- ✅ Configurable per admin preference
- ✅ Requires app restart to apply new timeout

---

## 🔧 For Developers

### How to Apply a Setting to Your Code

1. **Import the helper function:**
```python
from settings_helper import get_setting_name
```

2. **Use the setting:**
```python
value = get_setting_name()  # Returns the configured value
```

3. **Add error handling:**
```python
try:
    value = get_setting_name()
except Exception as e:
    value = default_value  # Fallback
```

### Available Helper Functions

See `settings_helper.py` for complete list:
- `get_int_setting(key, default)` - Get as integer
- `get_bool_setting(key, default)` - Get as boolean
- `get_float_setting(key, default)` - Get as float
- `get_setting(key, default)` - Get as string
- Specific functions like `get_password_min_length()`, etc.

---

## 🎉 Success!

Your password policy and security settings now **actually work**! When you change them in the admin panel, they are enforced throughout the system.

**Test it yourself:**
1. Change password minimum length to 12
2. Save settings
3. Try creating a user with an 8-character password
4. It will be rejected! ✓

---

**Maayong trabaho! (Good work!)** 😊

The settings are now fully functional and enforced!

