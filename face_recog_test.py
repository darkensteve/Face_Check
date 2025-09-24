import os
import time
import cv2
import numpy as np
import face_recognition
from attendance_utils import mark_attendance, load_today_names

try:
    import winsound
    def notify_beep():
        try:
            winsound.Beep(1000, 150)
        except:
            pass
except Exception:
    def notify_beep():
        pass

cv2.setUseOptimized(True)

# Camera / speed
CAM_W, CAM_H = 640, 480
HAAR_SCALE = 0.6
REDETECT_EVERY = 12
RECOGNIZE_EVERY = 45
LIVENESS_EVERY = 4
ROI_EXPAND = 0.30

# Matching (slightly relaxed so known faces match reliably)
MATCH_TOLERANCE = 0.62  # typical 0.50–0.62

# Liveness (blink + small motion)
REQUIRE_BLINKS = 1
EAR_CLOSE = 0.20
EAR_OPEN = 0.24
EAR_CONSEC_FRAMES = 2
MOTION_MIN_NOSE_PIX = 4

HAAR = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

def load_known_faces(folder="known_faces"):
    """Robust loader: CLAHE + multiple upsample passes to get encodings."""
    encs, names = [], []
    os.makedirs(folder, exist_ok=True)
    for f in os.listdir(folder):
        p = os.path.join(folder, f)
        if not os.path.isfile(p):
            continue
        if os.path.splitext(f)[1].lower() not in [".jpg", ".jpeg", ".png"]:
            continue
        name = os.path.splitext(f)[0].split("_")[0]  # keep raw id from filename

        bgr = cv2.imread(p)
        if bgr is None:
            print(f"Skipped (cannot read): {f}")
            continue

        # CLAHE to improve low-light faces
        ycrcb = cv2.cvtColor(bgr, cv2.COLOR_BGR2YCrCb)
        y, cr, cb = cv2.split(ycrcb)
        y = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(y)
        bgr = cv2.cvtColor(cv2.merge([y, cr, cb]), cv2.COLOR_YCrCb2BGR)

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        locs = face_recognition.face_locations(rgb, number_of_times_to_upsample=1, model="hog")
        if not locs:
            locs = face_recognition.face_locations(rgb, number_of_times_to_upsample=2, model="hog")
        if not locs:
            locs = face_recognition.face_locations(rgb, number_of_times_to_upsample=3, model="hog")

        e = face_recognition.face_encodings(rgb, locs) if locs else face_recognition.face_encodings(rgb)
        if not e:
            print(f"Skipped (no face encodings): {f}")
            continue

        encs.append(e[0])
        names.append(name)

    if not encs:
        print("Warning: no known faces loaded. Put clear frontal photos in 'known_faces/'.")
    else:
        print("Known IDs:", ", ".join(names))
    return encs, names

def reload_knowns():
    global KNOWN_ENCS, KNOWN_NAMES
    KNOWN_ENCS, KNOWN_NAMES = load_known_faces("known_faces")
    print(f"Loaded {len(KNOWN_ENCS)} face(s).")

def _euclid(p1, p2): return np.linalg.norm(np.array(p1) - np.array(p2))
def ear(eye_pts):
    A = _euclid(eye_pts[1], eye_pts[5]); B = _euclid(eye_pts[2], eye_pts[4]); C = _euclid(eye_pts[0], eye_pts[3])
    return (A + B) / (2.0 * C + 1e-6)

def validate_face_roi(frame_bgr, box_xywh):
    """Hard gate: Haar + face_recognition face + key landmarks (eyes + nose)."""
    (x, y, w, h) = box_xywh
    if w < 70 or h < 70:
        return False, None
    H, W = frame_bgr.shape[:2]
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(W, x + w), min(H, y + h)
    roi = frame_bgr[y1:y2, x1:x2]
    if roi.size == 0:
        return False, None

    rgray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    rfaces = HAAR.detectMultiScale(rgray, scaleFactor=1.12, minNeighbors=7, minSize=(60, 60))
    if len(rfaces) == 0:
        return False, None

    r_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
    rlocs = face_recognition.face_locations(r_rgb, number_of_times_to_upsample=2, model="hog")
    if not rlocs:
        rlocs = face_recognition.face_locations(r_rgb, number_of_times_to_upsample=3, model="hog")
    if not rlocs:
        return False, None

    lms = face_recognition.face_landmarks(r_rgb, face_locations=[rlocs[0]])
    if not lms or not all(k in lms[0] for k in ["left_eye", "right_eye", "nose_tip"]):
        return False, None

    encs = face_recognition.face_encodings(r_rgb, [rlocs[0]])
    enc = encs[0] if encs else None
    return (enc is not None), enc

def best_match_name(enc):
    if enc is None or not KNOWN_ENCS: return "Unknown"
    d = face_recognition.face_distance(KNOWN_ENCS, enc)
    i = int(np.argmin(d))
    return KNOWN_NAMES[i] if d[i] <= MATCH_TOLERANCE else "Unknown"

# Load DB
KNOWN_ENCS, KNOWN_NAMES = [], []
reload_knowns()

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAM_W); cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAM_H)

def create_tracker():
    try: return cv2.TrackerCSRT_create()
    except AttributeError:
        try: return cv2.legacy.TrackerCSRT_create()
        except AttributeError:
            try: return cv2.TrackerKCF_create()
            except AttributeError: return cv2.legacy.TrackerKCF_create()

tracker = None
current_name = "Unknown"
already_marked = set(load_today_names())

# Liveness
liveness = False
blink_frames = 0
blink_count = 0
nose_prev = None
nose_max_disp = 0.0

# Attendance notifier
notify_name = ""
notify_until = 0.0

box = None
frame_idx = 0

while True:
    ok, frame = cap.read()
    if not ok: break
    frame_idx += 1

    if tracker is None:
        # Haar detect on downsized frame
        small = cv2.resize(frame, (0, 0), fx=HAAR_SCALE, fy=HAAR_SCALE)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        faces = HAAR.detectMultiScale(gray, scaleFactor=1.12, minNeighbors=7, minSize=(100, 100))
        if len(faces):
            (x, y, w, h) = max(faces, key=lambda b: b[2] * b[3])
            X, Y, W, H = int(x / HAAR_SCALE), int(y / HAAR_SCALE), int(w / HAAR_SCALE), int(h / HAAR_SCALE)
            cand = (X, Y, W, H)

            ok_face, enc = validate_face_roi(frame, cand)
            if ok_face:
                current_name = best_match_name(enc)
                tracker = create_tracker()
                tracker.init(frame, cand)
                box = cand

                if current_name != "Unknown" and current_name not in already_marked:
                    liveness = True; blink_frames = 0; blink_count = 0
                    nose_prev = None; nose_max_disp = 0.0

                cv2.rectangle(frame, (X, Y), (X + W, Y + H), (0, 255, 0), 2)
                cv2.putText(frame, current_name, (X, Y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:
            cv2.putText(frame, "Detecting face...", (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    else:
        ok_t, tbox = tracker.update(frame)
        if ok_t:
            (x, y, w, h) = [int(v) for v in tbox]
            box = (x, y, w, h)
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.putText(frame, current_name, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Validated re-detect in ROI (keeps box on real faces only)
            if frame_idx % REDETECT_EVERY == 0:
                H, W = frame.shape[:2]
                ex, ey = int(w * ROI_EXPAND), int(h * ROI_EXPAND)
                rx1, ry1 = max(0, x - ex), max(0, y - ey)
                rx2, ry2 = min(W, x + w + ex), min(H, y + h + ey)
                roi = frame[ry1:ry2, rx1:rx2]
                if roi.size > 0:
                    rsmall = cv2.resize(roi, (0, 0), fx=HAAR_SCALE, fy=HAAR_SCALE)
                    rgray = cv2.cvtColor(rsmall, cv2.COLOR_BGR2GRAY)
                    rfaces = HAAR.detectMultiScale(rgray, scaleFactor=1.12, minNeighbors=7, minSize=(90, 90))
                    if len(rfaces):
                        (rx, ry, rw, rh) = max(rfaces, key=lambda b: b[2] * b[3])
                        nx, ny, nw, nh = rx1 + int(rx / HAAR_SCALE), ry1 + int(ry / HAAR_SCALE), int(rw / HAAR_SCALE), int(rh / HAAR_SCALE)
                        new_box = (nx, ny, nw, nh)
                        ok_face, _ = validate_face_roi(frame, new_box)
                        if ok_face:
                            tracker = create_tracker()
                            tracker.init(frame, new_box)
                            box = new_box

            # Rare re-identification on validated crop
            if frame_idx % RECOGNIZE_EVERY == 0 and box is not None:
                ok_face, enc = validate_face_roi(frame, box)
                if ok_face:
                    name = best_match_name(enc)
                    if name != "Unknown":
                        current_name = name
        else:
            tracker = None; box = None; current_name = "Unknown"
            liveness = False; nose_prev = None; nose_max_disp = 0.0

    # Liveness (blink + motion), throttled
    if liveness and box is not None and (frame_idx % LIVENESS_EVERY == 0):
        fx, fy, fw, fh = box
        fx1, fy1 = max(0, fx), max(0, fy)
        fx2, fy2 = min(frame.shape[1], fx + fw), min(frame.shape[0], fy + fh)
        crop = frame[fy1:fy2, fx1:fx2]
        if crop.size > 0:
            r = cv2.resize(crop, (220, 220))
            lms = face_recognition.face_landmarks(cv2.cvtColor(r, cv2.COLOR_BGR2RGB),
                                                  face_locations=[(0, r.shape[1], r.shape[0], 0)])
            if lms:
                lm = lms[0]
                if "left_eye" in lm and "right_eye" in lm:
                    e = (ear(lm["left_eye"]) + ear(lm["right_eye"])) / 2.0
                    if e < EAR_CLOSE: blink_frames += 1
                    elif e > EAR_OPEN:
                        if blink_frames >= EAR_CONSEC_FRAMES: blink_count += 1
                        blink_frames = 0
                if "nose_tip" in lm:
                    nose_xy = np.mean(np.array(lm["nose_tip"]), axis=0)
                    if nose_prev is not None:
                        nose_max_disp = max(nose_max_disp, float(np.linalg.norm(nose_xy - nose_prev)))
                    nose_prev = nose_xy

    # Mark + notifier banner
    if liveness and box is not None:
        h, w = frame.shape[:2]
        cv2.putText(frame, f"Blink + small head move • {blink_count}/{REQUIRE_BLINKS}",
                    (12, h - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        if blink_count >= REQUIRE_BLINKS and nose_max_disp >= MOTION_MIN_NOSE_PIX:
            if current_name != "Unknown" and mark_attendance(current_name):
                notify_name = current_name
                notify_until = time.time() + 1.8
                notify_beep()
                already_marked.add(current_name)
            liveness = False
            nose_prev = None; nose_max_disp = 0.0
            blink_count = 0; blink_frames = 0

    # Show banner if active
    if time.time() < notify_until and notify_name:
        h, w = frame.shape[:2]
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 48), (0, 180, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
        cv2.putText(frame, f"Marked present: {notify_name}", (12, 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

    cv2.imshow("Face Recognition (Faces Only) - Q quit, R reload faces", frame)
    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"): break
    if key == ord("r"):
        tracker = None; box = None; current_name = "Unknown"
        liveness = False; nose_prev = None; nose_max_disp = 0.0
        notify_name = ""; notify_until = 0.0
        reload_knowns(); already_marked = set(load_today_names())

cap.release()
cv2.destroyAllWindows()