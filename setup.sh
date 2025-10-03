#!/bin/bash
# Face_Check Quick Setup Script
# Run this script to set up Face_Check automatically

echo "🚀 Face_Check Automatic Setup"
echo "=========================================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.7+ first."
    exit 1
fi

# Check Python version
python_version=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
required_version="3.7"
if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
    echo "❌ Python $required_version or higher required. Found: $python_version"
    exit 1
fi

echo "✅ Python $python_version detected"

# Create virtual environment
echo "📦 Creating virtual environment..."
python3 -m venv .venv

# Activate virtual environment
echo "🔧 Activating virtual environment..."
if [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    # Windows
    source .venv/Scripts/activate
else
    # Linux/macOS
    source .venv/bin/activate
fi

# Upgrade pip
echo "⬆️ Upgrading pip..."
python -m pip install --upgrade pip

# Install core dependencies
echo "📋 Installing core dependencies..."
pip install -r requirements.txt

# Install face recognition dependencies (with error handling)
echo "🧠 Installing face recognition dependencies..."
echo "   This may take several minutes..."

# Try different installation strategies
if pip install dlib-bin; then
    echo "✅ dlib-bin installed successfully"
else
    echo "⚠️ dlib-bin installation failed, trying cmake..."
    pip install cmake
    if pip install dlib; then
        echo "✅ dlib installed successfully"
    else
        echo "❌ dlib installation failed. Face recognition may not work."
    fi
fi

# Install face_recognition
if pip install face-recognition; then
    echo "✅ face-recognition installed successfully"
else
    echo "⚠️ face-recognition installation failed, trying without dependencies..."
    pip install --no-deps face-recognition face-recognition-models
fi

# Install setuptools for compatibility
pip install setuptools

# Initialize database
echo "🗄️ Initializing database..."
python db.py

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p known_faces temp face_features attendance logs

# Run system check
echo "🔍 Running system check..."
python -c "
import warnings
warnings.filterwarnings('ignore')

try:
    import flask, bcrypt, cv2, numpy, face_recognition, sqlite3
    print('✅ All core libraries available')
except ImportError as e:
    print(f'⚠️ Some libraries missing: {e}')

try:
    conn = sqlite3.connect('facecheck.db')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM user;')
    user_count = cursor.fetchone()[0]
    conn.close()
    print(f'✅ Database initialized with {user_count} users')
except Exception as e:
    print(f'❌ Database issue: {e}')
"

echo ""
echo "🎉 Setup Complete!"
echo "=========================================="
echo "✅ Face_Check is ready to use!"
echo ""
echo "🚀 To start the application:"
echo "   python start_app.py"
echo ""
echo "🌍 Then open your browser to:"
echo "   http://localhost:5000"
echo ""
echo "🔐 Default login credentials:"
echo "   Username: admin"
echo "   Password: admin123"
echo "   ⚠️ IMPORTANT: Change this password after first login!"
echo ""
echo "📚 For more information, see:"
echo "   - README.md - Complete setup and usage guide"
echo "   - DATABASE_GUIDE.md - Database management"
echo "   - DEPLOYMENT_GUIDE.md - Production deployment"
echo ""
echo "🔍 To check system status anytime:"
echo "   python status_report.py"
echo ""
echo "=========================================="