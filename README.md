# Face_Check - Face Recognition Attendance System

A secure, robust Flask-based face recognition attendance system with advanced features for educational institutions.

## 🚀 Quick Start

### Prerequisites

- **Python 3.7+** (tested with Python 3.13)
- **Windows/Linux/macOS** (installation instructions may vary)
- **Webcam/Camera** for face recognition
- **Git** (for cloning)

### Installation

1. **Clone the Repository**
   ```bash
   git clone https://github.com/darkensteve/Face_Check.git
   cd Face_Check
   ```

2. **Create Virtual Environment**
   ```bash
   python -m venv .venv
   
   # On Windows
   .venv\Scripts\activate
   
   # On Linux/macOS
   source .venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   # Core dependencies
   pip install -r requirements.txt
   
   # Face recognition dependencies (may take time)
   pip install dlib-bin
   pip install face-recognition
   pip install face_recognition_models
   pip install setuptools
   ```

   **Note for Windows users**: If you encounter CMake/dlib build errors:
   ```bash
   pip install cmake
   pip install dlib-bin  # Pre-compiled dlib
   pip install --no-deps face-recognition face-recognition-models
   pip install setuptools
   ```

4. **Initialize Database**
   ```bash
   python db.py
   ```

5. **Start the Application**
   ```bash
   python start_app.py
   ```

6. **Access the Application**
   - Open your browser to: `http://localhost:5000`
   - Default admin login: `admin` / `admin123`
   - **⚠️ IMPORTANT: Change the default password after first login!**

## 📋 Features

### ✅ Implemented
- **Secure Authentication**: bcrypt password hashing, session management
- **Face Recognition**: Advanced face recognition with fallback to OpenCV
- **User Management**: Multi-role system (Admin/Faculty/Student)
- **Class Management**: Create and manage classes with student enrollment
- **Attendance Tracking**: Face-based attendance with manual override
- **Event Scheduling**: Create and manage events with attendance tracking
- **Admin Dashboard**: Complete administrative controls
- **Security Features**: Rate limiting, input validation, SQL injection protection
- **File Upload Security**: Secure image upload with validation
- **Database Migration**: Automatic database updates and security patches

### 🔒 Security Features
- ✅ bcrypt password hashing
- ✅ Rate-limited login (5 attempts per minute)
- ✅ Session security with timeouts
- ✅ Input validation and sanitization
- ✅ SQL injection protection
- ✅ File upload validation
- ✅ CSRF protection
- ✅ Secure file handling

## 🗃️ Database Management

### Check Database Status
```bash
python status_report.py
```

### View Database Contents
```bash
python view_db.py
```

### Migrate Database (for updates)
```bash
python migrate_database.py
```

### Reset Database (⚠️ Destroys all data)
```bash
python recreate_database.py
```

### Create Sample Data (for testing)
```bash
python create_sample_accounts.py
```

## 🧪 Testing

### Security Tests
```bash
python test_security.py
```

### Face Recognition Tests
```bash
python face_recog_test.py
python face_detect_test.py
```

### Camera Tests
```bash
python camera_test.py
```

## 📱 Usage Guide

### Admin Functions
1. **Login** with admin credentials
2. **User Management**: Create faculty and student accounts
3. **Class Management**: Set up classes and enroll students
4. **Event Scheduling**: Create attendance events
5. **View Reports**: Check attendance statistics

### Faculty Functions
1. **Login** with faculty credentials
2. **View Classes**: See assigned classes and students
3. **Take Attendance**: Use face recognition or manual entry
4. **View Reports**: Check class attendance patterns

### Student Functions
1. **Login** with student credentials
2. **Register Face**: Set up face recognition profile
3. **View Attendance**: Check personal attendance records
4. **View Schedule**: See upcoming classes and events

## 🛠️ Configuration

### Environment Variables (Optional)
Create `.env` file:
```env
SECRET_KEY=your-secret-key-here
FLASK_ENV=development
DATABASE_URL=sqlite:///facecheck.db
MAX_UPLOAD_SIZE=16777216
```

### Camera Configuration
The system automatically detects available cameras. To specify a camera:
- Edit `app.py` and modify `camera_index = 0` to your camera number

### Face Recognition Settings
- **Recognition Threshold**: Adjust in `app.py` → `face_distance < 0.6`
- **Detection Model**: Uses HOG by default, change to CNN for better accuracy (slower)

## 🚀 Production Deployment

### Security Checklist
- [ ] Change default admin password
- [ ] Set strong SECRET_KEY
- [ ] Use HTTPS in production
- [ ] Configure firewall
- [ ] Regular database backups
- [ ] Update dependencies regularly

### Production Server
Use a production WSGI server instead of Flask's development server:

```bash
# Using Gunicorn
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Using uWSGI
pip install uwsgi
uwsgi --http :5000 --wsgi-file app.py --callable app
```

## 📁 File Structure

```
Face_Check/
├── app.py                    # Main Flask application
├── db.py                     # Database initialization
├── start_app.py              # Enhanced startup script
├── status_report.py          # System diagnostics
├── requirements.txt          # Python dependencies
├── README.md                 # This file
│
├── security/
│   ├── test_security.py      # Security tests
│   ├── migrate_database.py   # Database migrations
│   └── security_config.py    # Security configurations
│
├── face_recognition/
│   ├── opencv_face_detector.py  # OpenCV fallback
│   ├── register_face.py         # Face registration utility
│   ├── face_recog_test.py      # Face recognition tests
│   └── camera_test.py          # Camera testing
│
├── templates/                # HTML templates
│   ├── login.html
│   ├── dashboard.html
│   ├── admin_*.html
│   └── ...
│
├── attendance/               # Attendance records
├── known_faces/             # Stored face encodings
├── face_features/           # Face feature data
└── temp/                    # Temporary files
```

## 🔧 Troubleshooting

### Common Issues

1. **Face recognition not working**
   - Ensure camera permissions are granted
   - Check camera index in `camera_test.py`
   - Verify face_recognition installation: `python -c "import face_recognition; print('OK')"`

2. **Database errors**
   - Run `python migrate_database.py`
   - Check database permissions
   - Verify SQLite is accessible

3. **Import errors**
   - Activate virtual environment
   - Reinstall dependencies: `pip install -r requirements.txt`
   - Check Python version compatibility

4. **Performance issues**
   - Adjust face recognition threshold
   - Use HOG instead of CNN model
   - Optimize image sizes

5. **pkg_resources warning**
   - This is cosmetic and doesn't affect functionality
   - Consider pinning setuptools version if needed

### Dependency Issues (Windows)

If you encounter CMake or dlib compilation errors:

```bash
# Uninstall problematic packages
pip uninstall cmake dlib face-recognition -y

# Install pre-compiled versions
pip install cmake
pip install dlib-bin
pip install --no-deps face-recognition face-recognition-models
pip install setuptools
```

### Getting Help

1. **Check Status**: Run `python status_report.py`
2. **View Logs**: Check console output for errors
3. **Test Components**: Use individual test scripts
4. **Database Issues**: Use `view_db.py` to inspect data

## 🔄 Updates and Maintenance

### Regular Maintenance
- **Weekly**: Check `status_report.py` for issues
- **Monthly**: Update dependencies with `pip list --outdated`
- **Quarterly**: Review security logs and update passwords

### Backup Strategy
```bash
# Backup database
cp facecheck.db facecheck_backup_$(date +%Y%m%d).db

# Backup face data
tar -czf face_data_backup_$(date +%Y%m%d).tar.gz known_faces/ face_features/
```

## 📜 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests: `python test_security.py`
5. Submit a pull request

## 📞 Support

For issues and questions:
- Check the troubleshooting section above
- Review the status report: `python status_report.py`
- Check existing GitHub issues
- Create a new issue with system information

---

**⚠️ Security Notice**: Always change default passwords and keep dependencies updated in production environments.