from flask import Flask, render_template
import csv
import os
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def home():
    return """
    <h1>�� FaceCheck Attendance System</h1>
    <p><a href="/attendance">View Today's Attendance</a></p>
    <p><a href="/register">Register New Student</a></p>
    <hr>
    <h3>How to use:</h3>
    <ol>
        <li>Run: <code>python register_face.py</code> (to add students)</li>
        <li>Run: <code>python face_recog_test.py</code> (for attendance)</li>
    </ol>
    """

@app.route('/attendance')
def attendance():
    today = datetime.now().strftime("%Y-%m-%d")
    records = []
    
    if os.path.exists("attendance/attendance.csv"):
        with open("attendance/attendance.csv", "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row["date"] == today:
                    records.append(row)
    
    return render_template('attendance.html', attendance=records)

if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5000)