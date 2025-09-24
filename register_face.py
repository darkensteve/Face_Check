import os
import cv2
import face_recognition

SAVE_DIR = "known_faces"
os.makedirs(SAVE_DIR, exist_ok=True)

def normalize_name(name: str) -> str:
    # "Maria Dela Cruz" -> "maria_delacruz"
    return "".join(ch for ch in name.lower() if ch.isalnum() or ch == " ").strip().replace(" ", "_")

def next_out_path(base: str) -> str:
    # Prefer base.jpg, then base_2.jpg, base_3.jpg, ...
    i = 1
    path = os.path.join(SAVE_DIR, f"{base}.jpg")
    while os.path.exists(path):
        i += 1
        path = os.path.join(SAVE_DIR, f"{base}_{i}.jpg")
    return path

name = input("Enter student name (e.g., Maria Dela Cruz or Maria): ").strip()
if not name:
    print("Name is required.")
    raise SystemExit(1)
base = normalize_name(name)

# Fast detector for smooth preview
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

print("Press 's' to save a face, 'q' to quit.")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Smooth preview: detect on a smaller grayscale image
    preview_scale = 0.6
    small = cv2.resize(frame, (0, 0), fx=preview_scale, fy=preview_scale)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))

    # Draw boxes on the full-size frame
    for (x, y, w, h) in faces:
        X = int(x / preview_scale)
        Y = int(y / preview_scale)
        W = int(w / preview_scale)
        H = int(h / preview_scale)
        cv2.rectangle(frame, (X, Y), (X + W, Y + H), (0, 255, 255), 2)

    cv2.imshow("Register Face - Press 's' to save, 'q' to quit", frame)
    key = cv2.waitKey(1) & 0xFF

    if key == ord('s'):
        if len(faces) == 0:
            print("No face detected. Try again.")
            continue

        # Select the largest face from preview for saving
        (x, y, w, h) = max(faces, key=lambda b: b[2] * b[3])
        X = int(x / preview_scale)
        Y = int(y / preview_scale)
        W = int(w / preview_scale)
        H = int(h / preview_scale)

        # Crop with margin from the original frame
        pad = 20
        Himg, Wimg = frame.shape[:2]
        x1 = max(0, X - pad)
        y1 = max(0, Y - pad)
        x2 = min(Wimg, X + W + pad)
        y2 = min(Himg, Y + H + pad)
        face_img = frame[y1:y2, x1:x2]

        # Validate: ensure a true face encoding exists in the crop
        rgb = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
        boxes = face_recognition.face_locations(rgb, number_of_times_to_upsample=1, model="hog")
        encs = face_recognition.face_encodings(rgb, boxes)
        if not encs:
            print("Face not clear enough. Move closer, look at camera, and try again.")
            continue

        out_path = next_out_path(base)
        cv2.imwrite(out_path, face_img)
        print(f"Saved: {out_path}")

    if key == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
print("Done.")