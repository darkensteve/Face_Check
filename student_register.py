import os
import cv2
import face_recognition
import csv
from datetime import datetime

def load_students():
    """Load existing student database"""
    students = {}
    if os.path.exists("students.csv"):
        with open("students.csv", "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                students[row["student_id"]] = row
    return students

def save_student(student_id, name, email):
    """Save new student to database"""
    students = load_students()
    students[student_id] = {
        "student_id": student_id,
        "name": name,
        "email": email,
        "registered_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    with open("students.csv", "w", newline="", encoding="utf-8") as f:
        fieldnames = ["student_id", "name", "email", "registered_date"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for student in students.values():
            writer.writerow(student)
    
    return True

def register_face_for_student(student_id):
    """Register face for a specific student"""
    os.makedirs("known_faces", exist_ok=True)
    
    print(f"\n🎓 Registering face for Student ID: {student_id}")
    print("Press 's' to save face, 'q' to quit")
    
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # Detect faces
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = haar.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
        
        cv2.putText(frame, f"Student ID: {student_id}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        cv2.putText(frame, "Press 's' to save, 'q' to quit", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        cv2.imshow("Student Face Registration", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('s'):
            if len(faces) > 0:
                # Save the largest face
                (x, y, w, h) = max(faces, key=lambda b: b[2] * b[3])
                face_img = frame[y:y+h, x:x+w]
                
                # Validate face
                rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
                face_locations = face_recognition.face_locations(rgb)
                face_encodings = face_recognition.face_encodings(rgb, face_locations)
                
                if face_encodings:
                    # Save face image
                    face_path = f"known_faces/{student_id}.jpg"
                    cv2.imwrite(face_path, face_img)
                    print(f"✅ Face registered: {face_path}")
                    cap.release()
                    cv2.destroyAllWindows()
                    return True
                else:
                    print("❌ No face detected. Try again.")
            else:
                print("❌ No face detected. Try again.")
        
        if key == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    return False

def main():
    print("�� Student Self-Registration System")
    print("=" * 40)
    
    # Get student information
    student_id = input("Enter your Student ID: ").strip()
    if not student_id:
        print("❌ Student ID is required.")
        return
    
    # Check if student already exists
    students = load_students()
    if student_id in students:
        print(f"✅ Student {student_id} already registered.")
        choice = input("Do you want to update your face? (y/n): ").lower()
        if choice != 'y':
            return
    else:
        name = input("Enter your full name: ").strip()
        email = input("Enter your email: ").strip()
        
        if not name or not email:
            print("❌ Name and email are required.")
            return
        
        # Save student info
        save_student(student_id, name, email)
        print(f"✅ Student {student_id} registered successfully!")
    
    # Register face
    if register_face_for_student(student_id):
        print("🎉 Face registration completed!")
    else:
        print("❌ Face registration failed.")

if __name__ == "__main__":
    main()