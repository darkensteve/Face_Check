"""
Face_Check Application Startup Script
Run this script to start the Face_Check application with proper error handling
"""

import sys
import os
import warnings
from pathlib import Path

# Suppress known deprecation warning from face_recognition_models
warnings.filterwarnings('ignore', category=UserWarning, module='face_recognition_models')

def check_requirements():
    """Check if all requirements are met"""
    issues = []
    
    # Check Python version
    if sys.version_info < (3, 7):
        issues.append("Python 3.7 or higher is required")
    
    # Check required packages
    try:
        import flask # type: ignore
        print("✅ Flask available")
    except ImportError:
        issues.append("Flask not installed: pip install flask")
    
    try:
        import bcrypt # type: ignore
        print("✅ bcrypt available - passwords will be secure")
    except ImportError:
        print("⚠️ bcrypt not available - passwords will be insecure")
        print("   Install with: pip install bcrypt")
    
    try:
        import cv2 # type: ignore
        print("✅ OpenCV available - basic face detection will work")
    except ImportError:
        issues.append("OpenCV not installed: pip install opencv-contrib-python")
    
    try:
        import face_recognition # type: ignore
        print("✅ face_recognition available - full face recognition will work")
    except ImportError:
        print("⚠️ face_recognition not available - using OpenCV fallback")
        print("   For full functionality: pip install face-recognition")
    
    # Check database
    if not Path("facecheck.db").exists():
        print("⚠️ Database not found - will be created on first run")
    else:
        print("✅ Database found")
    
    return issues

def create_directories():
    """Create required directories"""
    directories = ["known_faces", "temp", "face_features"]
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
        print(f"✅ Directory created/verified: {directory}")

def main():
    print("🚀 Face_Check Application Startup")
    print("=" * 40)
    
    # Check requirements
    issues = check_requirements()
    
    if issues:
        print("\n❌ Cannot start application due to missing requirements:")
        for issue in issues:
            print(f"   - {issue}")
        print("\nPlease install missing packages and try again.")
        return False
    
    # Create directories
    print("\n📁 Setting up directories...")
    create_directories()
    
    # Import and start the application
    try:
        print("\n🌐 Starting Flask application...")
        from app import app
        
        print("✅ Application loaded successfully!")
        print("\n" + "=" * 40)
        print("🎉 Face_Check is starting...")
        print("📝 Features available:")
        
        # Import to check features
        import app as app_module
        
        if app_module.BCRYPT_AVAILABLE:
            print("   ✅ Secure password hashing")
        else:
            print("   ⚠️ Basic password storage (install bcrypt for security)")
            
        if app_module.FACE_RECOGNITION_AVAILABLE:
            print("   ✅ Advanced face recognition")
        else:
            print("   ⚠️ Basic face detection (install face-recognition for better accuracy)")
        
        print("\n🌍 Application will be available at: http://localhost:5000")
        print("🔐 Default admin login: admin / admin123")
        print("⚠️ IMPORTANT: Change the default admin password after login!")
        print("\n" + "=" * 40)
        
        # Start the application
        app.run(debug=True, host='0.0.0.0', port=5000)
        
    except Exception as e:
        print(f"\n❌ Failed to start application: {e}")
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)