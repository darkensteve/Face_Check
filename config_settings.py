"""
Configuration Settings Manager
Stores and manages system settings in a JSON file without database modifications
"""

import json
import os
from datetime import datetime
from pathlib import Path

# Default settings configuration
DEFAULT_SETTINGS = {
    # Attendance Rules
    'late_threshold_minutes': '15',
    'minimum_attendance_percentage': '75',
    'absent_auto_mark': 'true',
    'lates_to_absent': '3',
    'absence_notification_threshold': '5',
    'enable_notifications': 'true',
    
    # Security Management
    'session_timeout': '3600',
    'max_login_attempts': '5',
    'lockout_duration': '15',
    'password_min_length': '8',
    'password_require_special': 'true',
    'password_require_number': 'true',
    'password_require_uppercase': 'true',
    
    # Database Settings
    'auto_backup': 'false',
    'backup_frequency': 'daily',
    'backup_retention_days': '30',
    'database_path': 'facecheck.db',
    'enable_logging': 'true',
    'log_retention_days': '90',
}

class SettingsManager:
    """Manage system settings using JSON file"""
    
    def __init__(self, settings_file='config/system_settings.json'):
        self.settings_file = settings_file
        self._ensure_config_dir()
        self._load_or_create_settings()
    
    def _ensure_config_dir(self):
        """Ensure config directory exists"""
        config_dir = os.path.dirname(self.settings_file)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
    
    def _load_or_create_settings(self):
        """Load settings from file or create with defaults"""
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r') as f:
                    self.settings = json.load(f)
                # Merge with defaults for any missing keys
                for key, value in DEFAULT_SETTINGS.items():
                    if key not in self.settings:
                        self.settings[key] = value
            except Exception as e:
                print(f"Error loading settings, using defaults: {e}")
                self.settings = DEFAULT_SETTINGS.copy()
        else:
            self.settings = DEFAULT_SETTINGS.copy()
            self._save_settings()
    
    def _save_settings(self):
        """Save settings to file"""
        try:
            with open(self.settings_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False
    
    def get_all_settings(self):
        """Get all settings"""
        return self.settings.copy()
    
    def get_setting(self, key, default=None):
        """Get a specific setting"""
        return self.settings.get(key, default)
    
    def update_settings(self, new_settings):
        """Update multiple settings"""
        try:
            # Update settings
            self.settings.update(new_settings)
            
            # Add metadata
            self.settings['last_updated'] = datetime.now().isoformat()
            
            # Save to file
            return self._save_settings()
        except Exception as e:
            print(f"Error updating settings: {e}")
            return False
    
    def update_setting(self, key, value):
        """Update a single setting"""
        return self.update_settings({key: value})
    
    def reset_to_defaults(self):
        """Reset all settings to defaults"""
        self.settings = DEFAULT_SETTINGS.copy()
        return self._save_settings()
    
    def export_settings(self):
        """Export settings as JSON string"""
        return json.dumps(self.settings, indent=4)
    
    def import_settings(self, json_string):
        """Import settings from JSON string"""
        try:
            imported = json.loads(json_string)
            self.settings.update(imported)
            return self._save_settings()
        except Exception as e:
            print(f"Error importing settings: {e}")
            return False

# Global settings manager instance
settings_manager = SettingsManager()

