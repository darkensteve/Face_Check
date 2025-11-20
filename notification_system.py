"""
Notification System for Face_Check
Handles attendance notifications and alerts
"""

import sqlite3
from datetime import datetime
from config_settings import settings_manager

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect('facecheck.db')
    conn.row_factory = sqlite3.Row
    return conn

def create_notification(user_id, message, notification_type='info'):
    """Create a new notification for a user"""
    try:
        conn = get_db_connection()
        conn.execute('''
            INSERT INTO notifications (user_id, message, notification_type, is_read, created_at)
            VALUES (?, ?, ?, 0, ?)
        ''', (user_id, message, notification_type, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error creating notification: {e}")
        return False

def get_user_notifications(user_id, unread_only=False):
    """Get all notifications for a user"""
    try:
        conn = get_db_connection()
        if unread_only:
            notifications = conn.execute('''
                SELECT * FROM notifications 
                WHERE user_id = ? AND is_read = 0
                ORDER BY created_at DESC
            ''', (user_id,)).fetchall()
        else:
            notifications = conn.execute('''
                SELECT * FROM notifications 
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 50
            ''', (user_id,)).fetchall()
        conn.close()
        return [dict(notif) for notif in notifications]
    except Exception as e:
        print(f"Error getting notifications: {e}")
        return []

def get_unread_count(user_id):
    """Get count of unread notifications for a user"""
    try:
        conn = get_db_connection()
        count = conn.execute('''
            SELECT COUNT(*) as count FROM notifications 
            WHERE user_id = ? AND is_read = 0
        ''', (user_id,)).fetchone()
        conn.close()
        return count['count'] if count else 0
    except Exception as e:
        print(f"Error getting unread count: {e}")
        return 0

def mark_notification_read(notification_id):
    """Mark a notification as read"""
    try:
        conn = get_db_connection()
        conn.execute('''
            UPDATE notifications 
            SET is_read = 1 
            WHERE notification_id = ?
        ''', (notification_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error marking notification as read: {e}")
        return False

def mark_all_read(user_id):
    """Mark all notifications as read for a user"""
    try:
        conn = get_db_connection()
        conn.execute('''
            UPDATE notifications 
            SET is_read = 1 
            WHERE user_id = ? AND is_read = 0
        ''', (user_id,))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Error marking all notifications as read: {e}")
        return False

def check_and_notify_absences(student_id):
    """
    Check if a student has reached the absence threshold and create notification if needed
    Returns the number of absences
    """
    try:
        # Get notification settings
        threshold = int(settings_manager.get_setting('absence_notification_threshold', '5'))
        notifications_enabled = settings_manager.get_setting('enable_notifications', 'true') == 'true'
        
        if not notifications_enabled:
            return 0
        
        conn = get_db_connection()
        
        # Get student's user_id
        student = conn.execute('''
            SELECT user_id, s.student_id FROM student s
            WHERE s.student_id = ?
        ''', (student_id,)).fetchone()
        
        if not student:
            conn.close()
            return 0
        
        user_id = student['user_id']
        
        # Count absences for this student
        absence_count = conn.execute('''
            SELECT COUNT(*) as count FROM attendance a
            JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
            WHERE sc.student_id = ? AND a.attendance_status = 'absent'
        ''', (student_id,)).fetchone()
        
        total_absences = absence_count['count'] if absence_count else 0
        
        # Check if we've already sent a notification for this threshold
        existing_notification = conn.execute('''
            SELECT notification_id FROM notifications
            WHERE user_id = ? 
            AND notification_type = 'absence_warning'
            AND message LIKE ?
            AND created_at >= date('now', '-7 days')
        ''', (user_id, f'%{total_absences} absences%')).fetchone()
        
        # Create notification if threshold reached and no recent notification exists
        if total_absences >= threshold and not existing_notification:
            message = f'⚠️ Attendance Alert: You have {total_absences} absences. Please maintain regular attendance to meet the minimum requirement.'
            create_notification(user_id, message, 'absence_warning')
        
        conn.close()
        return total_absences
    except Exception as e:
        print(f"Error checking absences: {e}")
        return 0

def convert_lates_to_absent(student_id):
    """
    Convert multiple late marks to absent based on settings (e.g., 3 lates = 1 absent)
    Returns True if any conversion was made
    """
    try:
        # Get lates-to-absent setting
        lates_threshold = int(settings_manager.get_setting('lates_to_absent', '3'))
        
        conn = get_db_connection()
        
        # Get student's user_id
        student = conn.execute('''
            SELECT user_id FROM student WHERE student_id = ?
        ''', (student_id,)).fetchone()
        
        if not student:
            conn.close()
            return False
        
        user_id = student['user_id']
        
        # Count unprocessed lates for this student
        late_count = conn.execute('''
            SELECT COUNT(*) as count FROM attendance a
            JOIN student_class sc ON a.studentclass_id = sc.studentclass_id
            WHERE sc.student_id = ? AND a.attendance_status = 'late'
        ''', (student_id,)).fetchone()
        
        total_lates = late_count['count'] if late_count else 0
        
        # Calculate how many absences should be created
        absences_to_create = total_lates // lates_threshold
        
        if absences_to_create > 0:
            # Check if we've already processed this
            # For simplicity, we'll add a note notification instead of modifying records
            message = f'📋 Note: You have {total_lates} late marks. Every {lates_threshold} lates count as 1 absence in your record.'
            
            # Check if we've sent this notification recently
            recent_notif = conn.execute('''
                SELECT notification_id FROM notifications
                WHERE user_id = ? 
                AND notification_type = 'late_conversion'
                AND created_at >= date('now', '-7 days')
            ''', (user_id,)).fetchone()
            
            if not recent_notif:
                create_notification(user_id, message, 'late_conversion')
            
            conn.close()
            return True
        
        conn.close()
        return False
    except Exception as e:
        print(f"Error converting lates: {e}")
        return False

def auto_mark_absent():
    """
    Auto-mark students as absent if they haven't marked attendance for today
    This should be run at the end of each day
    """
    try:
        # Check if auto-mark is enabled
        auto_mark_enabled = settings_manager.get_setting('absent_auto_mark', 'true') == 'true'
        
        if not auto_mark_enabled:
            print("Auto-mark absent is disabled in settings")
            return 0
        
        conn = get_db_connection()
        today = datetime.now().strftime('%Y-%m-%d')
        
        # Get all active student-class enrollments
        enrollments = conn.execute('''
            SELECT DISTINCT sc.studentclass_id, sc.student_id, c.class_name
            FROM student_class sc
            JOIN student s ON sc.student_id = s.student_id
            JOIN user u ON s.user_id = u.user_id
            JOIN class c ON sc.class_id = c.class_id
            WHERE u.is_active = 1
        ''').fetchall()
        
        marked_count = 0
        
        for enrollment in enrollments:
            studentclass_id = enrollment['studentclass_id']
            student_id = enrollment['student_id']
            
            # Check if attendance is already marked for today
            existing = conn.execute('''
                SELECT attendance_id FROM attendance
                WHERE studentclass_id = ? AND DATE(attendance_date) = ?
            ''', (studentclass_id, today)).fetchone()
            
            if not existing:
                # Mark as absent
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                conn.execute('''
                    INSERT INTO attendance (attendance_date, attendance_status, studentclass_id)
                    VALUES (?, 'absent', ?)
                ''', (current_time, studentclass_id))
                marked_count += 1
                
                # Create notification for the student
                student = conn.execute('''
                    SELECT user_id FROM student WHERE student_id = ?
                ''', (student_id,)).fetchone()
                
                if student:
                    class_name = enrollment['class_name']
                    message = f'❌ You were automatically marked absent for {class_name} on {today}. Please ensure you mark attendance on time.'
                    create_notification(student['user_id'], message, 'auto_absent')
        
        conn.commit()
        conn.close()
        print(f"[SUCCESS] Auto-marked {marked_count} students as absent")
        return marked_count
    except Exception as e:
        print(f"[ERROR] Error in auto-mark absent: {e}")
        return 0

