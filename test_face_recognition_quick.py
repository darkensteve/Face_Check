#!/usr/bin/env python3
"""Quick test to see if face recognition is working"""

print("Testing face recognition setup...")
print("=" * 60)

# Test 1: Import libraries
print("\n1. Testing library imports...")
try:
    import cv2
    print("   ✅ OpenCV (cv2) imported successfully")
except ImportError as e:
    print(f"   ❌ OpenCV import failed: {e}")
    exit(1)

try:
    import face_recognition
    print("   ✅ face_recognition imported successfully")
except ImportError as e:
    print(f"   ❌ face_recognition import failed: {e}")
    exit(1)

try:
    import numpy as np
    print("   ✅ NumPy imported successfully")
except ImportError as e:
    print(f"   ❌ NumPy import failed: {e}")
    exit(1)

# Test 2: Check database
print("\n2. Checking database for registered students...")
try:
    import sqlite3
    import os
    
    if not os.path.exists('facecheck.db'):
        print("   ❌ Database file 'facecheck.db' not found!")
        exit(1)
    
    conn = sqlite3.connect('facecheck.db')
    conn.row_factory = sqlite3.Row
    
    students = conn.execute('''
        SELECT s.student_id, u.firstname, u.lastname, s.attendance_image
        FROM student s
        JOIN user u ON s.user_id = u.user_id
        WHERE s.attendance_image IS NOT NULL AND s.attendance_image != ''
    ''').fetchall()
    
    print(f"   ✅ Database connected")
    print(f"   ✅ Found {len(students)} students with registered faces:")
    
    for student in students:
        img_exists = os.path.exists(student['attendance_image']) if student['attendance_image'] else False
        status = "✅" if img_exists else "❌"
        print(f"      {status} {student['firstname']} {student['lastname']} - {student['attendance_image']}")
    
    if len(students) == 0:
        print("\n   ⚠️  WARNING: No students have registered face images!")
        print("      Students need to register their faces first!")
    
    conn.close()
    
except Exception as e:
    print(f"   ❌ Database error: {e}")
    exit(1)

# Test 3: Check temp directory
print("\n3. Checking temp directory...")
try:
    if not os.path.exists('temp'):
        os.makedirs('temp', mode=0o755, exist_ok=True)
        print("   ✅ Created temp directory")
    else:
        print("   ✅ temp directory exists")
except Exception as e:
    print(f"   ❌ Could not create temp directory: {e}")

# Test 4: Test face detection on a sample image (if exists)
print("\n4. Testing face detection...")
if students and len(students) > 0:
    test_image = students[0]['attendance_image']
    if os.path.exists(test_image):
        try:
            image = cv2.imread(test_image)
            if image is not None:
                rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                face_locations = face_recognition.face_locations(rgb_image)
                print(f"   ✅ Successfully detected {len(face_locations)} face(s) in test image")
                if len(face_locations) > 0:
                    face_encodings = face_recognition.face_encodings(rgb_image, face_locations)
                    print(f"   ✅ Successfully encoded {len(face_encodings)} face(s)")
                else:
                    print(f"   ⚠️  No faces detected in {test_image}")
            else:
                print(f"   ❌ Could not load image: {test_image}")
        except Exception as e:
            print(f"   ❌ Face detection error: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"   ⚠️  Test image not found: {test_image}")
else:
    print("   ⚠️  No registered student images to test with")

print("\n" + "=" * 60)
print("SUMMARY:")
print("=" * 60)

if len(students) > 0:
    print("✅ Face recognition system is ready!")
    print(f"✅ {len(students)} students registered")
    print("\nYou can now use the attendance system.")
else:
    print("⚠️  Face recognition libraries are installed")
    print("⚠️  But NO STUDENTS have registered their faces yet!")
    print("\nSTUDENTS NEED TO:")
    print("1. Login to the system")
    print("2. Go to 'Register Face'")
    print("3. Take a photo of their face")
    print("4. Then faculty can take attendance")

print("=" * 60)

