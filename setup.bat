@echo off
rem Face_Check Quick Setup Script for Windows
rem Run this script to set up Face_Check automatically

echo 🚀 Face_Check Automatic Setup
echo ==========================================

rem Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python is not installed or not in PATH. Please install Python 3.7+ first.
    pause
    exit /b 1
)

echo ✅ Python detected

rem Create virtual environment
echo 📦 Creating virtual environment...
python -m venv .venv

rem Activate virtual environment
echo 🔧 Activating virtual environment...
call .venv\Scripts\activate.bat

rem Upgrade pip
echo ⬆️ Upgrading pip...
python -m pip install --upgrade pip

rem Install core dependencies
echo 📋 Installing core dependencies...
pip install -r requirements.txt

rem Install face recognition dependencies
echo 🧠 Installing face recognition dependencies...
echo    This may take several minutes...

rem Try different installation strategies
pip install dlib-bin
if errorlevel 1 (
    echo ⚠️ dlib-bin installation failed, trying cmake...
    pip install cmake
    pip install dlib
    if errorlevel 1 (
        echo ❌ dlib installation failed. Face recognition may not work.
    )
) else (
    echo ✅ dlib-bin installed successfully
)

rem Install face_recognition
pip install face-recognition
if errorlevel 1 (
    echo ⚠️ face-recognition installation failed, trying without dependencies...
    pip install --no-deps face-recognition face-recognition-models
)

rem Install setuptools for compatibility
pip install setuptools

rem Initialize database
echo 🗄️ Initializing database...
python db.py

rem Create necessary directories
echo 📁 Creating directories...
if not exist known_faces mkdir known_faces
if not exist temp mkdir temp
if not exist face_features mkdir face_features
if not exist attendance mkdir attendance
if not exist logs mkdir logs

rem Run system check
echo 🔍 Running system check...
python -c "import warnings; warnings.filterwarnings('ignore'); import flask, bcrypt, cv2, numpy, face_recognition, sqlite3; print('✅ All core libraries available'); import sqlite3; conn = sqlite3.connect('facecheck.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM user;'); user_count = cursor.fetchone()[0]; conn.close(); print(f'✅ Database initialized with {user_count} users')"

echo.
echo 🎉 Setup Complete!
echo ==========================================
echo ✅ Face_Check is ready to use!
echo.
echo 🚀 To start the application:
echo    python start_app.py
echo.
echo 🌍 Then open your browser to:
echo    http://localhost:5000
echo.
echo 🔐 Default login credentials:
echo    Username: admin
echo    Password: admin123
echo    ⚠️ IMPORTANT: Change this password after first login!
echo.
echo 📚 For more information, see:
echo    - README.md - Complete setup and usage guide
echo    - DATABASE_GUIDE.md - Database management
echo    - DEPLOYMENT_GUIDE.md - Production deployment
echo.
echo 🔍 To check system status anytime:
echo    python status_report.py
echo.
echo ==========================================
pause