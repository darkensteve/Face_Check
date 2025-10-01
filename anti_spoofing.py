"""
Advanced Anti-Spoofing Module for Face Recognition
Implements multiple techniques to detect fake faces and spoofing attempts
"""

import cv2
import numpy as np
import os
from datetime import datetime

class AntiSpoofingDetector:
    def __init__(self):
        """Initialize the anti-spoofing detector with configurable thresholds"""
        # Liveness detection thresholds
        self.EAR_THRESHOLD = 0.25  # Eye Aspect Ratio threshold for blink detection
        self.BLINK_FRAMES_THRESHOLD = 3  # Minimum frames for blink detection
        self.MOTION_THRESHOLD = 10.0  # Head movement threshold
        
        # Color/texture analysis thresholds
        self.TEXTURE_THRESHOLD = 0.5  # LBP texture threshold
        self.COLOR_DIVERSITY_THRESHOLD = 0.3  # Color diversity threshold
        
        # Reflection/specular analysis
        self.SPECULAR_THRESHOLD = 30  # Specular reflection threshold
        
        # Frame history for temporal analysis
        self.frame_history = []
        self.max_history_size = 10
        
        # Blink detection state
        self.blink_counter = 0
        self.blink_detected = False
        
    def calculate_ear(self, eye_landmarks):
        """Calculate Eye Aspect Ratio (EAR) for blink detection"""
        try:
            if len(eye_landmarks) < 6:
                return 0.0
                
            # Convert landmarks to numpy array
            eye = np.array(eye_landmarks)
            
            # Calculate vertical distances
            A = np.linalg.norm(eye[1] - eye[5])  # Left vertical
            B = np.linalg.norm(eye[2] - eye[4])  # Right vertical
            
            # Calculate horizontal distance
            C = np.linalg.norm(eye[0] - eye[3])  # Horizontal
            
            # Calculate EAR
            if C > 0:
                ear = (A + B) / (2.0 * C)
            else:
                ear = 0.0
                
            return ear
        except Exception as e:
            print(f"Error calculating EAR: {e}")
            return 0.0
    
    def detect_blink_pattern(self, face_landmarks):
        """Detect natural blinking patterns"""
        try:
            if not face_landmarks or 'left_eye' not in face_landmarks or 'right_eye' not in face_landmarks:
                return False, 0.0
                
            left_eye = face_landmarks['left_eye']
            right_eye = face_landmarks['right_eye']
            
            # Calculate EAR for both eyes
            left_ear = self.calculate_ear(left_eye)
            right_ear = self.calculate_ear(right_eye)
            avg_ear = (left_ear + right_ear) / 2.0
            
            # Check for blink
            if avg_ear < self.EAR_THRESHOLD:
                self.blink_counter += 1
            else:
                if self.blink_counter >= self.BLINK_FRAMES_THRESHOLD:
                    self.blink_detected = True
                self.blink_counter = 0
                
            return self.blink_detected, avg_ear
            
        except Exception as e:
            print(f"Error in blink detection: {e}")
            return False, 0.0
    
    def analyze_texture_lbp(self, face_region):
        """Analyze texture using Local Binary Patterns (LBP)"""
        try:
            # Convert to grayscale if needed
            if len(face_region.shape) == 3:
                gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
            else:
                gray = face_region
            
            # Calculate LBP
            lbp = self._calculate_lbp(gray)
            
            # Calculate texture uniformity
            hist = cv2.calcHist([lbp], [0], None, [256], [0, 256])
            hist_norm = hist / (lbp.shape[0] * lbp.shape[1])
            
            # Calculate entropy as texture measure
            entropy = -np.sum(hist_norm * np.log2(hist_norm + 1e-7))
            
            # Normalize entropy (higher entropy = more natural texture)
            texture_score = min(entropy / 8.0, 1.0)
            
            return texture_score > self.TEXTURE_THRESHOLD, texture_score
            
        except Exception as e:
            print(f"Error in texture analysis: {e}")
            return True, 0.5  # Default to pass if analysis fails
    
    def _calculate_lbp(self, image, radius=1, n_points=8):
        """Calculate Local Binary Pattern"""
        try:
            rows, cols = image.shape
            lbp = np.zeros_like(image)
            
            for i in range(radius, rows - radius):
                for j in range(radius, cols - radius):
                    center = image[i, j]
                    code = 0
                    
                    for p in range(n_points):
                        angle = 2 * np.pi * p / n_points
                        x = int(round(i + radius * np.cos(angle)))
                        y = int(round(j + radius * np.sin(angle)))
                        
                        if 0 <= x < rows and 0 <= y < cols:
                            if image[x, y] >= center:
                                code |= (1 << p)
                    
                    lbp[i, j] = code
            
            return lbp
            
        except Exception as e:
            print(f"Error calculating LBP: {e}")
            return image
    
    def analyze_color_distribution(self, face_region):
        """Analyze color distribution to detect printed photos"""
        try:
            # Convert to different color spaces
            hsv = cv2.cvtColor(face_region, cv2.COLOR_BGR2HSV)
            lab = cv2.cvtColor(face_region, cv2.COLOR_BGR2LAB)
            
            # Calculate color diversity in HSV
            h_std = np.std(hsv[:, :, 0])  # Hue standard deviation
            s_mean = np.mean(hsv[:, :, 1])  # Saturation mean
            
            # Calculate skin tone consistency in LAB
            a_std = np.std(lab[:, :, 1])  # A channel (green-red) std
            b_std = np.std(lab[:, :, 2])  # B channel (blue-yellow) std
            
            # Combine metrics
            color_diversity = (h_std / 180.0 + s_mean / 255.0 + a_std / 255.0 + b_std / 255.0) / 4.0
            
            is_natural = color_diversity > self.COLOR_DIVERSITY_THRESHOLD
            
            return is_natural, color_diversity
            
        except Exception as e:
            print(f"Error in color analysis: {e}")
            return True, 0.5
    
    def detect_specular_reflection(self, face_region):
        """Detect specular reflections that indicate screens or photos"""
        try:
            # Convert to grayscale
            gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
            
            # Apply Gaussian blur to reduce noise
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Find bright spots (potential reflections)
            _, bright_spots = cv2.threshold(blurred, 200, 255, cv2.THRESH_BINARY)
            
            # Count bright pixels
            bright_pixel_count = np.sum(bright_spots > 0)
            total_pixels = gray.shape[0] * gray.shape[1]
            bright_ratio = bright_pixel_count / total_pixels
            
            # Check for excessive bright spots (indicating reflection)
            has_excessive_reflection = bright_ratio > (self.SPECULAR_THRESHOLD / 100.0)
            
            return not has_excessive_reflection, bright_ratio
            
        except Exception as e:
            print(f"Error in specular reflection analysis: {e}")
            return True, 0.0
    
    def analyze_motion_patterns(self, current_landmarks, face_region):
        """Analyze head movement patterns"""
        try:
            # Store current frame
            self.frame_history.append({
                'landmarks': current_landmarks,
                'timestamp': datetime.now(),
                'face_region': face_region
            })
            
            # Keep only recent frames
            if len(self.frame_history) > self.max_history_size:
                self.frame_history.pop(0)
            
            if len(self.frame_history) < 3:
                return True, 0.0  # Not enough data yet
            
            # Calculate motion between frames
            motion_scores = []
            
            for i in range(1, len(self.frame_history)):
                prev_landmarks = self.frame_history[i-1]['landmarks']
                curr_landmarks = self.frame_history[i]['landmarks']
                
                if prev_landmarks and curr_landmarks and 'nose_tip' in prev_landmarks and 'nose_tip' in curr_landmarks:
                    prev_nose = np.array(prev_landmarks['nose_tip'][0])  # Get first nose tip point
                    curr_nose = np.array(curr_landmarks['nose_tip'][0])
                    
                    # Calculate Euclidean distance
                    motion = np.linalg.norm(curr_nose - prev_nose)
                    motion_scores.append(motion)
            
            if motion_scores:
                avg_motion = np.mean(motion_scores)
                has_natural_motion = avg_motion > self.MOTION_THRESHOLD
            else:
                has_natural_motion = True
                avg_motion = 0.0
            
            return has_natural_motion, avg_motion
            
        except Exception as e:
            print(f"Error in motion analysis: {e}")
            return True, 0.0
    
    def comprehensive_anti_spoofing_check(self, image, face_landmarks, face_location):
        """Perform comprehensive anti-spoofing analysis"""
        try:
            results = {
                'is_live': True,
                'confidence': 1.0,
                'checks': {}
            }
            
            # Extract face region
            top, right, bottom, left = face_location
            face_region = image[top:bottom, left:right]
            
            if face_region.size == 0:
                return {
                    'is_live': False,
                    'confidence': 0.0,
                    'checks': {'error': 'Invalid face region'},
                    'details': 'Could not extract face region'
                }
            
            # 1. Blink Detection
            blink_detected, ear_score = self.detect_blink_pattern(face_landmarks)
            results['checks']['blink_detection'] = {
                'passed': blink_detected,
                'ear_score': ear_score,
                'weight': 0.25
            }
            
            # 2. Texture Analysis
            texture_natural, texture_score = self.analyze_texture_lbp(face_region)
            results['checks']['texture_analysis'] = {
                'passed': texture_natural,
                'texture_score': texture_score,
                'weight': 0.20
            }
            
            # 3. Color Distribution
            color_natural, color_score = self.analyze_color_distribution(face_region)
            results['checks']['color_analysis'] = {
                'passed': color_natural,
                'color_score': color_score,
                'weight': 0.15
            }
            
            # 4. Specular Reflection
            no_reflection, reflection_ratio = self.detect_specular_reflection(face_region)
            results['checks']['reflection_analysis'] = {
                'passed': no_reflection,
                'reflection_ratio': reflection_ratio,
                'weight': 0.20
            }
            
            # 5. Motion Analysis
            natural_motion, motion_score = self.analyze_motion_patterns(face_landmarks, face_region)
            results['checks']['motion_analysis'] = {
                'passed': natural_motion,
                'motion_score': motion_score,
                'weight': 0.20
            }
            
            # Calculate weighted confidence score
            total_weight = 0
            weighted_score = 0
            
            for check_name, check_data in results['checks'].items():
                if 'weight' in check_data:
                    weight = check_data['weight']
                    passed = check_data['passed']
                    total_weight += weight
                    weighted_score += weight if passed else 0
            
            if total_weight > 0:
                confidence = weighted_score / total_weight
            else:
                confidence = 0.0
            
            # Determine if face is live (require at least 70% confidence)
            is_live = confidence >= 0.7
            
            results['is_live'] = is_live
            results['confidence'] = confidence
            results['details'] = f"Anti-spoofing confidence: {confidence:.2%}"
            
            return results
            
        except Exception as e:
            return {
                'is_live': False,
                'confidence': 0.0,
                'checks': {'error': str(e)},
                'details': f'Anti-spoofing analysis failed: {str(e)}'
            }
    
    def reset_state(self):
        """Reset detector state for new session"""
        self.frame_history.clear()
        self.blink_counter = 0
        self.blink_detected = False


# Global anti-spoofing detector instance
anti_spoofing_detector = AntiSpoofingDetector()