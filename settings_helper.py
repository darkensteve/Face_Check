"""
Settings Helper Functions
Provides convenient access to system settings throughout the application
"""

from config_settings import settings_manager

def get_setting(key, default=None):
    """
    Get a specific setting value
    
    Args:
        key (str): Setting key
        default: Default value if setting not found
        
    Returns:
        Setting value or default
    """
    return settings_manager.get_setting(key, default)

def get_int_setting(key, default=0):
    """Get setting as integer"""
    try:
        value = settings_manager.get_setting(key, default)
        return int(value)
    except (ValueError, TypeError):
        return default

def get_bool_setting(key, default=False):
    """Get setting as boolean"""
    value = settings_manager.get_setting(key, str(default).lower())
    if isinstance(value, bool):
        return value
    return str(value).lower() in ('true', '1', 'yes', 'on')

def get_float_setting(key, default=0.0):
    """Get setting as float"""
    try:
        value = settings_manager.get_setting(key, default)
        return float(value)
    except (ValueError, TypeError):
        return default

# Convenience functions for common settings
def get_late_threshold():
    """Get late threshold in minutes"""
    return get_int_setting('late_threshold_minutes', 15)

def get_minimum_attendance():
    """Get minimum attendance percentage"""
    return get_int_setting('minimum_attendance_percentage', 75)

def is_auto_mark_absent_enabled():
    """Check if auto-mark as absent is enabled"""
    return get_bool_setting('absent_auto_mark', True)

def get_session_timeout():
    """Get session timeout in seconds"""
    return get_int_setting('session_timeout', 3600)

def get_max_login_attempts():
    """Get max login attempts"""
    return get_int_setting('max_login_attempts', 5)

def get_lockout_duration():
    """Get lockout duration in minutes"""
    return get_int_setting('lockout_duration', 15)

def get_password_min_length():
    """Get minimum password length"""
    return get_int_setting('password_min_length', 8)

def is_password_special_required():
    """Check if special characters are required in passwords"""
    return get_bool_setting('password_require_special', True)

def is_password_number_required():
    """Check if numbers are required in passwords"""
    return get_bool_setting('password_require_number', True)

def is_password_uppercase_required():
    """Check if uppercase letters are required in passwords"""
    return get_bool_setting('password_require_uppercase', True)

def is_auto_backup_enabled():
    """Check if automatic backup is enabled"""
    return get_bool_setting('auto_backup', False)

def get_backup_frequency():
    """Get backup frequency (hourly, daily, weekly, monthly)"""
    return get_setting('backup_frequency', 'daily')

def get_backup_retention_days():
    """Get backup retention period in days"""
    return get_int_setting('backup_retention_days', 30)

def is_logging_enabled():
    """Check if activity logging is enabled"""
    return get_bool_setting('enable_logging', True)

def get_log_retention_days():
    """Get log retention period in days"""
    return get_int_setting('log_retention_days', 90)

# Example usage:
if __name__ == '__main__':
    print(f"Late Threshold: {get_late_threshold()} minutes")
    print(f"Grace Period: {get_grace_period()} minutes")
    print(f"Minimum Attendance: {get_minimum_attendance()}%")
    print(f"Auto-mark Absent: {is_auto_mark_absent_enabled()}")
    print(f"Session Timeout: {get_session_timeout()} seconds")
    print(f"Max Login Attempts: {get_max_login_attempts()}")
    print(f"Password Min Length: {get_password_min_length()}")

