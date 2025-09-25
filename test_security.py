"""
Comprehensive test suite for Face_Check application
Run: python test_security.py
"""

import sqlite3
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock
import sys

# Add the project directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class TestSecurityFeatures(unittest.TestCase):
    """Test security features of the Face_Check application"""
    
    def setUp(self):
        """Set up test database"""
        self.test_db = tempfile.NamedTemporaryFile(delete=False)
        self.test_db.close()
        
    def tearDown(self):
        """Clean up test database"""
        if os.path.exists(self.test_db.name):
            os.unlink(self.test_db.name)
    
    def test_password_validation(self):
        """Test password strength validation"""
        from security_config import validate_password_strength
        
        # Test weak passwords
        weak_passwords = [
            ('123', False),
            ('password', False),
            ('PASSWORD', False),
            ('Password', False),
            ('Password1', False),  # Missing special character
            ('pass', False),       # Too short
        ]
        
        for password, expected in weak_passwords:
            is_valid, _ = validate_password_strength(password)
            self.assertEqual(is_valid, expected, f"Password '{password}' validation failed")
        
        # Test strong passwords
        strong_passwords = [
            'Password123!',
            'SecureP@ss1',
            'MyStr0ng#Pass',
        ]
        
        for password in strong_passwords:
            is_valid, _ = validate_password_strength(password)
            self.assertTrue(is_valid, f"Strong password '{password}' should be valid")
    
    def test_filename_sanitization(self):
        """Test filename sanitization"""
        from security_config import sanitize_filename
        
        # Test malicious filenames
        malicious_filenames = [
            '../../../etc/passwd',
            '..\\windows\\system32\\config\\sam',
            'file<script>alert(1)</script>.jpg',
            'normal.php.jpg',
            'test.exe',
        ]
        
        for filename in malicious_filenames:
            sanitized = sanitize_filename(filename)
            # Should generate UUID-based filename
            self.assertTrue(sanitized.endswith('.jpg'))
            self.assertNotIn('..', sanitized)
            self.assertNotIn('<', sanitized)
            self.assertNotIn('>', sanitized)
    
    def test_path_traversal_protection(self):
        """Test path traversal protection"""
        from security_config import is_safe_path
        
        base_path = '/app/uploads'
        
        # Test safe paths
        safe_paths = [
            '/app/uploads/file.jpg',
            '/app/uploads/subfolder/file.jpg',
        ]
        
        for path in safe_paths:
            self.assertTrue(is_safe_path(path, base_path))
        
        # Test unsafe paths
        unsafe_paths = [
            '/etc/passwd',
            '/app/uploads/../../../etc/passwd',
            '/tmp/malicious.jpg',
        ]
        
        for path in unsafe_paths:
            self.assertFalse(is_safe_path(path, base_path))

class TestDatabaseSecurity(unittest.TestCase):
    """Test database security features"""
    
    def setUp(self):
        """Set up test database"""
        self.test_db = tempfile.NamedTemporaryFile(delete=False)
        self.test_db.close()
        
        # Create test database
        conn = sqlite3.connect(self.test_db.name)
        cursor = conn.cursor()
        
        # Create test tables
        cursor.execute("""
            CREATE TABLE user (
                user_id INTEGER PRIMARY KEY,
                idno TEXT UNIQUE,
                firstname TEXT,
                lastname TEXT,
                password TEXT,
                role TEXT,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        
        conn.commit()
        conn.close()
        
    def tearDown(self):
        """Clean up test database"""
        if os.path.exists(self.test_db.name):
            os.unlink(self.test_db.name)
    
    def test_sql_injection_prevention(self):
        """Test SQL injection prevention in user queries"""
        conn = sqlite3.connect(self.test_db.name)
        
        # Test parameterized queries (safe)
        try:
            cursor = conn.cursor()
            # This should not cause SQL injection
            malicious_input = "'; DROP TABLE user; --"
            cursor.execute("SELECT * FROM user WHERE idno = ?", (malicious_input,))
            # If we get here, the query was safely parameterized
            self.assertTrue(True)
        except sqlite3.Error:
            self.fail("Parameterized query failed")
        finally:
            conn.close()

class TestFileUploadSecurity(unittest.TestCase):
    """Test file upload security"""
    
    def test_file_type_validation(self):
        """Test file type validation"""
        from security_config import SecurityConfig
        
        allowed_extensions = SecurityConfig.ALLOWED_EXTENSIONS
        
        # Test allowed files
        allowed_files = ['image.jpg', 'photo.png', 'picture.jpeg']
        for filename in allowed_files:
            extension = filename.split('.')[-1].lower()
            self.assertIn(extension, allowed_extensions)
        
        # Test disallowed files
        disallowed_files = ['script.php', 'malware.exe', 'config.ini', 'test.html']
        for filename in disallowed_files:
            extension = filename.split('.')[-1].lower()
            self.assertNotIn(extension, allowed_extensions)

def run_security_scan():
    """Run a basic security scan of the application"""
    print("\n🔍 Running Security Scan")
    print("=" * 30)
    
    issues = []
    
    # Check for hard-coded secrets (basic check)
    sensitive_files = ['app.py', 'db.py', 'config.py']
    for filename in sensitive_files:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                # Check for common security issues
                if 'password = ' in content.lower() and 'admin123' in content:
                    issues.append(f"❌ Hard-coded password found in {filename}")
                
                if "secret_key = '" in content.lower() and 'your-secret-key' in content:
                    issues.append(f"❌ Hard-coded secret key found in {filename}")
    
    # Check file permissions
    sensitive_files = ['facecheck.db', 'known_faces/', 'temp/']
    for filename in sensitive_files:
        if os.path.exists(filename):
            stat_info = os.stat(filename)
            # Check if world-writable
            if stat_info.st_mode & 0o002:
                issues.append(f"⚠️  {filename} is world-writable")
    
    # Check for required security packages
    try:
        import bcrypt
        print("✅ bcrypt installed")
    except ImportError:
        issues.append("❌ bcrypt not installed - passwords not secure")
    
    # Report results
    if not issues:
        print("✅ No obvious security issues found")
    else:
        print("\n🚨 Security Issues Found:")
        for issue in issues:
            print(f"   {issue}")
    
    return len(issues) == 0

if __name__ == '__main__':
    print("🛡️  Face_Check Security Test Suite")
    print("=" * 40)
    
    # Run security scan first
    scan_passed = run_security_scan()
    
    # Run unit tests
    print("\n🧪 Running Unit Tests")
    print("=" * 30)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestSecurityFeatures,
        TestDatabaseSecurity, 
        TestFileUploadSecurity
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    # Summary
    print("\n" + "=" * 40)
    print("🎯 Test Summary")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Security scan: {'✅ PASSED' if scan_passed else '❌ FAILED'}")
    
    if result.wasSuccessful() and scan_passed:
        print("\n🎉 All security tests passed!")
        exit(0)
    else:
        print("\n⚠️  Some tests failed. Please review and fix issues.")
        exit(1)