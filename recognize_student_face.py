"""
recognize_student_face.py
Facial Recognition Utility for Student Identification

Purpose:
This script powers the facial recognition component of an AI-driven 
attendance system. It uses a webcam to detect student faces, compares 
them to a database of stored face encodings, and marks attendance in 
real-time. It also enables WebSocket-based communication with a frontend
dashboard for live updates.

🔧 Key Features:
- Captures and analyzes video frames using OpenCV and face_recognition.
- Matches detected faces against pre-encoded data from a database.
- Marks recognized students as "Present" and logs attendance.
- Emits live updates to a frontend interface via SocketIO.
- Supports end-of-session cleanup by marking absent students.
"""

# IMPORTS
import os  # Interacts with the operating system (not directly used here, can be removed if unused)
import cv2  # OpenCV for capturing video from webcam and image processing
import json  # To handle encoding data stored as JSON in the database
import numpy as np  # Used to calculate distances between face encodings
import sqlite3  # To connect to the SQLite database storing student data
import face_recognition  # Main library for face detection and face encoding
import base64  # (Later used) for encoding images to send over sockets
from datetime import datetime  # Get current timestamps for attendance records
from flask_socketio import SocketIO  # Enable WebSocket communication for real-time updates

# DATABASE SETUP
DATABASE = "attendance_system.db"  # SQLite database path

def connect_db():
    """
    Establishes a connection to the SQLite database.
    Returns a connection object that can be used to execute queries.
    """
    return sqlite3.connect(DATABASE)

def recognize_student_face():
    """
    Recognizes a student's face using webcam capture and compares it
    with previously stored face encodings in the database.

    Process:
    - Captures an image via webcam.
    - Detects face(s) in the image.
    - Encodes the face(s) using face_recognition.
    - Compares the encoding with stored encodings in the SQLite DB.
    - Returns the best matching student or None if no match is found.

    Returns:
        dict with student name and enrollment if matched,
        else None.
    """

    print("📷 DEBUG: Starting Facial Recognition...")

    cam = cv2.VideoCapture(0)  # Open the webcam (device 0)

    if not cam.isOpened():
        print("❌ ERROR: Camera could not be opened!")
        return None

    # Set resolution of captured image
    cam.set(3, 1280)  # width
    cam.set(4, 720)   # height

    # Capture one frame from the webcam
    ret, img = cam.read()
    cam.release()  # Always release the camera after capturing

    if not ret:
        print("❌ Camera error: Could not capture an image!")
        return None

    print("✅ Camera successfully captured an image.")

    # Convert image to RGB format for face_recognition
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Detect face locations using HOG model (faster, works offline)
    face_locations = face_recognition.face_locations(rgb_img, model="hog")

    if len(face_locations) == 0:
        print("❌ No face detected in the frame!")
        return None

    print(f"✅ {len(face_locations)} face(s) detected.")

    # Get facial encodings from the detected face(s)
    detected_encoding = face_recognition.face_encodings(rgb_img, face_locations)

    if not detected_encoding:
        print("❌ No encoding generated from the detected face.")
        return None

    # Only take the first face encoding (assuming one face at a time)
    detected_encoding = detected_encoding[0]

    # Connect to DB and fetch all students and their face encodings
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, enrollment, face_encoding FROM students")
        students = cursor.fetchall()

    best_match = None
    best_distance = 0.6  # Threshold for matching faces

    # Loop through each student and compare their encoding
    for student_id, name, enrollment, encoding_str in students:
        try:
            stored_encodings = json.loads(encoding_str)  # Load stringified encoding

            if not stored_encodings:
                print(f"⚠️ No valid encodings for {name}. Skipping.")
                continue

            for stored_encoding in stored_encodings:
                stored_encoding = np.array(stored_encoding, dtype=np.float64)

                # Compute distance between stored and detected encoding
                distance = np.linalg.norm(stored_encoding - detected_encoding)

                # If it's a better match (i.e., closer), store it
                if distance < best_distance:
                    best_match = {"Enrollment": enrollment, "Name": name}
                    best_distance = distance

        except json.JSONDecodeError:
            print(f"❌ Error decoding encodings for {name}. Skipping.")
            continue

    # Final decision: did we match anyone?
    if best_match:
        print(f"✅ Recognized: {best_match['Name']} ({best_match['Enrollment']})")
        return best_match

    print("❌ No match found!")
    return None


# WEBSOCKET SETUP

# This enables Flask to communicate with clients in real-time (e.g., stream video frames).
socketio = SocketIO(cors_allowed_origins="*")


# LOAD STORED FACE ENCODINGS FROM FILE

# We read the pre-saved face encodings from a JSON file for use in live detection
with open("face_recognition_model.json", "r") as f:
    model_data = json.load(f)

# The encodings are stored as lists of vectors (128-d), we convert them to NumPy arrays
known_face_encodings = np.array([np.array(enc_list) for enc_list in model_data["encodings"]]).reshape(-1, 128)

# Also load the list of student enrollment IDs associated with the encodings
known_face_enrollments = model_data["enrollments"]


# GLOBAL CAMERA INSTANCE FOR LIVE VIDEO (used later)
cam = None  # Stores OpenCV camera reference for streaming
stop_flag = False  # Flag used to stop streaming threads
background_task = None  # Placeholder for the async task/thread
 
def recognize_faces_live(app, socketio, class_id, professor_id):
    """
    Real-Time Face Recognition for Classroom Attendance

    This function activates the webcam and continuously captures video frames.
    Each frame is analyzed for faces using `face_recognition`, and matched against
    preloaded encodings to recognize students.

    Once students are recognized, their attendance is:
    - Sent live to the frontend via WebSocket (using SocketIO)
    - Recorded in the SQLite database
    - Tracked during the session to avoid duplicate entries

    Parameters:
    - app: Flask app instance used for context handling.
    - socketio: Flask-SocketIO instance for real-time communication.
    - class_id: ID of the current class session (used to tag attendance).
    - professor_id: ID of the professor (used for record tracking).

    The function runs until either:
    - The 'q' key is pressed
    - A global stop flag is triggered (`stop_flag = True`)

    Requirements:
    - The global `known_face_encodings` and `known_face_enrollments` must be loaded before calling this.
    - The global `cam` and `SESSION_RECOGNIZED_STUDENTS` are used and managed here.

    Returns:
    - None. It sends data via WebSocket and updates the database.
    """

    # Make variables global so we can share them between threads
    global cam, stop_flag, SESSION_RECOGNIZED_STUDENTS

    # Reset the stop flag to make sure the loop runs
    stop_flag = False

    # Activate Flask app context to interact with DB and emit events
    with app.app_context():

        # 📸 Open the webcam if it's not already active
        if cam is None:
            cam = cv2.VideoCapture(0)

        if not cam.isOpened():
            print("❌ Camera failed to open.")
            return

        print("📸 Starting Live Attendance...")

        # Infinite loop — runs until user quits or stop_flag is True
        while cam is not None:
            if stop_flag:  # 🚨 External flag to stop the loop
                print("🛑 Stop flag detected, force quitting...")
                break

            # Read a frame from the webcam
            ret, frame = cam.read()
            if not ret or frame is None:
                continue  # Skip if frame wasn't captured properly

            # Convert frame to RGB (required by face_recognition)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Detect all face locations in the frame
            face_locations = face_recognition.face_locations(rgb_frame)

            # Get encodings for all detected faces
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            recognized_students = []  # 📋 List to store enrollments of recognized students

            # Loop through each detected face
            for face_encoding, face_location in zip(face_encodings, face_locations):
                # Compare with known encodings (returns list of True/False)
                matches = face_recognition.compare_faces(
                    known_face_encodings, face_encoding, tolerance=0.4
                )

                # Measure how close the face is to each known face
                face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)

                # Find the closest matching known face
                best_match_index = np.argmin(face_distances) if face_distances.size > 0 else None

                # If we have a good match...
                if best_match_index is not None and matches[best_match_index]:
                    # Each student may have 20 encodings → figure out which student it is
                    student_index = best_match_index // 20

                    # Get the student's enrollment number
                    if student_index < len(known_face_enrollments):
                        enrollment = known_face_enrollments[student_index]
                        recognized_students.append(enrollment)

            # Send the current video frame and recognized students to the frontend
            send_frame_to_frontend(app, socketio, frame, recognized_students, class_id)

            # Skip DB updates if nobody is recognized
            if not recognized_students:
                print("⚠️ [DEBUG] No students recognized in this frame. Skipping attendance update.")
                continue

            # Save attendance in the database
            print(f"📝 Saving attendance for class {class_id}")
            mark_attendance_in_db(class_id, professor_id, recognized_students)

            # Compute recognition accuracy for debugging
            accuracy = compute_recognition_accuracy(class_id, recognized_students)
            print(f"✅ Facial Recognition Accuracy for class {class_id}: {accuracy:.2f}%")

            # Exit if user presses 'q' or if stop_flag was externally set
            if cv2.waitKey(1) & 0xFF == ord('q') or stop_flag:
                print("🛑 Stop flag triggered, breaking loop...")
                break    

        # Clean up resources after exiting the loop
        print("🛑 Stopping Live Attendance...")
        if cam:
            cam.release()  # 📷 Turn off the webcam
            cam = None
            print("✅ Camera released.")

        print("✅ Background task fully stopped.")


def compute_recognition_accuracy(class_id, recognized_students):
    """
    Compute Facial Recognition Accuracy for a Class

    This function compares the list of students recognized by the system in a session
    (`recognized_students`) with the list of students officially enrolled in the class (`class_id`)
    and computes how accurate the face recognition was.

    It helps assess how many present students were correctly identified by the system.
    """
    
    with sqlite3.connect("attendance_system.db") as conn:
        cursor = conn.cursor()
        
        # Get the ground-truth set of students enrolled in the class
        cursor.execute("SELECT enrollment FROM student_classes WHERE class_id = ?", (class_id,))
        actual_students_present = set([row[0] for row in cursor.fetchall()])

        # Calculate how many recognized students match with actual enrolled students
        correctly_recognized = len(set(recognized_students) & actual_students_present)
        total_present = len(actual_students_present)
        
        # Compute accuracy (percentage of correct recognitions)
        accuracy = (correctly_recognized / total_present) * 100 if total_present > 0 else 0
        print(f"🎯 Recognition Accuracy: {accuracy:.2f}%")
        
        return accuracy


def send_frame_to_frontend(app, socketio, frame, recognized_students, class_id):
    """
    Send Encoded Video Frame & Attendance Data to Frontend (Dashboard)

    This function encodes the current webcam frame and sends it to the frontend along with:
    - The list of students enrolled
    - The ones recognized in this session
    - Their total absences

    This allows the professor's dashboard to display real-time visual and attendance updates.
    """

    global SESSION_RECOGNIZED_STUDENTS

    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()

        # Fetch all students enrolled in this class
        cursor.execute("SELECT enrollment, student_name FROM student_classes WHERE class_id = ?", (class_id,))
        enrolled_students = {row[0]: row[1] for row in cursor.fetchall()}  # {enrollment: name}

        # Get the name of the class
        cursor.execute("SELECT class_name FROM classrooms WHERE id = ?", (class_id,))
        class_name = cursor.fetchone()
        class_name = class_name[0] if class_name else "Unknown Class"

        # Get count of absences for each student
        absences = {}
        for enrollment in enrolled_students.keys():
            cursor.execute("""
                SELECT COUNT(*) FROM attendance WHERE enrollment = ? AND status = 'Absent'
            """, (enrollment,))
            absences[enrollment] = cursor.fetchone()[0]

    # Convert webcam frame to base64 so it can be sent via WebSocket
    _, buffer = cv2.imencode('.jpg', frame)
    encoded_frame = base64.b64encode(buffer).decode('utf-8')

    # Track students recognized during the session
    SESSION_RECOGNIZED_STUDENTS.update(recognized_students)

    # Build attendance data for each student
    students_list = []
    for enrollment, student_name in enrolled_students.items():
        students_list.append({
            "enrollment": enrollment,
            "name": student_name,
            "status": "Present" if enrollment in SESSION_RECOGNIZED_STUDENTS else "Absent",
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S") if enrollment in SESSION_RECOGNIZED_STUDENTS else "N/A",
            "class": class_name,
            "class_id": class_id,
            "absences": absences.get(enrollment, 0)
        })

    # Debug Output
    print(f" [DEBUG] Updated SESSION_RECOGNIZED_STUDENTS: {SESSION_RECOGNIZED_STUDENTS}")
    print(f" [DEBUG] Sending to UI → {students_list}")

    # Emit event to frontend dashboard
    socketio.emit("video_frame", {
        "image": encoded_frame,
        "students": students_list
    })


SESSION_RECOGNIZED_STUDENTS = set()
def mark_attendance_in_db(class_id, professor_id, recognized_students, session_end=False):
    """
    Mark Attendance in Database (Live + End-of-Session)

    This function does 2 main things:
    1. Marks recognized students as 'Present' during live attendance
    2. If `session_end=True`, it marks all other enrolled students as 'Absent'

    Parameters:
    - class_id: Class session ID
    - professor_id: ID of professor taking attendance
    - recognized_students: List of enrollments recognized in the current frame
    - session_end (bool): If True, it closes the session and finalizes attendance
    """

    global SESSION_RECOGNIZED_STUDENTS  

    with sqlite3.connect("attendance_system.db") as conn:
        cursor = conn.cursor()
        now_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        today_date = datetime.now().strftime("%Y-%m-%d")

        # Get all students enrolled in the class
        cursor.execute("SELECT enrollment FROM student_classes WHERE class_id = ?", (class_id,))
        enrolled_students = {row[0] for row in cursor.fetchall()}
        print(f" [DEBUG] Enrolled students in class {class_id}: {enrolled_students}")

        # Check attendance already recorded today
        cursor.execute("""
            SELECT enrollment, status, time_recognized FROM attendance 
            WHERE class_id = ? AND date = ?
        """, (class_id, today_date))
        existing_attendance = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
        print(f" [DEBUG] Existing attendance for class {class_id}: {existing_attendance}")

        # Update session tracker
        SESSION_RECOGNIZED_STUDENTS.update(recognized_students)

        # Step 1: Mark recognized students as Present
        for student in recognized_students:
            if student in enrolled_students:
                prev_status, prev_time = existing_attendance.get(student, ("Absent", None))

                if prev_status == "Present":
                    # Update timestamp if already marked Present
                    print(f"✅ [INFO] Student {student} is already Present. Updating timestamp.")
                    cursor.execute("""
                        UPDATE attendance 
                        SET time_recognized = ?
                        WHERE class_id = ? AND enrollment = ? AND date = ?;
                    """, (now_timestamp, class_id, student, today_date))
                else:
                    # 🆕 Mark student as Present
                    print(f"✅ [UPDATE] Marking student {student} as Present in DB.")
                    cursor.execute("""
                        INSERT INTO attendance (class_id, enrollment, date, status, time_recognized, professor_id, absences)
                        VALUES (?, ?, ?, 'Present', ?, ?, 0)
                        ON CONFLICT(class_id, enrollment, date) 
                        DO UPDATE SET 
                            status = 'Present',
                            time_recognized = excluded.time_recognized;
                    """, (class_id, student, today_date, now_timestamp, professor_id))

                # Update memory
                existing_attendance[student] = ("Present", now_timestamp)

        # Step 2: If session ended, mark unrecognized students as Absent
        if session_end:
            print(f"⚠️ [DEBUG] SESSION_END TRIGGERED - Checking for Absent students!")

            cursor.execute("""
                SELECT enrollment, status FROM attendance 
                WHERE class_id = ? AND date = ?
            """, (class_id, today_date))
            final_existing_attendance = {row[0]: row[1] for row in cursor.fetchall()}

            absent_students = {
                student for student in enrolled_students 
                if student not in SESSION_RECOGNIZED_STUDENTS and final_existing_attendance.get(student) != "Present"
            }

            print(f"🚨 [DEBUG] Students that will be marked Absent: {absent_students}")

            for student in absent_students:
                previous_status = final_existing_attendance.get(student, "Never marked before")

                if previous_status == "Present":
                    print(f"🚨 [ERROR] Student {student} was already Present but is being changed to Absent! THIS SHOULD NOT HAPPEN!")

                # Insert Absent record or increment absences
                print(f"❌ [UPDATE] Marking student {student} as Absent. Previous status: {previous_status}.")
                cursor.execute("""
                    INSERT INTO attendance (class_id, enrollment, date, status, time_recognized, professor_id, absences)
                    VALUES (?, ?, ?, 'Absent', NULL, ?, 1)
                    ON CONFLICT(class_id, enrollment, date) 
                    DO UPDATE SET 
                        absences = attendance.absences + 1;
                """, (class_id, student, today_date, professor_id))

        # Final debug snapshot of attendance
        cursor.execute("""
            SELECT enrollment, status, time_recognized FROM attendance 
            WHERE class_id = ? AND date = ?
        """, (class_id, today_date))
        updated_attendance = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
        print(f" [DEBUG] Final attendance for class {class_id}: {updated_attendance}")

        conn.commit()
