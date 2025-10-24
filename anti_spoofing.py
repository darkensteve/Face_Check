"""
Enhanced Anti-Spoofing Module for Face Recognition
Optimized to reduce false positives while detecting fake faces (photos/videos)
"""

import cv2
import numpy as np
import os
from datetime import datetime

class AntiSpoofingDetector:
    def __init__(self):
        """Initialize the enhanced anti-spoofing detector with optimized thresholds"""
        
        # ============= OPTIMIZED THRESHOLDS FOR REAL PEOPLE =============
        # More lenient settings to avoid false positives on real people
        
        # Blink detection (optional - not required for real person)
        self.EAR_THRESHOLD = 0.30  # More lenient - higher threshold
        self.BLINK_FRAMES_THRESHOLD = 2  # Reduced frames needed
        
        # Motion detection (very lenient)
        self.MOTION_THRESHOLD = 5.0  # Lower threshold - easier to pass
        
        # Texture analysis (key for detecting photos)
        self.TEXTURE_THRESHOLD = 0.35  # Lower - more lenient for real skin
        
        # Color diversity (key for detecting screens)
        self.COLOR_DIVERSITY_THRESHOLD = 0.20  # Lower - more natural variation accepted
        
        # Specular reflection (key for detecting screens/photos)
        self.SPECULAR_THRESHOLD = 35  # Slightly higher - less sensitive
        
        # ============= STRICT CHECKS FOR OBVIOUS FAKES =============
        # These are strict and target obvious photo/video spoofing
        
        # Photo detection - looks for print artifacts
        self.PHOTO_DETECTION_ENABLED = True
        self.MIN_FACE_SIZE = 80  # Minimum face size in pixels (photos are often smaller)
        
        # Edge sharpness - photos/screens have different edge characteristics
        self.EDGE_SHARPNESS_THRESHOLD = 0.15  # Lower means blurrier (like photos)
        
        # Frequency analysis - real faces have different frequency patterns
        self.FREQUENCY_THRESHOLD = 0.25
        
        # ============= DETECTION STATE =============
        self.frame_history = []
        self.max_history_size = 5  # Reduced for faster processing
        
        self.blink_counter = 0
        self.blink_detected = False
        
        # Confidence mode
        self.strict_mode = False  # Set to True for higher security
        
    def calculate_ear(self, eye_landmarks):
        """Calculate Eye Aspect Ratio (EAR) for blink detection"""
        try:
            if len(eye_landmarks) < 6:
                return 0.5  # Return neutral value instead of 0
                
            eye = np.array(eye_landmarks)
            
            # Calculate vertical distances
            A = np.linalg.norm(eye[1] - eye[5])
            B = np.linalg.norm(eye[2] - eye[4])
            
            # Calculate horizontal distance
            C = np.linalg.norm(eye[0] - eye[3])
            
            if C > 0:
                ear = (A + B) / (2.0 * C)
            else:
                ear = 0.5
                
            return ear
        except Exception as e:
            print(f"Error calculating EAR: {e}")
            return 0.5  # Neutral value on error
    
    def detect_blink_pattern(self, face_landmarks):
        """Detect natural blinking patterns (optional check)"""
        try:
            if not face_landmarks or 'left_eye' not in face_landmarks or 'right_eye' not in face_landmarks:
                # Don't penalize if we can't detect eyes
                return True, 0.5  # Pass by default
                
            left_eye = face_landmarks['left_eye']
            right_eye = face_landmarks['right_eye']
            
            left_ear = self.calculate_ear(left_eye)
            right_ear = self.calculate_ear(right_eye)
            avg_ear = (left_ear + right_ear) / 2.0
            
            # Very lenient blink detection
            if avg_ear < self.EAR_THRESHOLD:
                self.blink_counter += 1
            else:
                if self.blink_counter >= self.BLINK_FRAMES_THRESHOLD:
                    self.blink_detected = True
                self.blink_counter = 0
            
            # Always pass if eyes are detected (don't require blink)
            return True, float(avg_ear)
            
        except Exception as e:
            print(f"Error in blink detection: {e}")
            return True, 0.5  # Pass on error
    
    def detect_print_artifacts(self, face_region):
        """Detect printing artifacts that indicate a photo"""
        try:
            gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY) if len(face_region.shape) == 3 else face_region
            
            # Check for print patterns using Fourier Transform
            f_transform = np.fft.fft2(gray)
            f_shift = np.fft.fftshift(f_transform)
            magnitude_spectrum = 20 * np.log(np.abs(f_shift) + 1)
            
            # Real faces have more high-frequency content than photos
            high_freq = np.mean(magnitude_spectrum[magnitude_spectrum > np.percentile(magnitude_spectrum, 75)])
            low_freq = np.mean(magnitude_spectrum[magnitude_spectrum < np.percentile(magnitude_spectrum, 25)])
            
            freq_ratio = high_freq / (low_freq + 1e-7)
            
            # Photos have lower frequency ratio
            is_real = freq_ratio > self.FREQUENCY_THRESHOLD
            
            return bool(is_real), float(freq_ratio)
            
        except Exception as e:
            print(f"Error in print detection: {e}")
            return True, 1.0  # Pass on error
    
    def check_edge_characteristics(self, face_region):
        """Check edge characteristics - photos/screens have different edges"""
        try:
            gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY) if len(face_region.shape) == 3 else face_region
            
            # Apply Canny edge detection
            edges = cv2.Canny(gray, 50, 150)
            
            # Calculate edge density and sharpness
            edge_density = np.sum(edges > 0) / edges.size
            
            # Apply Laplacian for sharpness
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            sharpness = laplacian.var() / 1000.0  # Normalize
            
            # Real faces have specific edge characteristics
            # Photos/screens tend to have either too sharp or too blurred edges
            is_natural = sharpness > self.EDGE_SHARPNESS_THRESHOLD
            
            return bool(is_natural), float(sharpness)
            
        except Exception as e:
            print(f"Error in edge analysis: {e}")
            return True, 1.0  # Pass on error
    
    def analyze_texture_lbp(self, face_region):
        """Analyze texture using Local Binary Patterns (LBP) - optimized"""
        try:
            gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY) if len(face_region.shape) == 3 else face_region
            
            # Use simpler LBP calculation for speed
            h, w = gray.shape
            lbp = np.zeros_like(gray)
            
            # Simple 3x3 LBP
            for i in range(1, h-1):
                for j in range(1, w-1):
                    center = gray[i, j]
                    code = 0
                    code |= (gray[i-1, j-1] >= center) << 0
                    code |= (gray[i-1, j] >= center) << 1
                    code |= (gray[i-1, j+1] >= center) << 2
                    code |= (gray[i, j+1] >= center) << 3
                    code |= (gray[i+1, j+1] >= center) << 4
                    code |= (gray[i+1, j] >= center) << 5
                    code |= (gray[i+1, j-1] >= center) << 6
                    code |= (gray[i, j-1] >= center) << 7
                    lbp[i, j] = code
            
            # Calculate entropy
            hist = cv2.calcHist([lbp], [0], None, [256], [0, 256])
            hist_norm = hist / (lbp.shape[0] * lbp.shape[1])
            entropy = -np.sum(hist_norm * np.log2(hist_norm + 1e-7))
            
            texture_score = min(entropy / 8.0, 1.0)
            
            # More lenient threshold
            return bool(texture_score > self.TEXTURE_THRESHOLD), float(texture_score)
            
        except Exception as e:
            print(f"Error in texture analysis: {e}")
            return True, 0.5  # Pass on error
    
    def analyze_color_distribution(self, face_region):
        """Analyze color distribution - screens/photos have different color characteristics"""
        try:
            # Convert to HSV and LAB for better color analysis
            hsv = cv2.cvtColor(face_region, cv2.COLOR_BGR2HSV)
            lab = cv2.cvtColor(face_region, cv2.COLOR_BGR2LAB)
            
            # Calculate color diversity
            h_std = np.std(hsv[:, :, 0]) / 180.0
            s_mean = np.mean(hsv[:, :, 1]) / 255.0
            
            # Check skin tone consistency
            a_std = np.std(lab[:, :, 1]) / 128.0
            b_std = np.std(lab[:, :, 2]) / 128.0
            
            # Combine metrics - more lenient
            color_diversity = (h_std + s_mean + a_std + b_std) / 4.0
            
            is_natural = color_diversity > self.COLOR_DIVERSITY_THRESHOLD
            
            return bool(is_natural), float(color_diversity)
            
        except Exception as e:
            print(f"Error in color analysis: {e}")
            return True, 0.5  # Pass on error
    
    def detect_specular_reflection(self, face_region):
        """Detect excessive specular reflections (screens/glossy photos)"""
        try:
            gray = cv2.cvtColor(face_region, cv2.COLOR_BGR2GRAY)
            
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            
            # Find very bright spots
            _, bright_spots = cv2.threshold(blurred, 220, 255, cv2.THRESH_BINARY)
            
            bright_pixel_count = np.sum(bright_spots > 0)
            total_pixels = gray.shape[0] * gray.shape[1]
            bright_ratio = bright_pixel_count / total_pixels
            
            # More lenient - only flag extreme cases
            has_excessive_reflection = bright_ratio > (self.SPECULAR_THRESHOLD / 100.0)
            
            return bool(not has_excessive_reflection), float(bright_ratio)
            
        except Exception as e:
            print(f"Error in reflection analysis: {e}")
            return True, 0.0  # Pass on error
    
    def analyze_motion_patterns(self, current_landmarks, face_region):
        """Analyze head movement patterns - very lenient"""
        try:
            self.frame_history.append({
                'landmarks': current_landmarks,
                'timestamp': datetime.now(),
                'face_region': face_region
            })
            
            if len(self.frame_history) > self.max_history_size:
                self.frame_history.pop(0)
            
            if len(self.frame_history) < 2:
                return True, 0.0  # Pass if not enough data
            
            # Calculate motion
            motion_scores = []
            for i in range(1, len(self.frame_history)):
                prev_landmarks = self.frame_history[i-1]['landmarks']
                curr_landmarks = self.frame_history[i]['landmarks']
                
                if prev_landmarks and curr_landmarks and 'nose_tip' in prev_landmarks and 'nose_tip' in curr_landmarks:
                    prev_nose = np.array(prev_landmarks['nose_tip'][0])
                    curr_nose = np.array(curr_landmarks['nose_tip'][0])
                    motion = np.linalg.norm(curr_nose - prev_nose)
                    motion_scores.append(motion)
            
            if motion_scores:
                avg_motion = np.mean(motion_scores)
                # Very lenient - even small motion is OK
                has_natural_motion = avg_motion > self.MOTION_THRESHOLD or len(self.frame_history) < 3
            else:
                has_natural_motion = True
                avg_motion = 0.0
            
            return bool(has_natural_motion), float(avg_motion)
            
        except Exception as e:
            print(f"Error in motion analysis: {e}")
            return True, 0.0  # Pass on error
    
    def comprehensive_anti_spoofing_check(self, image, face_landmarks, face_location):
        """
        Enhanced anti-spoofing analysis optimized for real people
        Focus on detecting obvious fakes (photos/videos) while being lenient on real faces
        """
        try:
            results = {
                'is_live': True,
                'confidence': 1.0,
                'checks': {},
                'details': 'Liveness check passed'
            }
            
            # Extract face region
            top, right, bottom, left = face_location
            face_region = image[top:bottom, left:right]
            
            if face_region.size == 0:
                # Don't fail completely, just warn
                return {
                    'is_live': True,  # Pass by default
                    'confidence': 0.7,
                    'checks': {'warning': 'Could not extract face region'},
                    'details': 'Face detected but region extraction had issues - allowing access'
                }
            
            # ========== CRITICAL CHECKS (Must pass to indicate real person) ==========
            
            # 1. Print Artifact Detection (KEY for photos)
            if self.PHOTO_DETECTION_ENABLED:
                is_not_print, freq_score = self.detect_print_artifacts(face_region)
                results['checks']['print_detection'] = {
                    'passed': is_not_print,
                    'score': freq_score,
                    'weight': 0.30,  # High weight
                    'critical': True
                }
            
            # 2. Edge Characteristics (KEY for screens/photos)
            is_natural_edges, sharpness = self.check_edge_characteristics(face_region)
            results['checks']['edge_analysis'] = {
                'passed': is_natural_edges,
                'score': sharpness,
                'weight': 0.25,  # High weight
                'critical': True
            }
            
            # ========== SUPPORTING CHECKS (Help but not critical) ==========
            
            # 3. Texture Analysis (supporting)
            texture_natural, texture_score = self.analyze_texture_lbp(face_region)
            results['checks']['texture_analysis'] = {
                'passed': texture_natural,
                'score': texture_score,
                'weight': 0.15,
                'critical': False
            }
            
            # 4. Color Distribution (supporting)
            color_natural, color_score = self.analyze_color_distribution(face_region)
            results['checks']['color_analysis'] = {
                'passed': color_natural,
                'score': color_score,
                'weight': 0.15,
                'critical': False
            }
            
            # 5. Specular Reflection (supporting)
            no_reflection, reflection_ratio = self.detect_specular_reflection(face_region)
            results['checks']['reflection_analysis'] = {
                'passed': no_reflection,
                'score': 1.0 - reflection_ratio,
                'weight': 0.10,
                'critical': False
            }
            
            # 6. Motion (optional - very lenient)
            natural_motion, motion_score = self.analyze_motion_patterns(face_landmarks, face_region)
            results['checks']['motion_analysis'] = {
                'passed': natural_motion,
                'score': min(motion_score / 10.0, 1.0),
                'weight': 0.05,
                'critical': False
            }
            
            # ========== CONFIDENCE CALCULATION ==========
            
            # Check critical tests first
            critical_checks = [check for check in results['checks'].values() if check.get('critical', False)]
            critical_passed = sum(1 for check in critical_checks if check['passed'])
            critical_total = len(critical_checks)
            
            # If ANY critical check fails, it's likely a fake
            if critical_total > 0 and critical_passed < critical_total:
                # Calculate how many critical checks failed
                critical_confidence = critical_passed / critical_total
                
                # Only fail if MULTIPLE critical checks fail or confidence is very low
                # Lowered threshold to 25% to reduce false positives with real students
                if critical_confidence < 0.25:  # Less than 25% of critical checks passed
                    results['is_live'] = False
                    results['confidence'] = critical_confidence * 0.6  # Scale down
                    results['details'] = f"⚠️ Anti-Spoofing: Detected patterns consistent with photo/video (confidence: {critical_confidence:.0%})"
                    return results
            
            # Calculate overall weighted score
            total_weight = sum(check.get('weight', 0) for check in results['checks'].values())
            weighted_score = sum(
                check.get('weight', 0) if check['passed'] else 0
                for check in results['checks'].values()
            )
            
            if total_weight > 0:
                confidence = weighted_score / total_weight
            else:
                confidence = 1.0
            
            # VERY LENIENT threshold - only fail on obvious fakes
            if self.strict_mode:
                threshold = 0.40  # Strict mode: 40%
            else:
                threshold = 0.25  # Normal mode: 25% (very lenient to reduce false positives)
            
            is_live = confidence >= threshold
            
            results['is_live'] = bool(is_live)
            results['confidence'] = float(confidence)
            
            if is_live:
                results['details'] = f"✅ Real person detected (confidence: {confidence:.0%})"
            else:
                results['details'] = f"⚠️ Possible photo/video detected (confidence: {confidence:.0%})"
            
            return results
            
        except Exception as e:
            # On any error, default to ALLOWING access (fail-open for user experience)
            print(f"Anti-spoofing error: {e}")
            return {
                'is_live': True,  # Allow on error
                'confidence': 0.8,
                'checks': {'error': str(e)},
                'details': 'Anti-spoofing analysis had an error - allowing access'
            }
    
    def reset_state(self):
        """Reset detector state for new session"""
        self.frame_history.clear()
        self.blink_counter = 0
        self.blink_detected = False


# Global anti-spoofing detector instance
anti_spoofing_detector = AntiSpoofingDetector()
