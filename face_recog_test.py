import os
import cv2
import face_recognition
from attendance_utils import mark_attendance, load_today_names

DETECTION_DOWNSCALE = 0.5
UPSAMPLE_TIMES = 2
FACE_MODEL = "hog"

def load_known_faces(folder="known_faces"):
    encodings = []
    names = []
    os.makedirs(folder, exist_ok=True)

    for fname in os.listdir(folder):
        path = os.path.join(folder, fname)
        if not os.path.isfile(path):
            continue
        ext = os.path.splitext(fname)[1].lower()
        if ext not in [".jpg", ".jpeg", ".png"]:
            continue
        base = os.path.splitext(fname)[0]
        person = base.split("_")[0]  # "steve_2" -> "steve"
        img = face_recognition.load_image_file(path)

        # Robust detection for saved crops
        boxes = face_recognition.face_locations(img, number_of_times_to_upsample=1, model="hog")
        if not boxes:
            boxes = face_recognition.face_locations(img, number_of_times_to_upsample=2, model="hog")
        if not boxes:
            print(f"Skipped (no face found): {fname}")
            continue

        encs = face_recognition.face_encodings(img, boxes)
        if not encs:
            print(f"Skipped (no encodings): {fname}")
            continue

        encodings.append(encs[0])
        names.append(person.title())
    return encodings, names

def reload_knowns():
    global known_face_encodings, known_face_names
    known_face_encodings, known_face_names = load_known_faces("known_faces")
    print(f"Loaded {len(known_face_encodings)} face(s).")

# Initial load
known_face_encodings, known_face_names = [], []
reload_knowns()

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

def create_kcf_tracker():
    try:
        return cv2.TrackerKCF_create()
    except AttributeError:
        return cv2.legacy.TrackerKCF_create()

tracker = None
current_name = "Unknown"
already_marked = set(load_today_names())

while True:
    ret, frame = cap.read()
    if not ret:
        break

    if tracker is None:
        small_frame = cv2.resize(frame, (0, 0), fx=DETECTION_DOWNSCALE, fy=DETECTION_DOWNSCALE)
        rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(
            rgb_small_frame,
            number_of_times_to_upsample=UPSAMPLE_TIMES,
            model=FACE_MODEL
        )
        face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

        if face_encodings:
            enc = face_encodings[0]
            current_name = "Unknown"
            if known_face_encodings:
                matches = face_recognition.compare_faces(known_face_encodings, enc)
                if True in matches:
                    match_index = matches.index(True)
                    current_name = known_face_names[match_index]
                    if current_name not in already_marked and mark_attendance(current_name):
                        already_marked.add(current_name)

            (top, right, bottom, left) = face_locations[0]
            scale = 1.0 / DETECTION_DOWNSCALE
            top, right, bottom, left = int(top*scale), int(right*scale), int(bottom*scale), int(left*scale)

            tracker = create_kcf_tracker()
            tracker.init(frame, (left, top, right-left, bottom-top))

            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            cv2.putText(frame, current_name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    else:
        success, box = tracker.update(frame)
        if success:
            (x, y, w, h) = [int(v) for v in box]
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(frame, current_name, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        else:
            tracker = None
            current_name = "Unknown"

    cv2.imshow("Face Recognition + Tracking - Press Q to exit (R to reload faces)", frame)

    key = cv2.waitKey(1) & 0xFF
    if key == ord("q"):
        break
    if key == ord("r"):
        tracker = None
        current_name = "Unknown"
        reload_knowns()
        already_marked = set(load_today_names())

cap.release()
cv2.destroyAllWindows()