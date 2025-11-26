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
    Auto-mark students as absent if they haven't marked attendance during their scheduled class time
    Auto-mark faculty as absent if they haven't marked attendance for events
    This checks if the class is scheduled TODAY and if the class time has ended
    """
    try:
        # Check if auto-mark is enabled
        auto_mark_enabled = settings_manager.get_setting('absent_auto_mark', 'true') == 'true'
        
        if not auto_mark_enabled:
            print("Auto-mark absent is disabled in settings")
            return 0
        
        conn = get_db_connection()
        today = datetime.now().strftime('%Y-%m-%d')
        current_datetime = datetime.now()
        current_weekday = current_datetime.strftime('%A')  # Monday, Tuesday, etc.
        
        # ========== PART 1: Auto-mark students absent for classes ==========
        # Get enrollments with class schedule including days
        enrollments = conn.execute('''
            SELECT DISTINCT sc.studentclass_id, sc.student_id, sc.class_id, s.user_id, 
                   c.class_name, c.start_time, c.end_time,
                   u.firstname, u.lastname,
                   GROUP_CONCAT(DISTINCT d.day_name) as class_days
            FROM student_class sc
            JOIN student s ON sc.student_id = s.student_id
            JOIN user u ON s.user_id = u.user_id
            JOIN class c ON sc.class_id = c.class_id
            LEFT JOIN class_days cd ON c.class_id = cd.class_id
            LEFT JOIN days d ON cd.day_id = d.day_id
            WHERE u.is_active = 1
            GROUP BY sc.studentclass_id, sc.student_id, sc.class_id, s.user_id, 
                     c.class_name, c.start_time, c.end_time, u.firstname, u.lastname
        ''').fetchall()
        
        marked_count = 0
        
        for enrollment in enrollments:
            studentclass_id = enrollment['studentclass_id']
            student_id = enrollment['student_id']
            user_id = enrollment['user_id']
            class_days = enrollment['class_days']
            start_time = enrollment['start_time']
            end_time = enrollment['end_time']
            
            # Check if class is scheduled today
            if not class_days or current_weekday not in class_days:
                continue  # Skip if class is not scheduled today
            
            # Check if class has ended for today
            class_ended = False
            if end_time:
                try:
                    # Parse end time (handle both HH:MM:SS and HH:MM formats)
                    if ':' in str(end_time):
                        time_parts = str(end_time).split(':')
                        end_hour = int(time_parts[0])
                        end_minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                        
                        # Compare with current time
                        if current_datetime.hour > end_hour or (current_datetime.hour == end_hour and current_datetime.minute >= end_minute):
                            class_ended = True
                except:
                    pass
            
            # Only mark absent if class has ended
            if not class_ended:
                continue
            
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
                class_name = enrollment['class_name']
                student_name = f"{enrollment['firstname']} {enrollment['lastname']}"
                
                # Format time for notification
                time_str = ''
                if start_time and end_time:
                    try:
                        from datetime import datetime as dt
                        start_obj = dt.strptime(str(start_time).split()[0] if ' ' in str(start_time) else str(start_time), 
                                               '%H:%M:%S' if ':' in str(start_time) and len(str(start_time).split(':')) == 3 else '%H:%M')
                        end_obj = dt.strptime(str(end_time).split()[0] if ' ' in str(end_time) else str(end_time), 
                                             '%H:%M:%S' if ':' in str(end_time) and len(str(end_time).split(':')) == 3 else '%H:%M')
                        time_str = f" ({start_obj.strftime('%I:%M %p')} - {end_obj.strftime('%I:%M %p')})"
                    except:
                        pass
                
                message = f'❌ You were automatically marked absent for {class_name}{time_str} on {today}. You did not mark attendance during the class period.'
                create_notification(user_id, message, 'auto_absent')
                print(f"[AUTO-ABSENT] Student {student_name} marked absent for {class_name}{time_str}")
        
        # ========== PART 2: Auto-mark faculty absent for events ==========
        # Get all events that happened today and have ended
        events_today = conn.execute('''
            SELECT e.event_id, e.event_name, e.end_time, e.event_date
            FROM event e
            WHERE DATE(e.event_date) = ?
        ''', (today,)).fetchall()
        
        faculty_marked = 0
        
        for event in events_today:
            event_id = event['event_id']
            event_name = event['event_name']
            end_time = event['end_time']
            
            # Check if event has ended
            event_ended = False
            if end_time:
                try:
                    if ':' in str(end_time):
                        time_parts = str(end_time).split(':')
                        end_hour = int(time_parts[0])
                        end_minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                        
                        if current_datetime.hour > end_hour or (current_datetime.hour == end_hour and current_datetime.minute >= end_minute):
                            event_ended = True
                except:
                    event_ended = current_datetime.hour >= 17
            else:
                event_ended = current_datetime.hour >= 17
            
            if not event_ended:
                continue
            
            # Get all faculty members (all faculty should attend all events)
            all_faculty = conn.execute('''
                SELECT f.faculty_id, f.user_id, u.firstname, u.lastname
                FROM faculty f
                JOIN user u ON f.user_id = u.user_id
                WHERE u.is_active = 1
            ''').fetchall()
            
            for faculty in all_faculty:
                faculty_id = faculty['faculty_id']
                user_id = faculty['user_id']
                
                # Check if attendance is already marked for this event
                existing = conn.execute('''
                    SELECT ea_id FROM event_attendance
                    WHERE event_id = ? AND faculty_id = ? AND DATE(attendance_time) = ?
                ''', (event_id, faculty_id, today)).fetchone()
                
                if not existing:
                    # Mark as absent
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    conn.execute('''
                        INSERT INTO event_attendance (event_id, faculty_id, status, attendance_time)
                        VALUES (?, ?, 'absent', ?)
                    ''', (event_id, faculty_id, current_time))
                    faculty_marked += 1
                    
                    # Create notification for the faculty
                    faculty_name = f"{faculty['firstname']} {faculty['lastname']}"
                    message = f'❌ You were automatically marked absent for event "{event_name}" on {today}. Please ensure you mark attendance for events on time.'
                    create_notification(user_id, message, 'auto_absent')
                    print(f"[AUTO-ABSENT] Faculty {faculty_name} marked absent for event {event_name}")
        
        conn.commit()
        conn.close()
        
        total_marked = marked_count + faculty_marked
        print(f"[SUCCESS] Auto-marked {marked_count} students and {faculty_marked} faculty as absent (Total: {total_marked})")
        return total_marked
    except Exception as e:
        print(f"[ERROR] Error in auto-mark absent: {e}")
        import traceback
        traceback.print_exc()
        return 0

