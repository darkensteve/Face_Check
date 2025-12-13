from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from datetime import datetime, timedelta, date
import os
import time
import secrets
import warnings
from pathlib import Path

# Suppress known deprecation warning from face_recognition_models
warnings.filterwarnings('ignore', category=UserWarning, module='face_recognition_models')

# Check for required packages
try:
    import bcrypt 
    BCRYPT_AVAILABLE = True
except ImportError:
    print("Warning: bcrypt not available. Passwords will not be secure!")
    BCRYPT_AVAILABLE = False

try:
    import cv2 
    import numpy as np 
    import face_recognition 
    FACE_RECOGNITION_AVAILABLE = True
    print("Face recognition libraries loaded successfully")
except ImportError as e:
    print(f"Face recognition not available: {e}")
    print("Install with: pip install face-recognition opencv-contrib-python")
    FACE_RECOGNITION_AVAILABLE = False

# Anti-spoofing detector (guarded import so development still works)
try:
    from anti_spoofing import anti_spoofing_detector
    ANTI_SPOOFING_AVAILABLE = True
except ImportError as e:
    print(f"Anti-spoofing not available: {e}")
    ANTI_SPOOFING_AVAILABLE = False

# Import settings manager
from config_settings import settings_manager

# Import notification system
try:
    from notification_system import (
        get_user_notifications, 
        get_unread_count, 
        mark_notification_read, 
        mark_all_read,
        auto_mark_absent,
        check_and_notify_absences,
        convert_lates_to_absent,
        create_notification
    )
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    print("Warning: Notification system not available")
    NOTIFICATIONS_AVAILABLE = False

app = Flask(__name__)
# Generate secure secret key from environment or create new one
app.secret_key = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

# Get session timeout from settings (with fallback to default)
try:
    from settings_helper import get_session_timeout
    session_timeout_seconds = get_session_timeout()
except:
    session_timeout_seconds = 7200  # Fallback to 2 hours

# Session configuration for security
app.config.update(
    SESSION_COOKIE_SECURE=False,  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=session_timeout_seconds,  # Uses admin setting
    SESSION_REFRESH_EACH_REQUEST=True  # Refresh session on each request
)

# Rate limiting for login attempts
login_attempts = {}

def is_rate_limited(ip_address, max_attempts=None, window_minutes=None):
    """Simple rate limiting for login attempts - uses admin settings"""
    try:
        from settings_helper import get_max_login_attempts, get_lockout_duration
        
        # Get settings from admin configuration
        if max_attempts is None:
            max_attempts = get_max_login_attempts()
        if window_minutes is None:
            window_minutes = get_lockout_duration()
    except Exception as e:
        # Fallback to defaults if settings not available
        print(f"Warning: Could not load security settings, using defaults: {e}")
        if max_attempts is None:
            max_attempts = 5
        if window_minutes is None:
            window_minutes = 15
    
    current_time = time.time()
    window_seconds = window_minutes * 60
    
    if ip_address not in login_attempts:
        login_attempts[ip_address] = []
    
    # Clean old attempts outside the window
    login_attempts[ip_address] = [
        attempt_time for attempt_time in login_attempts[ip_address]
        if current_time - attempt_time < window_seconds
    ]
    
    # Check if over limit
    if len(login_attempts[ip_address]) >= max_attempts:
        return True
    
    return False

def record_login_attempt(ip_address):
    """Record a failed login attempt"""
    if ip_address not in login_attempts:
        login_attempts[ip_address] = []
    login_attempts[ip_address].append(time.time())


def require_recent_live_check(person_id, attendance_type, class_id=None, event_id=None, max_age_seconds=20):
    """Ensure a recent anti-spoofing pass exists for this person/target before marking attendance."""
    live_check = session.get('last_live_check')
    if not live_check:
        return False, "Live face verification is required before marking attendance."
    if not live_check.get('is_live'):
        return False, "Latest liveness check failed. Please retry with a live face."
    if attendance_type != live_check.get('attendance_type'):
        return False, "Liveness check type mismatch. Please re-verify for this flow."

    if attendance_type == 'class':
        if str(live_check.get('class_id')) != str(class_id) or str(live_check.get('person_id')) != str(person_id):
            return False, "Liveness check must be done for the same student and class."
    else:
        if str(live_check.get('event_id')) != str(event_id) or str(live_check.get('person_id')) != str(person_id):
            return False, "Liveness check must be done for this faculty and event."

    ts = live_check.get('timestamp')
    if not ts or time.time() - ts > max_age_seconds:
        return False, "Liveness check expired. Please look at the camera again."

    return True, ""

# Database connection with better error handling
def get_db_connection():
    """Get database connection with error handling and timeout"""
    try:
        conn = sqlite3.connect('facecheck.db', timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable foreign key constraints
        conn.execute('PRAGMA foreign_keys = ON')
        # Ensure expected schema exists (idempotent)
        try:
            cur = conn.cursor()
            cur.execute("PRAGMA table_info(faculty)")
            columns = [row[1] for row in cur.fetchall()]
            if 'attendance_image' not in columns:
                cur.execute("ALTER TABLE faculty ADD COLUMN attendance_image VARCHAR(255)")
                conn.commit()
        except Exception:
            # Ignore if PRAGMA/ALTER not applicable; app may still function without this column
            pass
        return conn
    except sqlite3.Error as e:
        print(f"Database connection error: {e}")
        raise


# Helper to safely format database datetime values which may be stored/returned
# as strings (most common) or as datetime objects. Prevents AttributeError when
# code calls .strftime on a string.
def safe_strftime(value, fmt):
    from datetime import datetime as _dt
    if not value:
        return ''
    # If it's already a datetime object
    if isinstance(value, _dt):
        return value.strftime(fmt)
    # If it's a string, try common formats
    if isinstance(value, str):
        for f in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                parsed = _dt.strptime(value, f)
                return parsed.strftime(fmt)
            except Exception:
                continue
        # Fallback: return the raw string when parsing fails
        return value
    # Unknown type: convert to str
    return str(value)


def row_get(row, key, default=None):
    """Safely access fields from sqlite3.Row objects."""
    if row is None:
        return default
    try:
        if key in row.keys():
            return row[key]
    except AttributeError:
        return getattr(row, key, default)
    return default

# Authentication functions
def hash_password(password):
    """Hash password using bcrypt for secure storage"""
    if BCRYPT_AVAILABLE:
        import bcrypt 
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    else:
        # Fallback: NOT SECURE - only for development
        print("WARNING: Using insecure password storage!")
        return f"INSECURE_{password}"

def verify_password(stored_hash, password):
    """Verify password against stored hash"""
    if BCRYPT_AVAILABLE and not stored_hash.startswith('INSECURE_'):
        import bcrypt 
        try:
            return bcrypt.checkpw(password.encode('utf-8'), stored_hash.encode('utf-8'))
        except ValueError:
            # Handle legacy passwords
            return stored_hash == password
    else:
        # Fallback for insecure storage or legacy passwords
        return stored_hash == password or stored_hash == f"INSECURE_{password}"

@app.route('/profile/change-password', methods=['GET', 'POST'])
def change_password():
    """Allow logged-in users (student/faculty/admin) to change their own password."""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    
    if request.method == 'POST':
        # Check if this is an AJAX request
        content_type = request.headers.get('Content-Type', '')
        is_ajax = 'application/json' in content_type or request.is_json
        
        try:
            if is_ajax:
                data = request.get_json() or {}
                current_password = data.get('current_password', '')
                new_password = data.get('new_password', '')
                confirm_password = data.get('confirm_password', '')
            else:
                current_password = request.form.get('current_password', '')
                new_password = request.form.get('new_password', '')
                confirm_password = request.form.get('confirm_password', '')
        except Exception as e:
            print(f"Error parsing request data: {e}")
            if is_ajax:
                return jsonify({'success': False, 'message': 'Invalid request data. Please try again.'}), 400
            flash('Invalid request data. Please try again.', 'error')
            return redirect(url_for('change_password'))
        
        if not current_password or not new_password or not confirm_password:
            if is_ajax:
                return jsonify({'success': False, 'message': 'All password fields are required.'}), 400
            flash('All password fields are required.', 'error')
            return redirect(url_for('change_password'))
        
        if new_password != confirm_password:
            if is_ajax:
                return jsonify({'success': False, 'message': 'New password and confirmation do not match.'}), 400
            flash('New password and confirmation do not match.', 'error')
            return redirect(url_for('change_password'))
        
        conn = get_db_connection()
        user = conn.execute('SELECT password, idno FROM user WHERE user_id = ?', (user_id,)).fetchone()
        if not user:
            conn.close()
            if is_ajax:
                return jsonify({'success': False, 'message': 'User account not found.'}), 404
            flash('User account not found.', 'error')
            return redirect(url_for('change_password'))
        
        stored_hash = user['password']
        if not verify_password(stored_hash, current_password):
            conn.close()
            if is_ajax:
                return jsonify({'success': False, 'message': 'Current password is incorrect.'}), 400
            flash('Current password is incorrect.', 'error')
            return redirect(url_for('change_password'))
        
        # Validate new password strength using admin settings
        try:
            from security_config import validate_password_strength
            is_valid_password, password_message = validate_password_strength(new_password)
            if not is_valid_password:
                conn.close()
                if is_ajax:
                    return jsonify({'success': False, 'message': password_message}), 400
                flash(password_message, 'error')
                return redirect(url_for('change_password'))
        except Exception as e:
            print(f"Password strength validation error: {e}")
            conn.close()
            error_msg = f"Password validation error: {str(e)}"
            if is_ajax:
                return jsonify({'success': False, 'message': error_msg}), 500
            flash(error_msg, 'error')
            return redirect(url_for('change_password'))
        
        try:
            new_hash = hash_password(new_password)
            conn.execute('UPDATE user SET password = ? WHERE user_id = ?', (new_hash, user_id))
            conn.commit()
            conn.close()
        except Exception as e:
            conn.close()
            print(f"Error updating password: {e}")
            error_msg = f"Error updating password: {str(e)}"
            if is_ajax:
                return jsonify({'success': False, 'message': error_msg}), 500
            flash(error_msg, 'error')
            return redirect(url_for('change_password'))
        
        if NOTIFICATIONS_AVAILABLE:
            try:
                msg = '🔐 Your account password was changed successfully.'
                create_notification(user_id, msg, 'password_changed')
            except Exception as notify_err:
                print(f"Warning: failed to create password changed notification: {notify_err}")
        
        success_message = 'Your password has been changed successfully.'
        
        # Return JSON for AJAX requests, otherwise redirect
        if is_ajax:
            return jsonify({
                'success': True,
                'message': success_message
            })
        
        flash(success_message, 'success')
        # Redirect back to appropriate dashboard
        role = session.get('role')
        if role == 'faculty':
            return redirect(url_for('faculty_profile'))
        elif role == 'student':
            return redirect(url_for('my_classes'))
        else:
            return redirect(url_for('dashboard'))
    
    # GET: render simple change-password form
    return render_template('change_password.html')

def validate_input(data, field_type='text', min_len=1, max_len=255):
    """Validate and sanitize input data"""
    if not data or not isinstance(data, str):
        return False, "Invalid input"

    data = data.strip()

    if len(data) < min_len or len(data) > max_len:
        return False, f"Length must be between {min_len} and {max_len} characters"

    if field_type == 'idno':
        # Allow existing IDs that may contain letters, numbers, hyphens, and underscores
        # (e.g., the built-in 'admin' account), while still blocking other symbols.
        if not data.replace('-', '').replace('_', '').isalnum():
            return False, "ID number can only contain letters, numbers, hyphens, and underscores"
    elif field_type == 'name':
        # Allow letters (including unicode/international characters), spaces, and common name characters
        # This supports names from different cultures and languages
        import re
        # Block only dangerous characters that could be used for injection attacks
        # Allow unicode letters, spaces, periods, hyphens, apostrophes, and other common name characters
        if re.search(r'[<>{}[\]\\|`~;$&]', data):
            return False, "Names cannot contain special characters like < > { } [ ] \\ | ` ~ ; $ &"
        # Ensure the name contains at least some letters (not just symbols/numbers)
        if not re.search(r'[a-zA-Z\u00C0-\u017F\u0180-\u024F\u1E00-\u1EFF]', data):
            return False, "Names must contain at least one letter"
    elif field_type == 'role':
        if data not in ['admin', 'faculty', 'student']:
            return False, "Invalid role"
    
    return True, data

def authenticate_user(idno, password):
    """Authenticate user with secure password checking"""
    # Validate inputs
    is_valid_id, idno = validate_input(idno, 'idno', 1, 20)
    if not is_valid_id:
        return None
    
    is_valid_pass, password = validate_input(password, 'text', 1, 255)
    if not is_valid_pass:
        return None
    
    conn = get_db_connection()
    try:
        user = conn.execute(
            'SELECT * FROM user WHERE idno = ? AND is_active = 1',
            (idno,)
        ).fetchone()
        
        if user and verify_password(user['password'], password):
            return user
    except Exception as e:
        print(f"Authentication error: {e}")
    finally:
        conn.close()
    
    return None

def get_user_info(user_id):
    conn = get_db_connection()
    user = conn.execute(
        'SELECT u.*, d.dept_name FROM user u LEFT JOIN department d ON u.dept_id = d.dept_id WHERE u.user_id = ?',
        (user_id,)
    ).fetchone()
    conn.close()
    return user

def _start_of_week(value: date) -> date:
    """Return Monday of the week for the provided date."""
    return value - timedelta(days=value.weekday())

def _subtract_months(value: date, months_back: int) -> date:
    """Return the first day of the month `months_back` months before `value`."""
    total_months = value.year * 12 + (value.month - 1) - months_back
    new_year = total_months // 12
    new_month = total_months % 12 + 1
    return date(new_year, new_month, 1)

def _build_date_filters(start_date=None, end_date=None):
    clauses = []
    params = []
    if start_date:
        clauses.append("DATE(attendance_date) >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("DATE(attendance_date) <= ?")
        params.append(end_date)
    if clauses:
        return "WHERE " + " AND ".join(clauses), params
    return "", params

def build_attendance_series(conn):
    """Generate daily/weekly/monthly/yearly attendance aggregates for charts."""
    today = datetime.now().date()

    # Daily (last 7 days)
    daily_start = today - timedelta(days=6)
    daily_rows = conn.execute("""
        SELECT DATE(attendance_date) AS bucket, COUNT(*) AS total
        FROM attendance
        WHERE DATE(attendance_date) BETWEEN ? AND ?
        GROUP BY DATE(attendance_date)
    """, (daily_start.isoformat(), today.isoformat())).fetchall()
    daily_map = {row['bucket']: row['total'] for row in daily_rows}
    daily_series = []
    for offset in range(6, -1, -1):
        current_day = today - timedelta(days=offset)
        key = current_day.strftime('%Y-%m-%d')
        daily_series.append({
            'label': current_day.strftime('%b %d'),
            'value': daily_map.get(key, 0)
        })

    # Weekly (last 8 weeks)
    current_week_start = _start_of_week(today)
    weekly_start = current_week_start - timedelta(weeks=7)
    weekly_rows = conn.execute("""
        SELECT strftime('%Y', attendance_date) || '-W' || strftime('%W', attendance_date) AS bucket,
               COUNT(*) AS total
        FROM attendance
        WHERE DATE(attendance_date) >= ?
        GROUP BY bucket
    """, (weekly_start.isoformat(),)).fetchall()
    weekly_map = {row['bucket']: row['total'] for row in weekly_rows}
    weekly_series = []
    for offset in range(7, -1, -1):
        week_start = current_week_start - timedelta(weeks=offset)
        bucket_key = f"{week_start.strftime('%Y')}-W{week_start.strftime('%W')}"
        week_number = week_start.isocalendar()[1]
        weekly_series.append({
            'label': f"Week {week_number}",
            'value': weekly_map.get(bucket_key, 0)
        })

    # Monthly (last 6 months)
    current_month_start = today.replace(day=1)
    monthly_rows = conn.execute("""
        SELECT strftime('%Y-%m', attendance_date) AS bucket,
               COUNT(*) AS total
        FROM attendance
        WHERE DATE(attendance_date) >= ?
        GROUP BY bucket
    """, (_subtract_months(current_month_start, 5).isoformat(),)).fetchall()
    monthly_map = {row['bucket']: row['total'] for row in monthly_rows}
    monthly_series = []
    for months_back in range(5, -1, -1):
        month_start = _subtract_months(current_month_start, months_back)
        key = month_start.strftime('%Y-%m')
        monthly_series.append({
            'label': month_start.strftime('%b %Y'),
            'value': monthly_map.get(key, 0)
        })

    # Yearly (last 5 years)
    start_year = today.year - 4
    yearly_rows = conn.execute("""
        SELECT strftime('%Y', attendance_date) AS bucket,
               COUNT(*) AS total
        FROM attendance
        WHERE DATE(attendance_date) >= ?
        GROUP BY bucket
    """, (date(start_year, 1, 1).isoformat(),)).fetchall()
    yearly_map = {row['bucket']: row['total'] for row in yearly_rows}
    yearly_series = []
    for year_value in range(start_year, today.year + 1):
        key = str(year_value)
        yearly_series.append({
            'label': key,
            'value': yearly_map.get(key, 0)
        })

    return {
        'daily': daily_series,
        'weekly': weekly_series,
        'monthly': monthly_series,
        'yearly': yearly_series
    }

def build_recent_chart_series(conn, start_date=None, end_date=None):
    where_clause, params = _build_date_filters(start_date, end_date)

    def fetch_series(query, extra_params=None, limit=None, order_desc=True):
        combined_params = list(params)
        if extra_params:
            combined_params.extend(extra_params)
        sql = query
        if limit:
            sql += f" LIMIT {limit}"
        rows = conn.execute(sql, combined_params).fetchall()
        data = [{'label': row['label'], 'value': row['total']} for row in rows]
        if order_desc:
            data.reverse()
        return data

    daily = fetch_series(f'''
        SELECT DATE(attendance_date) AS label, COUNT(*) AS total
        FROM attendance
        {where_clause}
        GROUP BY DATE(attendance_date)
        ORDER BY DATE(attendance_date) DESC
    ''', limit=14)

    weekly = fetch_series(f'''
        SELECT strftime('%Y', attendance_date) || '-W' || strftime('%W', attendance_date) AS label,
               COUNT(*) AS total
        FROM attendance
        {where_clause}
        GROUP BY label
        ORDER BY label DESC
    ''', limit=10)

    monthly = fetch_series(f'''
        SELECT strftime('%Y-%m', attendance_date) AS label,
               COUNT(*) AS total
        FROM attendance
        {where_clause}
        GROUP BY label
        ORDER BY label DESC
    ''', limit=12)

    yearly = fetch_series(f'''
        SELECT strftime('%Y', attendance_date) AS label,
               COUNT(*) AS total
        FROM attendance
        {where_clause}
        GROUP BY label
        ORDER BY label DESC
    ''', limit=5)

    return {
        'daily': daily,
        'weekly': weekly,
        'monthly': monthly,
        'yearly': yearly
    }

def get_dashboard_stats(start_date=None, end_date=None):
    conn = get_db_connection()
    
    # Get total students
    total_students = conn.execute('SELECT COUNT(*) FROM student').fetchone()[0]
    
    # Get today's attendance
    today = datetime.now().strftime('%Y-%m-%d')
    today_attendance = conn.execute(
        'SELECT COUNT(*) FROM attendance WHERE DATE(attendance_date) = ?',
        (today,)
    ).fetchone()[0]
    
    # Get attendance rate
    attendance_rate = (today_attendance / total_students * 100) if total_students > 0 else 0
    
    # Build aggregated series for charts
    attendance_series = build_attendance_series(conn)
    recent_series = build_recent_chart_series(conn, start_date, end_date)
    
    conn.close()
    recent_attendance_chart = recent_series.get('daily', [])
    if len(recent_attendance_chart) > 8:
        recent_attendance_chart = recent_attendance_chart[-8:]
    return {
        'total_students': total_students,
        'today_attendance': today_attendance,
        'attendance_rate': round(attendance_rate, 1),
        'attendance_series': attendance_series,
        'recent_attendance_chart': recent_attendance_chart,
        'recent_chart_series': recent_series
    }

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.environ.get('REMOTE_ADDR', 'unknown'))
        
        # Check rate limiting
        if is_rate_limited(client_ip):
            flash('Too many login attempts. Please try again in 15 minutes.', 'error')
            return render_template('login.html')
        
        idno = request.form.get('idno')
        password = request.form.get('password')
        
        if not idno or not password:
            flash('Please fill in all fields', 'error')
            record_login_attempt(client_ip)
            return render_template('login.html')
        
        user = authenticate_user(idno, password)
        if user:
            # Successful login - clear any rate limiting for this IP
            if client_ip in login_attempts:
                del login_attempts[client_ip]
            
            session.permanent = True
            session['user_id'] = user['user_id']
            session['idno'] = user['idno']
            session['role'] = user['role']
            session['firstname'] = user['firstname']
            session['lastname'] = user['lastname']
            
            if user['role'] == 'admin':
                return redirect(url_for('dashboard'))
            elif user['role'] == 'student':
                return redirect(url_for('student_dashboard'))
            elif user['role'] == 'faculty':
                return redirect(url_for('faculty_dashboard'))
        else:
            flash('Invalid credentials', 'error')
            record_login_attempt(client_ip)
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    start_date = request.args.get('start_date') or None
    end_date = request.args.get('end_date') or None
    stats = get_dashboard_stats(start_date, end_date)
    return render_template('dashboard.html', 
                         total_students=stats['total_students'],
                         today_attendance=stats['today_attendance'],
                         attendance_rate=stats['attendance_rate'],
                         attendance_series=stats['attendance_series'],
                         recent_attendance_chart=stats['recent_attendance_chart'],
                         recent_chart_series=stats['recent_chart_series'],
                         start_date=start_date,
                         end_date=end_date)

# User Management Routes
@app.route('/admin/users')
def admin_users():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Add profile_picture column to faculty table if it doesn't exist
    try:
        conn.execute('ALTER TABLE faculty ADD COLUMN profile_picture VARCHAR(255)')
        conn.commit()
    except:
        pass  # Column already exists
    
    users = conn.execute('''
        SELECT u.*, 
               d.dept_name, 
               s.profile_picture AS student_profile_picture,
               f.profile_picture AS faculty_profile_picture,
               COALESCE(s.profile_picture, f.profile_picture) AS profile_picture,
               s.attendance_image AS student_attendance_image,
               f.attendance_image AS faculty_attendance_image,
               CASE WHEN s.student_id IS NOT NULL THEN 'Student' 
                    WHEN f.faculty_id IS NOT NULL THEN 'Faculty'
                    ELSE 'Admin' END as user_type,
               CASE 
                    WHEN u.role = 'student' AND s.attendance_image IS NOT NULL THEN 1
                    WHEN u.role = 'faculty' AND f.attendance_image IS NOT NULL THEN 1
                    ELSE 0
               END AS face_registered
        FROM user u
        LEFT JOIN department d ON u.dept_id = d.dept_id
        LEFT JOIN student s ON u.user_id = s.user_id
        LEFT JOIN faculty f ON u.user_id = f.user_id
        ORDER BY u.created_at DESC
    ''').fetchall()
    
    # Get unique departments by name, using the minimum dept_id if duplicates exist
    # Also exclude: Information Technology, Engineering, Computer Science, and duplicate Business Administration
    departments = conn.execute('''
        SELECT dept_id, dept_name 
        FROM department 
        WHERE dept_id IN (
            SELECT MIN(dept_id) 
            FROM department 
            WHERE dept_name NOT IN ('Information Technology', 'Engineering', 'Computer Science')
            GROUP BY dept_name
        )
        ORDER BY dept_name
    ''').fetchall()
    courses = conn.execute('SELECT * FROM course ORDER BY course_name').fetchall()
    
    conn.close()
    return render_template('admin_users.html', users=users, departments=departments, courses=courses)

@app.route('/admin/users/create', methods=['POST'])
def create_user():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        idno = request.form.get('idno')
        firstname = request.form.get('firstname')
        lastname = request.form.get('lastname')
        role = request.form.get('role')
        password = request.form.get('password')
        dept_id = request.form.get('dept_id')
        year_level = request.form.get('year_level')
        course_id = request.form.get('course_id')
        position = request.form.get('position')
        
        
        # Set default password if none provided (use ID number as-is, no validation)
        is_default_password = False
        if not password:
            password = idno  # Use ID number as default password
            is_default_password = True  # Flag to skip validation for default passwords
        
        # Validate required fields
        if not all([idno, firstname, lastname, role]):
            flash('Please fill in all required fields', 'error')
            return redirect(url_for('admin_users'))

        # For NEW users, enforce strictly numeric ID numbers.
        # This does not affect login; it only restricts what admins can create going forward.
        if not idno.isdigit():
            flash('ID number must contain numbers only (no letters or special characters)', 'error')
            return redirect(url_for('admin_users'))
        
        # Validate each field
        is_valid_id, validated_idno = validate_input(idno, 'idno', 1, 20)
        if not is_valid_id:
            flash(f'Invalid ID number: {validated_idno}', 'error')
            return redirect(url_for('admin_users'))
        
        is_valid_fname, validated_fname = validate_input(firstname, 'name', 1, 50)
        if not is_valid_fname:
            flash(f'Invalid first name: {validated_fname}', 'error')
            return redirect(url_for('admin_users'))
        
        is_valid_lname, validated_lname = validate_input(lastname, 'name', 1, 50)
        if not is_valid_lname:
            flash(f'Invalid last name: {validated_lname}', 'error')
            return redirect(url_for('admin_users'))
        
        is_valid_role, validated_role = validate_input(role, 'role')
        if not is_valid_role:
            flash(f'Invalid role: {validated_role}', 'error')
            return redirect(url_for('admin_users'))
        
        # Validate password strength only if NOT using default password
        # Default passwords (ID numbers) are allowed without validation
        if not is_default_password:
            from security_config import validate_password_strength
            is_valid_password, password_message = validate_password_strength(password)
            if not is_valid_password:
                flash(password_message, 'error')
                return redirect(url_for('admin_users'))
        
        # Validate department ID if provided
        if dept_id:
            try:
                dept_id = int(dept_id)
            except ValueError:
                flash('Invalid department ID', 'error')
                return redirect(url_for('admin_users'))
        
        # Validate course ID for students
        if validated_role == 'student' and course_id:
            try:
                course_id = int(course_id)
            except ValueError:
                flash('Invalid course ID', 'error')
                return redirect(url_for('admin_users'))
        
        # Password is already set from form data or default
        
        conn = get_db_connection()
        
        # Check if user already exists
        existing_user = conn.execute('SELECT idno FROM user WHERE idno = ?', (validated_idno,)).fetchone()
        if existing_user:
            flash('User ID already exists', 'error')
            conn.close()
            return redirect(url_for('admin_users'))
        
        # Hash password before storing
        hashed_password = hash_password(password)
        
        # Insert user
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO user (idno, firstname, lastname, role, password, dept_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (validated_idno, validated_fname, validated_lname, validated_role, hashed_password, dept_id if dept_id else None))
        
        user_id = cursor.lastrowid
        
        # Insert role-specific data
        if validated_role == 'student' and course_id:
            if not year_level:
                flash('Year level is required for students', 'error')
                conn.rollback()
                conn.close()
                return redirect(url_for('admin_users'))
            
            cursor.execute('''
                INSERT INTO student (year_level, course_id, user_id)
                VALUES (?, ?, ?)
            ''', (year_level, course_id, user_id))
        elif validated_role == 'faculty' and position:
            cursor.execute('''
                INSERT INTO faculty (position, user_id)
                VALUES (?, ?)
            ''', (position, user_id))
        
        conn.commit()
        conn.close()
        
        # Create welcome notification for new user
        if NOTIFICATIONS_AVAILABLE:
            try:
                if validated_role == 'student':
                    welcome_msg = (
                        "🎉 Welcome to FaceCheck! Your student account is ready. "
                        "Register your face in the portal so you can start marking attendance."
                    )
                elif validated_role == 'faculty':
                    welcome_msg = (
                        "👋 Welcome aboard! Your faculty account is active. "
                        "Register your face to start taking attendance and managing your classes."
                    )
                else:
                    welcome_msg = (
                        "⚙️ Welcome to the admin team! Use the dashboard to manage users, classes, "
                        "and system settings."
                    )
                
                create_notification(user_id, welcome_msg, 'welcome_account')
            except Exception as notification_error:
                print(f"Warning: Failed to create welcome notification: {notification_error}")
        
        flash('User created successfully', 'success')
        
    except Exception as e:
        flash(f'Error creating user: {str(e)}', 'error')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/edit', methods=['GET', 'POST'])
def edit_user(user_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    if request.method == 'POST':
        try:
            firstname = request.form.get('firstname')
            lastname = request.form.get('lastname')
            role = request.form.get('role')
            dept_id = request.form.get('dept_id')
            year_level = request.form.get('year_level')
            course_id = request.form.get('course_id')
            position = request.form.get('position')
            is_active = request.form.get('is_active', '0')
            
            if not all([firstname, lastname, role]):
                flash('Please fill in all required fields', 'error')
                conn.close()
                return redirect(url_for('edit_user', user_id=user_id))
            
            # Update user
            conn.execute('''
                UPDATE user SET firstname = ?, lastname = ?, role = ?, dept_id = ?, is_active = ?
                WHERE user_id = ?
            ''', (firstname, lastname, role, dept_id, is_active, user_id))
            
            # Update role-specific data
            if role == 'student' and course_id:
                # Check if student record exists
                student = conn.execute('SELECT student_id FROM student WHERE user_id = ?', (user_id,)).fetchone()
                if student:
                    conn.execute('''
                        UPDATE student SET year_level = ?, course_id = ?
                        WHERE user_id = ?
                    ''', (year_level, course_id, user_id))
                else:
                    conn.execute('''
                        INSERT INTO student (year_level, course_id, user_id)
                        VALUES (?, ?, ?)
                    ''', (year_level, course_id, user_id))
            elif role == 'faculty' and position:
                # Check if faculty record exists
                faculty = conn.execute('SELECT faculty_id FROM faculty WHERE user_id = ?', (user_id,)).fetchone()
                if faculty:
                    conn.execute('''
                        UPDATE faculty SET position = ?
                        WHERE user_id = ?
                    ''', (position, user_id))
                else:
                    conn.execute('''
                        INSERT INTO faculty (position, user_id)
                        VALUES (?, ?)
                    ''', (position, user_id))
            
            conn.commit()
            flash('User updated successfully', 'success')
            
        except Exception as e:
            flash(f'Error updating user: {str(e)}', 'error')
    
    # Get user data
    user = conn.execute('''
        SELECT u.*, d.dept_name, s.year_level, s.course_id, f.position
        FROM user u
        LEFT JOIN department d ON u.dept_id = d.dept_id
        LEFT JOIN student s ON u.user_id = s.user_id
        LEFT JOIN faculty f ON u.user_id = f.user_id
        WHERE u.user_id = ?
    ''', (user_id,)).fetchone()
    
    # Get unique departments by name, using the minimum dept_id if duplicates exist
    # Also exclude: Information Technology, Engineering, Computer Science, and duplicate Business Administration
    departments = conn.execute('''
        SELECT dept_id, dept_name 
        FROM department 
        WHERE dept_id IN (
            SELECT MIN(dept_id) 
            FROM department 
            WHERE dept_name NOT IN ('Information Technology', 'Engineering', 'Computer Science')
            GROUP BY dept_name
        )
        ORDER BY dept_name
    ''').fetchall()
    courses = conn.execute('SELECT * FROM course ORDER BY course_name').fetchall()
    
    conn.close()
    return render_template('edit_user.html', user=user, departments=departments, courses=courses)

@app.route('/admin/users/<int:user_id>/reset-password', methods=['POST'])
def reset_password(user_id):
    if 'user_id' not in session or session['role'] != 'admin':
        if request.headers.get('Content-Type') == 'application/json' or request.is_json:
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        
        # Get the user's ID number and role, which we use as the default password
        user = conn.execute('SELECT idno, firstname, lastname FROM user WHERE user_id = ?', (user_id,)).fetchone()
        if not user or not user['idno']:
            conn.close()
            error_msg = 'Unable to reset password: user has no ID number configured.'
            if request.headers.get('Content-Type') == 'application/json' or request.is_json:
                return jsonify({'success': False, 'message': error_msg}), 400
            flash(error_msg, 'error')
            return redirect(url_for('admin_users'))
        
        # Reset to ID number (no validation for password resets to default)
        default_password = str(user['idno']).strip()
        hashed_password = hash_password(default_password)
        
        conn.execute('UPDATE user SET password = ? WHERE user_id = ?', (hashed_password, user_id))
        conn.commit()
        conn.close()
        
        # Notify the user that their password was reset to the default
        if NOTIFICATIONS_AVAILABLE:
            try:
                reset_msg = (
                    '🔑 Your account password has been reset by the administrator. '
                    'Please use your ID number as your password and change it after logging in.'
                )
                create_notification(user_id, reset_msg, 'password_reset')
            except Exception as notify_err:
                print(f"Warning: failed to create password reset notification: {notify_err}")
        
        success_msg = f"Password reset successfully for {user['firstname']} {user['lastname']}. The password has been reset to their default ID number."
        
        # Return JSON for AJAX requests, otherwise redirect with flash
        if request.headers.get('Content-Type') == 'application/json' or request.is_json:
            return jsonify({
                'success': True,
                'message': success_msg
            })
        
        flash(success_msg, 'success')
        
    except Exception as e:
        error_msg = f'Error resetting password: {str(e)}'
        if request.headers.get('Content-Type') == 'application/json' or request.is_json:
            return jsonify({'success': False, 'message': error_msg}), 500
        flash(error_msg, 'error')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'])
def toggle_user_status(user_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        
        # Get current status
        user = conn.execute('SELECT is_active FROM user WHERE user_id = ?', (user_id,)).fetchone()
        new_status = 0 if user['is_active'] else 1
        
        # Update status
        conn.execute('UPDATE user SET is_active = ? WHERE user_id = ?', (new_status, user_id))
        conn.commit()
        conn.close()
        
        status_text = 'activated' if new_status else 'deactivated'
        flash(f'User {status_text} successfully', 'success')
        
    except Exception as e:
        flash(f'Error updating user status: {str(e)}', 'error')
    
    return redirect(url_for('admin_users'))

@app.route('/admin/users/profile/<int:user_id>')
def admin_user_profile(user_id):
    """API endpoint to get user profile information for admin"""
    try:
        # Admin should have access to view any user profile
        if 'user_id' not in session or session.get('role') != 'admin':
            return jsonify({'success': False, 'message': 'Unauthorized'}), 401
        
        conn = get_db_connection()
        
        # Get basic user info
        user_info = conn.execute('''
            SELECT u.user_id, u.idno, u.firstname, u.lastname, u.role, u.created_at, u.is_active,
                   d.dept_name
            FROM user u
            LEFT JOIN department d ON u.dept_id = d.dept_id
            WHERE u.user_id = ?
        ''', (user_id,)).fetchone()
        
        if not user_info:
            conn.close()
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        role = user_info['role']
        profile_data = {
            'user_id': user_info['user_id'],
            'idno': user_info['idno'],
            'firstname': user_info['firstname'],
            'lastname': user_info['lastname'],
            'full_name': f"{user_info['firstname']} {user_info['lastname']}",
            'role': role,
            'dept_name': user_info['dept_name'],
            'is_active': bool(user_info['is_active']),
            'created_at': user_info['created_at']
        }
        
        # Get role-specific information
        if role == 'student':
            student_info = conn.execute('''
                SELECT s.student_id, s.year_level, s.attendance_image, s.profile_picture,
                       c.course_name
                FROM student s
                LEFT JOIN course c ON s.course_id = c.course_id
                WHERE s.user_id = ?
            ''', (user_id,)).fetchone()
            
            if student_info:
                profile_data['profile_picture'] = student_info['profile_picture']
                profile_data['attendance_image'] = student_info['attendance_image']
                profile_data['year_level'] = student_info['year_level']
                profile_data['course_name'] = student_info['course_name']
                
                # Get attendance stats
                stats = conn.execute('''
                    SELECT 
                        COUNT(*) as total_records,
                        SUM(CASE WHEN a.attendance_status = 'present' THEN 1 ELSE 0 END) as present_count,
                        SUM(CASE WHEN a.attendance_status = 'late' THEN 1 ELSE 0 END) as late_count,
                        SUM(CASE WHEN a.attendance_status = 'absent' THEN 1 ELSE 0 END) as absent_count
                    FROM attendance a
                    JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
                    WHERE sc.student_id = ?
                ''', (student_info['student_id'],)).fetchone()
                
                total_records = stats['total_records'] or 0
                present_count = stats['present_count'] or 0
                late_count = stats['late_count'] or 0
                absent_count = stats['absent_count'] or 0
                attendance_rate = round((present_count / total_records * 100), 1) if total_records > 0 else 0
                
                profile_data['attendance_stats'] = {
                    'total': total_records,
                    'present': present_count,
                    'late': late_count,
                    'absent': absent_count,
                    'rate': attendance_rate
                }
                
                # Get enrolled classes
                classes = conn.execute('''
                    SELECT cl.class_name, cl.edpcode, cl.room,
                           GROUP_CONCAT(DISTINCT d.day_name) as days,
                           cl.start_time, cl.end_time
                    FROM student_class sc
                    JOIN class cl ON sc.class_id = cl.class_id
                    LEFT JOIN class_days cd ON cl.class_id = cd.class_id
                    LEFT JOIN days d ON cd.day_id = d.day_id
                    WHERE sc.student_id = ?
                    GROUP BY cl.class_name, cl.edpcode, cl.room, cl.start_time, cl.end_time
                    ORDER BY cl.class_name
                    LIMIT 10
                ''', (student_info['student_id'],)).fetchall()
                
                def format_time(value):
                    if not value:
                        return None
                    try:
                        return datetime.strptime(str(value), '%H:%M:%S').strftime('%I:%M %p')
                    except Exception:
                        try:
                            return datetime.strptime(str(value), '%H:%M').strftime('%I:%M %p')
                        except Exception:
                            return str(value)
                
                classes_list = []
                for item in classes:
                    schedule_parts = []
                    if item['days']:
                        schedule_parts.append(item['days'])
                    if item['start_time'] and item['end_time']:
                        schedule_parts.append(f"{format_time(item['start_time'])} - {format_time(item['end_time'])}")
                    classes_list.append({
                        'name': item['class_name'],
                        'code': item['edpcode'],
                        'room': item['room'],
                        'schedule': ' • '.join(schedule_parts) if schedule_parts else 'Schedule not set'
                    })
                profile_data['classes'] = classes_list
            else:
                # Student user but no student record - still return basic info
                profile_data['classes'] = []
            
        elif role == 'faculty':
            faculty_info = conn.execute('''
                SELECT f.faculty_id, f.position
                FROM faculty f
                WHERE f.user_id = ?
            ''', (user_id,)).fetchone()
            
            if faculty_info:
                profile_data['position'] = faculty_info['position']
                
                # Get classes taught
                classes = conn.execute('''
                    SELECT cl.class_name, cl.edpcode, cl.room,
                           GROUP_CONCAT(DISTINCT d.day_name) as days,
                           cl.start_time, cl.end_time,
                           COUNT(DISTINCT sc.student_id) as student_count
                    FROM class cl
                    LEFT JOIN student_class sc ON cl.class_id = sc.class_id
                    LEFT JOIN class_days cd ON cl.class_id = cd.class_id
                    LEFT JOIN days d ON cd.day_id = d.day_id
                    WHERE cl.faculty_id = ?
                    GROUP BY cl.class_id, cl.class_name, cl.edpcode, cl.room, cl.start_time, cl.end_time
                    ORDER BY cl.class_name
                    LIMIT 10
                ''', (faculty_info['faculty_id'],)).fetchall()
                
                def format_time(value):
                    if not value:
                        return None
                    try:
                        return datetime.strptime(str(value), '%H:%M:%S').strftime('%I:%M %p')
                    except Exception:
                        try:
                            return datetime.strptime(str(value), '%H:%M').strftime('%I:%M %p')
                        except Exception:
                            return str(value)
                
                classes_list = []
                for item in classes:
                    schedule_parts = []
                    if item['days']:
                        schedule_parts.append(item['days'])
                    if item['start_time'] and item['end_time']:
                        schedule_parts.append(f"{format_time(item['start_time'])} - {format_time(item['end_time'])}")
                    classes_list.append({
                        'name': item['class_name'],
                        'code': item['edpcode'],
                        'room': item['room'],
                        'student_count': item['student_count'] or 0,
                        'schedule': ' • '.join(schedule_parts) if schedule_parts else 'Schedule not set'
                    })
                profile_data['classes'] = classes_list
            else:
                # Faculty user but no faculty record - still return basic info
                profile_data['classes'] = []
        
        conn.close()
        return jsonify({
            'success': True,
            'user': profile_data
        })
    except Exception as e:
        print(f"Error in admin_user_profile: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': f'Error loading profile: {str(e)}'
        }), 500

# Class & Event Management Routes
@app.route('/admin/classes')
def admin_classes():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()

    # Optional filters
    search = request.args.get('search', '').strip()
    dept_filter = request.args.get('dept', '').strip()
    status_filter = request.args.get('status', '').strip()  # 'active', 'inactive', or ''
    
    # Get all classes with faculty info and days (including deactivated for admin view)
    base_query = '''
        SELECT c.*, u.firstname, u.lastname, d.dept_name,
               GROUP_CONCAT(DISTINCT day.day_name) as days
        FROM class c
        JOIN faculty f ON c.faculty_id = f.faculty_id
        JOIN user u ON f.user_id = u.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        LEFT JOIN class_days cd ON c.class_id = cd.class_id
        LEFT JOIN days day ON cd.day_id = day.day_id
    '''

    where_clauses = []
    params = []

    if search:
        where_clauses.append('('
                             'LOWER(c.class_name) LIKE LOWER(?) OR '
                             'LOWER(c.edpcode) LIKE LOWER(?) OR '
                             'LOWER(u.firstname || " " || u.lastname) LIKE LOWER(?)'
                             ')')
        like_term = f'%{search}%'
        params.extend([like_term, like_term, like_term])

    if dept_filter:
        where_clauses.append('d.dept_id = ?')
        params.append(dept_filter)

    if status_filter == 'active':
        where_clauses.append('c.is_active = 1')
    elif status_filter == 'inactive':
        where_clauses.append('c.is_active = 0')

    if where_clauses:
        base_query += ' WHERE ' + ' AND '.join(where_clauses)

    base_query += '''
        GROUP BY c.class_id, c.class_name, c.edpcode, c.start_time, c.end_time, c.room, 
                 c.faculty_id, u.firstname, u.lastname, d.dept_name, c.is_active
        ORDER BY c.is_active DESC, c.class_name
    '''

    classes_raw = conn.execute(base_query, tuple(params)).fetchall()
    
    # Format classes with 12-hour time format
    classes = []
    for class_item in classes_raw:
        # Format time (convert from 24-hour to 12-hour with AM/PM)
        time_str = ''
        if class_item['start_time'] and class_item['end_time']:
            try:
                start_time = str(class_item['start_time'])
                end_time = str(class_item['end_time'])
                
                # Handle different time formats (HH:MM:SS or HH:MM)
                time_formats = ['%H:%M:%S', '%H:%M']
                start_dt = None
                end_dt = None
                
                for fmt in time_formats:
                    try:
                        start_dt = datetime.strptime(start_time, fmt)
                        end_dt = datetime.strptime(end_time, fmt)
                        break
                    except ValueError:
                        continue
                
                if start_dt and end_dt:
                    time_str = f"{start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}"
                else:
                    time_str = f"{start_time} - {end_time}"
            except Exception as e:
                time_str = f"{class_item['start_time']} - {class_item['end_time']}"
        
        # Create formatted class dict
        formatted_class = dict(class_item)
        formatted_class['formatted_time'] = time_str
        classes.append(formatted_class)
    
    # Get all faculty for assignment
    faculty = conn.execute('''
        SELECT f.faculty_id, u.firstname, u.lastname, d.dept_name
        FROM faculty f
        JOIN user u ON f.user_id = u.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE u.is_active = 1
        ORDER BY u.firstname, u.lastname
    ''').fetchall()

    departments = conn.execute('SELECT dept_id, dept_name FROM department ORDER BY dept_name').fetchall()
    
    conn.close()
    return render_template('admin_classes.html',
                           classes=classes,
                           faculty=faculty,
                           departments=departments,
                           search=search,
                           selected_dept=dept_filter,
                           selected_status=status_filter)

@app.route('/admin/classes/create', methods=['GET', 'POST'])
def create_class():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            class_name = request.form.get('class_name')
            edpcode = request.form.get('edpcode')
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            room = request.form.get('room')
            faculty_id = request.form.get('faculty_id')
            days = request.form.getlist('days')  # Multiple days can be selected
            
            # Validate required fields including at least one schedule day
            if not all([class_name, edpcode, start_time, end_time, room, faculty_id]):
                flash('Please fill in all required fields', 'error')
                return redirect(url_for('create_class'))
            
            if not days:
                flash('Please select at least one day of the week for the class schedule', 'error')
                return redirect(url_for('create_class'))
            
            conn = get_db_connection()
            
            # Check if EDP code already exists
            existing_class = conn.execute('SELECT class_id FROM class WHERE edpcode = ?', (edpcode,)).fetchone()
            if existing_class:
                flash('EDP Code already exists', 'error')
                conn.close()
                return redirect(url_for('create_class'))
            
            # Insert class
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO class (class_name, edpcode, start_time, end_time, room, faculty_id)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (class_name, edpcode, start_time, end_time, room, faculty_id))
            
            class_id = cursor.lastrowid
            
            # Insert class days
            for day_id in days:
                cursor.execute('''
                    INSERT INTO class_days (class_id, day_id)
                    VALUES (?, ?)
                ''', (class_id, day_id))
            
            conn.commit()
            conn.close()
            
            flash('Class created successfully', 'success')
            return redirect(url_for('admin_classes'))
            
        except Exception as e:
            flash(f'Error creating class: {str(e)}', 'error')
            return redirect(url_for('create_class'))
    
    # GET request - show form
    conn = get_db_connection()
    faculty = conn.execute('''
        SELECT f.faculty_id, u.firstname, u.lastname, d.dept_name
        FROM faculty f
        JOIN user u ON f.user_id = u.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE u.is_active = 1
        ORDER BY u.firstname, u.lastname
    ''').fetchall()
    
    days = conn.execute('SELECT * FROM days ORDER BY day_id').fetchall()
    conn.close()
    
    return render_template('create_class.html', faculty=faculty, days=days)

@app.route('/admin/classes/<int:class_id>/edit', methods=['GET', 'POST'])
def edit_class(class_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    if request.method == 'POST':
        try:
            class_name = request.form.get('class_name')
            edpcode = request.form.get('edpcode')
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            room = request.form.get('room')
            faculty_id = request.form.get('faculty_id')
            days = request.form.getlist('days')
            
            # Validate required fields including at least one schedule day
            if not all([class_name, edpcode, start_time, end_time, room, faculty_id]):
                flash('Please fill in all required fields', 'error')
                conn.close()
                return redirect(url_for('edit_class', class_id=class_id))
            
            if not days:
                flash('Please select at least one day of the week for the class schedule', 'error')
                conn.close()
                return redirect(url_for('edit_class', class_id=class_id))
            
            # Check if EDP code already exists (excluding current class)
            existing_class = conn.execute('SELECT class_id FROM class WHERE edpcode = ? AND class_id != ?', (edpcode, class_id)).fetchone()
            if existing_class:
                flash('EDP Code already exists', 'error')
                conn.close()
                return redirect(url_for('edit_class', class_id=class_id))
            
            # Update class
            conn.execute('''
                UPDATE class SET class_name = ?, edpcode = ?, start_time = ?, end_time = ?, room = ?, faculty_id = ?
                WHERE class_id = ?
            ''', (class_name, edpcode, start_time, end_time, room, faculty_id, class_id))
            
            # Update class days
            conn.execute('DELETE FROM class_days WHERE class_id = ?', (class_id,))
            for day_id in days:
                conn.execute('''
                    INSERT INTO class_days (class_id, day_id)
                    VALUES (?, ?)
                ''', (class_id, day_id))
            
            conn.commit()
            flash('Class updated successfully', 'success')
            
        except Exception as e:
            flash(f'Error updating class: {str(e)}', 'error')
    
    # Get class data
    class_info = conn.execute('''
        SELECT c.*, u.firstname, u.lastname, d.dept_name
        FROM class c
        JOIN faculty f ON c.faculty_id = f.faculty_id
        JOIN user u ON f.user_id = u.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE c.class_id = ?
    ''', (class_id,)).fetchone()
    
    # Prevent editing deactivated classes
    if class_info and not row_get(class_info, 'is_active', 1):
        conn.close()
        flash('Cannot edit a deactivated class. Please reactivate it first.', 'error')
        return redirect(url_for('admin_classes'))
    
    # Get class days
    class_days = conn.execute('SELECT day_id FROM class_days WHERE class_id = ?', (class_id,)).fetchall()
    class_day_ids = [day['day_id'] for day in class_days]
    
    # Get faculty and days for form
    faculty = conn.execute('''
        SELECT f.faculty_id, u.firstname, u.lastname, d.dept_name
        FROM faculty f
        JOIN user u ON f.user_id = u.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE u.is_active = 1
        ORDER BY u.firstname, u.lastname
    ''').fetchall()
    
    days = conn.execute('SELECT * FROM days ORDER BY day_id').fetchall()
    
    conn.close()
    return render_template('edit_class.html', class_info=class_info, faculty=faculty, days=days, class_day_ids=class_day_ids)

@app.route('/admin/classes/<int:class_id>/students')
def class_students(class_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Get class info
    class_info = conn.execute('''
        SELECT c.*, u.firstname, u.lastname
        FROM class c
        JOIN faculty f ON c.faculty_id = f.faculty_id
        JOIN user u ON f.user_id = u.user_id
        WHERE c.class_id = ?
    ''', (class_id,)).fetchone()
    
    if not class_info:
        conn.close()
        flash('Class not found', 'error')
        return redirect(url_for('admin_classes'))
    
    # Show read-only message for deactivated classes
    is_readonly = not row_get(class_info, 'is_active', 1)
    
    # Get enrolled students (exclude deactivated users)
    enrolled_students = conn.execute('''
        SELECT u.idno, u.firstname, u.lastname, s.student_id, s.year_level, c.course_name, d.dept_name
        FROM student_class sc
        JOIN student s ON sc.student_id = s.student_id
        JOIN user u ON s.user_id = u.user_id
        LEFT JOIN course c ON s.course_id = c.course_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE sc.class_id = ? AND u.is_active = 1
        ORDER BY u.firstname, u.lastname
    ''', (class_id,)).fetchall()
    
    # Get available students (not enrolled in this class)
    available_students = conn.execute('''
        SELECT u.idno, u.firstname, u.lastname, s.student_id, s.year_level, c.course_name, d.dept_name
        FROM user u
        JOIN student s ON u.user_id = s.user_id
        LEFT JOIN course c ON s.course_id = c.course_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE u.is_active = 1 AND u.role = 'student'
        AND s.student_id NOT IN (
            SELECT sc.student_id FROM student_class sc WHERE sc.class_id = ?
        )
        ORDER BY u.firstname, u.lastname
    ''', (class_id,)).fetchall()
    
    conn.close()
    return render_template('class_students.html', 
                         class_info=class_info, 
                         enrolled_students=enrolled_students, 
                         available_students=available_students,
                         is_readonly=is_readonly)

@app.route('/admin/classes/<int:class_id>/enroll', methods=['POST'])
def enroll_student_to_class(class_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        student_id = request.form.get('student_id')
        
        if not student_id:
            flash('Please select a student', 'error')
            return redirect(url_for('class_students', class_id=class_id))
        
        conn = get_db_connection()
        
        # Check if student is already enrolled
        existing_enrollment = conn.execute('''
            SELECT studentclass_id FROM student_class 
            WHERE class_id = ? AND student_id = ?
        ''', (class_id, student_id)).fetchone()
        
        if existing_enrollment:
            flash('Student is already enrolled in this class', 'error')
            conn.close()
            return redirect(url_for('class_students', class_id=class_id))
        
        # Enroll student
        conn.execute('''
            INSERT INTO student_class (class_id, student_id)
            VALUES (?, ?)
        ''', (class_id, student_id))
        
        conn.commit()
        conn.close()
        
        flash('Student enrolled successfully', 'success')
        
    except Exception as e:
        flash(f'Error enrolling student: {str(e)}', 'error')
    
    return redirect(url_for('class_students', class_id=class_id))

@app.route('/admin/classes/<int:class_id>/bulk-enroll', methods=['POST'])
def bulk_enroll_students(class_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        student_ids = request.form.getlist('student_ids')
        
        if not student_ids:
            flash('Please select at least one student', 'error')
            return redirect(url_for('class_students', class_id=class_id))
        
        conn = get_db_connection()
        enrolled_count = 0
        already_enrolled = 0
        
        for student_id in student_ids:
            # Check if student is already enrolled
            existing_enrollment = conn.execute('''
                SELECT studentclass_id FROM student_class 
                WHERE class_id = ? AND student_id = ?
            ''', (class_id, student_id)).fetchone()
            
            if not existing_enrollment:
                # Enroll student
                conn.execute('''
                    INSERT INTO student_class (class_id, student_id)
                    VALUES (?, ?)
                ''', (class_id, student_id))
                enrolled_count += 1
            else:
                already_enrolled += 1
        
        conn.commit()
        conn.close()
        
        if enrolled_count > 0:
            flash(f'Successfully enrolled {enrolled_count} student(s)', 'success')
        if already_enrolled > 0:
            flash(f'{already_enrolled} student(s) were already enrolled', 'warning')
        
    except Exception as e:
        flash(f'Error enrolling students: {str(e)}', 'error')
    
    return redirect(url_for('class_students', class_id=class_id))

@app.route('/admin/classes/<int:class_id>/bulk-unenroll', methods=['POST'])
def bulk_unenroll_students(class_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        student_ids = request.form.getlist('student_ids')
        
        if not student_ids:
            flash('Please select at least one student', 'error')
            return redirect(url_for('class_students', class_id=class_id))
        
        conn = get_db_connection()
        unenrolled_count = 0
        
        for student_id in student_ids:
            # Remove student from class
            conn.execute('''
                DELETE FROM student_class 
                WHERE class_id = ? AND student_id = ?
            ''', (class_id, student_id))
            unenrolled_count += 1
        
        conn.commit()
        conn.close()
        
        flash(f'Successfully removed {unenrolled_count} student(s) from the class', 'success')
        
    except Exception as e:
        flash(f'Error removing students: {str(e)}', 'error')
    
    return redirect(url_for('class_students', class_id=class_id))

@app.route('/admin/classes/<int:class_id>/unenroll/<int:student_id>', methods=['POST'])
def unenroll_student_from_class(class_id, student_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        
        # Remove student from class
        conn.execute('''
            DELETE FROM student_class 
            WHERE class_id = ? AND student_id = ?
        ''', (class_id, student_id))
        
        conn.commit()
        conn.close()
        
        flash('Student unenrolled successfully', 'success')
        
    except Exception as e:
        flash(f'Error unenrolling student: {str(e)}', 'error')
    
    return redirect(url_for('class_students', class_id=class_id))

# Event Management Routes
@app.route('/admin/events')
def admin_events():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Get all events with faculty info (including deactivated for admin view)
    events = conn.execute('''
        SELECT e.*, u.firstname, u.lastname, d.dept_name
        FROM event e
        JOIN faculty f ON e.faculty_id = f.faculty_id
        JOIN user u ON f.user_id = u.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        ORDER BY e.is_active DESC, e.event_date DESC
    ''').fetchall()
    
    # Get all faculty for assignment
    faculty = conn.execute('''
        SELECT f.faculty_id, u.firstname, u.lastname, d.dept_name
        FROM faculty f
        JOIN user u ON f.user_id = u.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE u.is_active = 1
        ORDER BY u.firstname, u.lastname
    ''').fetchall()
    
    conn.close()
    return render_template('admin_events.html', events=events, faculty=faculty)

@app.route('/admin/events/create', methods=['GET', 'POST'])
def create_event():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            event_name = request.form.get('event_name')
            description = request.form.get('description')
            event_date = request.form.get('event_date')
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            room = request.form.get('room')
            faculty_id = request.form.get('faculty_id')
            
            if not all([event_name, event_date, start_time, end_time, faculty_id]):
                flash('Please fill in all required fields', 'error')
                return redirect(url_for('admin_events'))

            # Validate that event date/time is not in the past
            try:
                # Parse event date
                event_date_obj = datetime.strptime(event_date, '%Y-%m-%d').date()
                
                # Parse start time (support HH:MM and HH:MM:SS)
                time_str = start_time.strip()
                time_formats = ['%H:%M', '%H:%M:%S']
                start_time_obj = None
                for fmt in time_formats:
                    try:
                        start_time_obj = datetime.strptime(time_str, fmt).time()
                        break
                    except ValueError:
                        continue
                
                if not start_time_obj:
                    flash('Invalid start time format', 'error')
                    return redirect(url_for('admin_events'))
                
                event_start_dt = datetime.combine(event_date_obj, start_time_obj)
                now = datetime.now()
                
                if event_start_dt <= now:
                    flash('Event date and time must be in the future. You cannot schedule events in the past.', 'error')
                    return redirect(url_for('admin_events'))
            except Exception as e:
                flash(f'Invalid event date/time: {str(e)}', 'error')
                return redirect(url_for('admin_events'))
            
            conn = get_db_connection()
            
            # Insert event
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO event (event_name, description, event_date, start_time, end_time, room, faculty_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (event_name, description, event_date, start_time, end_time, room, faculty_id))
            
            event_id = cursor.lastrowid
            
            # DO NOT add organizer to event_faculty table
            # Organizer doesn't need to mark attendance - they take attendance for faculty participants
            # Only faculty participants (added via Manage Faculty page) go in event_faculty table
            
            conn.commit()
            conn.close()
            
            flash('Event created successfully', 'success')
            return redirect(url_for('admin_events'))
            
        except Exception as e:
            flash(f'Error creating event: {str(e)}', 'error')
    
    # GET request - show form
    conn = get_db_connection()
    faculty = conn.execute('''
        SELECT f.faculty_id, u.firstname, u.lastname, d.dept_name
        FROM faculty f
        JOIN user u ON f.user_id = u.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE u.is_active = 1
        ORDER BY u.firstname, u.lastname
    ''').fetchall()
    conn.close()
    
    # Provide today's date for min constraint on date picker
    today_str = datetime.now().strftime('%Y-%m-%d')
    
    return render_template('create_event.html', faculty=faculty, today=today_str)

@app.route('/admin/events/<int:event_id>/edit', methods=['GET', 'POST'])
def edit_event(event_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    if request.method == 'POST':
        try:
            event_name = request.form.get('event_name')
            description = request.form.get('description')
            event_date = request.form.get('event_date')
            start_time = request.form.get('start_time')
            end_time = request.form.get('end_time')
            room = request.form.get('room')
            faculty_id = request.form.get('faculty_id')
            
            if not all([event_name, event_date, start_time, end_time, faculty_id]):
                flash('Please fill in all required fields', 'error')
                conn.close()
                return redirect(url_for('edit_event', event_id=event_id))
            
            # Update event
            conn.execute('''
                UPDATE event SET event_name = ?, description = ?, event_date = ?, start_time = ?, end_time = ?, room = ?, faculty_id = ?
                WHERE event_id = ?
            ''', (event_name, description, event_date, start_time, end_time, room, faculty_id, event_id))
            
            conn.commit()
            flash('Event updated successfully', 'success')
            
        except Exception as e:
            flash(f'Error updating event: {str(e)}', 'error')
    
    # Get event data
    event_info = conn.execute('''
        SELECT e.*, u.firstname, u.lastname, d.dept_name
        FROM event e
        JOIN faculty f ON e.faculty_id = f.faculty_id
        JOIN user u ON f.user_id = u.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE e.event_id = ?
    ''', (event_id,)).fetchone()
    
    # Get faculty for form
    faculty = conn.execute('''
        SELECT f.faculty_id, u.firstname, u.lastname, d.dept_name
        FROM faculty f
        JOIN user u ON f.user_id = u.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE u.is_active = 1
        ORDER BY u.firstname, u.lastname
    ''').fetchall()
    
    conn.close()
    return render_template('edit_event.html', event_info=event_info, faculty=faculty)

@app.route('/admin/events/<int:event_id>/faculty')
def event_faculty(event_id):
    """View and manage faculty assigned to an event"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Get event info
    event_info = conn.execute('''
        SELECT e.*, u.firstname, u.lastname, d.dept_name
        FROM event e
        JOIN faculty f ON e.faculty_id = f.faculty_id
        JOIN user u ON f.user_id = u.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE e.event_id = ?
    ''', (event_id,)).fetchone()
    
    if not event_info:
        conn.close()
        flash('Event not found', 'error')
        return redirect(url_for('admin_events'))
    
    # Show read-only message for deactivated events
    is_readonly = not row_get(event_info, 'is_active', 1)
    
    # Get organizer info separately
    organizer_id = event_info['faculty_id']
    
    # Get faculty participants (from event_faculty table, EXCLUDING the organizer)
    assigned_faculty = conn.execute('''
        SELECT f.faculty_id, u.firstname, u.lastname, u.idno, d.dept_name, f.position
        FROM event_faculty ef
        JOIN faculty f ON ef.faculty_id = f.faculty_id
        JOIN user u ON f.user_id = u.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE ef.event_id = ? AND ef.faculty_id != ?
        ORDER BY u.firstname, u.lastname
    ''', (event_id, organizer_id)).fetchall()
    
    # Get available faculty (not assigned to this event AND not the organizer)
    available_faculty = conn.execute('''
        SELECT f.faculty_id, u.firstname, u.lastname, u.idno, d.dept_name, f.position
        FROM faculty f
        JOIN user u ON f.user_id = u.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE u.is_active = 1 AND u.role = 'faculty'
        AND f.faculty_id != ?
        AND f.faculty_id NOT IN (
            SELECT ef.faculty_id FROM event_faculty ef WHERE ef.event_id = ?
        )
        ORDER BY u.firstname, u.lastname
    ''', (organizer_id, event_id)).fetchall()
    
    conn.close()
    return render_template('event_faculty.html', 
                         event_info=event_info, 
                         assigned_faculty=assigned_faculty, 
                         available_faculty=available_faculty,
                         organizer_id=organizer_id,
                         is_readonly=is_readonly)

@app.route('/admin/events/<int:event_id>/add-faculty', methods=['POST'])
def add_faculty_to_event(event_id):
    """Add a faculty member to an event"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        faculty_id = request.form.get('faculty_id')
        
        if not faculty_id:
            flash('Please select a faculty member', 'error')
            return redirect(url_for('event_faculty', event_id=event_id))
        
        conn = get_db_connection()
        
        # Get event to check if trying to add the organizer
        event = conn.execute('SELECT faculty_id FROM event WHERE event_id = ?', (event_id,)).fetchone()
        if not event:
            flash('Event not found', 'error')
            conn.close()
            return redirect(url_for('admin_events'))
        
        # Prevent adding the organizer as faculty participant
        if faculty_id == str(event['faculty_id']):
            flash('The organizer is already part of this event and cannot be added as a faculty participant', 'error')
            conn.close()
            return redirect(url_for('event_faculty', event_id=event_id))
        
        # Check if faculty is already a participant
        existing = conn.execute('''
            SELECT eventfaculty_id FROM event_faculty 
            WHERE event_id = ? AND faculty_id = ?
        ''', (event_id, faculty_id)).fetchone()
        
        if existing:
            flash('Faculty member is already assigned to this event', 'error')
            conn.close()
            return redirect(url_for('event_faculty', event_id=event_id))
        
        # Add faculty to event
        conn.execute('''
            INSERT INTO event_faculty (event_id, faculty_id)
            VALUES (?, ?)
        ''', (event_id, faculty_id))
        
        conn.commit()
        conn.close()
        
        flash('Faculty member added successfully', 'success')
        
    except Exception as e:
        flash(f'Error adding faculty: {str(e)}', 'error')
    
    return redirect(url_for('event_faculty', event_id=event_id))

@app.route('/admin/events/<int:event_id>/bulk-add-faculty', methods=['POST'])
def bulk_add_faculty_to_event(event_id):
    """Add multiple faculty members to an event"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        faculty_ids = request.form.getlist('faculty_ids')
        
        if not faculty_ids:
            flash('Please select at least one faculty member', 'error')
            return redirect(url_for('event_faculty', event_id=event_id))
        
        conn = get_db_connection()
        
        # Get event to check organizer
        event = conn.execute('SELECT faculty_id FROM event WHERE event_id = ?', (event_id,)).fetchone()
        if not event:
            flash('Event not found', 'error')
            conn.close()
            return redirect(url_for('admin_events'))
        
        organizer_id = event['faculty_id']
        added_count = 0
        already_assigned = 0
        skipped_organizer = 0
        
        for faculty_id in faculty_ids:
            # Skip if trying to add the organizer
            if int(faculty_id) == organizer_id:
                skipped_organizer += 1
                continue
            
            # Check if faculty is already assigned
            existing = conn.execute('''
                SELECT eventfaculty_id FROM event_faculty 
                WHERE event_id = ? AND faculty_id = ?
            ''', (event_id, faculty_id)).fetchone()
            
            if not existing:
                # Add faculty to event
                conn.execute('''
                    INSERT INTO event_faculty (event_id, faculty_id)
                    VALUES (?, ?)
                ''', (event_id, faculty_id))
                added_count += 1
            else:
                already_assigned += 1
        
        conn.commit()
        conn.close()
        
        if added_count > 0:
            flash(f'Successfully added {added_count} faculty member(s)', 'success')
        if already_assigned > 0:
            flash(f'{already_assigned} faculty member(s) were already assigned', 'warning')
        if skipped_organizer > 0:
            flash(f'{skipped_organizer} selection(s) skipped - organizer cannot be added as a faculty participant', 'info')
        
    except Exception as e:
        flash(f'Error adding faculty: {str(e)}', 'error')
    
    return redirect(url_for('event_faculty', event_id=event_id))

@app.route('/admin/events/<int:event_id>/remove-faculty/<int:faculty_id>', methods=['POST'])
def remove_faculty_from_event(event_id, faculty_id):
    """Remove a faculty member from an event"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        conn = get_db_connection()
        
        # Remove faculty from event
        conn.execute('''
            DELETE FROM event_faculty
            WHERE event_id = ? AND faculty_id = ?
        ''', (event_id, faculty_id))
        
        conn.commit()
        conn.close()
        
        flash('Faculty member removed successfully', 'success')
        
    except Exception as e:
        flash(f'Error removing faculty: {str(e)}', 'error')
    
    return redirect(url_for('event_faculty', event_id=event_id))

@app.route('/admin/events/<int:event_id>/bulk-remove-faculty', methods=['POST'])
def bulk_remove_faculty_from_event(event_id):
    """Remove multiple faculty members from an event"""
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        faculty_ids = request.form.getlist('faculty_ids')
        
        if not faculty_ids:
            flash('Please select at least one faculty member', 'error')
            return redirect(url_for('event_faculty', event_id=event_id))
        
        conn = get_db_connection()
        
        # Get event to check organizer
        event = conn.execute('SELECT faculty_id FROM event WHERE event_id = ?', (event_id,)).fetchone()
        if not event:
            flash('Event not found', 'error')
            conn.close()
            return redirect(url_for('admin_events'))
        
        organizer_id = event['faculty_id']
        removed_count = 0
        skipped_organizer = 0
        
        for faculty_id in faculty_ids:
            # Prevent removing the organizer
            if int(faculty_id) == organizer_id:
                skipped_organizer += 1
                continue
            
            conn.execute('''
                DELETE FROM event_faculty
                WHERE event_id = ? AND faculty_id = ?
            ''', (event_id, faculty_id))
            removed_count += 1
        
        conn.commit()
        conn.close()
        
        if removed_count > 0:
            flash(f'Successfully removed {removed_count} faculty member(s) from the event', 'success')
        if skipped_organizer > 0:
            flash(f'{skipped_organizer} selection(s) skipped - organizer cannot be removed', 'info')
        
    except Exception as e:
        flash(f'Error removing faculty: {str(e)}', 'error')
    
    return redirect(url_for('event_faculty', event_id=event_id))

# Face Registration Route
@app.route('/register_face')
def register_face():
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('login'))
    
    # Get student info for the registration process
    conn = get_db_connection()
    student = conn.execute('''
        SELECT u.*, s.student_id, s.profile_picture
        FROM user u
        JOIN student s ON u.user_id = s.user_id
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    if not student:
        conn.close()
        flash('Student not found', 'error')
        return redirect(url_for('student_dashboard'))
    
    conn.close()
    
    return render_template('register_face.html', 
                         student=student,
                         student_name=student['firstname'] + ' ' + student['lastname'],
                         student_id=student['idno'])

# Faculty Face Registration Route
@app.route('/faculty/register_face')
def faculty_register_face():
    if 'user_id' not in session or session['role'] != 'faculty':
        return redirect(url_for('login'))
    
    # Get faculty info for the registration process
    conn = get_db_connection()
    
    # Add profile_picture column to faculty table if it doesn't exist
    try:
        conn.execute('ALTER TABLE faculty ADD COLUMN profile_picture VARCHAR(255)')
        conn.commit()
    except:
        pass  # Column already exists
    
    faculty_info = conn.execute('''
        SELECT u.*, f.faculty_id, f.position, f.attendance_image, f.profile_picture, d.dept_name
        FROM user u
        JOIN faculty f ON u.user_id = f.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    if not faculty_info:
        conn.close()
        flash('Faculty not found', 'error')
        return redirect(url_for('faculty_dashboard'))
    
    conn.close()
    
    return render_template('faculty/faculty_register_face.html', 
                         faculty_info=faculty_info,
                         faculty_name=faculty_info['firstname'] + ' ' + faculty_info['lastname'],
                         faculty_id=faculty_info['idno'])

# Student Dashboard
@app.route('/student/dashboard')
def student_dashboard():
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Get student info
    student = conn.execute('''
        SELECT u.*, s.student_id, s.year_level, s.attendance_image, s.profile_picture, c.course_name, d.dept_name
        FROM user u
        JOIN student s ON u.user_id = s.user_id
        LEFT JOIN course c ON s.course_id = c.course_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    # Get attendance history - format datetime at SQL level to remove microseconds
    attendance_history = conn.execute('''
        SELECT strftime('%Y-%m-%d %H:%M:%S', a.attendance_date) as attendance_date,
               a.attendance_status, cl.class_name
        FROM attendance a
        JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
        JOIN class cl ON sc.class_id = cl.class_id
        WHERE sc.student_id = ?
        ORDER BY a.attendance_date DESC
        LIMIT 10
    ''', (student['student_id'],)).fetchall()
    
    # Get upcoming schedule (next classes for this student)
    upcoming_raw = conn.execute('''
        SELECT 
            c.class_name,
            c.edpcode,
            GROUP_CONCAT(DISTINCT d.day_name) AS days,
            c.start_time,
            c.end_time,
            u_f.firstname AS faculty_firstname,
            u_f.lastname AS faculty_lastname
        FROM student_class sc
        JOIN class c ON sc.class_id = c.class_id
        LEFT JOIN class_days cd ON c.class_id = cd.class_id
        LEFT JOIN days d ON cd.day_id = d.day_id
        LEFT JOIN faculty f ON c.faculty_id = f.faculty_id
        LEFT JOIN user u_f ON f.user_id = u_f.user_id
        WHERE sc.student_id = ?
          AND c.is_active = 1
        GROUP BY c.class_id, c.class_name, c.edpcode, c.start_time, c.end_time
        ORDER BY c.class_name
        LIMIT 5
    ''', (student['student_id'],)).fetchall()
    
    # Format attendance history for template
    formatted_history = []
    for record in attendance_history:
        date_str = ''
        time_str = ''
        if record['attendance_date']:
            try:
                if isinstance(record['attendance_date'], str):
                    # Format: '2025-09-25 08:44:50' -> extract date and time
                    if ' ' in record['attendance_date']:
                        date_str = record['attendance_date'].split(' ')[0]
                        time_str = record['attendance_date'].split(' ')[1]
                    else:
                        date_str = record['attendance_date']
                        time_str = ''
                else:
                    # If it's a datetime object, use strftime
                    date_str = record['attendance_date'].strftime('%Y-%m-%d')
                    time_str = record['attendance_date'].strftime('%H:%M:%S')
            except:
                date_str = str(record['attendance_date'])
                time_str = ''
        
        formatted_history.append({
            'date': date_str,
            'time': time_str,
            'status': record['attendance_status']
        })
    
    # Check if student has registered their face (check database first, then file system)
    has_face_registered = False
    
    # Check if attendance_image is stored in database
    if student['attendance_image']:
        # Verify the file actually exists
        if os.path.exists(student['attendance_image']):
            has_face_registered = True
        else:
            # File doesn't exist, clear the database record
            conn.execute('UPDATE student SET attendance_image = NULL WHERE user_id = ?', (session['user_id'],))
            conn.commit()
    
    # Fallback: check file system directly (for backward compatibility)
    if not has_face_registered:
        face_image_path = f"known_faces/{student['idno']}.jpg"
        if os.path.exists(face_image_path):
            # Update database with the file path
            conn.execute('UPDATE student SET attendance_image = ? WHERE user_id = ?', (face_image_path, session['user_id']))
            conn.commit()
            has_face_registered = True
    
    # Format upcoming classes schedule nicely
    def format_time(value):
        if not value:
            return None
        try:
            return datetime.strptime(str(value), '%H:%M:%S').strftime('%I:%M %p')
        except Exception:
            try:
                return datetime.strptime(str(value), '%H:%M').strftime('%I:%M %p')
            except Exception:
                return str(value)

    upcoming_classes = []
    for item in upcoming_raw or []:
        schedule_parts = []
        if item['days']:
            schedule_parts.append(item['days'])
        if item['start_time'] and item['end_time']:
            schedule_parts.append(f"{format_time(item['start_time'])} - {format_time(item['end_time'])}")
        upcoming_classes.append({
            'class_name': item['class_name'],
            'edpcode': item['edpcode'],
            'schedule': ' • '.join(schedule_parts) if schedule_parts else 'Schedule not set',
            'faculty_firstname': item['faculty_firstname'],
            'faculty_lastname': item['faculty_lastname'],
        })

    conn.close()
    return render_template('student_dashboard.html', 
                         student_info=student,
                         student=student,
                         attendance_history=formatted_history,
                         has_face_registered=has_face_registered,
                         upcoming_classes=upcoming_classes)

# My Classes Route
@app.route('/my_classes')
def my_classes():
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Get student info
    student = conn.execute('''
        SELECT u.*, s.student_id, s.year_level, s.profile_picture, c.course_name, d.dept_name
        FROM user u
        JOIN student s ON u.user_id = s.user_id
        LEFT JOIN course c ON s.course_id = c.course_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    # Get enrolled classes with days
    enrolled_classes_raw = conn.execute('''
        SELECT cl.class_id, cl.class_name, cl.edpcode, cl.start_time, cl.end_time, cl.room,
               u_f.firstname as faculty_firstname, u_f.lastname as faculty_lastname,
               GROUP_CONCAT(DISTINCT d.day_name) as days
        FROM student_class sc
        JOIN class cl ON sc.class_id = cl.class_id
        JOIN faculty f ON cl.faculty_id = f.faculty_id
        JOIN user u_f ON f.user_id = u_f.user_id
        LEFT JOIN class_days cd ON cl.class_id = cd.class_id
        LEFT JOIN days d ON cd.day_id = d.day_id
        WHERE sc.student_id = ?
          AND cl.is_active = 1
        GROUP BY cl.class_id, cl.class_name, cl.edpcode, cl.start_time, cl.end_time, cl.room,
                 u_f.firstname, u_f.lastname
        ORDER BY cl.class_name
    ''', (student['student_id'],)).fetchall()
    
    # Format enrolled classes with schedule
    enrolled_classes = []
    faculty_names = set()
    for class_item in enrolled_classes_raw:
        # Format time (convert from 24-hour to 12-hour with AM/PM)
        time_str = ''
        if class_item['start_time'] and class_item['end_time']:
            try:
                start_time = str(class_item['start_time'])
                end_time = str(class_item['end_time'])
                
                # Handle different time formats (HH:MM:SS or HH:MM)
                time_formats = ['%H:%M:%S', '%H:%M']
                start_dt = None
                end_dt = None
                
                for fmt in time_formats:
                    try:
                        start_dt = datetime.strptime(start_time, fmt)
                        end_dt = datetime.strptime(end_time, fmt)
                        break
                    except ValueError:
                        continue
                
                if start_dt and end_dt:
                    time_str = f"{start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}"
                else:
                    time_str = f"{start_time} - {end_time}"
            except Exception as e:
                time_str = f"{class_item['start_time']} - {class_item['end_time']}"
        
        enrolled_classes.append({
            'class_id': class_item['class_id'],
            'class_name': class_item['class_name'],
            'edpcode': class_item['edpcode'],
            'days': class_item['days'],
            'time': time_str,
            'room': class_item['room'],
            'faculty_firstname': class_item['faculty_firstname'],
            'faculty_lastname': class_item['faculty_lastname'],
            'schedule': time_str
        })
        faculty_names.add(f"{class_item['faculty_firstname']} {class_item['faculty_lastname']}")
    
    total_classes = len(enrolled_classes)
    weekly_hours_estimate = total_classes * 3
    faculty_count = len(faculty_names)
    
    conn.close()
    return render_template('my_classes.html',
                         student=student,
                         enrolled_classes=enrolled_classes,
                         total_classes=total_classes,
                         weekly_hours_estimate=weekly_hours_estimate,
                         faculty_count=faculty_count)

@app.route('/my_classes/<int:class_id>/attendance')
def view_class_attendance(class_id):
    """View attendance records for a specific class"""
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Get student info
    student = conn.execute('''
        SELECT u.*, s.student_id, s.year_level, s.profile_picture, c.course_name, d.dept_name
        FROM user u
        JOIN student s ON u.user_id = s.user_id
        LEFT JOIN course c ON s.course_id = c.course_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    # Verify student is enrolled in this class
    enrollment = conn.execute('''
        SELECT sc.studentclass_id
        FROM student_class sc
        WHERE sc.student_id = ? AND sc.class_id = ?
    ''', (student['student_id'], class_id)).fetchone()
    
    if not enrollment:
        conn.close()
        flash('You are not enrolled in this class', 'error')
        return redirect(url_for('my_classes'))
    
    # Get class information
    class_info = conn.execute('''
        SELECT cl.class_id, cl.class_name, cl.edpcode, cl.room, cl.start_time, cl.end_time,
               u_f.firstname as faculty_firstname, u_f.lastname as faculty_lastname,
               GROUP_CONCAT(DISTINCT d.day_name) as days
        FROM class cl
        JOIN faculty f ON cl.faculty_id = f.faculty_id
        JOIN user u_f ON f.user_id = u_f.user_id
        LEFT JOIN class_days cd ON cl.class_id = cd.class_id
        LEFT JOIN days d ON cd.day_id = d.day_id
        WHERE cl.class_id = ?
        GROUP BY cl.class_id, cl.class_name, cl.edpcode, cl.room, cl.start_time, cl.end_time,
                 u_f.firstname, u_f.lastname
    ''', (class_id,)).fetchone()
    
    if not class_info:
        conn.close()
        flash('Class not found', 'error')
        return redirect(url_for('my_classes'))
    
    # Get attendance records for this student in this class
    attendance_records = conn.execute('''
        SELECT strftime('%Y-%m-%d %H:%M:%S', a.attendance_date) as attendance_date,
               a.attendance_status
        FROM attendance a
        JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
        WHERE sc.student_id = ? AND sc.class_id = ?
        ORDER BY a.attendance_date DESC
    ''', (student['student_id'], class_id)).fetchall()
    
    # Format attendance records
    formatted_records = []
    for record in attendance_records:
        date_str = ''
        time_str = ''
        if record['attendance_date']:
            try:
                from datetime import datetime
                dt = datetime.strptime(record['attendance_date'], '%Y-%m-%d %H:%M:%S')
                date_str = dt.strftime('%B %d, %Y')
                time_str = dt.strftime('%I:%M %p')
            except:
                date_str = str(record['attendance_date']).split(' ')[0]
                time_str = str(record['attendance_date']).split(' ')[1] if ' ' in str(record['attendance_date']) else ''
        
        formatted_records.append({
            'date': date_str,
            'time': time_str,
            'status': record['attendance_status']
        })
    
    # Calculate statistics
    total_records = len(formatted_records)
    present_count = sum(1 for r in formatted_records if r['status'] == 'present')
    late_count = sum(1 for r in formatted_records if r['status'] == 'late')
    absent_count = sum(1 for r in formatted_records if r['status'] == 'absent')
    attendance_rate = round((present_count / total_records * 100), 1) if total_records > 0 else 0
    
    # Format class schedule
    time_str = ''
    if class_info['start_time'] and class_info['end_time']:
        try:
            from datetime import datetime
            start_time = str(class_info['start_time'])
            end_time = str(class_info['end_time'])
            
            time_formats = ['%H:%M:%S', '%H:%M']
            start_dt = None
            end_dt = None
            
            for fmt in time_formats:
                try:
                    start_dt = datetime.strptime(start_time, fmt)
                    end_dt = datetime.strptime(end_time, fmt)
                    break
                except:
                    continue
            
            if start_dt and end_dt:
                time_str = f"{start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}"
        except:
            time_str = f"{class_info['start_time']} - {class_info['end_time']}"
    
    conn.close()
    
    return render_template('student_class_attendance.html',
                         student=student,
                         class_info=class_info,
                         attendance_records=formatted_records,
                         total_records=total_records,
                         present_count=present_count,
                         late_count=late_count,
                         absent_count=absent_count,
                         attendance_rate=attendance_rate,
                         time_str=time_str)

# Student Profile Route
@app.route('/profile')
def student_profile():
    if 'user_id' not in session or session['role'] != 'student':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Get comprehensive student info
    student = conn.execute('''
        SELECT u.*, s.student_id, s.year_level, s.attendance_image, s.profile_picture, c.course_name, d.dept_name
        FROM user u
        JOIN student s ON u.user_id = s.user_id
        LEFT JOIN course c ON s.course_id = c.course_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    # Get enrolled classes with days
    enrolled_classes_raw = conn.execute('''
        SELECT cl.class_id, cl.class_name, cl.edpcode, cl.start_time, cl.end_time, cl.room,
               u_f.firstname as faculty_firstname, u_f.lastname as faculty_lastname,
               GROUP_CONCAT(DISTINCT d.day_name) as days
        FROM student_class sc
        JOIN class cl ON sc.class_id = cl.class_id
        JOIN faculty f ON cl.faculty_id = f.faculty_id
        JOIN user u_f ON f.user_id = u_f.user_id
        LEFT JOIN class_days cd ON cl.class_id = cd.class_id
        LEFT JOIN days d ON cd.day_id = d.day_id
        WHERE sc.student_id = ?
        GROUP BY cl.class_id, cl.class_name, cl.edpcode, cl.start_time, cl.end_time, cl.room,
                 u_f.firstname, u_f.lastname
        ORDER BY cl.class_name
    ''', (student['student_id'],)).fetchall()
    
    # Format enrolled classes with schedule
    enrolled_classes = []
    for class_item in enrolled_classes_raw:
        # Format time (convert from 24-hour to 12-hour if needed)
        time_str = ''
        if class_item['start_time'] and class_item['end_time']:
            try:
                # Try to parse and format times
                start_time = class_item['start_time']
                end_time = class_item['end_time']
                
                # If times are in HH:MM format, convert to 12-hour
                if ':' in str(start_time):
                    try:
                        start_dt = datetime.strptime(str(start_time), '%H:%M')
                        end_dt = datetime.strptime(str(end_time), '%H:%M')
                        time_str = f"{start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}"
                    except:
                        time_str = f"{start_time} - {end_time}"
                else:
                    time_str = f"{start_time} - {end_time}"
            except:
                time_str = f"{class_item['start_time']} - {class_item['end_time']}"
        
        # Format days - get them ordered properly
        days_str = ''
        if class_item['days']:
            days_list = [day.strip() for day in class_item['days'].split(',')]
            # Sort days by day_id order (we'll need to get day order from database)
            # For now, just format nicely
            days_str = ', '.join(sorted(days_list))
        
        # Build complete schedule string
        schedule_parts = []
        if days_str:
            schedule_parts.append(days_str)
        if time_str:
            schedule_parts.append(time_str)
        
        schedule = ' • '.join(schedule_parts) if schedule_parts else 'Schedule not set'
        
        enrolled_classes.append({
            'class_name': class_item['class_name'],
            'edpcode': class_item['edpcode'],
            'schedule': schedule,
            'days': days_str,
            'time': time_str,
            'room': class_item['room'],
            'faculty_firstname': class_item['faculty_firstname'],
            'faculty_lastname': class_item['faculty_lastname']
        })
    
    # Check face registration status
    has_face_registered = False
    if student['attendance_image']:
        if os.path.exists(student['attendance_image']):
            has_face_registered = True
        else:
            conn.execute('UPDATE student SET attendance_image = NULL WHERE user_id = ?', (session['user_id'],))
            conn.commit()
    
    if not has_face_registered:
        face_image_path = f"known_faces/{student['idno']}.jpg"
        if os.path.exists(face_image_path):
            conn.execute('UPDATE student SET attendance_image = ? WHERE user_id = ?', (face_image_path, session['user_id']))
            conn.commit()
            has_face_registered = True
    
    # Get attendance statistics
    attendance_stats = conn.execute('''
        SELECT 
            COUNT(*) as total_records,
            SUM(CASE WHEN a.attendance_status = 'present' THEN 1 ELSE 0 END) as present_count,
            SUM(CASE WHEN a.attendance_status = 'absent' THEN 1 ELSE 0 END) as absent_count
        FROM attendance a
        JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
        WHERE sc.student_id = ?
    ''', (student['student_id'],)).fetchone()
    
    total_records = attendance_stats['total_records'] or 0
    present_count = attendance_stats['present_count'] or 0
    attendance_rate = (present_count / total_records * 100) if total_records > 0 else 0
    
    conn.close()
    return render_template('profile.html',
                         student=student,
                         enrolled_classes=enrolled_classes,
                         has_face_registered=has_face_registered,
                         total_records=total_records,
                         present_count=present_count,
                         attendance_rate=round(attendance_rate, 1))

@app.route('/profile/update_name', methods=['POST'])
def update_student_name():
    """Allow the currently logged-in student to update their first and last name."""
    if 'user_id' not in session or session.get('role') != 'student':
        return redirect(url_for('login'))

    firstname = request.form.get('firstname', '').strip()
    lastname = request.form.get('lastname', '').strip()

    # Basic required check
    if not firstname or not lastname:
        flash('First name and last name are required.', 'error')
        return redirect(url_for('student_profile'))

    # Reuse existing validation helper
    is_valid_fname, fname_msg = validate_input(firstname, 'name', 1, 50)
    if not is_valid_fname:
        flash(f'Invalid first name: {fname_msg}', 'error')
        return redirect(url_for('student_profile'))

    is_valid_lname, lname_msg = validate_input(lastname, 'name', 1, 50)
    if not is_valid_lname:
        flash(f'Invalid last name: {lname_msg}', 'error')
        return redirect(url_for('student_profile'))

    conn = get_db_connection()
    conn.execute(
        '''
        UPDATE user
        SET firstname = ?, lastname = ?
        WHERE user_id = ?
        ''',
        (firstname, lastname, session['user_id'])
    )
    conn.commit()
    conn.close()

    # Keep the session display name in sync
    session['username'] = f"{firstname} {lastname}"

    flash('Profile updated successfully.', 'success')
    return redirect(url_for('student_profile'))

# Faculty Dashboard
@app.route('/faculty/dashboard')
def faculty_dashboard():
    if 'user_id' not in session or session['role'] != 'faculty':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Add profile_picture column to faculty table if it doesn't exist
    try:
        conn.execute('ALTER TABLE faculty ADD COLUMN profile_picture VARCHAR(255)')
        conn.commit()
    except:
        pass  # Column already exists
    
    # Get faculty info
    faculty = conn.execute('''
        SELECT u.*, f.faculty_id, f.position, f.attendance_image, f.profile_picture, d.dept_name
        FROM user u
        JOIN faculty f ON u.user_id = f.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    # Get faculty stats
    my_students = conn.execute('''
        SELECT COUNT(DISTINCT sc.student_id) as student_count
        FROM class c
        JOIN student_class sc ON c.class_id = sc.class_id
        WHERE c.faculty_id = ?
    ''', (faculty['faculty_id'],)).fetchone()
    
    # Get today's attendance for faculty's classes
    today = datetime.now().strftime('%Y-%m-%d')
    today_attendance = conn.execute('''
        SELECT a.attendance_date, u.firstname, u.lastname, a.attendance_status, cl.class_name
        FROM attendance a
        JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
        JOIN student s ON sc.student_id = s.student_id
        JOIN user u ON s.user_id = u.user_id
        JOIN class cl ON sc.class_id = cl.class_id
        WHERE cl.faculty_id = ? AND DATE(a.attendance_date) = ?
        ORDER BY a.attendance_date DESC
    ''', (faculty['faculty_id'], today)).fetchall()
    
    # Calculate stats
    stats = {
        'total_students': my_students['student_count'] if my_students else 0,
        'today_present': len(today_attendance),
        'attendance_rate': 0  # Will be calculated based on total students
    }
    
    # Format attendance data for template
    formatted_attendance = []
    for record in today_attendance:
        # Extract time from datetime string
        time_str = ''
        if record['attendance_date']:
            try:
                # If it's already a string, extract the time part
                if isinstance(record['attendance_date'], str):
                    # Format: '2025-09-25 08:44:50' -> extract '08:44:50'
                    time_str = record['attendance_date'].split(' ')[1] if ' ' in record['attendance_date'] else record['attendance_date']
                else:
                    # If it's a datetime object, use strftime
                    time_str = record['attendance_date'].strftime('%H:%M:%S')
            except:
                time_str = str(record['attendance_date'])
        
        formatted_attendance.append({
            'name': f"{record['firstname']} {record['lastname']}",
            'time': time_str,
            'status': record['attendance_status']
        })
    
    # Build upcoming classes schedule (only active classes)
    classes = conn.execute('''
        SELECT c.class_id, c.class_name, c.room, c.start_time, c.end_time,
               GROUP_CONCAT(DISTINCT d.day_name) as days
        FROM class c
        LEFT JOIN class_days cd ON c.class_id = cd.class_id
        LEFT JOIN days d ON cd.day_id = d.day_id
        WHERE c.faculty_id = ? AND c.is_active = 1
        GROUP BY c.class_id, c.class_name, c.room, c.start_time, c.end_time
    ''', (faculty['faculty_id'],)).fetchall()
    
    def parse_time_value(value):
        if not value:
            return None
        try:
            value = str(value)
            fmt = '%H:%M:%S' if len(value.split(':')) == 3 else '%H:%M'
            return datetime.strptime(value, fmt).time()
        except Exception:
            return None
    
    def format_time_range(start_value, end_value):
        start_time = parse_time_value(start_value)
        end_time = parse_time_value(end_value)
        
        def format_single(time_obj):
            if not time_obj:
                return None
            return time_obj.strftime('%I:%M %p').lstrip('0')
        
        start_str = format_single(start_time)
        end_str = format_single(end_time)
        
        if start_str and end_str:
            return f"{start_str} - {end_str}"
        return start_str or end_str or 'TBA'
    
    weekday_map = {
        'Monday': 0, 'Tuesday': 1, 'Wednesday': 2, 'Thursday': 3,
        'Friday': 4, 'Saturday': 5, 'Sunday': 6
    }
    
    now = datetime.now()
    upcoming_classes = []
    
    for class_item in classes:
        days_list = [day.strip() for day in (class_item['days'] or '').split(',') if day]
        start_time = parse_time_value(class_item['start_time'])
        next_occurrence = None
        next_day_label = None
        
        for day in days_list:
            if day not in weekday_map or not start_time:
                continue
            days_ahead = (weekday_map[day] - now.weekday()) % 7
            candidate_date = now.date() + timedelta(days=days_ahead)
            candidate_dt = datetime.combine(candidate_date, start_time)
            if candidate_dt < now:
                candidate_dt += timedelta(days=7)
            if not next_occurrence or candidate_dt < next_occurrence:
                next_occurrence = candidate_dt
                next_day_label = day
        
        upcoming_classes.append({
            'class_name': class_item['class_name'],
            'room': class_item['room'] or 'TBA',
            'days': ', '.join(days_list) if days_list else 'No schedule set',
            'time_range': format_time_range(class_item['start_time'], class_item['end_time']),
            'next_occurrence': next_occurrence,
            'next_label': next_occurrence.strftime('%a, %b %d') if next_occurrence else 'Schedule pending',
        })
    
    upcoming_classes = sorted(
        upcoming_classes,
        key=lambda c: c['next_occurrence'] or (now + timedelta(days=30))
    )
    
    # Check if faculty has registered their face (database first, then filesystem)
    has_face_registered = False
    if faculty['attendance_image']:
        import os
        # attendance_image is expected to store the full relative path (e.g. "known_faces/faculty_1234.jpg")
        if os.path.exists(faculty['attendance_image']):
            has_face_registered = True
        else:
            # File doesn't exist, clear the database record
            conn.execute('UPDATE faculty SET attendance_image = NULL WHERE user_id = ?', (session['user_id'],))
            conn.commit()

    # Fallback: check common legacy paths directly and update database
    if not has_face_registered:
        import os
        possible_paths = [
            f"known_faces/faculty_{faculty['idno']}.jpg",  # current faculty registration pattern
            f"known_faces/{faculty['idno']}.jpg",          # legacy pattern without prefix
        ]
        for face_image_path in possible_paths:
            if os.path.exists(face_image_path):
                conn.execute(
                    'UPDATE faculty SET attendance_image = ? WHERE user_id = ?',
                    (face_image_path, session['user_id'])
                )
                conn.commit()
                has_face_registered = True
                break
    
    conn.close()
    return render_template('faculty/faculty_dashboard.html', 
                         faculty_info=faculty, 
                         stats=stats, 
                         today_attendance=formatted_attendance,
                         has_face_registered=has_face_registered,
                         upcoming_classes=upcoming_classes)

# API Routes
@app.route('/api/register_face', methods=['POST'])
def api_register_face():
    if 'user_id' not in session or session['role'] != 'student':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Get the uploaded face image
        if 'face_image' not in request.files:
            return jsonify({'error': 'No face image provided'}), 400
        
        face_file = request.files['face_image']
        if face_file.filename == '':
            return jsonify({'error': 'No face image selected'}), 400
        
        # Validate file type and size
        allowed_extensions = {'png', 'jpg', 'jpeg'}
        max_file_size = 5 * 1024 * 1024  # 5MB
        
        def allowed_file(filename):
            return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions
        
        if not allowed_file(face_file.filename):
            return jsonify({'error': 'Invalid file type. Only PNG, JPG, and JPEG are allowed'}), 400
        
        # Check file size
        face_file.seek(0, os.SEEK_END)
        file_size = face_file.tell()
        face_file.seek(0)
        
        if file_size > max_file_size:
            return jsonify({'error': 'File too large. Maximum size is 5MB'}), 400
        
        if file_size < 1024:  # Minimum 1KB
            return jsonify({'error': 'File too small. Minimum size is 1KB'}), 400
        
        # Get student info
        conn = get_db_connection()
        student = conn.execute('''
            SELECT u.idno FROM user u
            JOIN student s ON u.user_id = s.user_id
            WHERE u.user_id = ?
        ''', (session['user_id'],)).fetchone()
        
        if not student:
            conn.close()
            return jsonify({'error': 'Student not found'}), 404
        
        # Check if face recognition is available
        if not FACE_RECOGNITION_AVAILABLE:
            return jsonify({'error': 'Face recognition system is not configured. Please install required packages: pip install face-recognition opencv-contrib-python'}), 503
        
        # Create known_faces directory with proper permissions
        os.makedirs('known_faces', mode=0o755, exist_ok=True)
        
        # Read and validate the uploaded image
        try:
            face_data = face_file.read()
            if len(face_data) == 0:
                return jsonify({'error': 'Empty file received'}), 400
                
            nparr = np.frombuffer(face_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception as e:
            return jsonify({'error': 'Failed to read image data'}), 400
        
        if image is None:
            return jsonify({'error': 'Invalid image format or corrupted file'}), 400
        
        # Validate image dimensions
        height, width = image.shape[:2]
        if height < 100 or width < 100:
            return jsonify({'error': 'Image too small. Minimum resolution is 100x100 pixels'}), 400
        
        if height > 4000 or width > 4000:
            return jsonify({'error': 'Image too large. Maximum resolution is 4000x4000 pixels'}), 400
        
        # Convert BGR to RGB for face_recognition
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Detect faces using face_recognition library or fallback
        try:
            if FACE_RECOGNITION_AVAILABLE:
                face_locations = face_recognition.face_locations(rgb_image, model="hog")
                face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
            else:
                # Use OpenCV fallback
                from opencv_face_detector import simple_detector
                faces = simple_detector.detect_face(image)
                if len(faces) == 0:
                    face_encodings = []
                elif len(faces) > 1:
                    return jsonify({'error': 'Multiple faces detected. Please ensure only your face is visible in the camera.'}), 400
                else:
                    face_encodings = [1]  # Dummy encoding to indicate face found
        except Exception as e:
            return jsonify({'error': f'Face detection failed: {str(e)}'}), 400
        
        if not face_encodings:
            return jsonify({'error': 'No face detected in the image. Please ensure your face is clearly visible and try again.'}), 400
        
        if len(face_encodings) > 1:
            return jsonify({'error': 'Multiple faces detected. Please ensure only your face is visible in the camera.'}), 400
        
        # Generate secure filename
        import uuid
        filename = f"{student['idno']}_{uuid.uuid4().hex[:8]}.jpg"
        face_path = os.path.join('known_faces', filename)
        
        # Resize image to standard size to reduce storage
        max_size = 800
        if max(height, width) > max_size:
            scale = max_size / max(height, width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        # Save the face image with proper error handling
        try:
            if not cv2.imwrite(face_path, image):
                return jsonify({'error': 'Failed to save face image'}), 500
        except Exception as e:
            return jsonify({'error': f'Failed to save face image: {str(e)}'}), 500
        
        # Update the student record with the attendance_image path
        try:
            conn.execute('''
                UPDATE student 
                SET attendance_image = ? 
                WHERE user_id = ?
            ''', (face_path, session['user_id']))
            
            conn.commit()
            
            # Create notification for successful face registration
            if NOTIFICATIONS_AVAILABLE:
                try:
                    from notification_system import create_notification
                    create_notification(
                        session['user_id'],
                        '✅ Success! Your face has been registered successfully. You can now mark attendance using face recognition.',
                        'face_registration'
                    )
                except Exception as e:
                    print(f"Error creating registration notification: {e}")
                    
        except Exception as e:
            # Clean up the saved file if database update fails
            if os.path.exists(face_path):
                os.remove(face_path)
            return jsonify({'error': f'Failed to update student record: {str(e)}'}), 500
        finally:
            conn.close()
        
        return jsonify({'success': True, 'message': 'Face registered successfully'})
        
    except Exception as e:
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500

@app.route('/api/faculty/register_face', methods=['POST'])
def api_faculty_register_face():
    if 'user_id' not in session or session['role'] != 'faculty':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Get the uploaded face image
        if 'face_image' not in request.files:
            return jsonify({'error': 'No face image provided'}), 400
        
        face_file = request.files['face_image']
        if face_file.filename == '':
            return jsonify({'error': 'No face image selected'}), 400
        
        # Get faculty info
        conn = get_db_connection()
        faculty = conn.execute('''
            SELECT u.idno FROM user u
            JOIN faculty f ON u.user_id = f.user_id
            WHERE u.user_id = ?
        ''', (session['user_id'],)).fetchone()
        
        if not faculty:
            conn.close()
            return jsonify({'error': 'Faculty not found'}), 404
        
        # Import required libraries for face detection
        import cv2
        import numpy as np
        import face_recognition
        import os
        
        # Create known_faces directory
        os.makedirs('known_faces', exist_ok=True)
        
        # Read the uploaded image
        face_data = face_file.read()
        nparr = np.frombuffer(face_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if image is None:
            conn.close()
            return jsonify({'error': 'Invalid image format'}), 400
        
        # Convert BGR to RGB for face_recognition
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Detect faces using face_recognition library
        face_locations = face_recognition.face_locations(rgb_image)
        face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
        
        if not face_encodings:
            conn.close()
            return jsonify({'error': 'No face detected in the image. Please ensure your face is clearly visible and try again.'}), 400
        
        if len(face_encodings) > 1:
            conn.close()
            return jsonify({'error': 'Multiple faces detected. Please ensure only your face is visible in the camera.'}), 400
        
        # Save the face image with faculty prefix to distinguish from students
        face_path = f"known_faces/faculty_{faculty['idno']}.jpg"
        cv2.imwrite(face_path, image)
        
        # Add attendance_image column to faculty table if it doesn't exist
        try:
            conn.execute('ALTER TABLE faculty ADD COLUMN attendance_image VARCHAR(255)')
        except:
            pass  # Column already exists
        
        # Update the faculty record with the attendance_image path
        conn.execute('''
            UPDATE faculty 
            SET attendance_image = ? 
            WHERE user_id = ?
        ''', (face_path, session['user_id']))
        
        conn.commit()
        conn.close()
        
        # Create notification for successful face registration
        if NOTIFICATIONS_AVAILABLE:
            try:
                from notification_system import create_notification
                create_notification(
                    session['user_id'],
                    '✅ Success! Your face has been registered successfully. You can now mark attendance for events.',
                    'face_registration'
                )
            except Exception as e:
                print(f"Error creating registration notification: {e}")
        
        return jsonify({'success': True, 'message': 'Face registered successfully'})
        
    except ImportError as e:
        return jsonify({'error': 'Face recognition libraries not installed. Please contact administrator.'}), 500
    except Exception as e:
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500

@app.route('/api/students')
def api_students():
    conn = get_db_connection()
    students = conn.execute('''
        SELECT u.idno, u.firstname, u.lastname, s.year_level, c.course_name
        FROM user u
        JOIN student s ON u.user_id = s.user_id
        LEFT JOIN course c ON s.course_id = c.course_id
        WHERE u.role = 'student' AND u.is_active = 1
    ''').fetchall()
    conn.close()
    
    return jsonify([dict(student) for student in students])

@app.route('/api/upload-profile-picture', methods=['POST'])
def api_upload_profile_picture():
    """Handle profile picture uploads for students"""
    if 'user_id' not in session or session['role'] != 'student':
        return jsonify({'error': 'Unauthorized'}), 401
    
    if 'profile_picture' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['profile_picture']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Validate file type
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    
    if file_ext not in allowed_extensions:
        return jsonify({'error': 'Invalid file type. Allowed: PNG, JPG, JPEG, GIF, WEBP'}), 400
    
    try:
        # Get student info
        conn = get_db_connection()
        student = conn.execute('''
            SELECT s.student_id, s.profile_picture, u.idno
            FROM student s
            JOIN user u ON s.user_id = u.user_id
            WHERE u.user_id = ?
        ''', (session['user_id'],)).fetchone()
        
        if not student:
            conn.close()
            return jsonify({'error': 'Student not found'}), 404
        
        # Create profile_pictures directory inside static if it doesn't exist
        profile_pics_dir = Path('static/profile_pictures')
        profile_pics_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename using student ID and timestamp
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"student_{student['idno']}_{timestamp}.{file_ext}"
        filepath = profile_pics_dir / filename
        
        # Delete old profile picture if it exists
        if student['profile_picture']:
            old_filepath = profile_pics_dir / student['profile_picture']
            if old_filepath.exists():
                try:
                    old_filepath.unlink()
                except Exception as e:
                    print(f"Warning: Could not delete old profile picture: {e}")
        
        # Save the new file
        file.save(str(filepath))
        
        # Update database with new filename
        conn.execute('''
            UPDATE student
            SET profile_picture = ?
            WHERE student_id = ?
        ''', (filename, student['student_id']))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Profile picture uploaded successfully',
            'filename': filename
        }), 200
        
    except Exception as e:
        print(f"Error uploading profile picture: {e}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

@app.route('/api/faculty/upload-profile-picture', methods=['POST'])
def api_faculty_upload_profile_picture():
    """Handle profile picture uploads for faculty"""
    if 'user_id' not in session or session['role'] != 'faculty':
        return jsonify({'error': 'Unauthorized'}), 401
    
    if 'profile_picture' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['profile_picture']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Validate file type
    allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    
    if file_ext not in allowed_extensions:
        return jsonify({'error': 'Invalid file type. Allowed: PNG, JPG, JPEG, GIF, WEBP'}), 400
    
    try:
        # Get faculty info
        conn = get_db_connection()
        
        # Add profile_picture column to faculty table if it doesn't exist
        try:
            conn.execute('ALTER TABLE faculty ADD COLUMN profile_picture VARCHAR(255)')
            conn.commit()
        except:
            pass  # Column already exists
        
        faculty = conn.execute('''
            SELECT f.faculty_id, f.profile_picture, u.idno
            FROM faculty f
            JOIN user u ON f.user_id = u.user_id
            WHERE u.user_id = ?
        ''', (session['user_id'],)).fetchone()
        
        if not faculty:
            conn.close()
            return jsonify({'error': 'Faculty not found'}), 404
        
        # Create profile_pictures directory inside static if it doesn't exist
        profile_pics_dir = Path('static/profile_pictures')
        profile_pics_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate unique filename using faculty ID and timestamp
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        filename = f"faculty_{faculty['idno']}_{timestamp}.{file_ext}"
        filepath = profile_pics_dir / filename
        
        # Delete old profile picture if it exists
        if faculty['profile_picture']:
            old_filepath = profile_pics_dir / faculty['profile_picture']
            if old_filepath.exists():
                try:
                    old_filepath.unlink()
                except Exception as e:
                    print(f"Warning: Could not delete old profile picture: {e}")
        
        # Save the new file
        file.save(str(filepath))
        
        # Update database with new filename
        conn.execute('''
            UPDATE faculty
            SET profile_picture = ?
            WHERE faculty_id = ?
        ''', (filename, faculty['faculty_id']))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Profile picture uploaded successfully',
            'filename': filename
        }), 200
        
    except Exception as e:
        print(f"Error uploading faculty profile picture: {e}")
        return jsonify({'error': f'Upload failed: {str(e)}'}), 500

def calculate_ear(eye_landmarks):
    """Calculate Eye Aspect Ratio (EAR) for blink detection"""
    import numpy as np 
    
    # Convert to numpy array
    eye = np.array(eye_landmarks)
    
    # Calculate distances
    A = np.linalg.norm(eye[1] - eye[5])  # Vertical distance 1
    B = np.linalg.norm(eye[2] - eye[4])  # Vertical distance 2
    C = np.linalg.norm(eye[0] - eye[3])    # Horizontal distance
    
    # Calculate EAR
    ear = (A + B) / (2.0 * C)
    return ear

def process_face_recognition(image_path, attendance_type='class', class_id=None, event_id=None):
    """
    Process face recognition using the same logic as face_recog_test.py
    Args:
        image_path: Path to the image file
        attendance_type: 'class' for students, 'event' for faculty
        class_id: Class ID for filtering students (optional)
        event_id: Event ID for filtering faculty participants (optional)
    """
    try:
        anti_result = {
            'success': ANTI_SPOOFING_AVAILABLE,
            'is_live': not ANTI_SPOOFING_AVAILABLE,
            'confidence': 1.0 if not ANTI_SPOOFING_AVAILABLE else 0.0,
            'details': 'Anti-spoofing disabled' if not ANTI_SPOOFING_AVAILABLE else 'Pending analysis',
            'checks': {}
        }

        def _with_anti(payload):
            payload['anti_spoofing'] = anti_result
            return payload

        # Check if face recognition is available
        if not FACE_RECOGNITION_AVAILABLE:
            print("Using OpenCV fallback for face recognition")
            try:
                from opencv_face_detector import fallback_face_recognition
                return fallback_face_recognition(image_path)
            except ImportError as e:
                return _with_anti({
                    'success': False,
                    'message': f'Face recognition system is not configured: {e}',
                    'student_id': 'Unknown',
                    'student_name': 'Unknown'
                })
        
        print(f"Processing image: {image_path}, attendance_type: {attendance_type}")
        
        # Load known faces from database based on attendance type
        conn = get_db_connection()
        
        if attendance_type == 'event':
            # For events, load ONLY faculty participants (from event_faculty table) - EXCLUDE organizer
            # Organizer doesn't need to mark attendance, they take attendance for others
            if event_id:
                # Get organizer ID to exclude them
                event_info = conn.execute('SELECT faculty_id FROM event WHERE event_id = ?', (event_id,)).fetchone()
                organizer_id = event_info['faculty_id'] if event_info else None
                
                if organizer_id:
                    people = conn.execute('''
                        SELECT DISTINCT f.faculty_id as person_id, u.user_id, u.firstname, u.lastname, f.attendance_image
                        FROM event_faculty ef
                        JOIN faculty f ON ef.faculty_id = f.faculty_id
                        JOIN user u ON f.user_id = u.user_id
                        WHERE ef.event_id = ? AND ef.faculty_id != ? AND f.attendance_image IS NOT NULL AND u.is_active = 1
                    ''', (event_id, organizer_id)).fetchall()
                else:
                    people = []
            else:
                # Fallback: load all faculty if no event_id provided
                people = conn.execute('''
                    SELECT f.faculty_id as person_id, u.user_id, u.firstname, u.lastname, f.attendance_image
                    FROM faculty f
                    JOIN user u ON f.user_id = u.user_id
                    WHERE f.attendance_image IS NOT NULL AND u.is_active = 1
                ''').fetchall()
            person_type = 'faculty'
        else:
            # For classes, load students enrolled in the class
            if class_id:
                people = conn.execute('''
                    SELECT s.student_id as person_id, u.user_id, u.firstname, u.lastname, s.attendance_image
                    FROM student_class sc
                    JOIN student s ON sc.student_id = s.student_id
                    JOIN user u ON s.user_id = u.user_id
                    WHERE sc.class_id = ? AND s.attendance_image IS NOT NULL AND u.is_active = 1
                ''', (class_id,)).fetchall()
            else:
                # Fallback: load all students if no class_id provided
                people = conn.execute('''
                    SELECT s.student_id as person_id, u.user_id, u.firstname, u.lastname, s.attendance_image
                    FROM student s
                    JOIN user u ON s.user_id = u.user_id
                    WHERE s.attendance_image IS NOT NULL AND u.is_active = 1
                ''').fetchall()
            person_type = 'student'
        
        conn.close()
        
        print(f"Found {len(people)} registered {person_type}s")
        
        if not people:
            return _with_anti({
                'success': False,
                'message': f'No registered {person_type}s found',
                'student_id': 'Unknown',
                'student_name': 'Unknown'
            })
        
        # Load the image
        image = cv2.imread(image_path)
        if image is None:
            print("Could not load image")
            return _with_anti({
                'success': False,
                'message': 'Could not load image',
                'student_id': 'Unknown',
                'student_name': 'Unknown'
            })
        
        print(f"Image loaded: {image.shape}")
        
        # Convert BGR to RGB
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Find face locations
        print("Detecting faces...")
        face_locations = face_recognition.face_locations(rgb_image, number_of_times_to_upsample=1, model="hog")
        print(f"Found {len(face_locations)} face(s)")
        
        if not face_locations:
            return _with_anti({
                'success': False,
                'message': 'No face detected',
                'student_id': 'Unknown',
                'student_name': 'Unknown'
            })
        
        # Get face encodings and landmarks
        print("Encoding faces...")
        face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
        face_landmarks = face_recognition.face_landmarks(rgb_image, face_locations)
        print(f"Generated {len(face_encodings)} face encoding(s)")
        
        if not face_encodings:
            return _with_anti({
                'success': False,
                'message': 'Could not encode face',
                'student_id': 'Unknown',
                'student_name': 'Unknown'
            })

        # Run anti-spoofing check before matching
        if ANTI_SPOOFING_AVAILABLE:
            try:
                anti_result = anti_spoofing_detector.comprehensive_anti_spoofing_check(
                    image,
                    face_landmarks[0] if face_landmarks else None,
                    face_locations[0]
                )
            except Exception as anti_err:
                print(f"Anti-spoofing failed: {anti_err}")
                anti_result = {
                    'success': False,
                    'is_live': False,
                    'confidence': 0.0,
                    'details': f'Anti-spoofing error: {anti_err}',
                    'checks': {}
                }
        
        # Compare with known faces
        print("Comparing with known faces...")
        best_match = None
        best_distance = float('inf')
        
        for person in people:
            print(f"Checking {person_type}: {person['firstname']} {person['lastname']}")
            if not person['attendance_image'] or not os.path.exists(person['attendance_image']):
                print(f"  No valid image: {person['attendance_image']}")
                continue
                
            # Load known face
            known_image = cv2.imread(person['attendance_image'])
            if known_image is None:
                print(f"  Could not load image: {person['attendance_image']}")
                continue
                
            known_rgb = cv2.cvtColor(known_image, cv2.COLOR_BGR2RGB)
            known_encodings = face_recognition.face_encodings(known_rgb)
            
            if not known_encodings:
                print(f"  Could not encode known face")
                continue
            
            # Calculate distance
            distances = face_recognition.face_distance(known_encodings, face_encodings[0])
            min_distance = min(distances)
            print(f"  Distance: {min_distance}")
            
            if min_distance < best_distance:
                best_distance = min_distance
                best_match = person
        
        # Check if match is good enough (tolerance from face_recog_test.py)
        # Lower tolerance = more strict matching = fewer false positives
        # 0.5 is a good balance between accuracy and false rejections
        MATCH_TOLERANCE = 0.5
        print(f"Best match: {best_match['firstname'] if best_match else 'None'}")
        print(f"Best distance: {best_distance}")
        print(f"Tolerance: {MATCH_TOLERANCE}")
        
        # Additional validation: if no one has been checked or best_distance is still infinity, no match
        if best_match is None or best_distance == float('inf'):
            print("No valid faces to compare against")
            return _with_anti({
                'success': False,
                'message': f'No registered {person_type}s with valid face data found',
                'student_id': 'Unknown',
                'student_name': 'Unknown',
                'face_box': None if not face_locations else {
                    'x': int(face_locations[0][3]),
                    'y': int(face_locations[0][0]),
                    'width': int(face_locations[0][1] - face_locations[0][3]),
                    'height': int(face_locations[0][2] - face_locations[0][0])
                }
            })
        
        # Get face location coordinates for drawing box
        # Use landmarks for more accurate face bounding box (like real-world systems)
        face_box = None
        if face_landmarks and len(face_landmarks) > 0:
            # Calculate precise bounding box from facial landmarks
            landmarks = face_landmarks[0]
            all_points = []
            
            # Collect all landmark points
            for feature_name in ['chin', 'left_eyebrow', 'right_eyebrow', 'nose_bridge', 
                                 'nose_tip', 'left_eye', 'right_eye', 'top_lip', 'bottom_lip']:
                if feature_name in landmarks:
                    all_points.extend(landmarks[feature_name])
            
            if all_points:
                # Find min and max coordinates
                all_x = [p[0] for p in all_points]
                all_y = [p[1] for p in all_points]
                
                min_x = min(all_x)
                max_x = max(all_x)
                min_y = min(all_y)
                max_y = max(all_y)
                
                # Add small margin for better visualization (10% padding)
                width = max_x - min_x
                height = max_y - min_y
                margin_x = int(width * 0.15)  # 15% horizontal margin
                margin_y = int(height * 0.20)  # 20% vertical margin (more for forehead/hair)
                
                # Apply margins with boundary checking
                min_x = max(0, min_x - margin_x)
                min_y = max(0, min_y - margin_y)
                max_x = min(rgb_image.shape[1], max_x + margin_x)
                max_y = min(rgb_image.shape[0], max_y + margin_y)
                
                face_box = {
                    'x': int(min_x),
                    'y': int(min_y),
                    'width': int(max_x - min_x),
                    'height': int(max_y - min_y)
                }
        elif face_locations:
            # Fallback to basic face_locations if landmarks not available
            top, right, bottom, left = face_locations[0]
            face_box = {
                'x': int(left),
                'y': int(top),
                'width': int(right - left),
                'height': int(bottom - top)
            }

        # Enforce liveness/anti-spoofing before accepting any match
        MIN_LIVE_CONFIDENCE = 0.42
        if ANTI_SPOOFING_AVAILABLE:
            if not anti_result.get('is_live') or anti_result.get('confidence', 0) < MIN_LIVE_CONFIDENCE:
                print("Anti-spoofing blocked attempt (not live)")
                return _with_anti({
                    'success': False,
                    'message': 'Anti-spoofing blocked this attempt. Please present a live face (no photos or screens).',
                    'student_id': 'Unknown',
                    'student_name': 'Unknown',
                    'face_box': face_box
                })
        
        if best_match and best_distance <= MATCH_TOLERANCE:
            confidence = int((1 - best_distance) * 100)  # Convert distance to confidence percentage
            
            # Require minimum 50% confidence to accept the match
            MIN_CONFIDENCE = 50
            if confidence < MIN_CONFIDENCE:
                print(f"Match rejected: confidence {confidence}% is below minimum {MIN_CONFIDENCE}%")
                return _with_anti({
                    'success': False,
                    'message': f'Face detected but confidence too low ({confidence}%). Please ensure proper lighting and face the camera directly.',
                    'student_id': 'Unknown',
                    'student_name': 'Unknown',
                    'distance': float(best_distance),
                    'confidence': confidence,
                    'face_box': face_box
                })
            
            print(f"Match accepted! Confidence: {confidence}%")
            
            # For events, use user_id; for classes, use student_id (keep backward compatibility)
            person_id = int(best_match['user_id']) if attendance_type == 'event' else int(best_match['person_id'])
            
            return _with_anti({
                'success': True,
                'student_id': person_id,  # Keep 'student_id' key for backward compatibility
                'student_name': f"{best_match['firstname']} {best_match['lastname']}",
                'distance': float(best_distance),
                'confidence': confidence,
                'face_box': face_box  # Add face location for drawing box
            })
        else:
            print("No match found")
            return _with_anti({
                'success': False,
                'message': f'No matching {person_type} found',
                'student_id': 'Unknown',
                'student_name': 'Unknown',
                'distance': float(best_distance if best_match else 999.0),  # Use 999.0 instead of float('inf')
                'confidence': 0,
                'face_box': face_box  # Still provide face box even if no match
            })
            
    except Exception as e:
        print(f"Error in process_face_recognition: {str(e)}")
        import traceback
        traceback.print_exc()
        return _with_anti({
            'success': False,
            'message': f'Recognition error: {str(e)}',
            'student_id': 'Unknown',
            'student_name': 'Unknown'
        })

@app.route('/api/anti-spoofing/analyze', methods=['POST'])
def api_anti_spoofing_analyze():
    """Run anti-spoofing on a single frame (used by frontend status widget)."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    if not ANTI_SPOOFING_AVAILABLE:
        return jsonify({'success': False, 'message': 'Anti-spoofing not available'}), 503
    
    file = request.files.get('image')
    if not file:
        return jsonify({'success': False, 'message': 'No image provided'}), 400
    
    raw = file.read()
    if len(raw) > 5 * 1024 * 1024:
        return jsonify({'success': False, 'message': 'File too large'}), 400
    
    np_data = np.frombuffer(raw, np.uint8)
    image = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
    if image is None:
        return jsonify({'success': False, 'message': 'Could not decode image'}), 400
    
    result = anti_spoofing_detector.comprehensive_anti_spoofing_check(image)
    return jsonify(result)


@app.route('/api/anti-spoofing/reset', methods=['POST'])
def api_anti_spoofing_reset():
    """Reset rolling anti-spoofing state (motion history) and cached live check."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    if ANTI_SPOOFING_AVAILABLE:
        anti_spoofing_detector.reset_state()
    session.pop('last_live_check', None)
    
    return jsonify({'success': True, 'message': 'Anti-spoofing state cleared'})


@app.route('/api/attendance/detect', methods=['POST'])
def api_attendance_detect():
    """Face detection and recognition endpoint"""
    # Debug session info
    print(f"Session contents: {dict(session)}")
    print(f"Session has user_id: {'user_id' in session}")
    print(f"Session role: {session.get('role', 'NO ROLE')}")
    print(f"Request method: {request.method}")
    print(f"Request headers: {dict(request.headers)}")
    
    # Check session first
    if 'user_id' not in session:
        print("ERROR: No user_id in session! User needs to login again.")
        return jsonify({
            'success': False, 
            'message': 'Your session has expired. Please logout and login again to continue.',
            'expired': True,
            'redirect': '/login',
            'error_code': 'SESSION_EXPIRED'
        }), 401
    
    # Allow both faculty and admin to access this endpoint
    user_role = session.get('role')
    if user_role not in ['faculty', 'admin']:
        print(f"ERROR: Invalid role: {user_role}")
        return jsonify({
            'success': False, 
            'message': f'Only faculty and admin can access this feature. You are logged in as: {user_role}',
            'wrong_role': True,
            'current_role': user_role,
            'error_code': 'INSUFFICIENT_PERMISSIONS'
        }), 403  # Changed to 403 for insufficient permissions
    
    filepath = None
    try:
        # Get the uploaded image
        if 'image' not in request.files:
            return jsonify({'success': False, 'message': 'No image provided'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No image selected'}), 400
        
        # Get attendance type from form data (class or event)
        attendance_type = request.form.get('attendance_type', 'class')
        class_id = request.form.get('class_id')
        event_id = request.form.get('event_id')
        print(f"Attendance type: {attendance_type}, class_id: {class_id}, event_id: {event_id}")
        
        # Save the image temporarily with secure filename
        import uuid
        safe_filename = f"temp_{session['user_id']}_{uuid.uuid4().hex[:8]}.jpg"
        filepath = os.path.join('temp', safe_filename)
        os.makedirs('temp', mode=0o755, exist_ok=True)
        
        # Validate file size before saving
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > 10 * 1024 * 1024:  # 10MB limit
            return jsonify({'success': False, 'message': 'File too large'}), 400
        
        file.save(filepath)
        
        # Check if face recognition is available
        if not FACE_RECOGNITION_AVAILABLE:
            return jsonify({
                'success': False, 
                'message': 'Face recognition system is not configured. Please install required packages.',
                'student_id': 'Unknown',
                'student_name': 'Unknown'
            }), 503
        
        # Process the image for face recognition with attendance type
        print(f"Processing face recognition for image: {filepath}, type: {attendance_type}")
        result = process_face_recognition(filepath, attendance_type=attendance_type, class_id=class_id, event_id=event_id)
        print(f"Recognition result: {result}")

        # Persist recent liveness check for the specific target to guard the mark endpoints
        anti_result = result.get('anti_spoofing', {})
        if result.get('success') and anti_result and anti_result.get('is_live'):
            session['last_live_check'] = {
                'person_id': str(result.get('student_id')),
                'attendance_type': attendance_type,
                'class_id': str(class_id) if class_id else None,
                'event_id': str(event_id) if event_id else None,
                'is_live': True,
                'confidence': anti_result.get('confidence'),
                'timestamp': time.time()
            }
            session.modified = True
        
        return jsonify(result)
        
    except Exception as e:
        print(f"Error in api_attendance_detect: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Server error: {str(e)}'}), 500
    finally:
        # Always clean up temp file
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"Warning: Failed to clean up temp file {filepath}: {e}")

@app.route('/api/register/detect', methods=['POST'])
def api_register_detect():
    """Simple face detection endpoint for registration (just detects face, doesn't recognize)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    filepath = None
    try:
        # Get the uploaded image
        if 'image' not in request.files:
            return jsonify({'success': False, 'message': 'No image provided'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'success': False, 'message': 'No image selected'}), 400
        
        # Save the image temporarily
        import uuid
        safe_filename = f"register_detect_{session['user_id']}_{uuid.uuid4().hex[:8]}.jpg"
        filepath = os.path.join('temp', safe_filename)
        os.makedirs('temp', mode=0o755, exist_ok=True)
        
        # Validate file size
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)
        
        if file_size > 10 * 1024 * 1024:  # 10MB limit
            return jsonify({'success': False, 'message': 'File too large'}), 400
        
        file.save(filepath)
        
        # Check if face recognition is available
        if not FACE_RECOGNITION_AVAILABLE:
            return jsonify({
                'success': False, 
                'message': 'Face detection not available',
                'face_detected': False
            }), 503
        
        # Load and process the image
        import cv2
        import numpy as np
        image = cv2.imread(filepath)
        if image is None:
            return jsonify({'success': False, 'message': 'Could not load image', 'face_detected': False}), 400
        
        # Convert to RGB
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Detect faces
        face_locations = face_recognition.face_locations(rgb_image, number_of_times_to_upsample=1, model="hog")
        
        if not face_locations:
            return jsonify({
                'success': True,
                'face_detected': False,
                'message': 'No face detected'
            })
        
        if len(face_locations) > 1:
            return jsonify({
                'success': True,
                'face_detected': True,
                'multiple_faces': True,
                'message': 'Multiple faces detected. Please ensure only your face is visible.'
            })
        
        # Get face location
        top, right, bottom, left = face_locations[0]
        
        # Return face box coordinates
        face_box = {
            'x': int(left),
            'y': int(top),
            'width': int(right - left),
            'height': int(bottom - top)
        }
        
        return jsonify({
            'success': True,
            'face_detected': True,
            'face_box': face_box,
            'message': 'Face detected - Ready to capture!'
        })
        
    except Exception as e:
        print(f"Error in api_register_detect: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'Detection error: {str(e)}', 'face_detected': False}), 500
    finally:
        # Clean up temp file
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except Exception as e:
                print(f"Warning: Failed to clean up temp file {filepath}: {e}")

@app.route('/api/attendance/mark', methods=['POST'])
def api_attendance_mark():
    """Mark attendance for a recognized student"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized - Please login'}), 401
    
    # Allow both faculty and admin to access this endpoint
    if session.get('role') not in ['faculty', 'admin']:
        return jsonify({'success': False, 'message': 'Unauthorized - Faculty or Admin access required'}), 401
    
    try:
        data = request.get_json()
        print(f"Attendance mark request data: {data}")
        student_id = data.get('student_id')
        student_name = data.get('student_name')
        class_id = data.get('class_id')
        
        print(f"Student ID: {student_id}, Student Name: {student_name}, Class ID: {class_id}")
        
        if not student_id or not student_name or not class_id:
            return jsonify({'success': False, 'message': 'Missing student or class information'}), 400

        is_live_ok, live_message = require_recent_live_check(student_id, 'class', class_id=class_id)
        if not is_live_ok:
            return jsonify({'success': False, 'message': live_message, 'error_code': 'LIVENESS_REQUIRED'}), 403
        
        # Mark attendance in database
        conn = get_db_connection()
        print("Database connection established")

        # Get the correct studentclass_id for this student and class
        student_class = conn.execute('''
            SELECT sc.studentclass_id FROM student_class sc
            WHERE sc.student_id = ? AND sc.class_id = ?
        ''', (student_id, class_id)).fetchone()

        if not student_class:
            print(f"No student_class found for student_id: {student_id}")
            conn.close()
            return jsonify({'success': False, 'message': 'Student not enrolled in any class'})

        studentclass_id = student_class['studentclass_id']
        print(f"Found studentclass_id: {studentclass_id} for student_id: {student_id}")

        # Check if already marked today
        today = datetime.now().strftime('%Y-%m-%d')
        print(f"Checking for existing attendance on {today}")
        existing = conn.execute('''
            SELECT attendance_id FROM attendance 
            WHERE studentclass_id = ? AND DATE(attendance_date) = ?
        ''', (studentclass_id, today)).fetchone()

        if existing:
            print("Already marked today")
            conn.close()
            return jsonify({'success': False, 'message': 'Already marked today'})

        # Determine attendance status based on class schedule and late threshold
        from settings_helper import get_late_threshold
        late_threshold_minutes = get_late_threshold()

        # Get class schedule to check if student is late
        class_info = conn.execute('''
            SELECT start_time FROM class WHERE class_id = ?
        ''', (class_id,)).fetchone()

        attendance_status = 'present'  # Default status

        if class_info and class_info['start_time']:
            try:
                # Parse start_time (format: "HH:MM" or "HH:MM:SS")
                start_time_str = class_info['start_time'].strip()
                current_datetime = datetime.now()

                # Try to parse the start time
                try:
                    # Try HH:MM:SS format first
                    scheduled_time = datetime.strptime(start_time_str, '%H:%M:%S').time()
                except ValueError:
                    try:
                        # Try HH:MM format
                        scheduled_time = datetime.strptime(start_time_str, '%H:%M').time()
                    except ValueError:
                        # If parsing fails, default to present
                        scheduled_time = None

                if scheduled_time:
                    # Combine today's date with scheduled time
                    scheduled_datetime = datetime.combine(current_datetime.date(), scheduled_time)

                    # Calculate time difference in minutes
                    time_diff_minutes = (current_datetime - scheduled_datetime).total_seconds() / 60

                    # Check if student is late (arrived after schedule + threshold)
                    if time_diff_minutes > late_threshold_minutes:
                        attendance_status = 'late'
                        print(f"Student is late: arrived {time_diff_minutes:.1f} minutes after scheduled time (threshold: {late_threshold_minutes} min)")
                    else:
                        print(f"Student is on time: arrived {time_diff_minutes:.1f} minutes after scheduled time")
            except Exception as e:
                print(f"Error determining late status: {e}")
                # Default to present if there's an error
                attendance_status = 'present'

        # Insert attendance record with determined status
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"Inserting attendance record: studentclass_id={studentclass_id}, time={current_time}, status={attendance_status}")
        conn.execute('''
            INSERT INTO attendance (studentclass_id, attendance_date, attendance_status)
            VALUES (?, ?, ?)
        ''', (studentclass_id, current_time, attendance_status))
        
        conn.commit()
        print(f"Attendance record inserted successfully with status: {attendance_status}")
        conn.close()
        
        # Create immediate notification for every attendance action
        if NOTIFICATIONS_AVAILABLE:
            try:
                # Get student_id and user_id from the database (using numeric student_id)
                conn = get_db_connection()
                student_record = conn.execute('''
                    SELECT s.student_id, s.user_id
                    FROM student s
                    WHERE s.student_id = ?
                ''', (student_id,)).fetchone()
                
                if student_record:
                    db_student_id = student_record['student_id']
                    student_user_id = student_record['user_id']
                    
                    # Get class details
                    class_info = conn.execute('''
                        SELECT class_name, edpcode, start_time, end_time
                        FROM class WHERE class_id = ?
                    ''', (class_id,)).fetchone()
                    
                    class_label = 'your class'
                    if class_info:
                        class_dict = dict(class_info)
                        base_name = class_dict.get('class_name') or 'your class'
                        edp_code = class_dict.get('edpcode')
                        schedule = ''
                        if class_dict.get('start_time') and class_dict.get('end_time'):
                            try:
                                start_dt = datetime.strptime(str(class_dict['start_time']), '%H:%M:%S')
                                end_dt = datetime.strptime(str(class_dict['end_time']), '%H:%M:%S')
                                schedule = f" [{start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}]"
                            except Exception:
                                pass
                        if edp_code:
                            class_label = f"{base_name} ({edp_code}){schedule}"
                        else:
                            class_label = f"{base_name}{schedule}"
                    
                    # Create immediate notification based on status
                    current_time_str = datetime.now().strftime('%I:%M %p')
                    
                    if attendance_status == 'present':
                        notification_msg = f'✅ Attendance marked successfully for {class_label} at {current_time_str}.'
                        create_notification(student_user_id, notification_msg, 'attendance_present')
                    elif attendance_status == 'late':
                        notification_msg = f'⚠️ You were marked LATE for {class_label} at {current_time_str}. Please arrive on time next time.'
                        create_notification(student_user_id, notification_msg, 'attendance_late')
                    
                    # Check and notify for absences threshold
                    check_and_notify_absences(db_student_id)
                    # Check for late conversions
                    convert_lates_to_absent(db_student_id)
                    
                conn.close()
            except Exception as e:
                print(f"Error checking notifications: {e}")
        
        # Create appropriate message based on status
        if attendance_status == 'late':
            message = f'Attendance marked for {student_name} (LATE)'
        else:
            message = f'Attendance marked for {student_name}'
        
        session.pop('last_live_check', None)

        return jsonify({
            'success': True,
            'message': message,
            'student_id': student_id,
            'student_name': student_name,
            'attendance_status': attendance_status,
            'time': datetime.now().strftime('%H:%M:%S')
        })
        
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/attendance', methods=['POST'])
def api_mark_attendance():
    data = request.get_json()
    student_id = data.get('student_id')
    status = data.get('status', 'present')
    
    if not student_id:
        return jsonify({'error': 'Student ID required'}), 400
    
    conn = get_db_connection()
    
    # Get student_class_id
    student_class = conn.execute('''
        SELECT sc.studentclass_id FROM student_class sc
        JOIN student s ON sc.student_id = s.student_id
        WHERE s.user_id = ?
    ''', (student_id,)).fetchone()
    
    if student_class:
        # Insert attendance record
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('''
            INSERT INTO attendance (attendance_date, attendance_status, studentclass_id)
            VALUES (?, ?, ?)
        ''', (current_time, status, student_class['studentclass_id']))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Attendance marked successfully'})
    else:
        conn.close()
        return jsonify({'error': 'Student not enrolled in any class'}), 400

@app.route('/api/attendance/today')
def api_today_attendance():
    today = datetime.now().strftime('%Y-%m-%d')
    class_id = request.args.get('class_id')
    
    if not class_id:
        return jsonify([])
    
    # Auto-mark absent students if enabled and it's end of day (after 6 PM)
    # Only run once per request to avoid multiple calls
    try:
        current_hour = datetime.now().hour
        if current_hour >= 18:  # After 6 PM, consider it end of day
            auto_mark_absent()
    except Exception as e:
        print(f"Error in auto-mark absent: {e}")
    
    conn = get_db_connection()
    
    attendance = conn.execute('''
        SELECT s.student_id, u.firstname, u.lastname, a.attendance_status, a.attendance_date
        FROM attendance a
        JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
        JOIN student s ON sc.student_id = s.student_id
        JOIN user u ON s.user_id = u.user_id
        WHERE DATE(a.attendance_date) = ? AND sc.class_id = ?
        ORDER BY a.attendance_date DESC
    ''', (today, class_id)).fetchall()
    
    # Format the data for frontend
    formatted_attendance = []
    for record in attendance:
        # Extract time from datetime string and format to 12-hour
        time_str = ''
        if record['attendance_date']:
            try:
                if isinstance(record['attendance_date'], str):
                    # Parse the datetime string and format to 12-hour
                    # Handle both with and without microseconds
                    try:
                        dt = datetime.strptime(record['attendance_date'], '%Y-%m-%d %H:%M:%S.%f')
                    except ValueError:
                        dt = datetime.strptime(record['attendance_date'], '%Y-%m-%d %H:%M:%S')
                    time_str = dt.strftime('%I:%M %p')
                else:
                    time_str = record['attendance_date'].strftime('%I:%M %p')
            except:
                time_str = str(record['attendance_date'])
        
        formatted_attendance.append({
            'student_id': record['student_id'],
            'student_name': f"{record['firstname']} {record['lastname']}",
            'time': time_str,
            'status': record['attendance_status']
        })
    
    conn.close()
    return jsonify(formatted_attendance)

@app.route('/api/attendance/auto-mark-absent', methods=['POST'])
def api_auto_mark_absent():
    """API endpoint to manually trigger auto-mark absent"""
    if 'user_id' not in session or session['role'] not in ['admin', 'faculty']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        count = auto_mark_absent()
        return jsonify({
            'success': True,
            'message': f'Successfully marked {count} students as absent',
            'count': count
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Error: {str(e)}'
        }), 500

@app.route('/api/attendance/override', methods=['POST'])
def api_attendance_override():
    """Override attendance for a student (faculty only)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized - Please login'}), 401
    
    # Only faculty and admin can override attendance
    if session.get('role') not in ['faculty', 'admin']:
        return jsonify({'success': False, 'message': 'Unauthorized - Faculty or Admin access required'}), 401
    
    try:
        data = request.get_json()
        print(f"Attendance override request data: {data}")
        
        student_id = data.get('student_id')
        class_id = data.get('class_id')
        status = data.get('status', 'present')  # 'present', 'absent', 'late', or 'excuse'
        override_reason = data.get('reason', 'Manual override by faculty')
        
        if not student_id or not class_id:
            return jsonify({'success': False, 'message': 'Missing student or class information'}), 400
        
        if status not in ['present', 'absent', 'late', 'excuse']:
            return jsonify({'success': False, 'message': 'Invalid status. Must be "present", "absent", "late", or "excuse"'}), 400
        
        conn = get_db_connection()
        
        # Get student info
        student = conn.execute('''
            SELECT s.student_id, s.user_id, u.firstname, u.lastname
            FROM student s
            JOIN user u ON s.user_id = u.user_id
            WHERE s.student_id = ?
        ''', (student_id,)).fetchone()
        
        if not student:
            conn.close()
            return jsonify({'success': False, 'message': 'Student not found'}), 404
        
        # Get student_class_id
        student_class = conn.execute('''
            SELECT sc.studentclass_id 
            FROM student_class sc
            WHERE sc.student_id = ? AND sc.class_id = ?
        ''', (student_id, class_id)).fetchone()
        
        if not student_class:
            conn.close()
            return jsonify({'success': False, 'message': 'Student not enrolled in this class'}), 404
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Check if attendance already exists for today
        existing_attendance = conn.execute('''
            SELECT attendance_id, attendance_status 
            FROM attendance 
            WHERE studentclass_id = ? AND DATE(attendance_date) = ?
        ''', (student_class['studentclass_id'], today)).fetchone()
        
        if existing_attendance:
            # Update existing attendance
            conn.execute('''
                UPDATE attendance 
                SET attendance_status = ?, attendance_date = ?
                WHERE attendance_id = ?
            ''', (status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), existing_attendance['attendance_id']))
            action = 'updated'
            print(f"Updated attendance for student {student_id}: {status} (Reason: {override_reason})")
        else:
            # Insert new attendance record
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute('''
                INSERT INTO attendance (attendance_date, attendance_status, studentclass_id)
                VALUES (?, ?, ?)
            ''', (current_time, status, student_class['studentclass_id']))
            action = 'created'
            print(f"Created new attendance for student {student_id}: {status} (Reason: {override_reason})")
        
        conn.commit()
        conn.close()
        
        student_name = f"{student['firstname']} {student['lastname']}"
        
        # Create notification for manual override
        if NOTIFICATIONS_AVAILABLE:
            try:
                from notification_system import create_notification
                conn = get_db_connection()
                class_info = conn.execute('SELECT class_name FROM class WHERE class_id = ?', (class_id,)).fetchone()
                class_name = class_info['class_name'] if class_info else 'a class'
                conn.close()
                
                current_time_str = datetime.now().strftime('%I:%M %p')
                
                if status == 'present':
                    notification_msg = f'✅ Your attendance was manually marked as PRESENT for {class_name} at {current_time_str} by faculty.'
                    create_notification(student['user_id'], notification_msg, 'attendance_override_present')
                elif status == 'absent':
                    notification_msg = f'❌ Your attendance was manually marked as ABSENT for {class_name} at {current_time_str} by faculty.'
                    create_notification(student['user_id'], notification_msg, 'attendance_override_absent')
                elif status == 'late':
                    notification_msg = f'⚠️ Your attendance was manually marked as LATE for {class_name} at {current_time_str} by faculty.'
                    create_notification(student['user_id'], notification_msg, 'attendance_override_late')
                elif status == 'excuse':
                    notification_msg = f'📝 Your attendance was manually marked as EXCUSE for {class_name} at {current_time_str} by faculty.'
                    create_notification(student['user_id'], notification_msg, 'attendance_override_excuse')
            except Exception as e:
                print(f"Error creating override notification: {e}")
        
        return jsonify({
            'success': True, 
            'message': f'Attendance {action} for {student_name}: {status.title()}',
            'student_id': student_id,
            'student_name': student_name,
            'status': status,
            'time': datetime.now().strftime('%I:%M %p'),
            'action': action
        })
        
    except Exception as e:
        print(f"Error in attendance override: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/attendance/override', methods=['POST'])
def api_admin_attendance_override():
    """Admin override attendance by attendance_id"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized - Admin access required'}), 401
    
    try:
        data = request.get_json()
        attendance_id = data.get('attendance_id')
        status = data.get('status', 'present')
        reason = data.get('reason', 'Admin override')
        
        if not attendance_id:
            return jsonify({'success': False, 'message': 'Missing attendance ID'}), 400
        
        if status not in ['present', 'late', 'absent', 'excuse']:
            return jsonify({'success': False, 'message': 'Invalid status. Must be present, late, absent, or excuse'}), 400
        
        conn = get_db_connection()
        
        # Get attendance record with student and class info
        attendance = conn.execute('''
            SELECT a.*, sc.student_id, sc.class_id, s.user_id, u.firstname, u.lastname, c.class_name
            FROM attendance a
            JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
            JOIN student s ON sc.student_id = s.student_id
            JOIN user u ON s.user_id = u.user_id
            JOIN class c ON sc.class_id = c.class_id
            WHERE a.attendance_id = ?
        ''', (attendance_id,)).fetchone()
        
        if not attendance:
            conn.close()
            return jsonify({'success': False, 'message': 'Attendance record not found'}), 404
        
        # Update attendance status
        conn.execute('''
            UPDATE attendance 
            SET attendance_status = ?
            WHERE attendance_id = ?
        ''', (status, attendance_id))
        
        conn.commit()
        conn.close()
        
        # Create notification for student
        if NOTIFICATIONS_AVAILABLE:
            try:
                from notification_system import create_notification
                current_time_str = datetime.now().strftime('%I:%M %p on %B %d, %Y')
                class_name = attendance['class_name']
                
                if status == 'present':
                    notification_msg = f'✅ Your attendance was manually updated to PRESENT for {class_name} at {current_time_str} by admin.'
                    create_notification(attendance['user_id'], notification_msg, 'attendance_override_present')
                elif status == 'absent':
                    notification_msg = f'❌ Your attendance was manually updated to ABSENT for {class_name} at {current_time_str} by admin.'
                    create_notification(attendance['user_id'], notification_msg, 'attendance_override_absent')
                elif status == 'late':
                    notification_msg = f'⚠️ Your attendance was manually updated to LATE for {class_name} at {current_time_str} by admin.'
                    create_notification(attendance['user_id'], notification_msg, 'attendance_override_late')
                elif status == 'excuse':
                    notification_msg = f'📝 Your attendance was manually updated to EXCUSE for {class_name} at {current_time_str} by admin.'
                    create_notification(attendance['user_id'], notification_msg, 'attendance_override_excuse')
            except Exception as e:
                print(f"Error creating override notification: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Attendance updated to {status.title()}',
            'attendance_id': attendance_id,
            'status': status
        })
        
    except Exception as e:
        print(f"Error in admin attendance override: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/faculty/attendance/override', methods=['POST'])
def api_faculty_attendance_override():
    """Faculty override attendance by attendance_id (for their own classes)"""
    if 'user_id' not in session or session.get('role') != 'faculty':
        return jsonify({'success': False, 'message': 'Unauthorized - Faculty access required'}), 401
    
    try:
        data = request.get_json()
        attendance_id = data.get('attendance_id')
        status = data.get('status', 'present')
        reason = data.get('reason', 'Faculty override')
        
        if not attendance_id:
            return jsonify({'success': False, 'message': 'Missing attendance ID'}), 400
        
        if status not in ['present', 'late', 'absent', 'excuse']:
            return jsonify({'success': False, 'message': 'Invalid status. Must be present, late, absent, or excuse'}), 400
        
        conn = get_db_connection()
        
        # Get faculty_id
        faculty = conn.execute('''
            SELECT f.faculty_id FROM faculty f
            WHERE f.user_id = ?
        ''', (session['user_id'],)).fetchone()
        
        if not faculty:
            conn.close()
            return jsonify({'success': False, 'message': 'Faculty record not found'}), 404
        
        faculty_id = faculty['faculty_id']
        
        # Get attendance record and verify faculty owns the class
        attendance = conn.execute('''
            SELECT a.*, sc.student_id, sc.class_id, s.user_id, u.firstname, u.lastname, c.class_name, c.faculty_id
            FROM attendance a
            JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
            JOIN student s ON sc.student_id = s.student_id
            JOIN user u ON s.user_id = u.user_id
            JOIN class c ON sc.class_id = c.class_id
            WHERE a.attendance_id = ?
        ''', (attendance_id,)).fetchone()
        
        if not attendance:
            conn.close()
            return jsonify({'success': False, 'message': 'Attendance record not found'}), 404
        
        # Verify faculty owns this class
        if attendance['faculty_id'] != faculty_id:
            conn.close()
            return jsonify({'success': False, 'message': 'Unauthorized - You can only override attendance for your own classes'}), 403
        
        # Update attendance status
        conn.execute('''
            UPDATE attendance 
            SET attendance_status = ?
            WHERE attendance_id = ?
        ''', (status, attendance_id))
        
        conn.commit()
        conn.close()
        
        # Create notification for student
        if NOTIFICATIONS_AVAILABLE:
            try:
                from notification_system import create_notification
                current_time_str = datetime.now().strftime('%I:%M %p on %B %d, %Y')
                class_name = attendance['class_name']
                
                if status == 'present':
                    notification_msg = f'✅ Your attendance was manually updated to PRESENT for {class_name} at {current_time_str} by faculty.'
                    create_notification(attendance['user_id'], notification_msg, 'attendance_override_present')
                elif status == 'absent':
                    notification_msg = f'❌ Your attendance was manually updated to ABSENT for {class_name} at {current_time_str} by faculty.'
                    create_notification(attendance['user_id'], notification_msg, 'attendance_override_absent')
                elif status == 'late':
                    notification_msg = f'⚠️ Your attendance was manually updated to LATE for {class_name} at {current_time_str} by faculty.'
                    create_notification(attendance['user_id'], notification_msg, 'attendance_override_late')
                elif status == 'excuse':
                    notification_msg = f'📝 Your attendance was manually updated to EXCUSE for {class_name} at {current_time_str} by faculty.'
                    create_notification(attendance['user_id'], notification_msg, 'attendance_override_excuse')
            except Exception as e:
                print(f"Error creating override notification: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Attendance updated to {status.title()}',
            'attendance_id': attendance_id,
            'status': status
        })
        
    except Exception as e:
        print(f"Error in faculty attendance override: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/faculty/event/attendance/override', methods=['POST'])
def api_faculty_event_attendance_override():
    """Faculty override event attendance by event_attend_id (for their own events)"""
    if 'user_id' not in session or session.get('role') != 'faculty':
        return jsonify({'success': False, 'message': 'Unauthorized - Faculty access required'}), 401
    
    try:
        data = request.get_json()
        event_attend_id = data.get('event_attend_id')
        status = data.get('status', 'present')
        reason = data.get('reason', 'Faculty override')
        
        if not event_attend_id:
            return jsonify({'success': False, 'message': 'Missing event attendance ID'}), 400
        
        if status not in ['present', 'late', 'absent', 'excuse']:
            return jsonify({'success': False, 'message': 'Invalid status. Must be present, late, absent, or excuse'}), 400
        
        conn = get_db_connection()
        
        # Get faculty_id
        faculty = conn.execute('''
            SELECT f.faculty_id FROM faculty f
            WHERE f.user_id = ?
        ''', (session['user_id'],)).fetchone()
        
        if not faculty:
            conn.close()
            return jsonify({'success': False, 'message': 'Faculty record not found'}), 404
        
        faculty_id = faculty['faculty_id']
        
        # Get event attendance record and verify faculty owns or is assigned to the event
        event_attendance = conn.execute('''
            SELECT ea.*, e.event_name, e.faculty_id, u.user_id as attendee_user_id, u.firstname, u.lastname
            FROM event_attendance ea
            JOIN event e ON ea.event_id = e.event_id
            JOIN user u ON ea.user_id = u.user_id
            WHERE ea.event_attend_id = ?
        ''', (event_attend_id,)).fetchone()
        
        if not event_attendance:
            conn.close()
            return jsonify({'success': False, 'message': 'Event attendance record not found'}), 404
        
        # Verify faculty owns or is assigned to this event
        is_organizer = event_attendance['faculty_id'] == faculty_id
        is_assigned = conn.execute('''
            SELECT 1 FROM event_faculty ef
            WHERE ef.event_id = ? AND ef.faculty_id = ?
        ''', (event_attendance['event_id'], faculty_id)).fetchone() is not None
        
        if not (is_organizer or is_assigned):
            conn.close()
            return jsonify({'success': False, 'message': 'Unauthorized - You can only override attendance for your own events'}), 403
        
        # Update event attendance status
        conn.execute('''
            UPDATE event_attendance 
            SET status = ?
            WHERE event_attend_id = ?
        ''', (status, event_attend_id))
        
        conn.commit()
        conn.close()
        
        # Create notification for attendee
        if NOTIFICATIONS_AVAILABLE:
            try:
                from notification_system import create_notification
                current_time_str = datetime.now().strftime('%I:%M %p on %B %d, %Y')
                event_name = event_attendance['event_name']
                
                if status == 'present':
                    notification_msg = f'✅ Your event attendance was manually updated to PRESENT for {event_name} at {current_time_str} by faculty.'
                    create_notification(event_attendance['attendee_user_id'], notification_msg, 'event_attendance_override_present')
                elif status == 'absent':
                    notification_msg = f'❌ Your event attendance was manually updated to ABSENT for {event_name} at {current_time_str} by faculty.'
                    create_notification(event_attendance['attendee_user_id'], notification_msg, 'event_attendance_override_absent')
                elif status == 'late':
                    notification_msg = f'⚠️ Your event attendance was manually updated to LATE for {event_name} at {current_time_str} by faculty.'
                    create_notification(event_attendance['attendee_user_id'], notification_msg, 'event_attendance_override_late')
                elif status == 'excuse':
                    notification_msg = f'📝 Your event attendance was manually updated to EXCUSE for {event_name} at {current_time_str} by faculty.'
                    create_notification(event_attendance['attendee_user_id'], notification_msg, 'event_attendance_override_excuse')
            except Exception as e:
                print(f"Error creating override notification: {e}")
        
        return jsonify({
            'success': True,
            'message': f'Event attendance updated to {status.title()}',
            'event_attend_id': event_attend_id,
            'status': status
        })
        
    except Exception as e:
        print(f"Error in faculty event attendance override: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/admin/attendance/export/<fmt>')
def admin_attendance_export(fmt):
    """Export admin attendance records in CSV, Excel, or PDF format"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Get filter parameters
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        status_filter = request.args.get('status')
        class_filter = request.args.get('class')
        
        conn = get_db_connection()
        
        # Build query with filters
        query = '''
            SELECT 
                a.attendance_id,
                strftime('%Y-%m-%d %H:%M:%S', a.attendance_date) as attendance_date,
                a.attendance_status,
                u.firstname,
                u.lastname,
                u.idno,
                c.class_name,
                c.edpcode,
                fu.firstname as faculty_firstname,
                fu.lastname as faculty_lastname
            FROM attendance a
            JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
            JOIN student s ON sc.student_id = s.student_id
            JOIN user u ON s.user_id = u.user_id
            JOIN class c ON sc.class_id = c.class_id
            JOIN faculty f ON c.faculty_id = f.faculty_id
            JOIN user fu ON f.user_id = fu.user_id
            WHERE 1=1
        '''
        params = []
        
        if date_from:
            query += ' AND DATE(a.attendance_date) >= ?'
            params.append(date_from)
        if date_to:
            query += ' AND DATE(a.attendance_date) <= ?'
            params.append(date_to)
        if status_filter:
            query += ' AND a.attendance_status = ?'
            params.append(status_filter)
        if class_filter:
            query += ' AND c.class_name LIKE ?'
            params.append(f'%{class_filter}%')
        
        query += ' ORDER BY a.attendance_date DESC, u.lastname, u.firstname'
        
        attendance_records = conn.execute(query, params).fetchall()
        conn.close()
        
        if fmt == 'csv':
            from io import StringIO
            import csv
            output = StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow(['Attendance Records Export'])
            writer.writerow([f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
            if date_from or date_to:
                writer.writerow([f'Date Range: {date_from or "All"} to {date_to or "All"}'])
            writer.writerow([])
            
            # Column headers
            writer.writerow(['Student Name', 'Student ID', 'Class Name', 'EDP Code', 'Faculty', 'Date', 'Status'])
            
            # Format date for better readability
            def format_date_for_export(date_str):
                """Format date string to be more readable"""
                if not date_str:
                    return ''
                try:
                    # Parse and reformat: YYYY-MM-DD HH:MM:SS
                    dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                    return dt.strftime('%Y-%m-%d %H:%M:%S')
                except:
                    return str(date_str)
            
            # Data rows
            for record in attendance_records:
                formatted_date = format_date_for_export(record['attendance_date'])
                writer.writerow([
                    f"{record['firstname']} {record['lastname']}",
                    str(record['idno']),
                    record['class_name'],
                    str(record['edpcode']) if record['edpcode'] else '',
                    f"{record['faculty_firstname']} {record['faculty_lastname']}",
                    formatted_date,
                    record['attendance_status'].title()
                ])
            
            csv_data = output.getvalue()
            output.close()
            
            return app.response_class(
                csv_data,
                mimetype='text/csv',
                headers={
                    'Content-Disposition': f'attachment; filename=attendance_records_{datetime.now().strftime("%Y%m%d")}.csv',
                    'Content-Type': 'text/csv; charset=utf-8'
                }
            )
            
        elif fmt == 'xlsx':
            try:
                from io import BytesIO
                from openpyxl import Workbook
                from openpyxl.styles import Font, PatternFill, Alignment
                from openpyxl.utils import get_column_letter
                
                wb = Workbook()
                ws = wb.active
                ws.title = 'Attendance Records'
                
                # Title
                ws.append(['Attendance Records Export'])
                ws.append([f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
                if date_from or date_to:
                    ws.append([f'Date Range: {date_from or "All"} to {date_to or "All"}'])
                ws.append([])
                
                # Column headers
                headers = ['Student Name', 'Student ID', 'Class Name', 'EDP Code', 'Faculty', 'Date', 'Status']
                ws.append(headers)
                
                # Style header row
                header_font = Font(bold=True, color='FFFFFF')
                header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
                header_alignment = Alignment(horizontal='center', vertical='center')
                
                header_row = 5  # Row 5 is the header row
                for cell in ws[header_row]:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = header_alignment
                
                # Format date for better Excel compatibility
                def format_date_for_excel(date_str):
                    """Format date string to be more Excel-friendly"""
                    if not date_str:
                        return ''
                    try:
                        # Parse the date string and reformat it
                        dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        # Format as: YYYY-MM-DD HH:MM:SS (more readable)
                        return dt.strftime('%Y-%m-%d %H:%M:%S')
                    except:
                        return str(date_str)
                
                # Data rows
                for record in attendance_records:
                    formatted_date = format_date_for_excel(record['attendance_date'])
                    ws.append([
                        f"{record['firstname']} {record['lastname']}",
                        str(record['idno']),
                        record['class_name'],
                        str(record['edpcode']) if record['edpcode'] else '',
                        f"{record['faculty_firstname']} {record['faculty_lastname']}",
                        formatted_date,  # Use formatted date
                        record['attendance_status'].title()
                    ])
                
                # Set column widths explicitly (Date column needs to be wider)
                ws.column_dimensions['A'].width = 20  # Student Name
                ws.column_dimensions['B'].width = 15  # Student ID
                ws.column_dimensions['C'].width = 20  # Class Name
                ws.column_dimensions['D'].width = 12  # EDP Code
                ws.column_dimensions['E'].width = 20  # Faculty
                ws.column_dimensions['F'].width = 20  # Date (wider for full date/time)
                ws.column_dimensions['G'].width = 12  # Status
                
                # Format date column as text to prevent Excel from misinterpreting
                from openpyxl.styles.numbers import FORMAT_TEXT
                date_col = get_column_letter(6)  # Column F
                for row in range(header_row + 1, ws.max_row + 1):
                    cell = ws[f'{date_col}{row}']
                    cell.number_format = FORMAT_TEXT
                
                # Save to BytesIO
                output = BytesIO()
                wb.save(output)
                output.seek(0)
                
                return app.response_class(
                    output.read(),
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={
                        'Content-Disposition': f'attachment; filename=attendance_records_{datetime.now().strftime("%Y%m%d")}.xlsx'
                    }
                )
            except ImportError:
                return jsonify({'error': 'openpyxl library not installed. Install with: pip install openpyxl'}), 500
                
        elif fmt == 'pdf':
            try:
                from io import BytesIO
                from reportlab.lib.pagesizes import letter, landscape
                from reportlab.pdfgen import canvas
                from reportlab.lib.units import inch
                from reportlab.lib import colors
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.enums import TA_CENTER, TA_LEFT
                
                buffer = BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), topMargin=0.5*inch)
                # Set a descriptive PDF title so the browser tab doesn't show "(anonymous)"
                doc.title = f"FaceCheck Reports - {report_type.title()} ({date_from or 'All'} to {date_to or 'All'})"
                elements = []
                
                styles = getSampleStyleSheet()
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontSize=16,
                    textColor=colors.HexColor('#1F2937'),
                    spaceAfter=12,
                    alignment=TA_CENTER
                )
                
                # Title
                elements.append(Paragraph('Attendance Records Export', title_style))
                elements.append(Paragraph(f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', styles['Normal']))
                if date_from or date_to:
                    elements.append(Paragraph(f'Date Range: {date_from or "All"} to {date_to or "All"}', styles['Normal']))
                elements.append(Spacer(1, 0.2*inch))
                
                # Prepare table data
                table_data = [['Student Name', 'Student ID', 'Class Name', 'EDP Code', 'Faculty', 'Date', 'Status']]
                
                for record in attendance_records:
                    table_data.append([
                        f"{record['firstname']} {record['lastname']}",
                        record['idno'],
                        record['class_name'],
                        record['edpcode'],
                        f"{record['faculty_firstname']} {record['faculty_lastname']}",
                        record['attendance_date'],
                        record['attendance_status'].title()
                    ])
                
                # Create table
                table = Table(table_data, repeatRows=1)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('FONTSIZE', (0, 1), (-1, -1), 8),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                ]))
                
                elements.append(table)
                
                # Build PDF
                doc.build(elements)
                buffer.seek(0)
                
                return app.response_class(
                    buffer.read(),
                    mimetype='application/pdf',
                    headers={
                        'Content-Disposition': f'attachment; filename=attendance_records_{datetime.now().strftime("%Y%m%d")}.pdf'
                    }
                )
            except ImportError:
                return jsonify({'error': 'reportlab library not installed. Install with: pip install reportlab'}), 500
        else:
            return jsonify({'error': 'Invalid format. Use csv, xlsx, or pdf'}), 400
            
    except Exception as e:
        print(f"Error in admin attendance export: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/students/by-class/<int:class_id>')
def api_students_by_class(class_id):
    """Get all students enrolled in a specific class"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Allow both faculty and admin
    if session.get('role') not in ['faculty', 'admin']:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    
    students = conn.execute('''
        SELECT s.student_id, u.firstname, u.lastname, u.idno
        FROM student_class sc
        JOIN student s ON sc.student_id = s.student_id
        JOIN user u ON s.user_id = u.user_id
        WHERE sc.class_id = ? AND u.is_active = 1
        ORDER BY u.lastname, u.firstname
    ''', (class_id,)).fetchall()
    
    conn.close()
    
    return jsonify([{
        'student_id': record['student_id'],
        'student_name': f"{record['firstname']} {record['lastname']}",
        'idno': record['idno']
    } for record in students])

@app.route('/api/faculty/classes')
def api_faculty_classes():
    """Get classes assigned to the current faculty member"""
    if 'user_id' not in session or session['role'] != 'faculty':
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    
    # First get the faculty_id for the current user
    faculty = conn.execute('''
        SELECT f.faculty_id FROM faculty f
        WHERE f.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    if not faculty:
        conn.close()
        return jsonify([])
    
    # Then get classes assigned to this faculty (only active classes)
    classes = conn.execute('''
        SELECT c.class_id, c.class_name, c.edpcode, c.start_time, c.end_time, c.room, c.faculty_id
        FROM class c
        WHERE c.faculty_id = ? AND c.is_active = 1
        ORDER BY c.class_name
    ''', (faculty['faculty_id'],)).fetchall()
    
    conn.close()
    return jsonify([dict(record) for record in classes])

@app.route('/api/faculty/events')
def api_faculty_events():
    """Get events assigned to the current faculty member (via event_faculty table)"""
    if 'user_id' not in session or session['role'] != 'faculty':
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    
    # First get the faculty_id for the current user
    faculty = conn.execute('''
        SELECT f.faculty_id FROM faculty f
        WHERE f.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    if not faculty:
        conn.close()
        return jsonify([])
    
    # Get events where this faculty is the ORGANIZER (only organizers can take attendance, only active events)
    # Faculty participants will see events in their "My Classes/Events" but cannot take attendance
    events = conn.execute('''
        SELECT e.event_id, e.event_name, e.description, e.event_date, 
               e.start_time, e.end_time, e.room
        FROM event e
        WHERE e.faculty_id = ? AND e.is_active = 1
        ORDER BY e.event_date DESC
    ''', (faculty['faculty_id'],)).fetchall()
    
    conn.close()
    return jsonify([dict(record) for record in events])

@app.route('/api/faculty/all')
def api_faculty_all():
    """Get all active faculty members"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    
    faculty_list = conn.execute('''
        SELECT u.user_id, u.firstname, u.lastname, u.idno,
               (u.firstname || ' ' || u.lastname) as faculty_name
        FROM user u
        JOIN faculty f ON u.user_id = f.user_id
        WHERE u.is_active = 1
        ORDER BY u.firstname, u.lastname
    ''').fetchall()
    
    conn.close()
    return jsonify([dict(record) for record in faculty_list])

@app.route('/api/event/<int:event_id>/faculty')
def api_event_faculty(event_id):
    """Get faculty participants for an event (for organizer's attendance page)"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    
    # Check if current user is the organizer
    event = conn.execute('SELECT faculty_id FROM event WHERE event_id = ?', (event_id,)).fetchone()
    if not event:
        conn.close()
        return jsonify({'error': 'Event not found'}), 404
    
    # Get current user's faculty_id
    current_faculty = conn.execute('''
        SELECT f.faculty_id FROM faculty f WHERE f.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    if not current_faculty:
        conn.close()
        return jsonify({'error': 'Faculty record not found'}), 404
    
    # Only organizer can see the list
    if event['faculty_id'] != current_faculty['faculty_id'] and session.get('role') != 'admin':
        conn.close()
        return jsonify({'error': 'Only the event organizer can view faculty participants'}), 403
    
    # Get faculty participants ONLY (from event_faculty table) - EXCLUDE organizer
    # Organizer doesn't need to mark attendance, they take attendance for others
    organizer_id = event['faculty_id']
    faculty_list = conn.execute('''
        SELECT DISTINCT u.user_id, u.firstname, u.lastname, u.idno,
               (u.firstname || ' ' || u.lastname) as faculty_name,
               f.attendance_image
        FROM event_faculty ef
        JOIN faculty f ON ef.faculty_id = f.faculty_id
        JOIN user u ON f.user_id = u.user_id
        WHERE ef.event_id = ? AND ef.faculty_id != ? AND u.is_active = 1
        ORDER BY u.firstname, u.lastname
    ''', (event_id, organizer_id)).fetchall()
    
    conn.close()
    return jsonify([dict(record) for record in faculty_list])

@app.route('/api/event/attendance/mark', methods=['POST'])
def api_event_attendance_mark():
    """Mark attendance for a faculty member at an event - Only organizer can mark for others"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        print(f"Event attendance mark request: {data}")
        
        person_id = data.get('person_id')
        event_id = data.get('event_id')
        
        if not event_id:
            return jsonify({'success': False, 'message': 'Event ID required'}), 400

        is_live_ok, live_message = require_recent_live_check(person_id, 'event', event_id=event_id)
        if not is_live_ok:
            return jsonify({'success': False, 'message': live_message, 'error_code': 'LIVENESS_REQUIRED'}), 403
        
        conn = get_db_connection()
        
        # Get event and check if current user is the organizer
        event = conn.execute('SELECT faculty_id FROM event WHERE event_id = ?', (event_id,)).fetchone()
        if not event:
            conn.close()
            return jsonify({'success': False, 'message': 'Event not found'}), 404
        
        # Get current user's faculty_id
        current_faculty = conn.execute('''
            SELECT f.faculty_id FROM faculty f WHERE f.user_id = ?
        ''', (session['user_id'],)).fetchone()
        
        if not current_faculty:
            conn.close()
            return jsonify({'success': False, 'message': 'Faculty record not found'}), 404
        
        is_organizer = event['faculty_id'] == current_faculty['faculty_id']
        
        # Get the person's user_id
        person_user = conn.execute('SELECT user_id FROM user WHERE user_id = ?', (person_id,)).fetchone()
        if not person_user:
            conn.close()
            return jsonify({'success': False, 'message': 'Person not found'}), 404
        
        # Only organizer can mark attendance (no self-check-in for faculty participants)
        if not is_organizer:
            conn.close()
            return jsonify({
                'success': False, 
                'message': 'Only the event organizer can mark attendance. Please have the organizer mark your attendance.'
            }), 403
        
        # Verify the person being marked is assigned to this event (or is the organizer)
        if person_user['user_id'] != session['user_id']:
            # Check if they're assigned to this event
            person_faculty = conn.execute('''
                SELECT f.faculty_id FROM faculty f WHERE f.user_id = ?
            ''', (person_user['user_id'],)).fetchone()
            
            if person_faculty:
                # Check if they're the organizer
                if person_faculty['faculty_id'] != event['faculty_id']:
                    # Check if they're assigned to the event
                    assigned = conn.execute('''
                        SELECT eventfaculty_id FROM event_faculty 
                        WHERE event_id = ? AND faculty_id = ?
                    ''', (event_id, person_faculty['faculty_id'])).fetchone()
                    
                    if not assigned:
                        conn.close()
                        return jsonify({
                            'success': False, 
                            'message': 'This faculty member is not assigned to this event'
                        }), 403
        
        # Check if user exists
        user = conn.execute('SELECT * FROM user WHERE user_id = ?', (person_id,)).fetchone()
        if not user:
            conn.close()
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        # Check if already marked today
        today = datetime.now().strftime('%Y-%m-%d')
        existing = conn.execute('''
            SELECT event_attend_id FROM event_attendance 
            WHERE event_id = ? AND user_id = ? AND DATE(attendance_time) = ?
        ''', (event_id, person_id, today)).fetchone()
        
        if existing:
            conn.close()
            return jsonify({'success': False, 'message': 'Already marked today'}), 400
        
        # Mark attendance
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('''
            INSERT INTO event_attendance (attendance_time, status, event_id, user_id)
            VALUES (?, ?, ?, ?)
        ''', (current_time, 'present', event_id, person_id))
        
        conn.commit()
        conn.close()
        
        session.pop('last_live_check', None)

        return jsonify({
            'success': True,
            'message': f'Attendance marked for {user["firstname"]} {user["lastname"]}'
        })
        
    except Exception as e:
        print(f"Error marking event attendance: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/event/attendance/today')
def api_event_attendance_today():
    """Get today's attendance for a specific event - Only organizer can see full list"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    event_id = request.args.get('event_id')
    if not event_id:
        return jsonify([])
    
    conn = get_db_connection()
    
    # Check if user is organizer or admin
    is_admin = session.get('role') == 'admin'
    is_organizer = False
    
    if not is_admin:
        event = conn.execute('SELECT faculty_id FROM event WHERE event_id = ?', (event_id,)).fetchone()
        if event:
            current_faculty = conn.execute('''
                SELECT f.faculty_id FROM faculty f WHERE f.user_id = ?
            ''', (session['user_id'],)).fetchone()
            if current_faculty:
                is_organizer = event['faculty_id'] == current_faculty['faculty_id']
    
    # Only organizer or admin can see full attendance list
    if not is_admin and not is_organizer:
        conn.close()
        return jsonify({'error': 'Only the event organizer can view attendance'}), 403
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Get attendance records for faculty participants ONLY (exclude organizer)
    # Organizer doesn't need to mark attendance, they take attendance for others
    attendance = conn.execute('''
        SELECT ea.user_id, u.firstname, u.lastname,
               (u.firstname || ' ' || u.lastname) as faculty_name,
               ea.status, ea.attendance_time
        FROM event_attendance ea
        JOIN user u ON ea.user_id = u.user_id
        JOIN faculty f ON u.user_id = f.user_id
        JOIN event e ON ea.event_id = e.event_id
        WHERE DATE(ea.attendance_time) = ? AND ea.event_id = ?
        AND f.faculty_id != e.faculty_id  -- Exclude organizer
        AND u.is_active = 1               -- Exclude deactivated users
        ORDER BY ea.attendance_time DESC
    ''', (today, event_id)).fetchall()
    
    # Format the data for frontend
    formatted_attendance = []
    for record in attendance:
        time_str = ''
        if record['attendance_time']:
            try:
                if isinstance(record['attendance_time'], str):
                    dt = datetime.strptime(record['attendance_time'], '%Y-%m-%d %H:%M:%S')
                    time_str = dt.strftime('%I:%M %p')
                else:
                    time_str = record['attendance_time'].strftime('%I:%M %p')
            except:
                time_str = str(record['attendance_time'])
        
        formatted_attendance.append({
            'user_id': record['user_id'],
            'faculty_name': record['faculty_name'],
            'time': time_str,
            'status': record['status']
        })
    
    conn.close()
    return jsonify(formatted_attendance)

@app.route('/api/event/attendance/override', methods=['POST'])
def api_event_attendance_override():
    """Override attendance for a faculty member at an event"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    # Only faculty and admin can override
    if session.get('role') not in ['faculty', 'admin']:
        return jsonify({'success': False, 'message': 'Unauthorized - Faculty or Admin access required'}), 401
    
    try:
        data = request.get_json()
        print(f"Event attendance override request: {data}")
        
        user_id = data.get('user_id')
        event_id = data.get('event_id')
        status = data.get('status', 'present')
        
        if not user_id or not event_id:
            return jsonify({'success': False, 'message': 'Missing user or event information'}), 400
        
        if status not in ['present', 'absent', 'late', 'excuse']:
            return jsonify({'success': False, 'message': 'Invalid status. Must be present, absent, late, or excuse'}), 400
        
        conn = get_db_connection()
        
        # Get user info
        user = conn.execute('SELECT * FROM user WHERE user_id = ?', (user_id,)).fetchone()
        if not user:
            conn.close()
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Check if attendance exists for today
        existing = conn.execute('''
            SELECT event_attend_id FROM event_attendance 
            WHERE event_id = ? AND user_id = ? AND DATE(attendance_time) = ?
        ''', (event_id, user_id, today)).fetchone()
        
        if existing:
            # Update existing
            conn.execute('''
                UPDATE event_attendance 
                SET status = ?, attendance_time = ?
                WHERE event_attend_id = ?
            ''', (status, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), existing['event_attend_id']))
            action = 'updated'
        else:
            # Insert new
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            conn.execute('''
                INSERT INTO event_attendance (attendance_time, status, event_id, user_id)
                VALUES (?, ?, ?, ?)
            ''', (current_time, status, event_id, user_id))
            action = 'created'
        
        conn.commit()
        conn.close()
        
        faculty_name = f"{user['firstname']} {user['lastname']}"
        
        return jsonify({
            'success': True,
            'message': f'Attendance {action} for {faculty_name}: {status.title()}',
            'time': datetime.now().strftime('%I:%M %p')
        })
        
    except Exception as e:
        print(f"Error in event attendance override: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/classes/<int:class_id>/delete', methods=['POST'])
def delete_class(class_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    try:
        # Deactivate the class instead of deleting
        conn.execute('UPDATE class SET is_active = 0 WHERE class_id = ?', (class_id,))
        
        conn.commit()
        flash('Class deactivated successfully', 'success')
        
    except Exception as e:
        flash(f'Error deactivating class: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('admin_classes'))

@app.route('/admin/classes/<int:class_id>/reactivate', methods=['POST'])
def reactivate_class(class_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    try:
        # Reactivate the class
        conn.execute('UPDATE class SET is_active = 1 WHERE class_id = ?', (class_id,))
        
        conn.commit()
        flash('Class reactivated successfully', 'success')
        
    except Exception as e:
        flash(f'Error reactivating class: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('admin_classes'))

@app.route('/admin/events/<int:event_id>/delete', methods=['POST'])
def delete_event(event_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    try:
        # Deactivate the event instead of deleting
        conn.execute('UPDATE event SET is_active = 0 WHERE event_id = ?', (event_id,))
        
        conn.commit()
        flash('Event deactivated successfully', 'success')
        
    except Exception as e:
        flash(f'Error deactivating event: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('admin_events'))

@app.route('/admin/events/<int:event_id>/reactivate', methods=['POST'])
def reactivate_event(event_id):
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    try:
        # Reactivate the event
        conn.execute('UPDATE event SET is_active = 1 WHERE event_id = ?', (event_id,))
        
        conn.commit()
        flash('Event reactivated successfully', 'success')
        
    except Exception as e:
        flash(f'Error reactivating event: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('admin_events'))

@app.route('/admin/attendance')
def admin_attendance():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect(url_for('login'))
    
    # Auto-mark absent students if enabled and it's end of day (after 6 PM)
    try:
        current_hour = datetime.now().hour
        if current_hour >= 18:  # After 6 PM, consider it end of day
            auto_mark_absent()
    except Exception as e:
        print(f"Error in auto-mark absent: {e}")
    
    conn = get_db_connection()
    
    total_records = conn.execute('SELECT COUNT(*) AS total FROM attendance').fetchone()['total']
    
    stats = conn.execute('''
        SELECT
            SUM(CASE WHEN attendance_status = 'present' THEN 1 ELSE 0 END) AS present_count,
            SUM(CASE WHEN attendance_status = 'late' THEN 1 ELSE 0 END) AS late_count,
            SUM(CASE WHEN attendance_status = 'absent' THEN 1 ELSE 0 END) AS absent_count
        FROM attendance
    ''').fetchone()
    
    present_count = stats['present_count'] or 0
    late_count = stats['late_count'] or 0
    absent_count = stats['absent_count'] or 0
    
    # Load all attendance records for client-side pagination
    attendance_records = conn.execute('''
        SELECT 
            a.attendance_id,
            strftime('%Y-%m-%d %H:%M:%S', a.attendance_date) as attendance_date,
            a.attendance_status,
            u.firstname,
            u.lastname,
            u.idno,
            c.class_name,
            c.edpcode,
            fu.firstname as faculty_firstname,
            fu.lastname as faculty_lastname
        FROM attendance a
        JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
        JOIN student s ON sc.student_id = s.student_id
        JOIN user u ON s.user_id = u.user_id
        JOIN class c ON sc.class_id = c.class_id
        JOIN faculty f ON c.faculty_id = f.faculty_id
        JOIN user fu ON f.user_id = fu.user_id
        ORDER BY a.attendance_date DESC, u.lastname, u.firstname
    ''').fetchall()
    
    attendance_rate = ((present_count + late_count) / total_records * 100) if total_records > 0 else 0
    
    conn.close()
    
    return render_template('admin_attendance.html', 
                         attendance_records=attendance_records,
                         total_records=total_records,
                         present_count=present_count,
                         late_count=late_count,
                         absent_count=absent_count,
                         attendance_rate=round(attendance_rate, 1))

@app.route('/reports')
def admin_reports():
    """Render admin reports and analytics page"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    return render_template('admin_reports.html')

@app.route('/api/admin/reports/<report_type>')
def api_admin_reports(report_type):
    """Get report data for admin"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    try:
        conn = get_db_connection()
        
        if report_type == 'class':
            # Class attendance summary
            data = conn.execute('''
                SELECT 
                    DATE(a.attendance_date) as date,
                    c.class_name as name,
                    COUNT(CASE WHEN a.attendance_status = 'present' THEN 1 END) as present,
                    COUNT(CASE WHEN a.attendance_status = 'absent' THEN 1 END) as absent,
                    COUNT(CASE WHEN a.attendance_status = 'late' THEN 1 END) as late,
                    ROUND(COUNT(CASE WHEN a.attendance_status = 'present' THEN 1 END) * 100.0 / COUNT(*), 1) as rate
                FROM attendance a
                JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
                JOIN class c ON sc.class_id = c.class_id
                WHERE DATE(a.attendance_date) BETWEEN ? AND ?
                GROUP BY DATE(a.attendance_date), c.class_id
                ORDER BY date DESC
            ''', (date_from, date_to)).fetchall()
            
        elif report_type == 'event':
            # Event attendance summary
            data = conn.execute('''
                SELECT 
                    DATE(ea.attendance_time) as date,
                    e.event_name as name,
                    COUNT(CASE WHEN ea.status = 'present' THEN 1 END) as present,
                    COUNT(CASE WHEN ea.status = 'absent' THEN 1 END) as absent,
                    COUNT(CASE WHEN ea.status = 'late' THEN 1 END) as late,
                    ROUND(COUNT(CASE WHEN ea.status = 'present' THEN 1 END) * 100.0 / COUNT(*), 1) as rate
                FROM event_attendance ea
                JOIN event e ON ea.event_id = e.event_id
                WHERE DATE(ea.attendance_time) BETWEEN ? AND ?
                GROUP BY DATE(ea.attendance_time), e.event_id
                ORDER BY date DESC
            ''', (date_from, date_to)).fetchall()
            
        elif report_type == 'absence':
            # Absence patterns
            data = conn.execute('''
                SELECT 
                    u.lastname || ', ' || u.firstname as name,
                    DATE(a.attendance_date) as date,
                    0 as present,
                    COUNT(CASE WHEN a.attendance_status = 'absent' THEN 1 END) as absent,
                    COUNT(CASE WHEN a.attendance_status = 'late' THEN 1 END) as late,
                    0 as rate
                FROM attendance a
                JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
                JOIN student s ON sc.student_id = s.student_id
                JOIN user u ON s.user_id = u.user_id
                WHERE DATE(a.attendance_date) BETWEEN ? AND ?
                    AND a.attendance_status IN ('absent', 'late')
                GROUP BY u.user_id, DATE(a.attendance_date)
                ORDER BY date DESC, name
            ''', (date_from, date_to)).fetchall()
            
        elif report_type == 'monthly':
            # Monthly summary
            data = conn.execute('''
                SELECT 
                    strftime('%Y-%m', a.attendance_date) as date,
                    'Monthly Total' as name,
                    COUNT(CASE WHEN a.attendance_status = 'present' THEN 1 END) as present,
                    COUNT(CASE WHEN a.attendance_status = 'absent' THEN 1 END) as absent,
                    COUNT(CASE WHEN a.attendance_status = 'late' THEN 1 END) as late,
                    ROUND(COUNT(CASE WHEN a.attendance_status = 'present' THEN 1 END) * 100.0 / COUNT(*), 1) as rate
                FROM attendance a
                WHERE DATE(a.attendance_date) BETWEEN ? AND ?
                GROUP BY strftime('%Y-%m', a.attendance_date)
                ORDER BY date DESC
            ''', (date_from, date_to)).fetchall()
        else:
            return jsonify({'success': False, 'error': 'Invalid report type'}), 400
        
        # Convert to list of dicts
        details = []
        for row in data:
            details.append({
                'date': row['date'],
                'name': row['name'],
                'present': row['present'],
                'absent': row['absent'],
                'late': row['late'],
                'rate': row['rate']
            })
        
        # Calculate summary
        total_present = sum(d['present'] for d in details)
        total_absent = sum(d['absent'] for d in details)
        total_late = sum(d['late'] for d in details)
        total = total_present + total_absent + total_late
        attendance_rate = round(total_present * 100.0 / total, 1) if total > 0 else 0
        
        # Generate trend data
        trend_labels = []
        trend_present = []
        trend_absent = []
        trend_late = []
        
        for d in details[:10]:  # Last 10 entries for trend
            trend_labels.insert(0, d['date'])
            trend_present.insert(0, d['present'])
            trend_absent.insert(0, d['absent'])
            trend_late.insert(0, d['late'])
        
        conn.close()
        
        return jsonify({
            'success': True,
            'summary': {
                'total_present': total_present,
                'total_absent': total_absent,
                'total_late': total_late,
                'attendance_rate': attendance_rate
            },
            'trend': {
                'labels': trend_labels,
                'present': trend_present,
                'absent': trend_absent,
                'late': trend_late
            },
            'details': details
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/reports/export/<fmt>')
def export_reports(fmt):
    """Export reports in various formats"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    report_type = request.args.get('type', 'class')
    
    try:
        conn = get_db_connection()
        
        # Use the same data logic as api_admin_reports so export matches the on-screen table,
        # but allow date range to be optional (no range = all data).
        params = []
        if report_type == 'class':
            # Class attendance summary
            query = '''
                SELECT 
                    DATE(a.attendance_date) as date,
                    c.class_name as name,
                    COUNT(CASE WHEN a.attendance_status = 'present' THEN 1 END) as present,
                    COUNT(CASE WHEN a.attendance_status = 'absent' THEN 1 END) as absent,
                    COUNT(CASE WHEN a.attendance_status = 'late' THEN 1 END) as late
                FROM attendance a
                JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
                JOIN class c ON sc.class_id = c.class_id
                WHERE 1=1
            '''
            if date_from:
                query += ' AND DATE(a.attendance_date) >= ?'
                params.append(date_from)
            if date_to:
                query += ' AND DATE(a.attendance_date) <= ?'
                params.append(date_to)
            query += ' GROUP BY DATE(a.attendance_date), c.class_id ORDER BY date DESC'
            data = conn.execute(query, params).fetchall()
        
        elif report_type == 'event':
            # Event attendance summary
            query = '''
                SELECT 
                    DATE(ea.attendance_time) as date,
                    e.event_name as name,
                    COUNT(CASE WHEN ea.status = 'present' THEN 1 END) as present,
                    COUNT(CASE WHEN ea.status = 'absent' THEN 1 END) as absent,
                    COUNT(CASE WHEN ea.status = 'late' THEN 1 END) as late
                FROM event_attendance ea
                JOIN event e ON ea.event_id = e.event_id
                WHERE 1=1
            '''
            if date_from:
                query += ' AND DATE(ea.attendance_time) >= ?'
                params.append(date_from)
            if date_to:
                query += ' AND DATE(ea.attendance_time) <= ?'
                params.append(date_to)
            query += ' GROUP BY DATE(ea.attendance_time), e.event_id ORDER BY date DESC'
            data = conn.execute(query, params).fetchall()
        
        elif report_type == 'absence':
            # Absence patterns
            query = '''
                SELECT 
                    u.lastname || ', ' || u.firstname as name,
                    DATE(a.attendance_date) as date,
                    0 as present,
                    COUNT(CASE WHEN a.attendance_status = 'absent' THEN 1 END) as absent,
                    COUNT(CASE WHEN a.attendance_status = 'late' THEN 1 END) as late
                FROM attendance a
                JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
                JOIN student s ON sc.student_id = s.student_id
                JOIN user u ON s.user_id = u.user_id
                WHERE a.attendance_status IN ('absent', 'late')
            '''
            if date_from:
                query += ' AND DATE(a.attendance_date) >= ?'
                params.append(date_from)
            if date_to:
                query += ' AND DATE(a.attendance_date) <= ?'
                params.append(date_to)
            query += ' GROUP BY u.user_id, DATE(a.attendance_date) ORDER BY date DESC, name'
            data = conn.execute(query, params).fetchall()
        
        elif report_type == 'monthly':
            # Monthly summary
            query = '''
                SELECT 
                    strftime('%Y-%m', a.attendance_date) as date,
                    'Monthly Total' as name,
                    COUNT(CASE WHEN a.attendance_status = 'present' THEN 1 END) as present,
                    COUNT(CASE WHEN a.attendance_status = 'absent' THEN 1 END) as absent,
                    COUNT(CASE WHEN a.attendance_status = 'late' THEN 1 END) as late
                FROM attendance a
                WHERE 1=1
            '''
            if date_from:
                query += ' AND DATE(a.attendance_date) >= ?'
                params.append(date_from)
            if date_to:
                query += ' AND DATE(a.attendance_date) <= ?'
                params.append(date_to)
            query += " GROUP BY strftime('%Y-%m', a.attendance_date) ORDER BY date DESC"
            data = conn.execute(query, params).fetchall()
        
        else:
            conn.close()
            flash('Invalid report type for export', 'error')
            return redirect(url_for('admin_reports'))
        
        conn.close()
        
        if fmt == 'csv':
            import io
            import csv
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Date', 'Class/Event', 'Present', 'Absent', 'Late'])
            
            for row in data:
                writer.writerow([row['date'], row['name'], row['present'], row['absent'], row['late']])
            
            response = app.make_response(output.getvalue())
            response.headers['Content-Type'] = 'text/csv'
            response.headers['Content-Disposition'] = f'attachment; filename=report_{report_type}_{date_from}_{date_to}.csv'
            return response
            
        elif fmt == 'excel' or fmt == 'xlsx':
            try:
                from io import BytesIO
                from openpyxl import Workbook
                from openpyxl.styles import Font, PatternFill, Alignment
                from openpyxl.utils import get_column_letter
                
                wb = Workbook()
                ws = wb.active
                ws.title = 'Reports'
                
                # Title
                ws.append(['Reports & Analytics Export'])
                ws.append([f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
                ws.append([f'Date Range: {date_from} to {date_to}'])
                ws.append([f'Report Type: {report_type.title()}'])
                ws.append([])
                
                # Column headers
                headers = ['Date', 'Class/Event', 'Present', 'Absent', 'Late']
                ws.append(headers)
                
                # Style header row
                header_font = Font(bold=True, color='FFFFFF')
                header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
                header_alignment = Alignment(horizontal='center', vertical='center')
                
                header_row = 6  # Row 6 is the header row
                for cell in ws[header_row]:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = header_alignment
                
                # Data rows
                for row in data:
                    ws.append([
                        str(row['date']),
                        row['name'],
                        row['present'],
                        row['absent'],
                        row['late']
                    ])
                
                # Set column widths
                ws.column_dimensions['A'].width = 15  # Date
                ws.column_dimensions['B'].width = 25  # Class/Event
                ws.column_dimensions['C'].width = 12  # Present
                ws.column_dimensions['D'].width = 12  # Absent
                ws.column_dimensions['E'].width = 12  # Late
                
                # Save to BytesIO
                output = BytesIO()
                wb.save(output)
                output.seek(0)
                
                return app.response_class(
                    output.read(),
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={
                        'Content-Disposition': f'attachment; filename=report_{report_type}_{date_from}_{date_to}.xlsx'
                    }
                )
            except ImportError:
                flash('openpyxl library not installed. Install with: pip install openpyxl', 'error')
                return redirect(url_for('admin_reports'))
            except Exception as e:
                flash(f'Excel export failed: {str(e)}', 'error')
                return redirect(url_for('admin_reports'))
                
        elif fmt == 'pdf':
            try:
                from io import BytesIO
                from reportlab.lib.pagesizes import letter, landscape
                from reportlab.pdfgen import canvas
                from reportlab.lib.units import inch
                from reportlab.lib import colors
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.enums import TA_CENTER, TA_LEFT
                
                buffer = BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), topMargin=0.5*inch)
                elements = []
                
                styles = getSampleStyleSheet()
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontSize=16,
                    spaceAfter=30,
                    alignment=TA_CENTER
                )
                
                elements.append(Paragraph('Reports & Analytics Export', title_style))
                elements.append(Paragraph(f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', styles['Normal']))
                elements.append(Paragraph(f'Date Range: {date_from} to {date_to}', styles['Normal']))
                elements.append(Paragraph(f'Report Type: {report_type.title()}', styles['Normal']))
                elements.append(Spacer(1, 20))
                
                # Table data
                table_data = [['Date', 'Class/Event', 'Present', 'Absent', 'Late']]
                for row in data:
                    table_data.append([
                        str(row['date']),
                        row['name'],
                        str(row['present']),
                        str(row['absent']),
                        str(row['late'])
                    ])
                
                table = Table(table_data)
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('FONTSIZE', (0, 1), (-1, -1), 10),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                ]))
                
                elements.append(table)
                doc.build(elements)
                buffer.seek(0)
                
                return app.response_class(
                    buffer.read(),
                    mimetype='application/pdf',
                    headers={
                        'Content-Disposition': f'attachment; filename=report_{report_type}_{date_from}_{date_to}.pdf'
                    }
                )
            except ImportError:
                flash('reportlab library not installed. Install with: pip install reportlab', 'error')
                return redirect(url_for('admin_reports'))
            except Exception as e:
                flash(f'PDF export failed: {str(e)}', 'error')
                return redirect(url_for('admin_reports'))
            
        else:
            flash('Export format not supported', 'error')
            return redirect(url_for('admin_reports'))
            
    except Exception as e:
        flash(f'Export error: {str(e)}', 'error')
        return redirect(url_for('admin_reports'))


# Faculty Manage Students
@app.route('/manage_students')
def faculty_manage_students():
    if 'user_id' not in session or session['role'] != 'faculty':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Add profile_picture column to faculty table if it doesn't exist
    try:
        conn.execute('ALTER TABLE faculty ADD COLUMN profile_picture VARCHAR(255)')
        conn.commit()
    except:
        pass  # Column already exists
    
    # Get faculty info
    faculty = conn.execute('''
        SELECT f.faculty_id, u.firstname, u.lastname, u.idno, f.profile_picture FROM faculty f 
        JOIN user u ON f.user_id = u.user_id 
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    if not faculty:
        conn.close()
        flash('Faculty record not found', 'error')
        return redirect(url_for('faculty_dashboard'))
    
    # Get classes assigned to this faculty
    classes = conn.execute('''
        SELECT c.class_id, c.class_name, c.edpcode
        FROM class c
        WHERE c.faculty_id = ?
        ORDER BY c.class_name
    ''', (faculty['faculty_id'],)).fetchall()
    
    # Get events assigned to this faculty
    events = conn.execute('''
        SELECT e.event_id, e.event_name, e.event_date
        FROM event e
        WHERE e.faculty_id = ?
        ORDER BY e.event_date DESC
    ''', (faculty['faculty_id'],)).fetchall()
    
    conn.close()
    return render_template('faculty/faculty_manage_students.html', classes=classes, events=events, faculty=faculty)

@app.route('/faculty/students/<path:selection>')
def faculty_get_students(selection):
    if 'user_id' not in session or session['role'] != 'faculty':
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    
    # Get faculty info
    faculty = conn.execute('''
        SELECT f.faculty_id FROM faculty f 
        JOIN user u ON f.user_id = u.user_id 
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    if not faculty:
        conn.close()
        return jsonify({'error': 'Faculty record not found'}), 404
    
    students = []
    
    if selection.startswith('class_'):
        class_id = selection.replace('class_', '')
        # Get students enrolled in this class
        students = conn.execute('''
            SELECT u.user_id, u.idno, u.firstname, u.lastname, u.is_active,
                   s.year_level, s.profile_picture, c.course_name
            FROM student_class sc
            JOIN student s ON sc.student_id = s.student_id
            JOIN user u ON s.user_id = u.user_id
            LEFT JOIN course c ON s.course_id = c.course_id
            JOIN class cl ON sc.class_id = cl.class_id
            WHERE sc.class_id = ? AND cl.faculty_id = ? AND u.is_active = 1
            ORDER BY u.firstname, u.lastname
        ''', (class_id, faculty['faculty_id'])).fetchall()
        
    elif selection.startswith('event_'):
        event_id = selection.replace('event_', '')
        # Get students who have attended this event (exclude deactivated)
        students = conn.execute('''
            SELECT DISTINCT u.user_id, u.idno, u.firstname, u.lastname, u.is_active,
                   s.year_level, s.profile_picture, c.course_name
            FROM event_attendance ea
            JOIN user u ON ea.user_id = u.user_id
            JOIN student s ON u.user_id = s.user_id
            LEFT JOIN course c ON s.course_id = c.course_id
            JOIN event e ON ea.event_id = e.event_id
            WHERE ea.event_id = ? AND e.faculty_id = ? AND u.is_active = 1
            ORDER BY u.firstname, u.lastname
        ''', (event_id, faculty['faculty_id'])).fetchall()
    
    conn.close()
    return jsonify([dict(student) for student in students])

@app.route('/faculty/students/edit', methods=['POST'])
def faculty_edit_student():
    if 'user_id' not in session or session['role'] != 'faculty':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        firstname = data.get('firstname')
        lastname = data.get('lastname')
        year_level = data.get('year_level')
        is_active = data.get('is_active')
        
        if not all([user_id, firstname, lastname]):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        conn = get_db_connection()
        
        # Verify faculty has access to this student (through classes/events)
        faculty = conn.execute('''
            SELECT f.faculty_id FROM faculty f 
            JOIN user u ON f.user_id = u.user_id 
            WHERE u.user_id = ?
        ''', (session['user_id'],)).fetchone()
        
        if not faculty:
            conn.close()
            return jsonify({'success': False, 'message': 'Faculty record not found'}), 404
        
        # Check if student is in faculty's classes or events
        student_access = conn.execute('''
            SELECT 1 FROM student_class sc
            JOIN class c ON sc.class_id = c.class_id
            JOIN student s ON sc.student_id = s.student_id
            WHERE s.user_id = ? AND c.faculty_id = ?
            UNION
            SELECT 1 FROM event_attendance ea
            JOIN event e ON ea.event_id = e.event_id
            WHERE ea.user_id = ? AND e.faculty_id = ?
        ''', (user_id, faculty['faculty_id'], user_id, faculty['faculty_id'])).fetchone()
        
        if not student_access:
            conn.close()
            return jsonify({'success': False, 'message': 'You do not have permission to edit this student'}), 403
        
        # Update user information
        conn.execute('''
            UPDATE user SET firstname = ?, lastname = ?, is_active = ?
            WHERE user_id = ?
        ''', (firstname, lastname, is_active, user_id))
        
        # Update student information if year_level is provided
        if year_level:
            conn.execute('''
                UPDATE student SET year_level = ?
                WHERE user_id = ?
            ''', (year_level, user_id))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Student updated successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error updating student: {str(e)}'}), 500

@app.route('/faculty/students/reset-password', methods=['POST'])
def faculty_reset_student_password():
    if 'user_id' not in session or session['role'] != 'faculty':
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        new_password = data.get('new_password')
        
        if not all([user_id, new_password]):
            return jsonify({'success': False, 'message': 'Missing required fields'}), 400
        
        conn = get_db_connection()
        
        # Verify faculty has access to this student (through classes/events)
        faculty = conn.execute('''
            SELECT f.faculty_id FROM faculty f 
            JOIN user u ON f.user_id = u.user_id 
            WHERE u.user_id = ?
        ''', (session['user_id'],)).fetchone()
        
        if not faculty:
            conn.close()
            return jsonify({'success': False, 'message': 'Faculty record not found'}), 404
        
        # Check if student is in faculty's classes or events
        student_access = conn.execute('''
            SELECT 1 FROM student_class sc
            JOIN class c ON sc.class_id = c.class_id
            JOIN student s ON sc.student_id = s.student_id
            WHERE s.user_id = ? AND c.faculty_id = ?
            UNION
            SELECT 1 FROM event_attendance ea
            JOIN event e ON ea.event_id = e.event_id
            WHERE ea.user_id = ? AND e.faculty_id = ?
        ''', (user_id, faculty['faculty_id'], user_id, faculty['faculty_id'])).fetchone()
        
        if not student_access:
            conn.close()
            return jsonify({'success': False, 'message': 'You do not have permission to reset this student\'s password'}), 403
        
        # Update password
        conn.execute('UPDATE user SET password = ? WHERE user_id = ?', (new_password, user_id))
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Password reset successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error resetting password: {str(e)}'}), 500

@app.route('/faculty/students/profile/<int:user_id>')
def faculty_student_profile(user_id):
    if 'user_id' not in session or session['role'] != 'faculty':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    
    faculty = conn.execute('''
        SELECT f.faculty_id FROM faculty f 
        JOIN user u ON f.user_id = u.user_id 
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    if not faculty:
        conn.close()
        return jsonify({'success': False, 'message': 'Faculty record not found'}), 404
    
    student_info = conn.execute('''
        SELECT u.user_id, u.idno, u.firstname, u.lastname, u.created_at, u.is_active,
               s.student_id, s.year_level, s.attendance_image, s.profile_picture,
               c.course_name, d.dept_name
        FROM user u
        JOIN student s ON u.user_id = s.user_id
        LEFT JOIN course c ON s.course_id = c.course_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE u.user_id = ?
    ''', (user_id,)).fetchone()
    
    if not student_info:
        conn.close()
        return jsonify({'success': False, 'message': 'Student not found'}), 404
    
    # Verify access
    access = conn.execute('''
        SELECT 1 FROM student_class sc
        JOIN class c ON sc.class_id = c.class_id
        JOIN student s ON sc.student_id = s.student_id
        WHERE s.user_id = ? AND c.faculty_id = ?
        UNION
        SELECT 1 FROM event_attendance ea
        JOIN event e ON ea.event_id = e.event_id
        WHERE ea.user_id = ? AND e.faculty_id = ?
    ''', (user_id, faculty['faculty_id'], user_id, faculty['faculty_id'])).fetchone()
    
    if not access:
        conn.close()
        return jsonify({'success': False, 'message': 'You do not have permission to view this student'}), 403
    
    student_id = student_info['student_id']
    
    stats = conn.execute('''
        SELECT 
            COUNT(*) as total_records,
            SUM(CASE WHEN a.attendance_status = 'present' THEN 1 ELSE 0 END) as present_count,
            SUM(CASE WHEN a.attendance_status = 'late' THEN 1 ELSE 0 END) as late_count,
            SUM(CASE WHEN a.attendance_status = 'absent' THEN 1 ELSE 0 END) as absent_count
        FROM attendance a
        JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
        WHERE sc.student_id = ?
    ''', (student_id,)).fetchone()
    
    total_records = stats['total_records'] or 0
    present_count = stats['present_count'] or 0
    late_count = stats['late_count'] or 0
    absent_count = stats['absent_count'] or 0
    attendance_rate = round((present_count / total_records * 100), 1) if total_records > 0 else 0
    
    last_attendance = conn.execute('''
        SELECT a.attendance_status, a.attendance_date, cl.class_name
        FROM attendance a
        JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
        JOIN class cl ON sc.class_id = cl.class_id
        WHERE sc.student_id = ?
        ORDER BY a.attendance_date DESC
        LIMIT 1
    ''', (student_id,)).fetchone()
    
    classes = conn.execute('''
        SELECT cl.class_name, cl.edpcode, cl.room,
               GROUP_CONCAT(DISTINCT d.day_name) as days,
               cl.start_time, cl.end_time
        FROM student_class sc
        JOIN class cl ON sc.class_id = cl.class_id
        LEFT JOIN class_days cd ON cl.class_id = cd.class_id
        LEFT JOIN days d ON cd.day_id = d.day_id
        WHERE sc.student_id = ? AND cl.faculty_id = ?
        GROUP BY cl.class_name, cl.edpcode, cl.room, cl.start_time, cl.end_time
        ORDER BY cl.class_name
        LIMIT 5
    ''', (student_id, faculty['faculty_id'])).fetchall()
    
    conn.close()
    
    def format_time(value):
        if not value:
            return None
        try:
            return datetime.strptime(str(value), '%H:%M:%S').strftime('%I:%M %p')
        except Exception:
            return str(value)
    
    classes_list = []
    for item in classes:
        schedule_parts = []
        if item['days']:
            schedule_parts.append(item['days'])
        if item['start_time'] and item['end_time']:
            schedule_parts.append(f"{format_time(item['start_time'])} - {format_time(item['end_time'])}")
        classes_list.append({
            'name': item['class_name'],
            'code': item['edpcode'],
            'room': item['room'],
            'schedule': ' • '.join(schedule_parts) if schedule_parts else 'Schedule not set'
        })
    
    last_attendance_data = None
    if last_attendance:
        try:
            attendance_dt = datetime.strptime(last_attendance['attendance_date'], '%Y-%m-%d %H:%M:%S')
            formatted_dt = attendance_dt.strftime('%B %d, %Y %I:%M %p')
        except Exception:
            formatted_dt = last_attendance['attendance_date']
        last_attendance_data = {
            'status': last_attendance['attendance_status'],
            'class_name': last_attendance['class_name'],
            'timestamp': formatted_dt
        }
    
    return jsonify({
        'success': True,
        'student': {
            'user_id': student_info['user_id'],
            'student_id': student_id,
            'idno': student_info['idno'],
            'firstname': student_info['firstname'],
            'lastname': student_info['lastname'],
            'full_name': f"{student_info['firstname']} {student_info['lastname']}",
            'course_name': student_info['course_name'],
            'year_level': student_info['year_level'],
            'dept_name': student_info['dept_name'],
            'is_active': bool(student_info['is_active']),
            'profile_picture': student_info['profile_picture'],
            'attendance_image': student_info['attendance_image'],
            'created_at': student_info['created_at']
        },
        'attendance_stats': {
            'total': total_records,
            'present': present_count,
            'late': late_count,
            'absent': absent_count,
            'rate': attendance_rate
        },
        'last_attendance': last_attendance_data,
        'classes': classes_list
    })

@app.route('/faculty/profile')
def faculty_profile():
    """Faculty profile page - similar to student profile"""
    if 'user_id' not in session or session['role'] != 'faculty':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Add profile_picture column to faculty table if it doesn't exist
    try:
        conn.execute('ALTER TABLE faculty ADD COLUMN profile_picture VARCHAR(255)')
        conn.commit()
    except:
        pass  # Column already exists
    
    # Get comprehensive faculty info
    faculty = conn.execute('''
        SELECT u.*, f.faculty_id, f.position, f.attendance_image, f.profile_picture, d.dept_name
        FROM user u
        JOIN faculty f ON u.user_id = f.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    # Get classes assigned to this faculty
    classes = conn.execute('''
        SELECT cl.class_id, cl.class_name, cl.edpcode, cl.start_time, cl.end_time, cl.room,
               GROUP_CONCAT(DISTINCT d.day_name) as days,
               COUNT(DISTINCT sc.student_id) as student_count
        FROM class cl
        LEFT JOIN student_class sc ON cl.class_id = sc.class_id
        LEFT JOIN class_days cd ON cl.class_id = cd.class_id
        LEFT JOIN days d ON cd.day_id = d.day_id
        WHERE cl.faculty_id = ?
        GROUP BY cl.class_id, cl.class_name, cl.edpcode, cl.start_time, cl.end_time, cl.room
        ORDER BY cl.class_name
    ''', (faculty['faculty_id'],)).fetchall()
    
    # Format classes with schedule
    formatted_classes = []
    for class_item in classes:
        time_str = ''
        if class_item['start_time'] and class_item['end_time']:
            try:
                start_dt = datetime.strptime(str(class_item['start_time']), '%H:%M:%S')
                end_dt = datetime.strptime(str(class_item['end_time']), '%H:%M:%S')
                time_str = f"{start_dt.strftime('%I:%M %p')} - {end_dt.strftime('%I:%M %p')}"
            except:
                time_str = f"{class_item['start_time']} - {class_item['end_time']}"
        
        days_str = class_item['days'] or 'Schedule not set'
        schedule = f"{days_str} • {time_str}" if time_str else days_str
        
        formatted_classes.append({
            'class_name': class_item['class_name'],
            'edpcode': class_item['edpcode'],
            'schedule': schedule,
            'room': class_item['room'],
            'student_count': class_item['student_count'] or 0
        })
    
    # Check face registration status (database first, then filesystem)
    has_face_registered = False
    if faculty['attendance_image']:
        # attendance_image should already contain the correct relative path
        if os.path.exists(faculty['attendance_image']):
            has_face_registered = True
        else:
            conn.execute('UPDATE faculty SET attendance_image = NULL WHERE user_id = ?', (session['user_id'],))
            conn.commit()
    
    # Fallback: check common faculty face image locations and update database
    if not has_face_registered:
        possible_paths = [
            f"known_faces/faculty_{faculty['idno']}.jpg",  # current faculty registration pattern
            f"known_faces/{faculty['idno']}.jpg",          # legacy pattern without prefix
        ]
        for face_image_path in possible_paths:
            if os.path.exists(face_image_path):
                conn.execute(
                    'UPDATE faculty SET attendance_image = ? WHERE user_id = ?',
                    (face_image_path, session['user_id'])
                )
                conn.commit()
                has_face_registered = True
                break
    
    # Get today's attendance stats
    today = datetime.now().strftime('%Y-%m-%d')
    today_stats = conn.execute('''
        SELECT COUNT(*) as today_count
        FROM attendance a
        JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
        JOIN class cl ON sc.class_id = cl.class_id
        WHERE cl.faculty_id = ? AND DATE(a.attendance_date) = ?
    ''', (faculty['faculty_id'], today)).fetchone()
    
    # Get total students across all classes
    total_students = conn.execute('''
        SELECT COUNT(DISTINCT sc.student_id) as total
        FROM class c
        JOIN student_class sc ON c.class_id = sc.class_id
        WHERE c.faculty_id = ?
    ''', (faculty['faculty_id'],)).fetchone()
    
    conn.close()
    
    return render_template('faculty/faculty_profile.html',
                         faculty=faculty,
                         classes=formatted_classes,
                         has_face_registered=has_face_registered,
                         today_attendance=today_stats['today_count'] if today_stats else 0,
                         total_students=total_students['total'] if total_students else 0)

@app.route('/faculty/profile/update_name', methods=['POST'])
def update_faculty_name():
    """Allow the currently logged-in faculty to update their first and last name."""
    if 'user_id' not in session or session.get('role') != 'faculty':
        return redirect(url_for('login'))

    firstname = request.form.get('firstname', '').strip()
    lastname = request.form.get('lastname', '').strip()

    if not firstname or not lastname:
        flash('First name and last name are required.', 'error')
        return redirect(url_for('faculty_profile'))

    conn = get_db_connection()
    conn.execute(
        '''
        UPDATE user
        SET firstname = ?, lastname = ?
        WHERE user_id = ?
        ''',
        (firstname, lastname, session['user_id'])
    )
    conn.commit()
    conn.close()

    # Keep the session display name in sync for the dashboard/header
    session['username'] = f"{firstname} {lastname}"

    flash('Profile updated successfully.', 'success')
    return redirect(url_for('faculty_profile'))

# Faculty My Classes
@app.route('/faculty/my_classes')
def faculty_my_classes():
    if 'user_id' not in session or session['role'] != 'faculty':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Add profile_picture column to faculty table if it doesn't exist
    try:
        conn.execute('ALTER TABLE faculty ADD COLUMN profile_picture VARCHAR(255)')
        conn.commit()
    except:
        pass  # Column already exists
    
    # Get faculty info
    faculty_info = conn.execute('''
        SELECT u.*, f.faculty_id, f.position, f.attendance_image, f.profile_picture, d.dept_name
        FROM user u
        JOIN faculty f ON u.user_id = f.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    if not faculty_info:
        conn.close()
        flash('Faculty record not found', 'error')
        return redirect(url_for('faculty_dashboard'))
    
    # Get classes assigned to this faculty with student counts (only active classes)
    classes = conn.execute('''
        SELECT c.*, 
               COUNT(DISTINCT sc.student_id) as student_count,
               GROUP_CONCAT(DISTINCT d.day_name) as days
        FROM class c
        LEFT JOIN student_class sc ON c.class_id = sc.class_id
        LEFT JOIN class_days cd ON c.class_id = cd.class_id
        LEFT JOIN days d ON cd.day_id = d.day_id
        WHERE c.faculty_id = ? AND c.is_active = 1
        GROUP BY c.class_id
        ORDER BY c.class_name
    ''', (faculty_info['faculty_id'],)).fetchall()
    
    # Get events assigned to this faculty with attendee counts (only active events)
    events = conn.execute('''
        SELECT e.*, 
               COUNT(DISTINCT ea.user_id) as attendee_count
        FROM event e
        LEFT JOIN event_attendance ea ON e.event_id = ea.event_id
        WHERE e.faculty_id = ? AND e.is_active = 1
        GROUP BY e.event_id
        ORDER BY e.event_date DESC
    ''', (faculty_info['faculty_id'],)).fetchall()
    
    # Calculate total students across all classes (only active classes)
    total_students = conn.execute('''
        SELECT COUNT(DISTINCT sc.student_id) as total
        FROM class c
        JOIN student_class sc ON c.class_id = sc.class_id
        WHERE c.faculty_id = ? AND c.is_active = 1
    ''', (faculty_info['faculty_id'],)).fetchone()
    
    conn.close()
    return render_template('faculty/faculty_my_classes.html', 
                         faculty_info=faculty_info,
                         classes=classes, 
                         events=events, 
                         total_students=total_students['total'] if total_students else 0)

@app.route('/faculty/class/<int:class_id>')
def faculty_class_view(class_id):
    """Full page view for faculty class details"""
    if 'user_id' not in session or session['role'] != 'faculty':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Add profile_picture column to faculty table if it doesn't exist
    try:
        conn.execute('ALTER TABLE faculty ADD COLUMN profile_picture VARCHAR(255)')
        conn.commit()
    except:
        pass  # Column already exists
    
    # Get faculty info
    faculty = conn.execute('''
        SELECT f.faculty_id, u.firstname, u.lastname, u.idno, f.attendance_image, f.profile_picture
        FROM faculty f 
        JOIN user u ON f.user_id = u.user_id 
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    if not faculty:
        conn.close()
        flash('Faculty record not found', 'error')
        return redirect(url_for('faculty_dashboard'))
    
    # Get class details (only active classes)
    class_info = conn.execute('''
        SELECT c.*, 
               GROUP_CONCAT(DISTINCT d.day_name) as days
        FROM class c
        LEFT JOIN class_days cd ON c.class_id = cd.class_id
        LEFT JOIN days d ON cd.day_id = d.day_id
        WHERE c.class_id = ? AND c.faculty_id = ? AND c.is_active = 1
        GROUP BY c.class_id
    ''', (class_id, faculty['faculty_id'])).fetchone()
    
    if not class_info:
        conn.close()
        flash('Class not found or access denied', 'error')
        return redirect(url_for('faculty_my_classes'))
    
    # Get enrolled students (exclude deactivated users)
    students = conn.execute('''
        SELECT u.idno, u.firstname, u.lastname, s.student_id, s.year_level, 
               c.course_name, d.dept_name, s.profile_picture
        FROM student_class sc
        JOIN student s ON sc.student_id = s.student_id
        JOIN user u ON s.user_id = u.user_id
        LEFT JOIN course c ON s.course_id = c.course_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE sc.class_id = ? AND u.is_active = 1
        ORDER BY u.firstname, u.lastname
    ''', (class_id,)).fetchall()
    
    # Format time (convert from 24-hour to 12-hour with AM/PM)
    def format_time(value):
        if not value:
            return None
        try:
            time_str = str(value)
            # Handle different time formats (HH:MM:SS or HH:MM)
            time_formats = ['%H:%M:%S', '%H:%M']
            for fmt in time_formats:
                try:
                    return datetime.strptime(time_str, fmt).strftime('%I:%M %p')
                except ValueError:
                    continue
            return time_str
        except Exception:
            return str(value)
    
    start_time = format_time(class_info['start_time'])
    end_time = format_time(class_info['end_time'])
    
    conn.close()
    return render_template('faculty/faculty_class_view.html',
                         class_info=class_info,
                         students=students,
                         faculty=faculty,
                         start_time=start_time,
                         end_time=end_time)

@app.route('/faculty/event/<int:event_id>')
def faculty_event_view(event_id):
    """Full page view for faculty event details"""
    if 'user_id' not in session or session['role'] != 'faculty':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Add profile_picture column to faculty table if it doesn't exist
    try:
        conn.execute('ALTER TABLE faculty ADD COLUMN profile_picture VARCHAR(255)')
        conn.commit()
    except:
        pass  # Column already exists
    
    # Get faculty info
    faculty = conn.execute('''
        SELECT f.faculty_id, u.firstname, u.lastname, u.idno, f.attendance_image, f.profile_picture
        FROM faculty f 
        JOIN user u ON f.user_id = u.user_id 
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    if not faculty:
        conn.close()
        flash('Faculty record not found', 'error')
        return redirect(url_for('faculty_dashboard'))
    
    # Get event details - check if faculty is organizer OR assigned to this event (only active events)
    event_info = conn.execute('''
        SELECT e.* FROM event e
        WHERE e.event_id = ? AND e.is_active = 1
        AND (e.faculty_id = ? OR e.event_id IN (
            SELECT ef.event_id FROM event_faculty ef WHERE ef.faculty_id = ?
        ))
    ''', (event_id, faculty['faculty_id'], faculty['faculty_id'])).fetchone()
    
    if not event_info:
        conn.close()
        flash('Event not found or access denied', 'error')
        return redirect(url_for('faculty_my_classes'))
    
    # Check if current faculty is the organizer
    is_organizer = event_info['faculty_id'] == faculty['faculty_id']
    
    # Get all faculty members: organizer + faculty participants
    # Organizer is always included, plus faculty participants from event_faculty
    faculty_members = conn.execute('''
        SELECT u.idno, u.firstname, u.lastname, d.dept_name, f.position, f.attendance_image,
               CASE WHEN e.faculty_id = f.faculty_id THEN 1 ELSE 0 END as is_organizer
        FROM event e
        LEFT JOIN event_faculty ef ON e.event_id = ef.event_id
        JOIN faculty f ON (e.faculty_id = f.faculty_id OR ef.faculty_id = f.faculty_id)
        JOIN user u ON f.user_id = u.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE e.event_id = ?
        GROUP BY f.faculty_id
        ORDER BY is_organizer DESC, u.firstname, u.lastname
    ''', (event_id,)).fetchall()
    
    # Format time (convert from 24-hour to 12-hour with AM/PM)
    def format_time(value):
        if not value:
            return None
        try:
            time_str = str(value)
            # Handle different time formats (HH:MM:SS or HH:MM)
            time_formats = ['%H:%M:%S', '%H:%M']
            for fmt in time_formats:
                try:
                    return datetime.strptime(time_str, fmt).strftime('%I:%M %p')
                except ValueError:
                    continue
            return time_str
        except Exception:
            return str(value)
    
    start_time = format_time(event_info['start_time'])
    end_time = format_time(event_info['end_time'])
    
    conn.close()
    return render_template('faculty/faculty_event_view.html',
                         event_info=event_info,
                         faculty=faculty,
                         faculty_members=faculty_members,
                         start_time=start_time,
                         end_time=end_time,
                         is_organizer=is_organizer)

@app.route('/faculty/attendance-records')
def faculty_attendance_records():
    """Page where a faculty member can see attendance records for their classes and events,
    and also their own attendance when joining events.
    """
    if 'user_id' not in session or session['role'] != 'faculty':
        return redirect(url_for('login'))

    conn = get_db_connection()

    # Ensure profile_picture column exists
    try:
        conn.execute('ALTER TABLE faculty ADD COLUMN profile_picture VARCHAR(255)')
        conn.commit()
    except Exception:
        pass

    # Get faculty info
    faculty_info = conn.execute('''
        SELECT u.*, f.faculty_id, f.position, f.attendance_image, f.profile_picture, d.dept_name
        FROM user u
        JOIN faculty f ON u.user_id = f.user_id
        LEFT JOIN department d ON u.dept_id = d.dept_id
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()

    if not faculty_info:
        conn.close()
        flash('Faculty record not found', 'error')
        return redirect(url_for('faculty_dashboard'))

    faculty_id = faculty_info['faculty_id']
    user_id = session['user_id']

    # All active classes handled by this faculty (for dropdown)
    classes = conn.execute('''
        SELECT class_id, class_name, edpcode
        FROM class
        WHERE faculty_id = ? AND is_active = 1
        ORDER BY class_name
    ''', (faculty_id,)).fetchall()

    # Handle selected class (optional, via query param)
    selected_class_id = request.args.get('class_id', type=int)
    class_page = request.args.get('page', 1, type=int) or 1
    if class_page < 1:
        class_page = 1
    
    # Date filter for class attendance
    class_date_filter = request.args.get('class_date', type=str)

    if not selected_class_id and classes:
        selected_class_id = classes[0]['class_id']

    class_attendance = []
    class_page_size = 10
    class_has_next = False
    class_has_prev = False

    if selected_class_id:
        # Detailed attendance for the selected class
        offset = (class_page - 1) * class_page_size
        query_params = [faculty_id, selected_class_id]
        date_filter_clause = ''
        if class_date_filter:
            date_filter_clause = 'AND DATE(a.attendance_date) = ?'
            query_params.append(class_date_filter)
        
        query_params.extend([class_page_size + 1, offset])
        
        rows = conn.execute(f'''
            SELECT 
                a.attendance_id,
                DATE(a.attendance_date) AS date,
                a.attendance_date,
                a.attendance_status,
                u.firstname,
                u.lastname,
                c.class_name
            FROM attendance a
            JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
            JOIN student s ON sc.student_id = s.student_id
            JOIN user u ON s.user_id = u.user_id
            JOIN class c ON sc.class_id = c.class_id
            WHERE c.faculty_id = ?
              AND c.class_id = ?
              {date_filter_clause}
            ORDER BY a.attendance_date DESC
            LIMIT ? OFFSET ?
        ''', tuple(query_params)).fetchall()

        if len(rows) > class_page_size:
            class_has_next = True
            rows = rows[:class_page_size]

        class_has_prev = class_page > 1

        for r in rows:
            # normalize time string
            time_str = ''
            if r['attendance_date']:
                try:
                    if isinstance(r['attendance_date'], str):
                        time_str = r['attendance_date'].split(' ')[1] if ' ' in r['attendance_date'] else r['attendance_date']
                    else:
                        time_str = r['attendance_date'].strftime('%H:%M:%S')
                except Exception:
                    time_str = str(r['attendance_date'])

            class_attendance.append({
                'attendance_id': r['attendance_id'],
                'date': r['date'],
                'time': time_str,
                'status': r['attendance_status'],
                'student_name': f"{r['firstname']} {r['lastname']}",
                'class_name': r['class_name'],
            })

    # Event attendance for events this faculty organizes or is assigned to
    # Date filter for event attendance
    event_date_filter = request.args.get('event_date', type=str)
    
    event_query_params = [faculty_id, faculty_id]
    event_date_filter_clause = ''
    if event_date_filter:
        event_date_filter_clause = 'AND DATE(ea.attendance_time) = ?'
        event_query_params.append(event_date_filter)
    
    event_rows = conn.execute(f'''
        SELECT 
            ea.event_attend_id,
            e.event_name,
            DATE(e.event_date) AS event_date,
            ea.attendance_time,
            ea.status,
            u.firstname,
            u.lastname,
            ea.user_id
        FROM event_attendance ea
        JOIN event e ON ea.event_id = e.event_id
        JOIN user u ON ea.user_id = u.user_id
        WHERE e.is_active = 1
          AND (
                e.faculty_id = ?
                OR e.event_id IN (
                    SELECT ef.event_id FROM event_faculty ef WHERE ef.faculty_id = ?
              )
          )
          {event_date_filter_clause}
        ORDER BY e.event_date DESC, ea.attendance_time DESC
    ''', tuple(event_query_params)).fetchall()

    event_attendance = []
    for r in event_rows:
        time_str = ''
        if r['attendance_time']:
            try:
                if isinstance(r['attendance_time'], str):
                    time_str = r['attendance_time'].split(' ')[1] if ' ' in r['attendance_time'] else r['attendance_time']
                else:
                    time_str = r['attendance_time'].strftime('%H:%M:%S')
            except Exception:
                time_str = str(r['attendance_time'])

        event_attendance.append({
            'event_attend_id': r['event_attend_id'],
            'event_name': r['event_name'],
            'event_date': r['event_date'],
            'time': time_str,
            'status': r['status'],
            'attendee_name': f"{r['firstname']} {r['lastname']}",
            'is_self': r['user_id'] == user_id,
        })

    # Faculty member's own attendance to any events
    my_rows = conn.execute('''
        SELECT 
            e.event_name,
            DATE(e.event_date) AS event_date,
            ea.attendance_time,
            ea.status
        FROM event_attendance ea
        JOIN event e ON ea.event_id = e.event_id
        WHERE ea.user_id = ?
        ORDER BY e.event_date DESC, ea.attendance_time DESC
    ''', (user_id,)).fetchall()

    my_event_attendance = []
    for r in my_rows:
        time_str = ''
        if r['attendance_time']:
            try:
                if isinstance(r['attendance_time'], str):
                    time_str = r['attendance_time'].split(' ')[1] if ' ' in r['attendance_time'] else r['attendance_time']
                else:
                    time_str = r['attendance_time'].strftime('%H:%M:%S')
            except Exception:
                time_str = str(r['attendance_time'])

        my_event_attendance.append({
            'event_name': r['event_name'],
            'event_date': r['event_date'],
            'time': time_str,
            'status': r['status'],
        })

    conn.close()
    return render_template(
        'faculty/faculty_attendance_records.html',
        faculty_info=faculty_info,
        classes=classes,
        selected_class_id=selected_class_id,
        class_attendance=class_attendance,
        class_page=class_page,
        class_page_size=class_page_size,
        class_has_next=class_has_next,
        class_has_prev=class_has_prev,
        class_date_filter=class_date_filter,
        event_attendance=event_attendance,
        event_date_filter=event_date_filter,
        my_event_attendance=my_event_attendance,
    )

@app.route('/faculty/class-details/<type>/<int:id>')
def faculty_class_details(type, id):
    if 'user_id' not in session or session['role'] != 'faculty':
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = get_db_connection()
    
    # Get faculty info
    faculty = conn.execute('''
        SELECT f.faculty_id FROM faculty f 
        JOIN user u ON f.user_id = u.user_id 
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    if not faculty:
        conn.close()
        return jsonify({'error': 'Faculty record not found'}), 404
    
    if type == 'class':
        # Get class details (only active classes)
        class_info = conn.execute('''
            SELECT c.*, 
                   GROUP_CONCAT(DISTINCT d.day_name) as days
            FROM class c
            LEFT JOIN class_days cd ON c.class_id = cd.class_id
            LEFT JOIN days d ON cd.day_id = d.day_id
            WHERE c.class_id = ? AND c.faculty_id = ? AND c.is_active = 1
            GROUP BY c.class_id
        ''', (id, faculty['faculty_id'])).fetchone()
        
        if not class_info:
            conn.close()
            return jsonify({'error': 'Class not found or access denied'}), 404
        
        # Get enrolled students
        students = conn.execute('''
            SELECT u.idno, u.firstname, u.lastname, s.year_level, c.course_name
            FROM student_class sc
            JOIN student s ON sc.student_id = s.student_id
            JOIN user u ON s.user_id = u.user_id
            LEFT JOIN course c ON s.course_id = c.course_id
            WHERE sc.class_id = ?
            ORDER BY u.firstname, u.lastname
        ''', (id,)).fetchall()
        
        conn.close()
        return jsonify({
            'class_name': class_info['class_name'],
            'edpcode': class_info['edpcode'],
            'start_time': class_info['start_time'],
            'end_time': class_info['end_time'],
            'room': class_info['room'],
            'days': class_info['days'],
            'students': [dict(student) for student in students]
        })
        
    elif type == 'event':
        # Get event details (only active events)
        event_info = conn.execute('''
            SELECT * FROM event 
            WHERE event_id = ? AND faculty_id = ? AND is_active = 1
        ''', (id, faculty['faculty_id'])).fetchone()
        
        if not event_info:
            conn.close()
            return jsonify({'error': 'Event not found or access denied'}), 404
        
        # Get event attendees
        attendees = conn.execute('''
            SELECT DISTINCT u.idno, u.firstname, u.lastname, s.year_level, c.course_name
            FROM event_attendance ea
            JOIN user u ON ea.user_id = u.user_id
            JOIN student s ON u.user_id = s.user_id
            LEFT JOIN course c ON s.course_id = c.course_id
            WHERE ea.event_id = ?
            ORDER BY u.firstname, u.lastname
        ''', (id,)).fetchall()
        
        conn.close()
        return jsonify({
            'event_name': event_info['event_name'],
            'description': event_info['description'],
            'event_date': event_info['event_date'],
            'start_time': event_info['start_time'],
            'end_time': event_info['end_time'],
            'room': event_info['room'],
            'attendees': [dict(attendee) for attendee in attendees]
        })
    
    conn.close()
    return jsonify({'error': 'Invalid type'}), 400

# Faculty Attendance
@app.route('/attendance')
def attendance():
    """Faculty attendance page - Take attendance using face recognition"""
    if 'user_id' not in session:
        flash('Please login to access attendance', 'error')
        return redirect(url_for('login'))
    
    # Allow both faculty and admin
    if session.get('role') not in ['faculty', 'admin']:
        flash('Only faculty and admin can access this page', 'error')
        return redirect(url_for('login'))
    
    # Get classes and events for faculty
    conn = get_db_connection()
    classes = []
    events = []
    
    # Add profile_picture column to faculty table if it doesn't exist
    try:
        conn.execute('ALTER TABLE faculty ADD COLUMN profile_picture VARCHAR(255)')
        conn.commit()
    except:
        pass  # Column already exists
    
    faculty_info = None
    selected_class_id = request.args.get('class_id')
    selected_event_id = request.args.get('event_id')

    if session.get('role') == 'faculty':
        # Get faculty info
        faculty_info = conn.execute('''
            SELECT u.*, f.faculty_id, f.position, f.attendance_image, f.profile_picture, d.dept_name
            FROM user u
            JOIN faculty f ON u.user_id = f.user_id
            LEFT JOIN department d ON u.dept_id = d.dept_id
            WHERE u.user_id = ?
        ''', (session['user_id'],)).fetchone()
        
        if faculty_info:
            classes = conn.execute('''
                SELECT c.class_id, c.class_name, c.edpcode, c.start_time, c.end_time, c.room
                FROM class c
                WHERE c.faculty_id = ? AND c.is_active = 1
                ORDER BY c.class_name
            ''', (faculty_info['faculty_id'],)).fetchall()
            
            # Get events where this faculty is the ORGANIZER (only organizers can take attendance, only active events)
            events = conn.execute('''
                SELECT e.event_id, e.event_name, e.description, e.event_date, 
                       e.start_time, e.end_time, e.room
                FROM event e
                WHERE e.faculty_id = ? AND e.is_active = 1
                ORDER BY e.event_date DESC
            ''', (faculty_info['faculty_id'],)).fetchall()
    elif session.get('role') == 'admin':
        # Admin can see all classes and events (only active)
        classes = conn.execute('''
            SELECT c.class_id, c.class_name, c.edpcode, c.start_time, c.end_time, c.room
            FROM class c
            WHERE c.is_active = 1
            ORDER BY c.class_name
        ''').fetchall()
        
        events = conn.execute('''
            SELECT e.event_id, e.event_name, e.description, e.event_date,
                   e.start_time, e.end_time, e.room
            FROM event e
            WHERE e.is_active = 1
            ORDER BY e.event_date DESC
        ''').fetchall()
    
    conn.close()
    
    return render_template(
        'faculty_attendance.html',
        faculty_info=faculty_info,
        classes=classes,
        events=events,
        preselected_class_id=selected_class_id,
        preselected_event_id=selected_event_id
    )

# Faculty Reports & Analytics
@app.route('/attendance_reports')
def faculty_reports():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Allow faculty access
    if session.get('role') == 'faculty':
        conn = get_db_connection()
        
        # Add profile_picture column to faculty table if it doesn't exist
        try:
            conn.execute('ALTER TABLE faculty ADD COLUMN profile_picture VARCHAR(255)')
            conn.commit()
        except:
            pass  # Column already exists
        
        faculty = conn.execute('''
            SELECT u.firstname, u.lastname, f.faculty_id, f.profile_picture
            FROM user u
            JOIN faculty f ON u.user_id = f.user_id
            WHERE u.user_id = ?
        ''', (session['user_id'],)).fetchone()
        conn.close()
        
        if not faculty:
            flash('Faculty record not found.', 'error')
            return redirect(url_for('faculty_dashboard'))
        
        faculty_info = {
            'faculty_id': faculty['faculty_id'],
            'firstname': faculty['firstname'],
            'lastname': faculty['lastname'],
            'profile_picture': faculty['profile_picture']
        }
        
        return render_template('faculty/faculty_reports.html', faculty_info=faculty_info)
    
    # Allow admin access
    if session.get('role') == 'admin':
        return redirect(url_for('admin_reports'))
    
    return redirect(url_for('login'))

@app.route('/api/faculty/reports/summary')
def api_faculty_reports_summary():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    # Require faculty or admin role
    if session.get('role') not in ['faculty', 'admin']:
        return jsonify({'error': 'Access denied'}), 403
    start = request.args.get('start')
    end = request.args.get('end')
    if not start or not end:
        today = datetime.now().strftime('%Y-%m-%d')
        start = today
        end = today
    conn = get_db_connection()
    faculty = conn.execute('''
        SELECT f.faculty_id FROM faculty f JOIN user u ON f.user_id = u.user_id
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    if not faculty:
        conn.close()
        return jsonify([])
    rows = conn.execute('''
        SELECT c.class_name, c.edpcode,
               COUNT(a.attendance_id) AS present_count,
               COUNT(DISTINCT sc.student_id) AS unique_students
        FROM class c
        JOIN student_class sc ON sc.class_id = c.class_id
        LEFT JOIN attendance a ON a.studentclass_id = sc.studentclass_id
            AND DATE(a.attendance_date) BETWEEN ? AND ?
        WHERE c.faculty_id = ?
        GROUP BY c.class_id
        ORDER BY c.class_name
    ''', (start, end, faculty['faculty_id'])).fetchall()
    conn.close()
    return jsonify([{
        'class_name': r['class_name'],
        'edpcode': r['edpcode'] if 'edpcode' in r.keys() else None,
        'present_count': r['present_count'] or 0,
        'unique_students': r['unique_students'] or 0
    } for r in rows])

@app.route('/api/faculty/reports/absence-patterns')
def api_faculty_reports_absence_patterns():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    # Require faculty or admin role
    if session.get('role') not in ['faculty', 'admin']:
        return jsonify({'error': 'Access denied'}), 403
    start = request.args.get('start')
    end = request.args.get('end')
    if not start or not end:
        today = datetime.now().strftime('%Y-%m-%d')
        start = today
        end = today
    conn = get_db_connection()
    faculty = conn.execute('''
        SELECT f.faculty_id FROM faculty f JOIN user u ON f.user_id = u.user_id
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    if not faculty:
        conn.close()
        return jsonify([])
    rows = conn.execute('''
        SELECT (u.firstname || ' ' || u.lastname) AS student_name,
               c.class_name,
               SUM(CASE WHEN a.attendance_status = 'present' THEN 1 ELSE 0 END) AS present_count,
               SUM(CASE WHEN a.attendance_status = 'absent' THEN 1 ELSE 0 END) AS absent_count
        FROM class c
        JOIN student_class sc ON sc.class_id = c.class_id
        JOIN student s ON sc.student_id = s.student_id
        JOIN user u ON s.user_id = u.user_id
        LEFT JOIN attendance a ON a.studentclass_id = sc.studentclass_id
            AND DATE(a.attendance_date) BETWEEN ? AND ?
        WHERE c.faculty_id = ?
        GROUP BY sc.student_id, c.class_id
        HAVING present_count >= 0
        ORDER BY absent_count DESC, student_name
        LIMIT 200
    ''', (start, end, faculty['faculty_id'])).fetchall()
    conn.close()
    return jsonify([{
        'student_name': r['student_name'],
        'class_name': r['class_name'],
        'present_count': r['present_count'] or 0,
        'absent_count': r['absent_count'] or 0
    } for r in rows])

@app.route('/api/faculty/reports/events/summary')
def api_faculty_reports_events_summary():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    # Require faculty or admin role
    if session.get('role') not in ['faculty', 'admin']:
        return jsonify({'error': 'Access denied'}), 403
    start = request.args.get('start')
    end = request.args.get('end')
    if not start or not end:
        today = datetime.now().strftime('%Y-%m-%d')
        start = today
        end = today
    conn = get_db_connection()
    faculty = conn.execute('''
        SELECT f.faculty_id FROM faculty f JOIN user u ON f.user_id = u.user_id
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    if not faculty:
        conn.close()
        return jsonify([])
    rows = conn.execute('''
        SELECT e.event_name,
               DATE(e.event_date) AS event_date,
               COUNT(CASE WHEN ea.status = 'present' THEN 1 END) AS present_count,
               COUNT(DISTINCT ea.user_id) AS unique_attendees
        FROM event e
        LEFT JOIN event_attendance ea ON e.event_id = ea.event_id
        WHERE e.faculty_id = ? AND DATE(e.event_date) BETWEEN ? AND ?
        GROUP BY e.event_id
        ORDER BY e.event_date DESC
    ''', (faculty['faculty_id'], start, end)).fetchall()
    conn.close()
    return jsonify([{
        'event_name': r['event_name'],
        'event_date': r['event_date'],
        'present_count': r['present_count'] or 0,
        'unique_attendees': r['unique_attendees'] or 0
    } for r in rows])

@app.route('/api/faculty/reports/events/absence-patterns')
def api_faculty_reports_events_absence():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    # Require faculty or admin role
    if session.get('role') not in ['faculty', 'admin']:
        return jsonify({'error': 'Access denied'}), 403
    start = request.args.get('start')
    end = request.args.get('end')
    if not start or not end:
        today = datetime.now().strftime('%Y-%m-%d')
        start = today
        end = today
    conn = get_db_connection()
    faculty = conn.execute('''
        SELECT f.faculty_id FROM faculty f JOIN user u ON f.user_id = u.user_id
        WHERE u.user_id = ?
    ''', (session['user_id'],)).fetchone()
    if not faculty:
        conn.close()
        return jsonify([])
    rows = conn.execute('''
        SELECT (u.firstname || ' ' || u.lastname) AS attendee_name,
               e.event_name,
               SUM(CASE WHEN ea.status = 'present' THEN 1 ELSE 0 END) AS present_count,
               SUM(CASE WHEN ea.status = 'absent' THEN 1 ELSE 0 END) AS absent_count
        FROM event_attendance ea
        JOIN event e ON ea.event_id = e.event_id
        JOIN user u ON ea.user_id = u.user_id
        WHERE e.faculty_id = ? AND DATE(e.event_date) BETWEEN ? AND ?
        GROUP BY ea.user_id, e.event_id
        HAVING present_count >= 0 OR absent_count > 0
        ORDER BY absent_count DESC, attendee_name
        LIMIT 200
    ''', (faculty['faculty_id'], start, end)).fetchall()
    conn.close()
    return jsonify([{
        'attendee_name': r['attendee_name'],
        'event_name': r['event_name'],
        'present_count': r['present_count'] or 0,
        'absent_count': r['absent_count'] or 0
    } for r in rows])

@app.route('/attendance_reports/export/<fmt>')
def faculty_reports_export(fmt):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    # Allow faculty access
    if session.get('role') not in ['faculty', 'admin']:
        flash('Access denied.', 'error')
        return redirect(url_for('login'))
    
    try:
        start = request.args.get('start')
        end = request.args.get('end')
        if not start or not end:
            today = datetime.now().strftime('%Y-%m-%d')
            start = today
            end = today
        
        # Fetch datasets using the same queries
        conn = get_db_connection()
        faculty = conn.execute('''
            SELECT f.faculty_id FROM faculty f JOIN user u ON f.user_id = u.user_id
            WHERE u.user_id = ?
        ''', (session['user_id'],)).fetchone()
        
        if not faculty:
            conn.close()
            return jsonify({'error': 'No faculty record found'}), 404
        
        # Get class attendance summaries
        summary = conn.execute('''
            SELECT c.class_name, c.edpcode,
                   COUNT(a.attendance_id) AS present_count,
                   COUNT(DISTINCT sc.student_id) AS unique_students
            FROM class c
            JOIN student_class sc ON sc.class_id = c.class_id
            LEFT JOIN attendance a ON a.studentclass_id = sc.studentclass_id
                AND DATE(a.attendance_date) BETWEEN ? AND ?
            WHERE c.faculty_id = ?
            GROUP BY c.class_id
            ORDER BY c.class_name
        ''', (start, end, faculty['faculty_id'])).fetchall()
        
        # Get absence patterns
        absence = conn.execute('''
            SELECT (u.firstname || ' ' || u.lastname) AS student_name,
                   c.class_name,
                   COUNT(a.attendance_id) AS present_count
            FROM class c
            JOIN student_class sc ON sc.class_id = c.class_id
            JOIN student s ON sc.student_id = s.student_id
            JOIN user u ON s.user_id = u.user_id
            LEFT JOIN attendance a ON a.studentclass_id = sc.studentclass_id
                AND DATE(a.attendance_date) BETWEEN ? AND ?
            WHERE c.faculty_id = ?
            GROUP BY sc.student_id, c.class_id
            ORDER BY present_count ASC, student_name
        ''', (start, end, faculty['faculty_id'])).fetchall()
        
        # Get monthly attendance data
        monthly = conn.execute('''
            SELECT strftime('%Y', a.attendance_date) AS year,
                   strftime('%m', a.attendance_date) AS month,
                   COUNT(a.attendance_id) AS present_count
            FROM attendance a
            JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
            JOIN class c ON sc.class_id = c.class_id
            WHERE c.faculty_id = ?
            GROUP BY strftime('%Y', a.attendance_date), strftime('%m', a.attendance_date)
            ORDER BY year, month
        ''', (faculty['faculty_id'],)).fetchall()
        
        conn.close()

        if fmt == 'csv':
            from io import StringIO
            import csv
            output = StringIO()
            writer = csv.writer(output)
            
            # Header
            writer.writerow([f"Faculty Reports & Analytics ({start} to {end})"])
            writer.writerow([f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
            writer.writerow([])
            
            # Class Attendance Summaries
            writer.writerow(['Class Attendance Summaries'])
            writer.writerow(['Class Name', 'EDP Code', 'Present Count', 'Unique Students'])
            for r in summary:
                writer.writerow([
                    r['class_name'] or '', 
                    r['edpcode'] or '', 
                    r['present_count'] or 0, 
                    r['unique_students'] or 0
                ])
            
            writer.writerow([])
            
            # Absence Patterns
            writer.writerow(['Absence Patterns (by low presence)'])
            writer.writerow(['Student Name', 'Class Name', 'Present Count'])
            for r in absence:
                writer.writerow([
                    r['student_name'] or '', 
                    r['class_name'] or '', 
                    r['present_count'] or 0
                ])
            
            writer.writerow([])
            
            # Monthly Attendance
            writer.writerow(['Monthly Attendance'])
            writer.writerow(['Year', 'Month', 'Present Count'])
            for r in monthly:
                writer.writerow([
                    r['year'] or '', 
                    r['month'] or '', 
                    r['present_count'] or 0
                ])
            
            csv_data = output.getvalue()
            output.close()
            
            return app.response_class(
                csv_data,
                mimetype='text/csv',
                headers={
                    'Content-Disposition': f'attachment; filename=faculty_reports_{start}_to_{end}.csv',
                    'Content-Type': 'text/csv; charset=utf-8'
                }
            )
            
        elif fmt == 'xlsx':
            try:
                from io import BytesIO
                from openpyxl import Workbook
                from openpyxl.styles import Font, PatternFill, Alignment
                
                wb = Workbook()
                
                # Remove default sheet and create new ones
                wb.remove(wb.active)
                
                # Summary sheet
                ws1 = wb.create_sheet('Class Summaries')
                ws1.append([f'Faculty Reports & Analytics ({start} to {end})'])
                ws1.append([f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
                ws1.append([])
                ws1.append(['Class Name', 'EDP Code', 'Present Count', 'Unique Students'])
                
                # Style header row
                header_font = Font(bold=True)
                header_fill = PatternFill(start_color='CCCCCC', end_color='CCCCCC', fill_type='solid')
                for cell in ws1[4]:
                    cell.font = header_font
                    cell.fill = header_fill
                
                for r in summary:
                    ws1.append([
                        r['class_name'] or '', 
                        r['edpcode'] or '', 
                        r['present_count'] or 0, 
                        r['unique_students'] or 0
                    ])
                
                # Absence patterns sheet
                ws2 = wb.create_sheet('Absence Patterns')
                ws2.append([f'Faculty Reports & Analytics ({start} to {end})'])
                ws2.append([f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
                ws2.append([])
                ws2.append(['Student Name', 'Class Name', 'Present Count'])
                
                # Style header row
                for cell in ws2[4]:
                    cell.font = header_font
                    cell.fill = header_fill
                
                for r in absence:
                    ws2.append([
                        r['student_name'] or '', 
                        r['class_name'] or '', 
                        r['present_count'] or 0
                    ])
                
                # Monthly attendance sheet
                ws3 = wb.create_sheet('Monthly Attendance')
                ws3.append([f'Faculty Reports & Analytics ({start} to {end})'])
                ws3.append([f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}'])
                ws3.append([])
                ws3.append(['Year', 'Month', 'Present Count'])
                
                # Style header row
                for cell in ws3[4]:
                    cell.font = header_font
                    cell.fill = header_fill
                
                for r in monthly:
                    ws3.append([
                        r['year'] or '', 
                        r['month'] or '', 
                        r['present_count'] or 0
                    ])
                
                # Auto-adjust column widths
                for ws in [ws1, ws2, ws3]:
                    for column in ws.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max_length + 2, 50)
                        ws.column_dimensions[column_letter].width = adjusted_width
                
                stream = BytesIO()
                wb.save(stream)
                stream.seek(0)
                
                return app.response_class(
                    stream.read(),
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': f'attachment; filename=faculty_reports_{start}_to_{end}.xlsx'}
                )
                
            except ImportError as e:
                return jsonify({'error': f'Excel export requires openpyxl. Error: {str(e)}'}), 500
            except Exception as e:
                return jsonify({'error': f'Excel export failed: {str(e)}'}), 500
                
        elif fmt == 'pdf':
            try:
                from io import BytesIO
                from reportlab.lib.pagesizes import letter
                from reportlab.pdfgen import canvas
                from reportlab.lib.units import inch
                from reportlab.lib import colors
                from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
                from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
                from reportlab.lib.enums import TA_CENTER, TA_LEFT
                
                buffer = BytesIO()
                doc = SimpleDocTemplate(buffer, pagesize=letter)
                styles = getSampleStyleSheet()
                story = []
                
                # Title
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=styles['Heading1'],
                    fontSize=16,
                    spaceAfter=30,
                    alignment=TA_CENTER
                )
                story.append(Paragraph(f"Faculty Reports & Analytics ({start} to {end})", title_style))
                story.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
                story.append(Spacer(1, 20))
                
                # Class Attendance Summaries
                story.append(Paragraph("Class Attendance Summaries", styles['Heading2']))
                story.append(Spacer(1, 12))
                
                summary_data = [['Class Name', 'EDP Code', 'Present Count', 'Unique Students']]
                for r in summary:
                    summary_data.append([
                        r['class_name'] or '', 
                        r['edpcode'] or '', 
                        str(r['present_count'] or 0), 
                        str(r['unique_students'] or 0)
                    ])
                
                summary_table = Table(summary_data)
                summary_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(summary_table)
                story.append(Spacer(1, 20))
                
                # Absence Patterns
                story.append(Paragraph("Absence Patterns (by low presence)", styles['Heading2']))
                story.append(Spacer(1, 12))
                
                absence_data = [['Student Name', 'Class Name', 'Present Count']]
                for r in absence:
                    absence_data.append([
                        r['student_name'] or '', 
                        r['class_name'] or '', 
                        str(r['present_count'] or 0)
                    ])
                
                absence_table = Table(absence_data)
                absence_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(absence_table)
                story.append(Spacer(1, 20))
                
                # Monthly Attendance
                story.append(Paragraph("Monthly Attendance", styles['Heading2']))
                story.append(Spacer(1, 12))
                
                monthly_data = [['Year', 'Month', 'Present Count']]
                for r in monthly:
                    monthly_data.append([
                        r['year'] or '', 
                        r['month'] or '', 
                        str(r['present_count'] or 0)
                    ])
                
                monthly_table = Table(monthly_data)
                monthly_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 12),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                story.append(monthly_table)
                
                doc.build(story)
                pdf = buffer.getvalue()
                buffer.close()
                
                return app.response_class(
                    pdf,
                    mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename=faculty_reports_{start}_to_{end}.pdf'}
                )
                
            except ImportError as e:
                return jsonify({'error': f'PDF export requires reportlab. Error: {str(e)}'}), 500
            except Exception as e:
                return jsonify({'error': f'PDF export failed: {str(e)}'}), 500
        else:
            return jsonify({'error': 'Unsupported format. Supported formats: csv, xlsx, pdf'}), 400
            
    except Exception as e:
        return jsonify({'error': f'Export failed: {str(e)}'}), 500

# ==================== SYSTEM CONFIGURATION MODULE ====================

@app.route('/settings')
def admin_settings():
    """Render admin settings page"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    return render_template('admin_settings.html')

@app.route('/api/settings/all', methods=['GET'])
def api_get_all_settings():
    """Get all system settings"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        settings_dict = settings_manager.get_all_settings()
        return jsonify({'success': True, 'settings': settings_dict})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings/save', methods=['POST'])
def api_save_settings():
    """Save system settings"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        settings = request.get_json()
        
        # Update settings using settings manager
        success = settings_manager.update_settings(settings)
        
        if success:
            return jsonify({'success': True, 'message': 'Settings saved successfully'})
        else:
            return jsonify({'success': False, 'error': 'Failed to save settings'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings/test-email', methods=['POST'])
def api_test_email():
    """Test email configuration"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        # Get email settings from database
        conn = get_db_connection()
        settings = conn.execute('''
            SELECT setting_key, setting_value 
            FROM system_settings 
            WHERE setting_type = 'email'
        ''').fetchall()
        conn.close()
        
        email_settings = {row['setting_key']: row['setting_value'] for row in settings}
        
        # Check if email is enabled
        if email_settings.get('email_enabled') != 'true':
            return jsonify({'success': False, 'error': 'Email notifications are disabled'})
        
        # Validate required fields
        required_fields = ['smtp_server', 'smtp_port', 'smtp_username', 'smtp_password', 'email_from']
        missing_fields = [f for f in required_fields if not email_settings.get(f)]
        
        if missing_fields:
            return jsonify({'success': False, 'error': f'Missing required fields: {", ".join(missing_fields)}'})
        
        # Import email libraries
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Create test email
        msg = MIMEMultipart()
        msg['From'] = email_settings['email_from']
        msg['To'] = email_settings['email_from']  # Send to self for testing
        msg['Subject'] = 'FaceCheck - Test Email'
        
        body = '''
        <html>
        <body>
            <h2>Test Email Successful!</h2>
            <p>This is a test email from your FaceCheck system.</p>
            <p>Your email configuration is working correctly.</p>
            <p><strong>System:</strong> FaceCheck Attendance System</p>
            <p><strong>Time:</strong> {}</p>
        </body>
        </html>
        '''.format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        
        msg.attach(MIMEText(body, 'html'))
        
        # Send email
        server = smtplib.SMTP(email_settings['smtp_server'], int(email_settings['smtp_port']))
        server.starttls()
        server.login(email_settings['smtp_username'], email_settings['smtp_password'])
        server.send_message(msg)
        server.quit()
        
        return jsonify({'success': True, 'message': 'Test email sent successfully'})
        
    except smtplib.SMTPAuthenticationError:
        return jsonify({'success': False, 'error': 'SMTP authentication failed. Check username and password.'})
    except smtplib.SMTPException as e:
        return jsonify({'success': False, 'error': f'SMTP error: {str(e)}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings/backup-now', methods=['POST'])
def api_backup_now():
    """Create database backup"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        import shutil
        from datetime import datetime
        
        # Create backups directory if not exists
        backup_dir = 'backups'
        if not os.path.exists(backup_dir):
            os.makedirs(backup_dir)
        
        # Generate backup filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_filename = f'facecheck_backup_{timestamp}.db'
        backup_path = os.path.join(backup_dir, backup_filename)
        
        # Copy database file
        shutil.copy2('facecheck.db', backup_path)
        
        # Log the backup
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO system_settings (setting_key, setting_value, setting_type, description)
            VALUES (?, ?, 'backup', ?)
        ''', (f'backup_{timestamp}', backup_filename, f'Database backup created at {datetime.now()}'))
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': 'Backup created successfully',
            'filename': backup_filename
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/settings/optimize-db', methods=['POST'])
def api_optimize_db():
    """Optimize database"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        conn = get_db_connection()
        
        # Run VACUUM to optimize database
        conn.execute('VACUUM')
        
        # Analyze tables for query optimization
        conn.execute('ANALYZE')
        
        conn.close()
        
        return jsonify({'success': True, 'message': 'Database optimized successfully'})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/admin/logs')
def admin_logs():
    """View activity logs (placeholder for future implementation)"""
    if 'user_id' not in session or session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # This is a placeholder - you can implement full logging later
    flash('Activity logs feature coming soon!', 'info')
    return redirect(url_for('admin_settings'))

# Session check endpoint
@app.route('/api/check-session')
def check_session():
    """Check if user session is valid"""
    if 'user_id' in session:
        return jsonify({
            'valid': True,
            'user_id': session['user_id'],
            'role': session.get('role'),
            'name': f"{session.get('firstname', '')} {session.get('lastname', '')}".strip()
        })
    else:
        return jsonify({
            'valid': False,
            'message': 'No active session'
        }), 401

# Notification API endpoints
@app.route('/api/notifications')
def api_get_notifications():
    """Get notifications for current user"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    if not NOTIFICATIONS_AVAILABLE:
        return jsonify({'success': False, 'message': 'Notifications not available'}), 500
    
    try:
        unread_only = request.args.get('unread_only', 'false').lower() == 'true'
        notifications = get_user_notifications(session['user_id'], unread_only)
        unread_count = get_unread_count(session['user_id'])
        
        return jsonify({
            'success': True,
            'notifications': notifications,
            'unread_count': unread_count
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/notifications/unread-count')
def api_get_unread_count():
    """Get unread notification count for current user"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    if not NOTIFICATIONS_AVAILABLE:
        return jsonify({'success': False, 'count': 0})
    
    try:
        count = get_unread_count(session['user_id'])
        return jsonify({'success': True, 'count': count})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e), 'count': 0})

@app.route('/api/notifications/mark-read/<int:notification_id>', methods=['POST'])
def api_mark_notification_read(notification_id):
    """Mark a notification as read"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    if not NOTIFICATIONS_AVAILABLE:
        return jsonify({'success': False, 'message': 'Notifications not available'}), 500
    
    try:
        success = mark_notification_read(notification_id)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/notifications/mark-all-read', methods=['POST'])
def api_mark_all_notifications_read():
    """Mark all notifications as read for current user"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    if not NOTIFICATIONS_AVAILABLE:
        return jsonify({'success': False, 'message': 'Notifications not available'}), 500
    
    try:
        success = mark_all_read(session['user_id'])
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Create database if it doesn't exist
    if not os.path.exists('facecheck.db'):
        from db import create_database
        create_database()
    
    app.run(debug=True)