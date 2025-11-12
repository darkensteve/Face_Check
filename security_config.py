"""
Security configuration and utilities for Face_Check application
"""
import os
import secrets
from datetime import timedelta

class SecurityConfig:
    """Security configuration class"""
    
    # Secret key for sessions and CSRF
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    
    # Session security
    SESSION_COOKIE_SECURE = os.environ.get('HTTPS', 'false').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.environ.get('SESSION_TIMEOUT_HOURS', '1')))
    
    # Rate limiting
    MAX_LOGIN_ATTEMPTS = int(os.environ.get('MAX_LOGIN_ATTEMPTS', '5'))
    LOGIN_RATE_LIMIT_MINUTES = int(os.environ.get('LOGIN_RATE_LIMIT_MINUTES', '15'))
    
    # File upload security
    MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', '5242880'))  # 5MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', 'known_faces')
    TEMP_FOLDER = os.environ.get('TEMP_FOLDER', 'temp')
    
    # Face recognition settings
    MATCH_TOLERANCE = float(os.environ.get('MATCH_TOLERANCE', '0.62'))
    
    # Database settings
    DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///facecheck.db')

def validate_password_strength(password):
    """
    Validate password strength based on admin settings
    Returns: (is_valid, message)
    
    Note: Passwords are automatically set to user ID numbers,
    so we only check minimum length requirement.
    """
    try:
        from settings_helper import get_password_min_length
        
        # Get minimum length from admin configuration
        min_length = get_password_min_length()
        
    except Exception as e:
        # Fallback to default if settings not available
        print(f"Warning: Could not load password settings, using default: {e}")
        min_length = 6
    
    # Check minimum length only (since passwords are ID numbers)
    if len(password) < min_length:
        return False, f"Password must be at least {min_length} characters long"
    
    return True, "Password meets requirements"

def sanitize_filename(filename):
    """
    Sanitize filename to prevent path traversal attacks
    """
    import re
    import uuid
    
    # Get file extension
    if '.' in filename:
        extension = filename.rsplit('.', 1)[1].lower()
        if extension not in SecurityConfig.ALLOWED_EXTENSIONS:
            extension = 'jpg'  # Default extension
    else:
        extension = 'jpg'
    
    # Generate secure filename
    secure_name = f"{uuid.uuid4().hex[:16]}.{extension}"
    return secure_name

def is_safe_path(path, base_path):
    """
    Check if a file path is safe (no directory traversal)
    """
    import os.path
    
    # Resolve paths to absolute paths
    base_path = os.path.abspath(base_path)
    path = os.path.abspath(path)
    
    # Check if the resolved path starts with the base path
    return path.startswith(base_path)