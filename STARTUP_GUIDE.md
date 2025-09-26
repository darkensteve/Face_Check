# 🚀 Face_Check Startup Guide & Troubleshooting

## ✅ **Current Status:**
- **OpenCV**: opencv-contrib-python 4.9.0.80 ✅ (Full OpenCV with extra features)
- **Flask**: 3.1.2 ✅
- **Face Recognition**: Working ✅
- **Database**: Initialized ✅
- **Application**: Successfully tested and running ✅

---

## 🚀 **How to Start Face_Check**

### **Method 1: Quick Start (Recommended)**
```bash
# Navigate to project directory
cd "c:\Users\chdev\Documents\Github\Capstone"

# Activate virtual environment
source .venv/Scripts/activate

# Start the application
python start_app.py
```

### **Method 2: Direct Python Path**
```bash
# Navigate to project directory
cd "c:\Users\chdev\Documents\Github\Capstone"

# Use virtual environment Python directly
.venv/Scripts/python.exe start_app.py
```

### **Method 3: Windows Command Prompt**
```cmd
cd "c:\Users\chdev\Documents\Github\Capstone"
.venv\Scripts\activate
python start_app.py
```

### **Method 4: VS Code Integrated Terminal**
1. Open VS Code in the project folder
2. Open integrated terminal (`Ctrl+``)
3. Ensure virtual environment is selected
4. Run: `python start_app.py`

---

## 🔧 **Troubleshooting Common Issues**

### **Problem 1: "ModuleNotFoundError: No module named 'flask'"**

**Cause**: VS Code is using system Python instead of virtual environment

**Solution A - VS Code Python Interpreter:**
1. Press `Ctrl+Shift+P`
2. Type: `Python: Select Interpreter`
3. Choose: `C:\Users\chdev\Documents\Github\Capstone\.venv\Scripts\python.exe`

**Solution B - Activate Virtual Environment:**
```bash
# In terminal
cd "c:\Users\chdev\Documents\Github\Capstone"
source .venv/Scripts/activate
python start_app.py
```

**Solution C - Reinstall Dependencies:**
```bash
cd "c:\Users\chdev\Documents\Github\Capstone"
source .venv/Scripts/activate
pip install -r requirements.txt
```

### **Problem 2: "bash: ource: command not found"**

**Cause**: Typo in command - missing 's' in 'source'

**Solution:**
```bash
# Correct command
source .venv/Scripts/activate

# Alternative for Windows
.venv/Scripts/activate
```

### **Problem 3: Virtual Environment Not Activating**

**Windows Git Bash:**
```bash
source .venv/Scripts/activate
```

**Windows Command Prompt:**
```cmd
.venv\Scripts\activate.bat
```

**Windows PowerShell:**
```powershell
.venv\Scripts\Activate.ps1
```

### **Problem 4: Database Errors**

**Solution:**
```bash
cd "c:\Users\chdev\Documents\Github\Capstone"
source .venv/Scripts/activate
python db.py  # Reinitialize database
```

### **Problem 5: Permission Errors**

**Solution:**
```bash
# Check file permissions
ls -la facecheck.db

# Fix permissions (if needed)
chmod 664 facecheck.db
```

### **Problem 6: Port Already in Use**

**Solution:**
```bash
# Find process using port 5000
netstat -ano | findstr :5000

# Kill the process (replace PID)
taskkill /PID <process_id> /F

# Or use different port
python start_app.py --port 8000
```

---

## 🔍 **Verification Commands**

### **Check Virtual Environment:**
```bash
cd "c:\Users\chdev\Documents\Github\Capstone"
source .venv/Scripts/activate
which python
# Should show: /c/Users/chdev/Documents/Github/Capstone/.venv/Scripts/python
```

### **Check Dependencies:**
```bash
source .venv/Scripts/activate
python -c "
import flask, bcrypt, cv2, numpy, face_recognition, sqlite3
print('✅ All dependencies working!')
print('Flask:', flask.__version__)
print('OpenCV:', cv2.__version__)
print('NumPy:', numpy.__version__)
"
```

### **Check Database:**
```bash
source .venv/Scripts/activate
python -c "
import sqlite3
conn = sqlite3.connect('facecheck.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM user;')
print('✅ Database users:', cursor.fetchone()[0])
conn.close()
"
```

### **Full System Check:**
```bash
source .venv/Scripts/activate
python status_report.py
```

---

## 🌍 **Access the Application**

Once started successfully, you'll see:
```
🎉 Face_Check is starting...
📝 Features available:
   ✅ Secure password hashing
   ✅ Advanced face recognition

🌍 Application will be available at: http://localhost:5000
🔐 Default admin login: admin / admin123
```

**Access URLs:**
- **Main**: http://localhost:5000
- **Alternative**: http://127.0.0.1:5000
- **Network**: http://192.168.1.8:5000 (varies by network)

---

## 🔐 **Default Login Credentials**

| Role | Username | Password |
|------|----------|----------|
| Admin | admin | admin123 |
| Student | STU001 | password123 |
| Faculty | FAC001 | password123 |

**⚠️ IMPORTANT**: Change default passwords after first login!

---

## 📋 **Pre-Start Checklist**

Before starting, ensure:
- [ ] Virtual environment exists (`.venv` folder)
- [ ] Dependencies installed (`pip list` shows Flask, OpenCV, etc.)
- [ ] Database exists (`facecheck.db` file)
- [ ] Required directories exist (`known_faces`, `temp`, `face_features`)
- [ ] No other process using port 5000

---

## 🛠️ **Quick Setup Script**

If you encounter multiple issues, run the automated setup:

**Windows:**
```cmd
setup.bat
```

**Linux/macOS:**
```bash
bash setup.sh
```

---

## 📊 **System Requirements Verification**

### **Python Version:**
```bash
python --version
# Should be Python 3.7 or higher
```

### **Available Memory:**
```bash
# Check available memory (face recognition can be memory intensive)
python -c "
import psutil
print(f'Available RAM: {psutil.virtual_memory().available / (1024**3):.1f} GB')
print(f'Total RAM: {psutil.virtual_memory().total / (1024**3):.1f} GB')
"
```

### **Camera Access (if using face recognition):**
```bash
source .venv/Scripts/activate
python camera_test.py
```

---

## 🔄 **Alternative Startup Methods**

### **Using Gunicorn (Production):**
```bash
source .venv/Scripts/activate
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### **Using Flask Development Server:**
```bash
source .venv/Scripts/activate
export FLASK_APP=app.py
export FLASK_ENV=development
flask run
```

### **Background Process:**
```bash
source .venv/Scripts/activate
nohup python start_app.py > app.log 2>&1 &
```

---

## 📞 **Getting Help**

### **Diagnostic Commands:**
```bash
# System status
python status_report.py

# Database inspection
python view_db.py

# Security tests
python test_security.py

# View recent logs
tail -f logs/app.log
```

### **Common Error Patterns:**

1. **Import Errors** → Check Python interpreter
2. **Database Errors** → Run `python db.py`
3. **Port Conflicts** → Use different port or kill process
4. **Permission Errors** → Check file permissions
5. **Memory Issues** → Check available RAM
6. **Camera Issues** → Test with `python camera_test.py`

---

## ✅ **Success Indicators**

When everything is working correctly, you should see:
- ✅ All startup checks passing
- ✅ Flask development server running
- ✅ No import errors
- ✅ Database connection successful
- ✅ Web interface accessible at http://localhost:5000
- ✅ Login page loads properly
- ✅ Face recognition features working

---

**🎉 Your Face_Check application is ready to use!**

For additional help, refer to:
- `README.md` - Complete documentation
- `DATABASE_GUIDE.md` - Database management
- `DEPLOYMENT_GUIDE.md` - Production deployment