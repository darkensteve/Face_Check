"""
Alternative face detection using only OpenCV (no dlib dependency)
This provides basic face detection for systems where face-recognition library can't be installed
"""

import cv2 
import numpy as np
import os
import hashlib
from pathlib import Path

class SimpleFaceDetector:
    """Simple face detector using OpenCV without external dependencies"""
    
    def __init__(self):
        # Load Haar cascade for face detection
        self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        
    def detect_face(self, image):
        """
        Detect faces in image
        Returns: list of (x, y, w, h) rectangles
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray, 
            scaleFactor=1.1, 
            minNeighbors=5, 
            minSize=(60, 60),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        return faces
    
    def extract_face_features(self, image, face_rect):
        """
        Extract simple features from face region
        This is a basic implementation - not as accurate as face_recognition library
        """
        x, y, w, h = face_rect
        face_roi = image[y:y+h, x:x+w]
        
        # Resize face to standard size
        face_roi = cv2.resize(face_roi, (100, 100))
        
        # Convert to grayscale and normalize
        gray_face = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        
        # Calculate histogram as feature vector
        hist = cv2.calcHist([gray_face], [0], None, [256], [0, 256])
        hist = hist.flatten()
        
        # Normalize histogram
        hist = hist / (hist.sum() + 1e-7)
        
        return hist
    
    def compare_faces(self, features1, features2, threshold=0.6):
        """
        Compare two feature vectors
        Returns similarity score (0-1, higher is more similar)
        """
        # Calculate correlation coefficient
        correlation = cv2.compareHist(features1, features2, cv2.HISTCMP_CORREL)
        return correlation
    
    def register_face(self, image_path, student_id):
        """
        Register a face for a student
        """
        try:
            # Read image
            image = cv2.imread(image_path)
            if image is None:
                return False, "Could not read image"
            
            # Detect faces
            faces = self.detect_face(image)
            
            if len(faces) == 0:
                return False, "No face detected in image"
            
            if len(faces) > 1:
                return False, "Multiple faces detected. Please ensure only one face is visible"
            
            # Extract features from the largest face
            largest_face = max(faces, key=lambda rect: rect[2] * rect[3])
            features = self.extract_face_features(image, largest_face)
            
            # Save features to file
            features_dir = Path("face_features")
            features_dir.mkdir(exist_ok=True)
            
            features_file = features_dir / f"{student_id}_features.npy"
            np.save(features_file, features)
            
            # Also save the face image
            x, y, w, h = largest_face
            face_image = image[y:y+h, x:x+w]
            face_image_path = f"known_faces/{student_id}.jpg"
            cv2.imwrite(face_image_path, face_image)
            
            return True, "Face registered successfully"
            
        except Exception as e:
            return False, f"Error registering face: {str(e)}"
    
    def recognize_face(self, image_path, threshold=0.65):
        """
        Recognize face in image against registered faces
        """
        try:
            # Read image
            image = cv2.imread(image_path)
            if image is None:
                return None, "Could not read image"
            
            # Detect faces
            faces = self.detect_face(image)
            
            if len(faces) == 0:
                return None, "No face detected"
            
            # Get the largest face
            largest_face = max(faces, key=lambda rect: rect[2] * rect[3])
            test_features = self.extract_face_features(image, largest_face)
            
            # Load all registered face features
            features_dir = Path("face_features")
            if not features_dir.exists():
                return None, "No registered faces found"
            
            best_match = None
            best_similarity = 0
            
            for features_file in features_dir.glob("*_features.npy"):
                try:
                    stored_features = np.load(features_file)
                    similarity = self.compare_faces(test_features, stored_features)
                    
                    if similarity > best_similarity:
                        best_similarity = similarity
                        student_id = features_file.stem.replace('_features', '')
                        best_match = student_id
                        
                except Exception as e:
                    print(f"Error loading features from {features_file}: {e}")
                    continue
            
            if best_match and best_similarity >= threshold:
                return best_match, f"Match found with {best_similarity:.2f} confidence"
            else:
                return None, f"No match found (best similarity: {best_similarity:.2f})"
                
        except Exception as e:
            return None, f"Error recognizing face: {str(e)}"

# Global instance
simple_detector = SimpleFaceDetector()

def fallback_face_registration(image_path, student_id):
    """
    Fallback face registration using simple OpenCV detection
    """
    return simple_detector.register_face(image_path, student_id)

def fallback_face_recognition(image_path):
    """
    Fallback face recognition using simple OpenCV detection
    """
    student_id, message = simple_detector.recognize_face(image_path)
    
    if student_id:
        # Get student info from database
        import sqlite3
        try:
            conn = sqlite3.connect('facecheck.db')
            student = conn.execute('''
                SELECT s.student_id, u.firstname, u.lastname 
                FROM student s
                JOIN user u ON s.user_id = u.user_id
                WHERE u.idno = ?
            ''', (student_id,)).fetchone()
            conn.close()
            
            if student:
                return {
                    'success': True,
                    'student_id': student[0],
                    'student_name': f"{student[1]} {student[2]}",
                    'message': message,
                    'method': 'opencv_fallback'
                }
        except Exception as e:
            print(f"Database error: {e}")
    
    return {
        'success': False,
        'student_id': 'Unknown',
        'student_name': 'Unknown', 
        'message': message,
        'method': 'opencv_fallback'
    }