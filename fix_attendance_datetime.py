"""
Script to fix attendance_date records in the database by removing microseconds.
This ensures all datetime values are in consistent format: 'YYYY-MM-DD HH:MM:SS'
"""

import sqlite3
from datetime import datetime
import os

def get_db_path():
    """Get the database path"""
    db_path = 'facecheck.db'
    if os.path.exists(db_path):
        return db_path
    return None

def fix_attendance_datetimes():
    """Remove microseconds from all attendance_date records"""
    db_path = get_db_path()
    if not db_path:
        print("[ERROR] Database file not found!")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Get all attendance records
        cursor.execute('SELECT attendance_id, attendance_date FROM attendance')
        records = cursor.fetchall()
        
        print(f"Found {len(records)} attendance records to process...")
        
        updated_count = 0
        skipped_count = 0
        
        for record in records:
            attendance_id = record['attendance_id']
            attendance_date = record['attendance_date']
            
            # Parse the datetime (handle both with and without microseconds)
            try:
                date_str = str(attendance_date)
                
                # Check if the string contains microseconds (has a dot with numbers after seconds)
                has_microseconds = '.' in date_str and len(date_str.split('.')) > 1
                
                if not has_microseconds:
                    # Already in correct format, skip
                    skipped_count += 1
                    continue
                
                # Parse with microseconds
                try:
                    dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S.%f')
                except ValueError:
                    # Try without microseconds (shouldn't happen if we detected it, but just in case)
                    try:
                        dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
                        skipped_count += 1
                        continue
                    except ValueError:
                        print(f"[WARNING] Could not parse date for record {attendance_id}: {attendance_date}")
                        skipped_count += 1
                        continue
                
                # Format without microseconds
                formatted_date = dt.strftime('%Y-%m-%d %H:%M:%S')
                
                # Only update if the formatted date is different
                if formatted_date != date_str:
                    # Update the record
                    cursor.execute('''
                        UPDATE attendance 
                        SET attendance_date = ? 
                        WHERE attendance_id = ?
                    ''', (formatted_date, attendance_id))
                    
                    updated_count += 1
                    print(f"[UPDATE] Record {attendance_id}: {date_str} -> {formatted_date}")
                else:
                    skipped_count += 1
                
            except Exception as e:
                print(f"[WARNING] Error processing record {attendance_id}: {e}")
                skipped_count += 1
                continue
        
        # Commit changes
        conn.commit()
        
        print(f"\n[OK] Successfully updated {updated_count} records")
        print(f"[SKIP] Skipped {skipped_count} records (already in correct format or errors)")
        print(f"[INFO] Total records processed: {len(records)}")
        
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    import sys
    
    print("=" * 60)
    print("Fixing Attendance DateTime Format")
    print("=" * 60)
    print("\nThis script will remove microseconds from all attendance_date records")
    print("to ensure consistent datetime format: 'YYYY-MM-DD HH:MM:SS'\n")
    
    # Check if running with --auto flag to skip confirmation
    if '--auto' in sys.argv:
        print("Running in auto mode (no confirmation required)...\n")
        fix_attendance_datetimes()
        print("\n[OK] Process completed!")
    else:
        try:
            response = input("Do you want to continue? (yes/no): ")
            if response.lower() in ['yes', 'y']:
                fix_attendance_datetimes()
                print("\n[OK] Process completed!")
            else:
                print("\n[CANCELLED] Process cancelled.")
        except EOFError:
            # If no input available (non-interactive), run automatically
            print("Running in non-interactive mode...\n")
            fix_attendance_datetimes()
            print("\n[OK] Process completed!")

