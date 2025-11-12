"""
Test script to verify the settings system is working correctly
"""

import os
import sys

def test_settings_system():
    """Test the settings system functionality"""
    
    print("=" * 60)
    print("Testing FaceCheck Settings System")
    print("=" * 60)
    print()
    
    # Test 1: Import settings manager
    print("1. Testing import of settings manager...")
    try:
        from config_settings import settings_manager
        print("   ✓ Settings manager imported successfully")
    except Exception as e:
        print(f"   ✗ Failed to import settings manager: {e}")
        return False
    
    # Test 2: Check config directory
    print("\n2. Checking config directory...")
    if os.path.exists('config'):
        print("   ✓ Config directory exists")
    else:
        print("   ✗ Config directory not found")
        return False
    
    # Test 3: Get all settings
    print("\n3. Testing get_all_settings()...")
    try:
        settings = settings_manager.get_all_settings()
        print(f"   ✓ Retrieved {len(settings)} settings")
        print(f"   ✓ Settings file location: {settings_manager.settings_file}")
    except Exception as e:
        print(f"   ✗ Failed to get settings: {e}")
        return False
    
    # Test 4: Display current settings
    print("\n4. Current settings:")
    print("   " + "-" * 56)
    for key, value in settings.items():
        if key != 'last_updated':  # Skip metadata
            print(f"   {key:35} = {value}")
    print("   " + "-" * 56)
    
    # Test 5: Test update setting
    print("\n5. Testing update_setting()...")
    try:
        original_value = settings_manager.get_setting('late_threshold_minutes')
        settings_manager.update_setting('late_threshold_minutes', '20')
        new_value = settings_manager.get_setting('late_threshold_minutes')
        
        if new_value == '20':
            print(f"   ✓ Setting updated successfully (15 -> 20)")
            # Restore original value
            settings_manager.update_setting('late_threshold_minutes', original_value)
            print(f"   ✓ Setting restored to original value")
        else:
            print(f"   ✗ Setting update failed")
            return False
    except Exception as e:
        print(f"   ✗ Failed to update setting: {e}")
        return False
    
    # Test 6: Test helper functions
    print("\n6. Testing helper functions...")
    try:
        from settings_helper import (
            get_late_threshold,
            get_grace_period,
            is_auto_mark_absent_enabled,
            get_session_timeout
        )
        
        late = get_late_threshold()
        grace = get_grace_period()
        auto_absent = is_auto_mark_absent_enabled()
        timeout = get_session_timeout()
        
        print(f"   ✓ get_late_threshold() = {late} minutes")
        print(f"   ✓ get_grace_period() = {grace} minutes")
        print(f"   ✓ is_auto_mark_absent_enabled() = {auto_absent}")
        print(f"   ✓ get_session_timeout() = {timeout} seconds")
    except Exception as e:
        print(f"   ✗ Failed to test helper functions: {e}")
        return False
    
    # Test 7: Check settings file
    print("\n7. Checking settings file...")
    settings_file = settings_manager.settings_file
    if os.path.exists(settings_file):
        file_size = os.path.getsize(settings_file)
        print(f"   ✓ Settings file exists: {settings_file}")
        print(f"   ✓ File size: {file_size} bytes")
    else:
        print(f"   ✗ Settings file not found: {settings_file}")
        return False
    
    print("\n" + "=" * 60)
    print("All tests passed! ✓")
    print("=" * 60)
    print("\nSettings system is working correctly!")
    print("\nYou can now:")
    print("  1. Start the application (python app.py)")
    print("  2. Login as admin")
    print("  3. Go to Settings page")
    print("  4. Configure and save settings")
    print()
    
    return True

if __name__ == '__main__':
    success = test_settings_system()
    sys.exit(0 if success else 1)

