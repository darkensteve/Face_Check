"""
Lightweight anti-spoofing / liveness heuristics built on OpenCV and NumPy.

The detector blends multiple signals so that printed photos, screen replays,
and still frames have a much harder time passing the liveness gate:

- Texture sharpness (Laplacian variance)
- Frequency content (screens/prints often show excess high frequencies)
- Color variation (flat, desaturated areas are suspicious)
- Motion between frames (identical consecutive frames are blocked)
- Optional blink score from facial landmarks when available
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any, Dict, Optional, Tuple

import cv2
import numpy as np


class AntiSpoofingDetector:
    def __init__(self):
        self.last_gray: Optional[np.ndarray] = None
        self.last_timestamp: Optional[float] = None
        self.motion_history: deque[float] = deque(maxlen=10)  # Longer history for better detection
        self.frame_count: int = 0
        self.last_face_landmarks: Optional[Dict[str, Any]] = None
        self.landmark_history: deque[Dict[str, Any]] = deque(maxlen=5)

    def reset_state(self) -> None:
        """Clear rolling state to restart motion tracking."""
        self.last_gray = None
        self.last_timestamp = None
        self.motion_history.clear()
        self.frame_count = 0
        self.last_face_landmarks = None
        self.landmark_history.clear()

    def _prepare_face(self, image: np.ndarray, face_location=None) -> np.ndarray:
        """Crop and downscale the face region for faster analysis."""
        face_roi = image
        if face_location:
            top, right, bottom, left = face_location
            top, right, bottom, left = int(top), int(right), int(bottom), int(left)
            face_roi = image[max(top, 0) : max(bottom, 0), max(left, 0) : max(right, 0)]

        # Guard against empty crops
        if face_roi.size == 0:
            face_roi = image

        # Normalize size for consistent scoring
        try:
            face_roi = cv2.resize(face_roi, (256, 256))
        except Exception:
            pass
        return face_roi

    def _texture_score(self, gray: np.ndarray) -> Tuple[float, float]:
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        # More lenient: lower threshold for texture (60 instead of 120)
        score = float(np.clip(lap_var / 60.0, 0.0, 1.0))
        return score, lap_var

    def _frequency_score(self, gray: np.ndarray) -> Tuple[float, float]:
        # Downsample for speed
        small = cv2.resize(gray, (128, 128))
        f = np.fft.fftshift(np.fft.fft2(small))
        mag = np.abs(f)

        h, w = mag.shape
        band = mag[h // 4 : 3 * h // 4, w // 4 : 3 * w // 4]
        total_energy = float(mag.sum() + 1e-8)
        center_energy = float(band.sum())
        high_energy = total_energy - center_energy

        ratio = high_energy / total_energy
        # More lenient: lower threshold (0.15 instead of 0.25) and wider range
        score = float(np.clip((ratio - 0.15) / 0.5, 0.0, 1.0))
        return score, ratio

    def _color_score(self, bgr: np.ndarray) -> Tuple[float, float]:
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        saturation = hsv[:, :, 1] / 255.0
        sat_std = float(np.std(saturation))
        # Slightly stricter color variation requirement to avoid flat prints
        score = float(np.clip((sat_std - 0.08) / 0.3, 0.0, 1.0))
        return score, sat_std

    def _illumination_check(self, gray: np.ndarray) -> Tuple[bool, float, float]:
        """Detect very dark or flat lighting where spoof checks are unreliable."""
        brightness = float(np.mean(gray))
        contrast = float(np.std(gray))
        # Only block VERY dark or VERY flat (photos/videos often have low contrast)
        # Allow reasonable lighting conditions to pass
        low_light = brightness < 40 or contrast < 15
        return low_light, brightness, contrast

    def _edge_screen_check(self, gray: np.ndarray) -> Tuple[bool, float, float]:
        edges = cv2.Canny(gray, 70, 200)
        edge_density = float(edges.mean() / 255.0)

        border_band = 8  # Wider border check
        top_band = float(edges[:border_band, :].sum())
        bottom_band = float(edges[-border_band:, :].sum())
        left_band = float(edges[:, :border_band].sum())
        right_band = float(edges[:, -border_band:].sum())
        total_edges = float(edges.sum() + 1e-8)

        border_ratio = (top_band + bottom_band + left_band + right_band) / total_edges
        # Stricter: detect borders more aggressively
        strong_border = border_ratio > 0.30 and edge_density < 0.15
        return strong_border, edge_density, border_ratio
    
    def _specular_reflection_check(self, bgr: np.ndarray) -> Tuple[bool, float]:
        """Check for specular reflections common in screens."""
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        # High brightness areas indicate screen reflections
        bright_pixels = np.sum(gray > 200) / gray.size
        # Screens often have very bright spots
        has_specular = bright_pixels > 0.15
        return has_specular, float(bright_pixels)
    
    def _temporal_consistency_check(self, face_landmarks: Optional[Dict[str, Any]]) -> Tuple[float, float]:
        """Check if facial landmarks change over time (photos/videos are static)."""
        if not face_landmarks or len(self.landmark_history) < 2:
            if face_landmarks:
                self.landmark_history.append(face_landmarks)
            return 0.5, 0.0
        
        # Calculate landmark movement
        current_nose = face_landmarks.get("nose_tip", [])
        if not current_nose:
            self.landmark_history.append(face_landmarks)
            return 0.5, 0.0
        
        current_center = np.mean(current_nose, axis=0)
        movements = []
        
        for past_landmarks in list(self.landmark_history)[-3:]:  # Check last 3 frames
            past_nose = past_landmarks.get("nose_tip", [])
            if past_nose:
                past_center = np.mean(past_nose, axis=0)
                movement = np.linalg.norm(current_center - past_center)
                movements.append(movement)
        
        self.landmark_history.append(face_landmarks)
        
        if not movements:
            return 0.5, 0.0
        
        avg_movement = float(np.mean(movements))
        # Score based on movement - static faces (photos) have very low movement
        score = float(np.clip(avg_movement / 5.0, 0.0, 1.0))
        return score, avg_movement

    def _motion_score(self, gray: np.ndarray) -> Tuple[float, float]:
        self.frame_count += 1
        
        if self.last_gray is None:
            self.last_gray = gray
            self.last_timestamp = time.time()
            # More lenient initial score
            return 0.5, 0.0

        diff = cv2.absdiff(gray, self.last_gray)
        motion_intensity = float(np.mean(diff))

        self.last_gray = gray
        self.last_timestamp = time.time()

        # More lenient motion detection
        norm_motion = float(np.clip(motion_intensity / 5.0, 0.0, 1.0))
        self.motion_history.append(norm_motion)
        
        # More lenient motion scoring
        if len(self.motion_history) < 2:
            # First frame: give benefit of doubt
            averaged = float(np.mean(self.motion_history)) * 0.9
        else:
            # After 2+ frames: average motion
            recent_motion = list(self.motion_history)[-3:]
            averaged = float(np.mean(recent_motion))
            # Only penalize if motion is EXTREMELY consistent (very suspicious)
            motion_variance = float(np.std(recent_motion))
            if motion_variance < 0.02:  # Only penalize extremely uniform motion
                averaged *= 0.7
            # Boost if we have good motion history
            if len(self.motion_history) >= 3:
                averaged = min(1.0, averaged * 1.1)
        
        return averaged, motion_intensity

    @staticmethod
    def _ear(eye_landmarks) -> float:
        eye = np.array(eye_landmarks)
        if eye.shape[0] < 6:
            return 0.0

        a = np.linalg.norm(eye[1] - eye[5])
        b = np.linalg.norm(eye[2] - eye[4])
        c = np.linalg.norm(eye[0] - eye[3])
        return float((a + b) / (2.0 * c + 1e-8))

    def _blink_score(self, face_landmarks: Optional[Dict[str, Any]]) -> Tuple[float, float]:
        if not face_landmarks:
            return 0.5, 0.0
        try:
            left = face_landmarks.get("left_eye")
            right = face_landmarks.get("right_eye")
            if not left or not right:
                return 0.5, 0.0
            left_ear = self._ear(left)
            right_ear = self._ear(right)
            ear = (left_ear + right_ear) / 2.0
            # Normal relaxed EAR tends to live between 0.18 and 0.32
            live_range = 0.18 <= ear <= 0.32
            score = 0.8 if live_range else 0.4
            return float(score), float(ear)
        except Exception:
            return 0.5, 0.0

    def comprehensive_anti_spoofing_check(
        self,
        image: np.ndarray,
        face_landmarks: Optional[Dict[str, Any]] = None,
        face_location: Optional[Tuple[int, int, int, int]] = None,
    ) -> Dict[str, Any]:
        """Analyze a detected face and return liveness confidence."""
        try:
            face_roi = self._prepare_face(image, face_location)
            gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)

            texture_score, lap_var = self._texture_score(gray)
            freq_score, freq_ratio = self._frequency_score(gray)
            color_score, sat_std = self._color_score(face_roi)
            motion_score, motion_intensity = self._motion_score(gray)
            blink_score, ear = self._blink_score(face_landmarks)
            strong_border, edge_density, border_ratio = self._edge_screen_check(gray)
            has_specular, specular_ratio = self._specular_reflection_check(face_roi)
            low_light, brightness, contrast = self._illumination_check(gray)
            temporal_score, landmark_movement = self._temporal_consistency_check(face_landmarks)

            # Balanced weights: favor texture and motion
            confidence = (
                0.28 * texture_score
                + 0.20 * freq_score
                + 0.18 * color_score
                + 0.24 * motion_score  # Keep motion important
                + 0.08 * blink_score
                + 0.02 * temporal_score  # small weight to landmark motion
            )
            confidence = float(round(confidence, 4))

            # Balanced thresholds - block spoofs but allow legitimate faces
            min_confidence = 0.45  # Lowered to allow good faces with decent lighting
            min_frames_required = 2  # Allow faster acceptance
            
            # Reasonable motion requirements - not too strict
            has_good_motion = motion_score >= 0.12 or (motion_score >= 0.08 and len(self.motion_history) >= 3)
            has_temporal_change = temporal_score >= 0.10 or landmark_movement > 1.5  # More reasonable movement
            
            # Calculate individual scores check - flexible OR logic
            has_good_individual_scores = (
                (freq_score >= 0.18 or texture_score >= 0.22)  # At least one texture/freq check passes
                and (motion_score >= 0.10 or len(self.motion_history) >= 3)  # Some motion detected
            )
            
            # Hard blocks ONLY for obvious spoofs or very unreliable conditions
            if strong_border or has_specular or low_light:
                is_live = False
                # Force very low confidence when screen reflection is detected (ensures notification trigger)
                if has_specular:
                    confidence = min(confidence, 0.15)  # Override confidence to guarantee anti-spoofing alert
            elif self.frame_count < min_frames_required:
                # Too early - need more frames
                is_live = False
            elif len(self.motion_history) < min_frames_required:
                # Not enough motion history
                is_live = False
            else:
                # More flexible: pass if confidence is good OR individual scores are good
                # Still require motion and block obvious spoofs
                is_live = (
                    (confidence >= min_confidence or has_good_individual_scores)  # Flexible: confidence OR good scores
                    and has_good_motion  # Still require some motion
                    and not strong_border
                    and not has_specular
                    and not low_light
                )

            details = "Live face confirmed" if is_live else "Spoofing pattern detected"
            if strong_border:
                details = "Screen/print border detected - please use a live face"
            elif has_specular:
                details = "Screen reflection detected - please use a live face, not a screen"
            elif low_light:
                details = "Environment too dark or low contrast - improve lighting"
            elif self.frame_count < min_frames_required:
                details = f"Verifying... ({min_frames_required - self.frame_count} more frame(s))"
            elif len(self.motion_history) < min_frames_required:
                details = "Building motion profile..."
            elif not has_good_motion:
                details = "Please move slightly for verification"
            elif confidence < min_confidence and not has_good_individual_scores:
                details = "Please ensure good lighting and face the camera directly"
            else:
                details = "Verifying liveness..."

            return {
                "success": True,
                "is_live": bool(is_live),
                "confidence": confidence,
                "details": details,
                "checks": {
                    "texture_analysis": {"passed": texture_score >= 0.22, "score": texture_score, "variance": lap_var},
                    "frequency_analysis": {"passed": freq_score >= 0.18, "score": freq_score, "ratio": freq_ratio},
                    "color_analysis": {"passed": color_score >= 0.18, "score": color_score, "sat_std": sat_std},
                    "motion_analysis": {"passed": motion_score >= 0.12 or (motion_score >= 0.08 and len(self.motion_history) >= 3), "score": motion_score, "intensity": motion_intensity, "frames": len(self.motion_history)},
                    "temporal_consistency": {"passed": temporal_score >= 0.10 or landmark_movement > 1.5, "score": temporal_score, "movement": landmark_movement},
                    "blink_detection": {"passed": blink_score >= 0.5, "score": blink_score, "ear": ear},
                    "border_screen": {"passed": not strong_border, "edge_density": edge_density, "border_ratio": border_ratio},
                    "specular_reflection": {"passed": not has_specular, "ratio": specular_ratio},
                    "illumination": {"passed": not low_light, "brightness": brightness, "contrast": contrast},
                },
            }
        except Exception as exc:
            print(f"Anti-spoofing error: {exc}")
            return {
                "success": False,
                "is_live": False,
                "confidence": 0.0,
                "details": f"Anti-spoofing error: {exc}",
                "checks": {},
            }


# Global anti-spoofing detector instance
anti_spoofing_detector = AntiSpoofingDetector()

