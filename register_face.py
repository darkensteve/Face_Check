import os
import cv2
import time
import threading

try:
    import winsound
    def beep_ok():
        try:
            winsound.Beep(900, 120)
        except:
            pass
except Exception:
    def beep_ok():
        pass

SAVE_DIR = "known_faces"
os.makedirs(SAVE_DIR, exist_ok=True)

def normalize_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum() or ch == " ").strip().replace(" ", "_")

def next_out_path(base: str) -> str:
    i = 1
    p = os.path.join(SAVE_DIR, f"{base}.jpg")
    while os.path.exists(p):
        i += 1
        p = os.path.join(SAVE_DIR, f"{base}_{i}.jpg")
    return p

name = input("Enter student name (e.g., Maria Dela Cruz or Maria): ").strip()
if not name:
    print("Name is required."); raise SystemExit(1)
base = normalize_name(name)

# Smooth preview detector (Haar)
haar = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

print("Press 's' to save instantly, 'q' to quit. (Tip: look at camera; keep face inside yellow box.)")

status_msg = ""
status_until = 0.0

def set_status(msg, seconds=2.0):
    global status_msg, status_until
    status_msg = msg
    status_until = time.time() + seconds

def save_crop(frame, box):
    (X, Y, W, H) = box
    pad = 20
    h, w = frame.shape[:2]
    x1 = max(0, X - pad); y1 = max(0, Y - pad)
    x2 = min(w, X + W + pad); y2 = min(h, Y + H + pad)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0 or W * H < 3000:  # only reject if extremely tiny
        set_status("Face too small. Move closer.", 2.0)
        return
    out_path = next_out_path(base)
    cv2.imwrite(out_path, crop)
    set_status(f"Saved: {os.path.basename(out_path)}", 1.5)
    beep_ok()

while True:
    ok, frame = cap.read()
    if not ok:
        break

    # Detect faces for preview
    preview_scale = 0.6
    small = cv2.resize(frame, (0, 0), fx=preview_scale, fy=preview_scale)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    faces = haar.detectMultiScale(gray, scaleFactor=1.08, minNeighbors=4, minSize=(60, 60))

    # Choose biggest face as target
    biggest = None
    biggest_area = 0
    for (x, y, w, h) in faces:
        X, Y = int(x/preview_scale), int(y/preview_scale)
        W, H = int(w/preview_scale), int(h/preview_scale)
        cv2.rectangle(frame, (X, Y), (X+W, Y+H), (0, 255, 255), 2)
        area = W * H
        if area > biggest_area:
            biggest_area = area
            biggest = (X, Y, W, H)

    # HUD
    cv2.putText(frame, "Press 's' to save instantly, 'q' to quit", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255,255,255), 2)
    if time.time() < status_until and status_msg:
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (frame.shape[1], 50), (0, 180, 0), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)
        cv2.putText(frame, status_msg, (12, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2)

    cv2.imshow("Register Face (Instant)", frame)
    key = cv2.waitKey(1) & 0xFF

    if key == ord('s'):
        if biggest is None:
            set_status("No face detected. Center your face and try again.", 2.0)
        else:
            # Save immediately; no heavy verification
            save_crop(frame, biggest)

    if key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Done.")