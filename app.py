# Flask imports for creating web server, routing, session management, and rendering templates
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file, send_from_directory

# Utility imports for handling file uploads and password hashing
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash

# OpenCV for computer vision tasks like image and video processing
import cv2

# Miscellaneous utility imports
import glob  # For working with file paths and patterns
import time  # For handling time-based functions
import random  # For generating random values (e.g., for filenames or tokens)
import string  # For string manipulation, e.g., generating random strings
import threading  # For creating and managing threads in the app
import uuid  # For generating unique identifiers
import os  # For interacting with the operating system, e.g., file and directory handling
import json  # For parsing and working with JSON data
import gc  # Garbage Collector – used to manually manage memory by collecting unused objects to free up space
import signal  # used to handle system signals like Ctrl+C – allows you to gracefully stop a program when it's interrupted
from datetime import datetime, timedelta # Date and time handling
import io  # Provides tools for handling input/output operations in memory (e.g., creating in-memory file-like objects)
import base64  # Used to encode and decode data in Base64 format – helpful for embedding images or files as text (e.g., in HTML)
import matplotlib.pyplot as plt  # Used for creating visual plots and charts – 'plt' is the common alias for Matplotlib's plotting module

# SQLite3 for database interactions
import sqlite3

# Data analysis library, useful for handling and analyzing large datasets
import pandas as pd

# Numpy for numerical operations, often used for handling arrays and matrices
import numpy as np

# Facial recognition library for detecting and recognizing faces in images and video
import face_recognition

# Text-to-speech library for providing voice instructions
import pyttsx3

# Alternative TTS option (subprocess) for system text-to-speech functionality
import subprocess

# Flask-SocketIO for real-time communication between client and server (WebSockets)
from flask_socketio import SocketIO, emit
from flask import current_app
from flask import Flask, request, jsonify
from app import socketio 

# OpenAI API for integrating GPT-based models for NLP tasks
import openai

# Dotenv for loading environment variables (e.g., API keys, sensitive data)
from dotenv import load_dotenv

# Custom agent for attendance insights (presumably a machine learning model or analysis tool)
from agents.insights_agent import AttendanceInsightsAgent
from agents.coordinator import AgentCoordinator  

# Importing custom face recognition functions (likely used for recognizing student faces)
from recognize_student_face import recognize_student_face, recognize_faces_live

# Custom module for training face recognition models
from train_model import train_face_recognition
# FLASK APP CONFIGURATION

# Initialize Flask application
app = Flask(__name__)  
app.secret_key = "my_attendance_secret_key"  # Secret key for encrypting session data

# Enable WebSocket support for real-time communication and allow cross-origin requests
socketio = SocketIO(app, cors_allowed_origins="*")

# Path to SQLite database file where attendance data is stored
DATABASE_PATH = "attendance_system.db"

# Function to get a connection to the SQLite database
def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)  # Connect to the database
    conn.row_factory = sqlite3.Row  # Allows columns to be accessed by name
    return conn

# Establish initial connection to the database
conn = get_db_connection()

# Folder to store attendance records as CSV files
ATTENDANCE_FOLDER = "Attendance_Records"
# Check if the folder exists, create it if not
if not os.path.exists(ATTENDANCE_FOLDER):
    os.makedirs(ATTENDANCE_FOLDER)

# Home Page Route: Displays the homepage (index.html)
@app.route("/")
def home():
    return render_template("index.html")  # Renders and serves the homepage template


# About Page Route: Displays the about page (about.html) with system info
@app.route('/about')
def about():
    return render_template('about.html')  # Renders the about page with system details

# Function to capture a student's face encoding using the webcam
def capture_face_encoding():
    video_capture = cv2.VideoCapture(0)  # Start video capture (webcam)

    # Check if webcam opened successfully
    if not video_capture.isOpened():
        print("❌ Error: Cannot open webcam.")
        return None, None

    # Capture a single frame from the webcam
    ret, frame = video_capture.read()
    video_capture.release()  # Release the webcam after capturing the frame

    # If no frame is captured, return None
    if not ret:
        print("❌ Error: Failed to capture image.")
        return None, None

    # Detect faces in the captured frame
    face_locations = face_recognition.face_locations(frame)
    if len(face_locations) == 0:
        print("⚠️ No face detected.")
        return None, None

    # Encode the detected faces
    face_encodings = face_recognition.face_encodings(frame, face_locations)
    if len(face_encodings) > 0:
        return face_encodings[0].tolist(), frame  # Return the first face encoding and the frame itself
    else:
        print("❌ Error: Could not extract encoding.")
        return None, None


# Route to handle student registration (GET for form, POST for form submission)
@app.route("/register-student", methods=["GET", "POST"])
def register_student_route():
    if request.method == "POST":  # If the form is submitted (POST request)
        print("📩 Received form data:", request.form)

        # Validate that required fields are provided
        required_fields = ["name", "email", "enrollment", "password", "professor_id"]
        for field in required_fields:
            if field not in request.form:
                flash(f"Error: {field} field is missing!", "danger")
                return redirect(url_for("register_student_route"))

        # Extract form data
        name = request.form["name"].strip()
        email = request.form["email"].strip()
        enrollment = request.form["enrollment"].strip()
        password = request.form["password"].strip()
        professor_id = request.form["professor_id"].strip()

        print(f"🛠 Registering Student: {name}, {email}, {enrollment}")

        # Check if a student with the same email already exists
        existing_student = get_student_by_email(email)
        if existing_student:
            flash("⚠️ Email already exists!", "danger")
            return redirect(url_for("register_student_route"))

        # Hash the password for secure storage
        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Register the student in the database and retrain the face recognition model
        if register_student(name, email, enrollment, hashed_password, professor_id):
            train_face_recognition()  # Retrain the model with the new student data
            flash("✅ Registration successful! You can now log in.", "success")
            return redirect(url_for("student_login"))  # Redirect to student login page
        else:
            flash("❌ Registration failed. Try again.", "danger")

    return render_template("register_student.html")  # If GET request, render registration form

# Function to log student activity (e.g., logging in)
def log_student_activity(student_id, action):
    """Logs student activity in the database"""
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO student_activities (student_id, activity) VALUES (?, ?)", 
                       (student_id, action))
        conn.commit()


# Route for student login via traditional method (username/password)
@app.route('/student-login', methods=['GET', 'POST'])
def student_login():
    if request.method == 'POST':  # If form is submitted
        enrollment = request.form['enrollment']
        password = request.form['password']

        # Authenticate the student using the provided enrollment and password
        student_name = authenticate_student(enrollment, password)
        if student_name:
            session['student_id'] = enrollment
            session['student_name'] = student_name
            
            # Log the login action
            log_student_activity(enrollment, "Logged into the system")

            flash("✅ Login successful!", "success")
            return redirect(url_for('student_dashboard'))  # Redirect to student dashboard
        else:
            flash("❌ Invalid credentials. Please try again.", "danger")

    return render_template('student_login.html')  # Render login form if GET request


# Route for student login using face recognition
@app.route("/student-login-face", methods=["POST"])
def student_login_face():
    """Authenticate student via real-time face recognition."""

    print("🔹 Received student face login request...")

    # Recognize the student's face and return student info if recognized
    recognized_student = recognize_student_face()
    print(f"🔹 Recognized student data: {recognized_student}")

    if recognized_student:
        enrollment = recognized_student.get("Enrollment")
        print(f"🔹 Extracted enrollment: {enrollment}")

        # If no enrollment found, notify and redirect
        if not enrollment:
            flash("❌ Face not recognized. Please try again!", "danger")
            return redirect(url_for("student_login"))

        # Fetch student data from the database
        with connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT enrollment, name FROM students WHERE enrollment = ?", (enrollment,))
            student_row = cursor.fetchone()
            print(f"🔹 Student row from DB: {student_row}")

        # If student is found in DB, log in and set session
        if student_row:
            session.clear()
            session["student_id"] = student_row[0]
            session["student_name"] = student_row[1]

            flash(f"✅ Logged in as {student_row[1]}!", "success")
            return redirect(url_for("student_dashboard"))

    flash("❌ Face not recognized. Please try again!", "danger")
    return redirect(url_for("student_login"))


# Route for admin registration
@app.route("/admin-register", methods=["GET", "POST"])
def admin_register():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        # Register admin and show success or failure
        result = register_admin(email, password)
        flash(result, "success" if "successfully" in result else "danger")
        return redirect(url_for("admin_login"))

    return render_template("admin_register.html")  # Render admin registration form


# Route for admin login
@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"].strip()

        print(f"🔍 Attempting login for email: {email}")

        # Authenticate the admin using email and password
        admin = authenticate_admin(email, password)

        if admin:
            session["admin_id"] = admin["id"]
            flash("✅ Login successful!", "success")
            return redirect(url_for("admin_dashboard"))  # Redirect to admin dashboard after successful login
        else:
            flash("❌ Invalid email or password!", "danger")

    return render_template("admin_login.html")  # Render admin login form


# Admin Dashboard Route 
@app.route("/admin-dashboard")
def admin_dashboard():
    """
    Route to display the admin dashboard.
    Fetches and displays recent activity, list of students, professors, and classrooms.
    Redirects if the admin is not logged in.
    """
    if "admin_id" not in session:
        flash("⚠️ Please log in first!", "warning")
        return redirect(url_for("admin_login"))

    conn = get_db_connection()

    # Fetch the 10 most recent admin activities
    activities = conn.execute(
        "SELECT * FROM admin_activity ORDER BY timestamp DESC LIMIT 10"
    ).fetchall()

    # Fetch all students
    students = conn.execute("SELECT id, name FROM students").fetchall()

    # Fetch all classrooms with professor name (assumes column exists)
    classrooms = conn.execute("SELECT id, class_name, professor_name FROM classrooms").fetchall()

    # Fetch all professors
    professors = conn.execute("SELECT id, name FROM professors").fetchall()

    conn.close()

    # Render admin dashboard with all fetched data
    return render_template(
        "admin_dashboard.html",
        activities=activities,
        students=students,
        classrooms=classrooms,
        professors=professors
    )


@app.route("/change-student-password", methods=["POST"])
def change_student_password():
    """
    Admin route to change a student's password.
    Only accessible if admin is logged in.
    """
    if "admin_id" not in session:
        flash("⚠️ Please log in as admin!", "warning")
        return redirect(url_for("admin_login"))

    student_id = request.form["student_id"]
    new_password = request.form["new_password"]

    # Hash the new password using bcrypt
    hashed_password = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    # Update the password in the database
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE students SET password = ? WHERE id = ?", (hashed_password, student_id))
        conn.commit()

    flash("✅ Student password updated successfully!", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/register-professor", methods=["GET", "POST"])
def register_professor_route():
    """
    Admin route to register a new professor.
    Displays form (GET) and processes submission (POST).
    Logs the activity after a successful registration.
    """
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip()
        password = request.form["password"].strip()

        result = register_professor(name, email, password)  # ➕ Register via helper function

        # Log if registration was successful
        if "successfully" in result:
            log_admin_activity(session["admin_id"], f"Added professor {name}")

        flash(result, "success" if "successfully" in result else "danger")
        return redirect(url_for("admin_dashboard"))

    return render_template("register_professor.html")


# Route for professor login (handles GET and POST methods)
@app.route("/professor-login", methods=["GET", "POST"])
def professor_login():
    """
    Login route for professors.
    Checks credentials (email, name, code, password) and logs in professor.
    """
    if request.method == "POST":
        email = request.form["email"].strip()
        name = request.form["name"].strip()
        professor_code = request.form["professor_code"].strip()
        password = request.form["password"].strip()

        print(f"🔍 Attempting professor login: {email}, {name}, {professor_code}")

        # 🔐 Authenticate with email, name, and professor code
        professor = get_professor_by_email_and_code(email, name, professor_code)

        if professor:
            stored_password = professor[3]
            print(f"🛠 Stored Hashed Password: {stored_password}")

            # Verify password
            if bcrypt.checkpw(password.encode("utf-8"), stored_password.encode("utf-8")):
                session["professor_id"] = professor[0]
                flash("✅ Professor login successful!", "success")
                return redirect(url_for("professor_dashboard"))
            else:
                flash("❌ Incorrect password!", "danger")
        else:
            flash("❌ No matching professor found! Contact admin@example.com", "danger")

    return render_template("professor_login.html")

def get_students_by_professor(professor_id):
    """
    Returns a list of students associated with a professor by ID.
    (Assumes student table includes a professor_id foreign key.)
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM students WHERE professor_id = ?", (professor_id,))
        return cursor.fetchall()

attendance_running = False  #  Used to control the state of live attendance recognition


# Route for manually recording attendance
@app.route("/manual-attendance", methods=["POST"])
def manual_attendance():
    professor_id = session.get("professor_id")
    if not professor_id:
        return jsonify({"error": "Professor not logged in"}), 403  # Return error if professor is not logged in

    # Generate today's date and create an attendance file for today
    date_today = datetime.now().strftime("%Y-%m-%d")
    attendance_file = os.path.join(ATTENDANCE_FOLDER, f"attendance_{date_today}.csv")

    # Get the list of students' attendance status from the form
    student_attendance = request.form.getlist("attendance")

    # Write the attendance data to the CSV file
    with open(attendance_file, mode="a", newline="") as f:
        writer = csv.writer(f)
        for student_data in student_attendance:
            student_id, name, status = student_data.split("|")
            writer.writerow([name, student_id, datetime.now().strftime("%H:%M:%S"), status])  # Write student info and status

    flash("✅ Manual attendance recorded successfully!", "success")  # Notify the professor
    return redirect(url_for("professor_dashboard"))  # Redirect to professor dashboard after recording attendance


# Route for viewing attendance records (GET and POST methods)
@app.route('/view-attendance', methods=['GET', 'POST'])
def view_attendance():
    if 'student_id' not in session:
        return redirect(url_for('student_login'))  # Redirect to login if student is not logged in

    student_id = session['student_id']  # Get the student ID from session

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Fetch all classes the student is enrolled in
    cursor.execute("""
        SELECT DISTINCT c.class_name 
        FROM student_classes sc
        JOIN classrooms c ON sc.class_id = c.id
        WHERE sc.enrollment = ?;
    """, (student_id,))
    
    student_classes = [row[0] for row in cursor.fetchall()]  # Get a list of class names the student is enrolled in
    attendance_records = []

    if request.method == 'POST':  # If form is submitted, fetch attendance for a selected class and date
        class_name = request.form.get('class_name')
        selected_date = request.form.get('selected_date')

        if class_name:
            if selected_date:  # Fetch attendance for a specific date
                cursor.execute("""
                    SELECT a.date, a.status 
                    FROM attendance a
                    JOIN classrooms c ON a.class_id = c.id
                    WHERE a.enrollment = ? AND c.class_name = ? AND a.date = ?
                """, (student_id, class_name, selected_date))
            else:  # Fetch all attendance records for the selected class
                cursor.execute("""
                    SELECT a.date, a.status 
                    FROM attendance a
                    JOIN classrooms c ON a.class_id = c.id
                    WHERE a.enrollment = ? AND c.class_name = ?
                """, (student_id, class_name))

            attendance_records = cursor.fetchall()

    conn.close()

    # Render the view attendance page with the fetched classes and attendance records
    return render_template(
        'view_attendance.html', 
        student_classes=student_classes, 
        attendance_records=attendance_records
    )


 # Route to display classes the student is enrolled in
@app.route('/student/classes')
def student_classes():
    # Check if the student is logged in
    if 'student_id' not in session:
        return redirect(url_for('student_login'))  # Redirect to login page if not logged in

    student_id = session['student_id']

    # Connect to the database and fetch the classes the student is enrolled in
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Fetch class names for the student by joining the student_classes table with classrooms table
    cursor.execute("""
    SELECT c.class_name 
    FROM student_classes sc
    JOIN classrooms c ON sc.class_id = c.id
    WHERE sc.enrollment = ?;
    """, (student_id,))

    student_classes = [row[0] for row in cursor.fetchall()]  # Extract class names from the query results
    conn.close()

    # Return the rendered page with the student's classes
    return render_template('student_classes.html', student_classes=student_classes)


# Route for student logout 
@app.route('/student-logout')
def student_logout():
    session.clear()  # Clear the session data
    return redirect(url_for('student_login'))  # Redirect to the student login page


# Route for admin logout
@app.route("/admin-logout")
def admin_logout():
    session.pop("admin_id", None)  # Remove admin ID from session to log out
    flash("✅ Logged out successfully!", "success")
    return redirect(url_for("admin_login"))  # Redirect to admin login page


# Route to view professors 
@app.route("/view_professors")
def view_professors():
    # Check if the admin is logged in
    if "admin_id" not in session:
        flash("⚠️ Please log in first!", "warning")
        return redirect(url_for("admin_login"))

    with connect_db() as conn:
        cursor = conn.cursor()
        # Fetch professors and their assigned classrooms using a LEFT JOIN
        cursor.execute("""
            SELECT p.id, p.name, p.email, 
                   GROUP_CONCAT(c.class_name, ', ') AS assigned_classes
            FROM professors p
            LEFT JOIN classrooms c ON p.id = c.professor_id
            GROUP BY p.id
        """)
        professors = cursor.fetchall()  # Fetch all professors and assigned classes

    return render_template("view_professors.html", professors=professors)  # Render professors page


# Route to view students 
@app.route("/view-students")
def view_students():
    """
    Admin-only route to view all registered students in the system.
    Displays a table with enrollment, name, and email.
    """
    if "admin_id" not in session:
        flash("⚠️ Please log in first!", "warning")
        return redirect(url_for("admin_login"))  # Force login if not authenticated

    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT enrollment, name, email FROM students")
        students = cursor.fetchall()  # Fetch all student records

    return render_template("view_students.html", students=students)


# Route to manage classrooms 
@app.route("/manage-classrooms")
def manage_classrooms():
    """
    Admin-only route to view and manage all classrooms and their assigned professors.
    """
    if "admin_id" not in session:
        flash("⚠️ Please log in first!", "warning")
        return redirect(url_for("admin_login"))

    with connect_db() as conn:
        cursor = conn.cursor()
        # 🧑‍🏫 Fetch classrooms and join with professor table to get their names
        cursor.execute("""
            SELECT classrooms.id, classrooms.class_name, professors.name 
            FROM classrooms
            JOIN professors ON classrooms.professor_id = professors.id
        """)
        classrooms = cursor.fetchall()

    return render_template("manage_classrooms.html", classrooms=classrooms)


# Route to handle professor password reset request 
@app.route("/professor-reset-password", methods=["GET", "POST"])
def professor_reset_password_request():
    """
    Route to initiate a professor's password reset.
    Validates the provided email and sets a reset token in session.
    """
    if request.method == "POST":
        email = request.form["email"].strip()

        # 🔍 Verify if email exists in professor records
        professor = get_professor_by_email(email)
        if professor:
            reset_token = str(uuid.uuid4())  # 🔑 Generate a unique token
            session["reset_email"] = email
            session["reset_token"] = reset_token

            flash("✅ Password reset request received. Check your email for further instructions!", "success")

            # 🔁 Normally, you'd email the reset link, but for demo, just redirect
            return redirect(url_for("professor_reset_password", token=reset_token))

        flash("❌ No account found with that email. Contact admin@example.com.", "danger")

    return render_template("professor_reset_password_request.html")


# Route to reset professor password 
@app.route("/professor-reset-password/<token>", methods=["GET", "POST"])
def professor_reset_password(token):
    """
    Allows professors to securely reset their password after verifying token.
    """
    # Validate the token against session
    if "reset_token" not in session or session["reset_token"] != token:
        flash("❌ Invalid or expired reset link!", "danger")
        return redirect(url_for("professor_login"))

    if request.method == "POST":
        new_password = request.form["password"].strip()
        hashed_password = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Update password for the professor based on email in session
        email = session.get("reset_email")
        update_professor_password(email, hashed_password)

        flash("✅ Password reset successful! You can now log in.", "success")

        # Clean up session
        session.pop("reset_email", None)
        session.pop("reset_token", None)

        return redirect(url_for("professor_login"))

    return render_template("professor_reset_password.html")


# Route to take attendance
@app.route("/take-attendance/<int:class_id>", methods=["GET", "POST"])
def take_attendance(class_id):
    if "professor_id" not in session:
        flash("⚠️ Please log in first!", "warning")
        return redirect(url_for("professor_login"))

    professor_id = session["professor_id"]

    # Get students enrolled in this class
    students = get_students_in_class(class_id)

    if request.method == "POST":
        # Mark manual attendance for each student
        for student in students:
            enrollment = student[0]
            status = request.form.get(f"attendance_{enrollment}", "Absent")  # Default to "Absent" if no status
            mark_attendance(enrollment, class_id, status, professor_id)

        flash("✅ Attendance marked successfully!", "success")
        return redirect(url_for("professor_dashboard"))

    return render_template("take_attendance.html", class_id=class_id, students=students)


# Route for professors to view and manage students in a specific class
@app.route("/manage-class/<int:class_id>")
def manage_class(class_id):
    """
    This route allows a logged-in professor to view and manage 
    all students enrolled in a specific classroom.

    Parameters:
    - class_id (int): ID of the classroom to manage (passed via the URL)

    Behavior:
    - Verifies professor is logged in
    - Fetches all students enrolled in the given class
    - Renders a template that lists the students and class info
    """

    # Check if the professor is authenticated
    if "professor_id" not in session:
        flash("⚠️ Please log in first!", "warning")  # Friendly message if not logged in
        return redirect(url_for("professor_login"))  # Redirect to login page

    professor_id = session["professor_id"]  # 🔑 Retrieve professor ID from session

    # Retrieve all students enrolled in this class
    students = get_students_in_class(class_id)

    # Render the "manage_class.html" template with the student list and class ID
    return render_template("manage_class.html", class_id=class_id, students=students)


# Route to log out the professor 
@app.route("/logout-professor")
def logout_professor():
    session.pop("professor_id", None)  # Remove professor ID from session to log out
    flash("✅ Logged out successfully!", "info")
    return redirect(url_for("professor_login"))  # Redirect to professor login page


# Route to handle adding a student to a class by a professor
@app.route('/add-student-to-class', methods=['POST'])
def add_student_to_class():
    """
    Allow professors to manually add a student to one of their classes.
    
    Expected POST data:
    - class_id: ID of the class to add the student to
    - student_enrollment: Enrollment number of the student to add

    Access: Only professors who are logged in can use this route
    """

    # Retrieve professor_id from session to check if the user is logged in
    professor_id = session.get("professor_id")
    if not professor_id:
        # ⚠️ If professor not logged in, redirect to login page
        return redirect(url_for("professor_login"))

    # Retrieve submitted form data (class and student info)
    class_id = request.form.get("class_id")  # ID of the class
    student_enrollment = request.form.get("student_enrollment")  # Enrollment of student

    with connect_db() as conn:
        cursor = conn.cursor()

        # Verify the class belongs to the logged-in professor
        cursor.execute("SELECT id FROM classrooms WHERE id = ? AND professor_id = ?", 
                       (class_id, professor_id))
        class_check = cursor.fetchone()

        if not class_check:
            # Return an error if professor is not authorized for this class
            return "❌ Error: You are not assigned to this class!", 403

        # If check passes, insert student into student_classes table
        cursor.execute("""
            INSERT INTO student_classes (enrollment, class_id) 
            VALUES (?, ?)
        """, (student_enrollment, class_id))
        conn.commit()  # Save changes

    # Redirect back to professor dashboard after successful addition
    return redirect(url_for("professor_dashboard"))

# Initialize WebSocket and start live attendance

socketio = SocketIO(app, cors_allowed_origins="*", transports=["websocket"])  # Force WebSocket only

cam = None  # Stores the OpenCV camera instance
stop_flag = False  # Controls background task stopping
background_task = None  # Global variable to track the running task


# Route to start live attendance using face recognition 
@app.route("/start-attendance/<class_id>", methods=["GET"])
def start_attendance(class_id):
    """
    Starts live attendance capture using the webcam and real-time face recognition.

    - Captures faces using OpenCV.
    - Runs in the background via Flask-SocketIO to avoid blocking.
    - Automatically links the recognized students to attendance records for the given class.
    """

    global cam, background_task, stop_flag  # Declare global variables used across routes

    # Ensure professor is logged in
    professor_id = session.get("professor_id")
    if not professor_id:
        return jsonify({"error": "Unauthorized"}), 403  # Return error if professor not logged in

    # Attempt to access webcam
    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        return jsonify({"error": "Camera failed to open"}), 500

    stop_flag = False  # Reset stop flag before starting recognition loop

    # Launch background task to continuously perform face recognition
    background_task = socketio.start_background_task(
        target=recognize_faces_live,
        app=app,
        socketio=socketio,
        class_id=class_id,
        professor_id=professor_id
    )

    return jsonify({"message": "Live Attendance Started"}), 200  # Inform frontend


# Route to stop live attendance
@app.route("/stop-attendance", methods=["POST"])
def stop_attendance():
    """
    Forcefully stops the background attendance capture process and releases the webcam.

    - Stops recognition by setting stop_flag.
    - Closes the webcam.
    - Attempts to kill the background thread (if needed).
    """

    global cam, stop_flag, background_task  # Access shared control variables

    print("🛑 Attempting to force stop attendance...")

    stop_flag = True  # Signal recognition loop to stop

    try:
        import time
        time.sleep(1)  # ⏱ Allow thread a moment to finish

        # Safely release the camera if open
        if cam and cam.isOpened():
            print("✅ Camera is open, attempting to release...")
            cam.release()  # 🎥 Turn off webcam
            cam = None
            print("✅ Camera successfully released!")

        # Ensure all OpenCV windows are closed (just in case)
        cv2.destroyAllWindows()
        cv2.waitKey(1)

        # Attempt to stop the thread (not ideal in Python but shown here as emergency exit)
        if background_task is not None:
            print("🔴 Forcefully terminating background thread...")

            for thread in threading.enumerate():
                if thread is background_task:
                    # 🚨 This will kill the Flask process entirely — not ideal, use with caution
                    os.kill(os.getpid(), signal.SIGKILL)
                    break

            background_task = None  # Clear thread reference

        return jsonify({"message": "✅ Attendance forcefully stopped!"}), 200  # Notify frontend

    except Exception as e:
        print(f"❌ Error force stopping attendance: {str(e)}")
        return jsonify({"error": f"Failed to force stop attendance. {str(e)}"}), 500

# Function to record attendance
def record_attendance(class_id, date, professor_id):
    """Recognize students and record attendance while session is active."""
    print(f"🔥 DEBUG: record_attendance() called for class {class_id} on {date}")

    if not attendance_active:  # If attendance is not active, skip the recognition
        print("⚠️ Attendance is not active. Skipping recognition.")
        return

    print("📷 Accessing camera for face recognition...")
    result = recognize_student_face()  # Recognize the student via face recognition
    
    if result is None:
        print("❌ Face recognition failed.")
        return

    student_name = result.get("name", "Unknown Student")
    enrollment = result["Enrollment"]

    with connect_db() as conn:
        cursor = conn.cursor()

        # Ensure the student is enrolled in this class
        cursor.execute("""
            SELECT 1 FROM student_classes WHERE enrollment = ? AND class_id = ?
        """, (enrollment, class_id))
        valid_class = cursor.fetchone()

        if not valid_class:
            print(f"⚠️ Student {student_name} ({enrollment}) is NOT enrolled in class {class_id}! Ignoring...")
            return

        # Insert attendance record into the database
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"📌 DEBUG: Inserting into database: Enrollment={enrollment}, Class ID={class_id}, Date={date}, Time={current_time}")

        sql_query = """
        INSERT INTO attendance (enrollment, class_id, date, status, professor_id, time_recognized)
        VALUES (?, ?, ?, 'Present', ?, ?);
        """

        try:
            cursor.execute(sql_query, (enrollment, class_id, date, professor_id, current_time))
            conn.commit()
            print("✅ Attendance successfully recorded.")
        except Exception as e:
            print(f"❌ ERROR: Failed to insert attendance record: {e}")

        # Retrieve the last inserted row to confirm the data
        cursor.execute("SELECT * FROM attendance WHERE enrollment = ? ORDER BY id DESC LIMIT 1", (enrollment,))
        inserted_row = cursor.fetchone()
        print(f"✅ DEBUG: Inserted Row from Python = {inserted_row}")


# Route for settings
@app.route("/settings", methods=["GET", "POST"])
def settings():
    # Check if the admin is logged in
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    conn = get_db_connection()
    admin = conn.execute("SELECT * FROM admins WHERE id = ?", (session["admin_id"],)).fetchone()
    conn.close()

    if request.method == "POST":
        # Extract new settings from form and update in the database
        new_email = request.form["email"]
        new_password = request.form["password"]

        # Hash the new password before saving it
        hashed_password = bcrypt.generate_password_hash(new_password).decode("utf-8")

        conn = get_db_connection()
        conn.execute("UPDATE admins SET email = ?, password = ? WHERE id = ?", (new_email, hashed_password, session["admin_id"]))
        conn.commit()
        conn.close()

        log_admin_activity(session["admin_id"], "Updated system settings")

        flash("✅ Settings updated successfully!", "success")
        return redirect(url_for("settings"))

    return render_template("settings.html", admin=admin)


# Route to update settings
@app.route("/update-settings", methods=["POST"])
def update_settings():
    """
    Allows an admin to update system-wide settings (e.g., configuration values).
    
    - Secured: Only accessible if the admin is logged in.
    - Accepts new setting value from a form.
    - Logs the admin activity after successful update.
    """

    # Ensure the user is logged in as an admin
    if "admin_id" not in session:
        flash("❌ Unauthorized access!", "danger")
        return redirect(url_for("admin_login"))  # Redirect if not authorized

    admin_id = session["admin_id"]  # Get admin ID from session

    # Extract the new setting value from the submitted form
    new_setting = request.form.get("setting_value")

    # Connect to the database
    conn = get_db_connection()

    # ⚙️ Update the 'some_setting' setting value in the settings table
    conn.execute("UPDATE settings SET value = ? WHERE name = 'some_setting'", (new_setting,))
    conn.commit()  # Apply changes

    # Log this update in the admin activity log
    log_admin_activity(admin_id, "Updated system settings")

    # Notify the user and redirect
    flash("✅ Settings updated successfully!", "success")
    conn.close()
    return redirect(url_for("admin_dashboard"))


# Route for recent admin activity 
@app.route("/recent-activity")
def recent_activity():
    """
    Displays the most recent administrative actions logged in the system.

    - Secured: Requires admin to be logged in
    - Fetches the 10 most recent entries from the `admin_activity` table
    - Renders the activity data in a template (recent_activity.html)
    """

    # Check if the admin is authenticated
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))  # Redirect if not logged in

    # Connect to the database
    conn = get_db_connection()

    # Query the last 10 admin actions, ordered by most recent first
    activities = conn.execute(
        "SELECT * FROM admin_activity ORDER BY timestamp DESC LIMIT 10"
    ).fetchall()

    # Close the connection to avoid leaks
    conn.close()
    
    # Render the template and pass in the activity data
    return render_template("recent_activity.html", activities=activities)


# Route for weekly attendance report
@app.route('/weekly-report/<int:class_id>')
def weekly_report_for_class(class_id):
    conn = sqlite3.connect("attendance_system.db")
    cursor = conn.cursor()

    # Print received class_id to debug
    print(f"🔍 Received class_id: {class_id}")

    # Get past 7 days
    today = datetime.today()
    start_of_week = (today - timedelta(days=6)).strftime('%Y-%m-%d')  # Start of the week
    last_week_dates = [(today - timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]

    # Get the correct class name
    cursor.execute("SELECT class_name FROM classrooms WHERE id = ?", (class_id,))
    class_record = cursor.fetchone()
    if not class_record:
        return jsonify({"error": f"Class ID {class_id} not found"}), 404
    
    class_name = class_record[0]  # Extract class name
    print(f"📌 Class name fetched: {class_name}")  # Debugging step

    # Create a folder for this week's report
    folder_name = f"attendance_{class_name}_week_of_{start_of_week}"
    folder_path = os.path.join(os.getcwd(), folder_name)  # Save in the current directory
    os.makedirs(folder_path, exist_ok=True)

    # Get all students in this class
    cursor.execute("""
        SELECT s.name, s.enrollment
        FROM students s
        JOIN student_classes cs ON s.enrollment = cs.enrollment
        WHERE cs.class_id = ?
    """, (class_id,))
    
    students = cursor.fetchall()

    report = []

    # Loop through every day and every student
    for date in last_week_dates:
        for student in students:
            student_name, enrollment = student

            # Check if this student has an attendance record for this day
            cursor.execute("""
                SELECT status FROM attendance 
                WHERE class_id = ? AND enrollment = ? AND date = ?
            """, (class_id, enrollment, date))

            attendance = cursor.fetchone()

            status = attendance[0] if attendance else "Absent"  # If no record, assume Absent

            report.append({
                "student_name": student_name,
                "enrollment": enrollment,
                "class_name": class_name,
                "date": date,
                "status": status
            })

    conn.close()

    # Save JSON file
    json_path = os.path.join(folder_path, "weekly_report.json")
    with open(json_path, "w") as json_file:
        json.dump(report, json_file, indent=4)

    # Save CSV file
    csv_path = os.path.join(folder_path, "weekly_report.csv")
    with open(csv_path, "w", newline="") as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["Student Name", "Enrollment ID", "Class Name", "Date", "Status"])
        for row in report:
            csv_writer.writerow([row["student_name"], row["enrollment"], row["class_name"], row["date"], row["status"]])

    print(f"✅ Weekly report saved in: {folder_path}")  # Debugging step

    return jsonify({
        "message": f"✅ Weekly report saved in {folder_path}",
        "folder": folder_path
    })


# Route to export attendance data as CSV 
@app.route("/export-attendance", methods=["GET"])
def export_attendance():
    """
    Exports all attendance records from the database as a downloadable CSV file.

    Access should be restricted to admins or professors in future versions.
    Joins `attendance` with `students` to fetch student names alongside attendance logs.
    """

    try:
        # Open a database connection
        with connect_db() as conn:
            cursor = conn.cursor()

            # Query attendance records joined with student names
            cursor.execute("""
                SELECT s.name, a.enrollment, a.class_name, a.date, a.status, a.time_recognized 
                FROM attendance a
                LEFT JOIN students s ON a.enrollment = s.enrollment
                ORDER BY a.date DESC
            """)

            records = cursor.fetchall()  # Fetch all matching records

            # CSV Header
            csv_output = "Student Name,Enrollment ID,Class Name,Date,Status,Time Detected\n"

            # Loop through each record and format as CSV
            for record in records:
                csv_output += (
                    f"{record[0]},"                             # Student Name
                    f"{record[1]},"                             # Enrollment ID
                    f"{record[2] if record[2] else 'Unknown Class'},"  # Class Name fallback
                    f"{record[3]},"                             # Date
                    f"{record[4]},"                             # Status (Present/Absent)
                    f"{record[5] if record[5] else '--'}\n"     # Time Detected fallback
                )

            # Create a downloadable CSV response
            response = make_response(csv_output)
            response.headers["Content-Disposition"] = "attachment; filename=attendance_report.csv"
            response.headers["Content-type"] = "text/csv"
            return response

    except Exception as e:
        # If an error occurs, log it and return an error response
        print(f"❌ ERROR: Failed to export attendance CSV: {e}")
        return jsonify({"error": str(e)}), 500

# Function to log admin activity
def log_admin_activity(admin_id, action):
    """Logs the actions taken by the admin."""
    conn = get_db_connection()
    conn.execute("INSERT INTO admin_activity (admin_id, action) VALUES (?, ?)", (admin_id, action))
    conn.commit()
    conn.close()


# Route to list weekly reports
@app.route('/list-weekly-reports/<int:class_id>')
def list_weekly_reports(class_id):
    """Lists all weekly reports for a given class."""
    class_name_query = "SELECT class_name FROM classrooms WHERE id = ?"
    cursor.execute(class_name_query, (class_id,))
    class_name = cursor.fetchone()
    class_name = class_name[0] if class_name else f"Class_{class_id}"

    # Find folders matching the report pattern (e.g., "attendance_ClassName_week_of_")
    report_folders = glob.glob(f"attendance_{class_name}_week_of_*")

    reports = []
    for folder in report_folders:
        reports.append({
            "name": folder,
            "json": f"{folder}/weekly_report.json",  # Path to JSON report
            "csv": f"{folder}/weekly_report.csv"    # Path to CSV report
        })

    return jsonify({"reports": reports})  # Return a list of reports in JSON format

# Function to get the correct class name 
def get_class_name(class_id):
    """Maps class IDs to class names."""
    class_map = {
        "7": "ENGL100",  # Example: Map class_id 7 to class name ENGL100
        "8": "MATH200"    # Add more class mappings as needed
    }
    return class_map.get(str(class_id), f"Class_{class_id}")  # Default to "Class_X" if not found


# Route to download a report (CSV or JSON) 
@app.route('/download/<report_type>/<class_id>')
def download_report(report_type, class_id):
    """Downloads the requested report (CSV or JSON) for a specific class."""
    base_dir = os.getcwd()  # Get current working directory
    class_name = get_class_name(class_id)  # Get the class name from the class_id

    # Construct the folder name based on the class_name (adjust dynamically as needed)
    report_folder = f"attendance_{class_name}_week_of_2025-02-22"
    report_path = os.path.join(base_dir, report_folder)

    # Determine which report type to download (CSV or JSON)
    if report_type == "csv":
        filename = "weekly_report.csv"
    elif report_type == "json":
        filename = "weekly_report.json"
    else:
        return jsonify({"error": "Invalid report type"}), 400  # Return error if report type is invalid

    file_path = os.path.join(report_path, filename)
    
    # Check if the file exists and send it as an attachment if found
    if os.path.exists(file_path):
        return send_from_directory(report_path, filename, as_attachment=True)
    else:
        return jsonify({"error": f"File {filename} not found in {report_folder}"}), 404


# Route to remove a professor 
@app.route("/remove-professor/<int:professor_id>", methods=["POST"])
def remove_professor(professor_id):
    """Allows the admin to remove a professor from the system."""
    if "admin_id" not in session:
        flash("❌ Unauthorized access!", "danger")
        return redirect(url_for("admin_login"))

    admin_id = session["admin_id"]
    conn = get_db_connection()

    # Fetch professor name before deletion
    professor = conn.execute("SELECT name FROM professors WHERE id = ?", (professor_id,)).fetchone()

    if professor:
        professor_name = professor["name"]
        conn.execute("DELETE FROM professors WHERE id = ?", (professor_id,))
        conn.commit()

        # Log the activity
        log_admin_activity(admin_id, f"Removed professor {professor_name}")

        flash(f"✅ Professor {professor_name} removed successfully!", "success")
    else:
        flash("❌ Professor not found!", "danger")

    conn.close()
    return redirect(url_for("view_professors"))  # Redirect back to professor view page


# Route to add a new classroom 
@app.route('/add-classroom', methods=['POST'])
def add_classroom():
    """Admin adds a new classroom."""
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    class_name = request.form["class_name"].strip()

    with connect_db() as conn:
        cursor = conn.cursor()

        # Insert the new classroom (professor_id is NULL initially)
        cursor.execute("INSERT INTO classrooms (class_name, professor_id) VALUES (?, NULL);", (class_name,))
        conn.commit()

        # Log the activity
        log_admin_activity(session["admin_id"], f"Created new classroom: {class_name}")

    flash(f"✅ Classroom '{class_name}' added successfully!", "success")
    return redirect(url_for("admin_dashboard"))  # Redirect to admin dashboard

# Function to insert default classrooms 
def insert_default_classrooms():
    """
    Inserts a predefined list of classrooms into the database.

    - Only inserts if no classrooms exist (avoids duplication).
    - Professor ID is set to NULL by default (to be assigned later).
    """

    with connect_db() as conn:
        cursor = conn.cursor()

        # Predefined classroom names to seed the system with common courses
        classrooms = [
            ("MATH110",), ("CS101",), ("PHYS202",), ("ENG105",), ("BIO220",),
            ("HIST300",), ("CHEM210",), ("ECON101",), ("PSYCH150",), ("ART200",)
        ]

        # Check if any classrooms already exist to prevent duplication
        cursor.execute("SELECT COUNT(*) FROM classrooms;")
        count = cursor.fetchone()[0]

        if count == 0:
            # Bulk insert classrooms with NULL professor_id
            cursor.executemany(
                "INSERT INTO classrooms (class_name, professor_id) VALUES (?, NULL);",
                classrooms
            )
            conn.commit()
            print("✅ Default classrooms added to the database.")


# Route to assign a professor to a classroom 
@app.route("/assign-professor-to-class", methods=["POST"])
def assign_professor_to_class():
    """
    Assigns a selected professor to a classroom.

    - Admin-only access (requires session).
    - Updates `classrooms` table with both professor ID and professor name.
    - Logs the action for recent activity tracking.
    """

    # Ensure only logged-in admins can access
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    # Retrieve submitted form data
    professor_id = request.form["professor_id"]
    classroom_id = request.form["classroom_id"]

    with connect_db() as conn:
        cursor = conn.cursor()

        # 🔍 Get the professor’s name to save alongside the ID
        cursor.execute("SELECT name FROM professors WHERE id = ?", (professor_id,))
        professor = cursor.fetchone()

        if not professor:
            flash("⚠️ Professor not found!", "danger")
            return redirect(url_for("admin_dashboard"))

        professor_name = professor[0]  # Extract the name from the tuple

        # Update the classroom record with the assigned professor
        cursor.execute("""
            UPDATE classrooms 
            SET professor_id = ?, professor_name = ? 
            WHERE id = ?
        """, (professor_id, professor_name, classroom_id))
        conn.commit()

        # Log this change in the admin activity log
        log_admin_activity(
            session["admin_id"],
            f"Assigned Professor {professor_name} to Classroom {classroom_id}"
        )

    # Notify the user and redirect to dashboard
    flash("✅ Professor assigned to classroom successfully!", "success")
    return redirect(url_for("admin_dashboard"))


# Route to create a new classroom 
@app.route("/create-classroom", methods=["POST"])
def create_classroom():
    """
    Handles the creation of a new classroom by the admin.

    Admin must be logged in.
    Saves the new class name into the `classrooms` table.
    Initially sets `professor_id` to NULL (professor can be assigned later).
    Logs the activity for tracking.
    """

    # Ensure the user is logged in as an admin
    if "admin_id" not in session:
        flash("❌ Unauthorized access!", "danger")
        return redirect(url_for("admin_login"))

    # Extract and clean the classroom name from the submitted form
    class_name = request.form["class_name"].strip()

    with connect_db() as conn:
        cursor = conn.cursor()

        # Insert the new classroom into the database with no assigned professor yet
        cursor.execute(
            "INSERT INTO classrooms (class_name, professor_id) VALUES (?, NULL)",
            (class_name,)
        )
        conn.commit()

        # Log this creation action for audit trail
        log_admin_activity(
            session["admin_id"],
            f"Created classroom {class_name}"
        )

    # Notify admin and return to dashboard
    flash(f"✅ Classroom '{class_name}' created successfully!", "success")
    return redirect(url_for("admin_dashboard"))


# Route to assign a student to a classroom 
@app.route("/assign-student", methods=["POST"])
def assign_student_to_classroom():
    """Admin assigns a student to a classroom."""
    if "admin_id" not in session:
        return redirect(url_for("admin_login"))

    student_id = request.form.get("student_id")  # This is the student's ID (primary key)
    classroom_id = request.form.get("classroom_id")

    if not student_id or not classroom_id:
        flash("⚠️ Please select both a student and a classroom!", "warning")
        return redirect(url_for("admin_dashboard"))

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Fetch the enrollment number and name using student_id
        cursor.execute("SELECT enrollment, name FROM students WHERE id = ?", (student_id,))
        student = cursor.fetchone()

        if not student:
            flash("⚠️ Student not found!", "warning")
            return redirect(url_for("admin_dashboard"))

        enrollment, student_name = student  # Extract enrollment and name

        # Fetch the class name
        cursor.execute("SELECT class_name FROM classrooms WHERE id = ?", (classroom_id,))
        class_row = cursor.fetchone()
        if not class_row:
            flash("⚠️ Classroom not found!", "warning")
            return redirect(url_for("admin_dashboard"))
        
        class_name = class_row[0]  # Extract class name

        # Check if the student is already assigned to the class
        cursor.execute("""
            SELECT * FROM student_classes WHERE enrollment = ? AND class_id = ?
        """, (enrollment, classroom_id))

        existing = cursor.fetchone()
        if existing:
            flash("⚠️ Student is already assigned to this classroom!", "warning")
        else:
            # Insert enrollment, student_name, class_id, AND class_name into student_classes
            cursor.execute("""
                INSERT INTO student_classes (enrollment, student_name, class_id, class_name) 
                VALUES (?, ?, ?, ?)
            """, (enrollment, student_name, classroom_id, class_name))
            conn.commit()
            flash(f"✅ Student {student_name} assigned to {class_name} successfully!", "success")
            log_admin_activity(session["admin_id"], f"Assigned student {student_name} (Enrollment: {enrollment}) to class {class_name}")

    return redirect(url_for("admin_dashboard"))  # Redirect to admin dashboard after assigning the student

# Initialize SocketIO 
socketio = SocketIO(app)  # Initialize SocketIO to enable real-time communication

# Function to log student attendance 
def log_attendance(enrollment, class_id, date, status="Present"):
    """Logs attendance for a specific date."""
    with connect_db() as conn:
        cursor = conn.cursor()

        # Ensure student is actually enrolled in the class
        cursor.execute("""
            SELECT 1 FROM student_classes WHERE enrollment = ? AND class_id = ?
        """, (enrollment, class_id))
        
        valid_assignment = cursor.fetchone()  # Verify student-class enrollment
        
        if valid_assignment:
            # Insert attendance record with selected date and status
            cursor.execute("""
                INSERT INTO attendance (enrollment, class_id, time_recognized, date, status)
                VALUES (?, ?, datetime('now', 'localtime'), ?, ?)
            """, (enrollment, class_id, date, status))
            
            conn.commit()  # Save attendance record
            print(f"✅ Attendance recorded for {enrollment} on {date}")

            # Emit real-time event for the new attendance (using SocketIO)
            socketio.emit('new_attendance', {
                'enrollment': enrollment,
                'name': student_name,  # Student name (make sure it's defined)
                'date': date,
                'status': status,
                'time': current_time,  # Include timestamp for the attendance
                'absence_message': None  # Placeholder for any absence message
            })


# Route to download CSV report 
@app.route('/download/csv/<int:class_id>')
def download_csv(class_id):
    """Allows downloading the weekly attendance report as CSV."""
    today = datetime.today()
    start_of_week = (today - timedelta(days=6)).strftime('%Y-%m-%d')  # Get the start of the week

    conn = sqlite3.connect("attendance_system.db")
    cursor = conn.cursor()

    # Fetch the class name from the database
    cursor.execute("SELECT class_name FROM classrooms WHERE id = ?", (class_id,))
    class_record = cursor.fetchone()
    if not class_record:
        return jsonify({"error": f"Class ID {class_id} not found"}), 404
    
    class_name = class_record[0]
    folder_name = f"attendance_{class_name}_week_of_{start_of_week}"
    csv_path = os.path.join(os.getcwd(), folder_name, "weekly_report.csv")  # Construct the CSV file path

    # Check if the file exists and return it
    if not os.path.exists(csv_path):
        return jsonify({"error": f"File weekly_report.csv not found in {folder_name}"}), 404

    return send_file(csv_path, as_attachment=True)  # Send the CSV file for download


# Route to download JSON report 
@app.route('/download/json/<int:class_id>')
def download_json(class_id):
    """Allows downloading the weekly attendance report as JSON."""
    today = datetime.today()
    start_of_week = (today - timedelta(days=6)).strftime('%Y-%m-%d')

    conn = sqlite3.connect("attendance_system.db")
    cursor = conn.cursor()

    # Fetch the class name from the database
    cursor.execute("SELECT class_name FROM classrooms WHERE id = ?", (class_id,))
    class_record = cursor.fetchone()
    if not class_record:
        return jsonify({"error": f"Class ID {class_id} not found"}), 404
    
    class_name = class_record[0]
    folder_name = f"attendance_{class_name}_week_of_{start_of_week}"
    json_path = os.path.join(os.getcwd(), folder_name, "weekly_report.json")

    # Check if the file exists and return it
    if not os.path.exists(json_path):
        return jsonify({"error": f"File weekly_report.json not found in {folder_name}"}), 404

    return send_file(json_path, as_attachment=True)  # Send the JSON file for download


# Profile Picture Upload 
UPLOAD_FOLDER = "static/profile_pictures"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    """Check if the uploaded file is an allowed type"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# Route to upload profile picture 
@app.route('/upload-profile-picture', methods=['POST'])
def upload_profile_picture():
    """Handles student profile picture upload."""
    if 'student_id' not in session:
        flash("⚠️ You must be logged in!", "danger")
        return redirect(url_for("student_login"))

    student_id = session['student_id']

    if 'profile_picture' not in request.files:
        flash("⚠️ No file uploaded!", "danger")
        return redirect(url_for("student_dashboard"))

    file = request.files['profile_picture']
    
    if file.filename == '':
        flash("⚠️ No file selected!", "danger")
        return redirect(url_for("student_dashboard"))

    if file and allowed_file(file.filename):
        # Save the file using the student's ID as the filename
        filename = secure_filename(f"{student_id}.{file.filename.rsplit('.', 1)[1].lower()}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Update the student's profile picture in the database
        with connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE students SET profile_picture = ? WHERE enrollment = ?", (file_path, student_id))
            conn.commit()

        flash("✅ Profile picture updated successfully!", "success")
        return redirect(url_for("student_dashboard"))

    flash("❌ Invalid file type!", "danger")
    return redirect(url_for("student_dashboard"))


# Route to display student dashboard
@app.route("/student-dashboard")
def student_dashboard():
    """Displays student dashboard with recent activities and messages."""
    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    student_id = session['student_id']

    with connect_db() as conn:
        cursor = conn.cursor()

        # Fetch student details (name, profile picture, etc.)
        cursor.execute("SELECT name, profile_picture, enrollment FROM students WHERE enrollment = ?", (student_id,))
        student = cursor.fetchone()

        if student:
            student_name, profile_picture, student_enrollment = student
        else:
            student_name, profile_picture, student_enrollment = "Unknown", None, None

        # Use default profile picture if none exists
        profile_picture = profile_picture if profile_picture else url_for('static', filename='images/default-profile.png')

        # Fetch student's enrolled classes
        cursor.execute("""
            SELECT c.id, c.class_name 
            FROM classrooms c
            JOIN student_classes sc ON c.id = sc.class_id
            WHERE sc.enrollment = ?
        """, (student_enrollment,))
        
        classes = cursor.fetchall()

        # Fetch recent student activities
        cursor.execute("""
            SELECT activity, timestamp FROM student_activities 
            WHERE student_id = ? ORDER BY timestamp DESC LIMIT 5
        """, (student_id,))
        recent_activities = cursor.fetchall()

        # Fetch messages for the student (from both AI and professor)
        cursor.execute("""
            SELECT messages.id, messages.message, messages.timestamp, messages.sender_type
            FROM messages
            WHERE messages.student_enrollment = ?
            AND messages.recipient_type = 'student'  -- Ensure we get messages for the student
            ORDER BY messages.timestamp DESC;
        """, (student_enrollment,))
        
        messages = [{"id": row[0], "message": row[1], "timestamp": row[2], "sender_type": row[3]} for row in cursor.fetchall()]

    # Return the student dashboard template with the fetched data
    return render_template("student_dashboard.html", 
                           student_name=student_name, 
                           profile_picture=profile_picture, 
                           classes=classes, 
                           recent_activities=recent_activities,
                           messages=messages)  # Include the messages in the template


# Route for changing profile picture 
@app.route("/change-profile-picture", methods=["POST"])
def change_profile_picture():
    """Allows student to upload a new profile picture"""
    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    if 'profile_picture' not in request.files:
        flash("No file selected!", "danger")
        return redirect(url_for('student_dashboard'))

    file = request.files['profile_picture']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Update the database with the new profile picture
        with connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE students SET profile_picture = ? WHERE enrollment = ?", (filepath, session['student_id']))
            conn.commit()

        # Log profile picture change
        log_student_activity(session['student_id'], "Updated profile picture")

        flash("Profile picture updated successfully!", "success")
    
    return redirect(url_for('student_dashboard'))


# Route for changing student password 
@app.route("/change-password", methods=["POST"])
def change_password():
    """
    Allows a logged-in student to securely change their password.

    Requires the current password for verification.
    Hashes the new password before storing.
    Uses bcrypt for secure password handling.
    """

    # Check if the student is logged in
    if 'student_id' not in session:
        flash("❌ Please log in first!", "danger")
        return redirect(url_for('student_login'))

    # Get old and new passwords from form
    old_password = request.form.get("old_password")
    new_password = request.form.get("new_password")

    with connect_db() as conn:
        cursor = conn.cursor()

        # Get the current hashed password from the database
        cursor.execute("SELECT password FROM students WHERE enrollment = ?", (session['student_id'],))
        result = cursor.fetchone()

        if not result:
            flash("❌ Student not found!", "danger")
            return redirect(url_for('student_dashboard'))

        current_hashed_password = result[0].encode("utf-8")

        # Compare old password with stored hash
        if not bcrypt.checkpw(old_password.encode("utf-8"), current_hashed_password):
            flash("❌ Incorrect current password!", "danger")
            return redirect(url_for('student_dashboard'))

        # Hash the new password
        new_hashed_password = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        # Update the password in the database
        cursor.execute("UPDATE students SET password = ? WHERE enrollment = ?", (new_hashed_password, session['student_id']))
        conn.commit()

    # Notify the student
    flash("🔐 Password updated successfully!", "success")
    return redirect(url_for('student_dashboard'))

# Initialize database with default tables 
def initialize_database():
    """Creates necessary tables if they don't exist."""
    with connect_db() as conn:
        cursor = conn.cursor()
        
        # Create student_activities table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS student_activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            activity TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(enrollment)
        );
        """)
        
        conn.commit()

# Chatbot Route 

# Initialize the Coordinator which handles user requests
coordinator = AgentCoordinator()

@app.route("/chatbot-response", methods=["POST"])
def chatbot_response():
    """Handles chatbot responses for the student."""
    if "student_id" not in session:
        return jsonify({"response": "❌ You are not logged in!"})  # Return error if the student is not logged in

    student_id = session["student_id"]
    user_message = request.json.get("message", "").lower()  # Get the user's message from the request and convert to lowercase

    # Use the coordinator to handle the user's request and get a response
    response = coordinator.handle_user_request(user_message, student_id)

    return jsonify({"response": response})  # Return the response to the student


# Function to generate attendance graph 
def generate_attendance_graph(student_id, class_name=None):
    """Generates an attendance graph for the student, optionally filtered by class."""
    with sqlite3.connect("attendance_system.db") as conn:
        cursor = conn.cursor()

        # Fetch attendance records for the student
        if class_name:
            cursor.execute("""
                SELECT date, status FROM attendance 
                WHERE enrollment = ? AND class_id IN (SELECT id FROM classrooms WHERE class_name = ?)
            """, (student_id, class_name))
        else:
            cursor.execute("SELECT date, status FROM attendance WHERE enrollment = ?", (student_id,))

        records = cursor.fetchall()

    # Prepare data for visualization
    dates = []
    statuses = []
    for date, status in records:
        dates.append(date)
        statuses.append(1 if status == "Present" else 0)  # 1 = Present, 0 = Absent

    # Generate graph
    plt.figure(figsize=(8, 4))
    plt.plot(dates, statuses, marker="o", linestyle="-", color="blue", label="Attendance Record")
    plt.xticks(rotation=45)
    plt.yticks([0, 1], ["Absent", "Present"])
    plt.xlabel("Date")
    plt.ylabel("Attendance Status")
    plt.title(f"📊 Attendance Record ({class_name})" if class_name else "📊 Your Attendance Record")
    plt.legend()
    plt.tight_layout()

    # Save to memory and encode to base64 for embedding in HTML
    img = io.BytesIO()
    plt.savefig(img, format="png")
    img.seek(0)
    graph_url = base64.b64encode(img.getvalue()).decode("utf-8")
    plt.close()

    return f"data:image/png;base64,{graph_url}"  # Return base64-encoded image


# Profile Picture Upload 
UPLOAD_FOLDER = "static/profile_pictures"
ALLOWED_EXTENSIONS = {"pdf", "jpg", "png", "jpeg"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    """Check if the uploaded file is an allowed type."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# Route to upload profile picture 
@app.route('/upload-profile-picture', methods=['POST'])
def upload_profile_picture():
    """Handles student profile picture upload."""
    if 'student_id' not in session:
        flash("⚠️ You must be logged in!", "danger")
        return redirect(url_for("student_login"))

    student_id = session['student_id']

    if 'profile_picture' not in request.files:
        flash("⚠️ No file uploaded!", "danger")
        return redirect(url_for("student_dashboard"))

    file = request.files['profile_picture']
    
    if file.filename == '':
        flash("⚠️ No file selected!", "danger")
        return redirect(url_for("student_dashboard"))

    if file and allowed_file(file.filename):
        # Save the file using the student's ID as the filename
        filename = secure_filename(f"{student_id}.{file.filename.rsplit('.', 1)[1].lower()}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Update the student's profile picture in the database
        with connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE students SET profile_picture = ? WHERE enrollment = ?", (file_path, student_id))
            conn.commit()

        flash("✅ Profile picture updated successfully!", "success")
        return redirect(url_for("student_dashboard"))

    flash("❌ Invalid file type!", "danger")
    return redirect(url_for("student_dashboard"))


# Student Dashboard 
@app.route("/student-dashboard")
def student_dashboard():
    """
    Displays the student's dashboard, including:

    Profile information (name, picture)
    Enrolled classes
    Recent activity logs
    Messages from professors and AI
    """

    # Ensure the student is logged in
    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    student_id = session['student_id']

    with connect_db() as conn:
        cursor = conn.cursor()

        # 🔍 Fetch student profile details
        cursor.execute("""
            SELECT name, profile_picture, enrollment 
            FROM students 
            WHERE enrollment = ?
        """, (student_id,))
        
        student = cursor.fetchone()

        if student:
            student_name, profile_picture_blob, student_enrollment = student
        else:
            # If student is not found, use fallbacks
            student_name, profile_picture_blob, student_enrollment = "Unknown", None, None

        # Use default profile picture if none is found
        profile_picture = profile_picture_blob if profile_picture_blob else url_for('static', filename='images/default-profile.png')

        # Fetch all classes the student is enrolled in
        cursor.execute("""
            SELECT c.id, c.class_name 
            FROM classrooms c
            JOIN student_classes sc ON c.id = sc.class_id
            WHERE sc.enrollment = ?
        """, (student_enrollment,))
        
        classes = cursor.fetchall()  # List of (class_id, class_name)

        # Get recent activity logs for the student
        cursor.execute("""
            SELECT activity, timestamp 
            FROM student_activities 
            WHERE student_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 5
        """, (student_id,))
        
        recent_activities = cursor.fetchall()

        # Fetch latest messages for this student (from professors or AI)
        cursor.execute("""
            SELECT messages.id, messages.message, messages.timestamp, messages.sender_type
            FROM messages
            WHERE messages.student_enrollment = ?
            AND messages.recipient_type = 'student'  -- Only messages directed to student
            ORDER BY messages.timestamp DESC;
        """, (student_enrollment,))
        
        messages = [
            {
                "id": row[0],
                "message": row[1],
                "timestamp": row[2],
                "sender_type": row[3]
            } 
            for row in cursor.fetchall()
        ]

    # Render the dashboard with all the gathered data
    return render_template(
        "student_dashboard.html", 
        student_name=student_name, 
        profile_picture=profile_picture, 
        classes=classes, 
        recent_activities=recent_activities,
        messages=messages
    )


# Route for changing profile picture 
@app.route("/change-profile-picture", methods=["POST"])
def change_profile_picture():
    """Allows student to upload a new profile picture."""
    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    if 'profile_picture' not in request.files:
        flash("No file selected!", "danger")
        return redirect(url_for('student_dashboard'))

    file = request.files['profile_picture']
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        # Update the database with the new profile picture
        with connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE students SET profile_picture = ? WHERE enrollment = ?", (filepath, session['student_id']))
            conn.commit()

        # Log profile picture change
        log_student_activity(session['student_id'], "Updated profile picture")

        flash("Profile picture updated successfully!", "success")
    
    return redirect(url_for('student_dashboard'))


# Route for changing student password 
@app.route("/change-password", methods=["POST"])
def change_password():
    """Allows student to change password."""
    if 'student_id' not in session:
        return redirect(url_for('student_login'))

    old_password = request.form.get("old_password")
    new_password = request.form.get("new_password")

    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM students WHERE enrollment = ?", (session['student_id'],))
        current_password = cursor.fetchone()[0]

        if old_password != current_password:
            flash("Incorrect current password!", "danger")
            return redirect(url_for('student_dashboard'))

        cursor.execute("UPDATE students SET password = ? WHERE enrollment = ?", (new_password, session['student_id']))
        conn.commit()

    flash("Password updated successfully!", "success")
    return redirect(url_for('student_dashboard'))

# Delayed Notification for Professor 
def delayed_notify_professor(student_enrollment, class_id):
    """
    Wait 5 minutes before notifying the professor.

    This allows AI to respond automatically first. If not, the professor is notified manually.
    """
    time.sleep(300)  # Delay for 5 minutes
    socketio.emit("new_absence_message", {
        "student_enrollment": student_enrollment,
        "class_name": class_id
    })


# Route to Send Absence Message 
@app.route('/send-absence-message', methods=['POST'])
def send_absence_message():
    """
    Handles student-submitted absence messages:
    - Saves the message in the DB
    - Allows AI to auto-respond if appropriate
    - Notifies professor (immediately or delayed)
    """
    # Check student session
    if "student_id" not in session:
        return redirect(url_for("student_login"))

    student_enrollment = session["student_id"]
    class_id = request.form.get("class_id")
    student_message = request.form.get("message")

    # Validate form inputs
    if not class_id or not student_message:
        flash("Error: Missing class or message.", "danger")
        return redirect(url_for("student_dashboard"))

    with connect_db() as conn:
        cursor = conn.cursor()

        # Get the professor assigned to the class
        cursor.execute("SELECT professor_id FROM classrooms WHERE id = ?", (class_id,))
        professor = cursor.fetchone()

        if not professor:
            flash("Error: Class not found.", "danger")
            return redirect(url_for("student_dashboard"))

        professor_id = professor[0]

        # Save student message in DB (with `replied=False` and no response yet)
        cursor.execute("""
            INSERT INTO messages 
            (student_enrollment, professor_id, class_id, message, seen, timestamp, sender_type, recipient_type, replied, response_to_message_id, justification_file) 
            VALUES (?, ?, ?, ?, 0, CURRENT_TIMESTAMP, 'student', 'professor', FALSE, NULL, NULL)
        """, (student_enrollment, professor_id, class_id, student_message))

        message_id = cursor.lastrowid  # Get the ID of this newly inserted message
        conn.commit()

        # AI Agent attempts to auto-handle the message
        ai_response = generate_ai_response(
            student_message, 
            student_enrollment, 
            class_id, 
            message_id
        )

        if ai_response:
            # AI responded → Save AI reply in DB, linked to student’s message
            recipient_type = 'student'
            cursor.execute("""
                INSERT INTO messages 
                (student_enrollment, professor_id, class_id, message, seen, timestamp, sender_type, recipient_type, replied, response_to_message_id, justification_file)
                VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP, 'ai_agent', ?, 1, ?, NULL)
            """, (student_enrollment, professor_id, class_id, ai_response, recipient_type, message_id))
            
            conn.commit()

            # Notify professor that AI handled it
            socketio.emit("ai_handled_absence", {
                "student_enrollment": student_enrollment,
                "class_name": class_id,
                "ai_response": ai_response
            })

            flash("✅ Absence request was auto-processed by AI.", "info")

        else:
            # No AI response → Notify professor directly via WebSocket
            socketio.emit("new_absence_message", {
                "student_enrollment": student_enrollment,
                "class_name": class_id
            })

            flash("✅ Absence message sent successfully!", "success")

    return redirect(url_for("student_dashboard"))

# Function to Generate Professor's Reply 
def generate_professor_reply(student_message, student_enrollment, class_id):
    """
    Uses GPT-4 to generate a professional and personalized response
    for a professor to send to a student who submitted an absence message.

    Args:
        student_message (str): The actual absence message from the student.
        student_enrollment (str): The student's enrollment ID.
        class_id (int): The class in which the absence occurred.

    Returns:
        str: A concise, context-aware response generated using GPT-4.
    """

    #  Step 1: Count student's absences in the class 
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) 
            FROM messages 
            WHERE student_enrollment = ? AND class_id = ? AND sender_type = 'student';
        """, (student_enrollment, class_id))
        
        absence_count = cursor.fetchone()[0]

    # Step 2: Construct AI prompt for GPT-4 
    prompt = f"""
    You are a professor responding to a student absence request.

    - Student Message: "{student_message}"
    - This student has been absent {absence_count} times in this class.
    
    Please:
    - Write a professional, respectful response in 2–3 sentences.
    - If the student has been absent 3 or more times, include a polite warning about their attendance.
    """

    # Step 3: Use GPT-4 to generate a response 
    response = client.ChatCompletion.create(
        model="gpt-4",  # Using OpenAI's GPT-4
        messages=[
            {"role": "system", "content": "You are an AI assistant for professors, generating absence responses."},
            {"role": "user", "content": prompt}
        ]
    )

    # Step 4: Return the generated reply 
    return response["choices"][0]["message"]["content"]


# Route for Replying to Messages 
@app.route('/reply-message', methods=['POST'])
def reply_message():
    """
    Handles professor replies to student messages, typically absence-related.

    - Retrieves original message details from the database.
    - Inserts the professor’s reply into the messages table.
    - Links it to the original message.
    - Marks the original message as "replied".
    - Notifies any external systems (e.g., AI agents) via the coordinator.

    Only accessible if the professor is logged in.
    """
    professor_id = session.get("professor_id")  # 🧾 Session validation
    if not professor_id:
        print("❌ Professor is not logged in!")
        return redirect(url_for("professor_login"))

    # Retrieve form values
    message_id = request.form.get("message_id")  # ID of the message being replied to
    reply_message_text = request.form.get("reply_message")  # Text of the professor's reply

    with connect_db() as conn:
        cursor = conn.cursor()

        # Fetch original message details
        cursor.execute("""
            SELECT student_enrollment, class_id, message 
            FROM messages 
            WHERE id = ?;
        """, (message_id,))
        student_info = cursor.fetchone()

        if student_info:
            student_enrollment, class_id, original_message = student_info

            # Logic to determine reply recipient
            # If the student's message contains a special flag, treat it as meant for the AI
            recipient = "ai_agent" if "requested confirmation" in original_message.lower() else "student"

            # Track message thread by linking the reply to the original
            response_to_message_id = message_id

            # Store the professor’s reply
            cursor.execute("""
                INSERT INTO messages 
                (student_enrollment, professor_id, class_id, message, timestamp, sender_type, recipient_type, replied, response_to_message_id)
                VALUES (?, ?, ?, ?, datetime('now'), 'professor', ?, 1, ?);
            """, (student_enrollment, professor_id, class_id, reply_message_text, recipient, response_to_message_id))

            # Mark original message as replied
            cursor.execute("UPDATE messages SET replied = 1 WHERE id = ?;", (message_id,))

            conn.commit()

            # Log confirmation
            print(f"✅ Professor's reply stored for {recipient} (Message ID: {message_id})")

            # Let the system know the professor has responded (e.g., to trigger notifications)
            coordinator.handle_professor_response(
                professor_id=professor_id, 
                student_enrollment=student_enrollment, 
                class_id=class_id, 
                reply=reply_message_text
            )

        else:
            print("❌ Error: No student info found for the provided message_id.")

    # Redirect professor back to dashboard after reply
    return redirect(url_for("professor_dashboard"))


# Professor Dashboard 
@app.route('/professor-dashboard')
def professor_dashboard():
    """
    Displays the professor's dashboard with:
    - Their assigned classrooms
    - All messages sent to them by students or AI agents
    - Linked AI responses for context
    - Status flags for each message (handled, pending, etc.)
    """
    # Check if the professor is logged in
    professor_id = session.get("professor_id")
    if not professor_id:
        return redirect(url_for("professor_login"))

    with connect_db() as conn:
        cursor = conn.cursor()

        # Fetch Professor’s Classes
        cursor.execute("""
            SELECT id, class_name 
            FROM classrooms 
            WHERE professor_id = ?;
        """, (professor_id,))
        classes = [{"id": row[0], "class_name": row[1]} for row in cursor.fetchall()]

        # Fetch Messages from Students/AI 
        cursor.execute("""
            SELECT 
                messages.id, students.name, classrooms.class_name, messages.message, 
                messages.timestamp, messages.seen, messages.sender_type, 
                messages.student_enrollment, messages.class_id,
                messages.replied, messages.recipient_type
            FROM messages
            JOIN students ON messages.student_enrollment = students.enrollment
            JOIN classrooms ON messages.class_id = classrooms.id
            WHERE messages.professor_id = ? 
              AND (messages.sender_type = 'student' OR messages.sender_type = 'ai_agent')
              AND messages.recipient_type = 'professor'
            ORDER BY messages.timestamp DESC;
        """, (professor_id,))
        student_messages = cursor.fetchall()

        # Fetch AI-Generated Responses 
        cursor.execute("""
            SELECT id, message, timestamp, response_to_message_id
            FROM messages
            WHERE sender_type = 'ai_agent'
            ORDER BY timestamp DESC;
        """)
        ai_messages = cursor.fetchall()

        # Map AI responses by the original message they are replying to
        ai_responses = {
            row[3]: {
                "id": row[0],
                "message": row[1],
                "timestamp": row[2]
            } for row in ai_messages
        }

        # Combine Messages with AI Replies 
        messages = []
        for row in student_messages:
            msg = {
                "id": row[0],
                "name": row[1],
                "class_name": row[2],
                "message": row[3],
                "timestamp": row[4],
                "seen": row[5],
                "sender_type": row[6],
                "student_enrollment": row[7],
                "class_id": row[8],
                "replied": row[9],
                "recipient_type": row[10]
            }

            # Flag status based on who sent it
            if msg["sender_type"] == "ai_agent":
                msg["status"] = "❌ Requires Professor Review"
            else:
                msg["status"] = "📌 Student Inquiry"

            # Attach AI response if it exists
            ai_response = ai_responses.get(msg["id"])
            msg["ai_response"] = ai_response
            msg["ai_handled"] = bool(ai_response)  # True if AI responded

            messages.append(msg)

        conn.commit()  # Ensure DB state is saved (if needed)

    # Render the dashboard template with classes and messages
    return render_template("professor_dashboard.html", classes=classes, messages=messages)


# Professor Attendance View 
@app.route("/professor-attendance", methods=["GET"])
def professor_attendance():
    """
    Displays a detailed attendance table for a professor's selected class and date.
    
    - Shows each student's status (Present/Absent)
    - Shows the time of recognition (if any)
    - Displays any message the student submitted explaining their absence
    """
    # Ensure professor is logged in
    if "professor_id" not in session:
        flash("⚠️ Please log in first!", "warning")
        return redirect(url_for("professor_login"))

    professor_id = session["professor_id"]

    # Get selected date from query string, default to today if not provided
    selected_date = request.args.get("date", datetime.today().strftime('%Y-%m-%d'))

    # Get selected class_id from query string
    class_id = request.args.get("class_id")

    with connect_db() as conn:
        cursor = conn.cursor()

        # Fetch Professor's Classes 
        cursor.execute("SELECT id, class_name FROM classrooms WHERE professor_id = ?", (professor_id,))
        classes = cursor.fetchall()

        attendance_records = []

        # If a class was selected, fetch attendance data
        if class_id:
            # Get Attendance for Class & Date 
            cursor.execute("""
                SELECT 
                    s.name,                     -- Student Name
                    s.enrollment,               -- Student Enrollment ID
                    COALESCE(a.status, 'Absent'),      -- Status if available, else 'Absent'
                    COALESCE(a.time_recognized, 'Not Detected'), -- Time if available, else fallback
                    COALESCE(m.message, 'No message')  -- Absence message if any
                FROM student_classes sc
                JOIN students s ON sc.enrollment = s.enrollment
                LEFT JOIN attendance a 
                    ON s.enrollment = a.enrollment 
                    AND a.class_id = sc.class_id 
                    AND a.date = ?
                LEFT JOIN absence_messages m 
                    ON s.enrollment = m.enrollment 
                    AND m.date = ?
                WHERE sc.class_id = ?
            """, (selected_date, selected_date, class_id))

            attendance_records = cursor.fetchall()

    # Render the Attendance Table 
    return render_template(
        "professor_attendance.html",
        classes=classes,
        attendance_records=attendance_records,
        selected_date=selected_date
    )


# View Classroom Attendance 
@app.route('/view-classroom/<int:class_id>', methods=['GET', 'POST'])
def view_classroom(class_id):
    """
    Displays attendance information for a specific classroom, accessible only to its assigned professor.

    - Validates professor authorization
    - Supports viewing attendance for a specific date (defaults to today)
    - Joins attendance data with absence messages and student info
    """
    professor_id = session.get('professor_id')  # Get professor from session
    if not professor_id:
        return redirect(url_for('login'))  # Redirect if not logged in

    conn = get_db_connection()
    cursor = conn.cursor()

    # Verify Access to Classroom
    class_query = """
    SELECT id, class_name 
    FROM classrooms 
    WHERE id = ? AND professor_id = ?
    """
    class_record = cursor.execute(class_query, (class_id, professor_id)).fetchone()

    if not class_record:
        flash("You are not authorized to view this class.", "danger")
        conn.close()
        return redirect(url_for('professor_dashboard'))

    # Get Selected Attendance Date 
    attendance_date = request.form.get("attendance_date")
    if not attendance_date:
        from datetime import datetime
        attendance_date = datetime.today().strftime('%Y-%m-%d')  # Default to today's date

    # Fetch Attendance with Messages
    attendance_query = """
    SELECT 
        COALESCE(students.name, 'Unknown Student') AS student_name,
        COALESCE(attendance.enrollment, 'Unknown ID') AS enrollment,
        attendance.status, 
        COALESCE(attendance.time_recognized, '--') AS time_recognized,
        COALESCE(messages.message, '--') AS absence_message
    FROM attendance 
    LEFT JOIN students ON students.enrollment = attendance.enrollment 
    LEFT JOIN messages ON messages.student_enrollment = attendance.enrollment 
        AND messages.class_id = attendance.class_id 
        AND DATE(messages.timestamp) = attendance.date
    WHERE attendance.class_id = ? 
        AND attendance.professor_id = ? 
        AND attendance.date = ?
    ORDER BY attendance.status DESC, students.name
    """
    attendance_records = cursor.execute(
        attendance_query, 
        (class_id, professor_id, attendance_date)
    ).fetchall()

    conn.close()

    # Render Template 
    return render_template(
        "view_classrooms.html", 
        class_name=class_record[1],  # Classroom name
        attendance_records=attendance_records,  # Attendance list with absences & messages
        class_id=class_id,
        selected_date=attendance_date
    )

#  Mark Attendance When Recognized
@socketio.on("student_recognized")
def mark_attendance(student_enrollment, class_id):
    """Marks a student as 'Present' when recognized."""
    today_date = datetime.today().strftime('%Y-%m-%d')

    with connect_db() as conn:
        cursor = conn.cursor()

        # Update status from "Absent" to "Present"
        cursor.execute("""
            UPDATE attendance
            SET status = 'Present'
            WHERE enrollment = ? AND class_id = ? AND date = ?
        """, (student_enrollment, class_id, today_date))

        conn.commit()

# Update Attendance in Real-Time 
@socketio.on("update_attendance")
def update_attendance(data):
    """
    Updates the attendance table in real-time when students are recognized via face recognition.

    Triggered by: Frontend or background task via socket.emit("update_attendance", {...})

    Parameters in `data`:
    - class_id (int): ID of the class where attendance is being taken
    - recognized_students (list of str): List of student enrollment numbers that were recognized
    """

    class_id = data.get("class_id")
    recognized_students = data.get("recognized_students")  # 🧑‍🎓 List of enrollments
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # ⏰ Timestamp of recognition

    with connect_db() as conn:
        cursor = conn.cursor()

        # Loop through each recognized student and update their status
        for student_enrollment in recognized_students:
            cursor.execute("""
                UPDATE attendance 
                SET status = 'Present', time_recognized = ? 
                WHERE class_id = ? AND enrollment = ? AND date = ?
            """, (
                current_time,                    # Time the student was recognized
                class_id,                        # Class in which they're being marked present
                student_enrollment,              # Enrollment number
                datetime.now().date()            # Attendance for today only
            ))

        conn.commit()  # Save all updates to the database


# Detect Faces and Update Attendance
@socketio.on("detect_faces")
def detect_faces(data):
    """
    Detects student faces in real-time and emits an update to mark them as present.

    Triggered by: Frontend or backend background process via socket.emit("detect_faces", {...})

    Parameters:
    - data (dict): {
        "class_id": ID of the class for which attendance is being recorded
      }

    Behavior:
    - Uses face recognition to identify students
    - Emits a socket event to update their attendance in the DB
    """

    class_id = data.get("class_id")  # 🏷️ Extract class ID from the request

    # Detect student faces for the given class using the recognition module
    recognized_students = recognize_student_face(class_id)

    # If any students were detected, emit an event to update their attendance
    if recognized_students:
        socketio.emit("update_attendance", {
            "recognized_students": recognized_students,
            "class_id": class_id
        })

# Helper Functions 

def connect_db():
    """
    Establish a connection to the SQLite database.
    Returns:
        sqlite3.Connection object
    """
    return sqlite3.connect(DATABASE_PATH)

def speak_instruction(text):
    """
    Speaks a movement instruction using the system’s built-in Text-to-Speech (TTS) engine.
    
    Args:
        text (str): The instruction to vocalize.
    """
    try:
        if os.name == "posix":  # macOS or Linux
            subprocess.run(["say", text])
        elif os.name == "nt":  # Windows
            subprocess.run([
                "powershell", 
                "-Command", 
                f"Add-Type –AssemblyName System.Speech; " +
                f"(New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{text}');"
            ])
    except Exception as e:
        print(f"⚠️ TTS Error: {e}")

def register_student(name, email, enrollment, password, professor_id):
    """
    Registers a student by capturing face encodings from a webcam and saving them,
    along with personal details, into the database.

    Args:
        name (str): Full name of the student.
        email (str): Email address.
        enrollment (str): Unique enrollment number.
        password (str): Hashed password.
        professor_id (int): ID of the assigned professor.

    Returns:
        bool: True if registration is successful, False otherwise.
    """

    # Start webcam
    cam = cv2.VideoCapture(0)
    if not cam.isOpened():
        print("❌ Camera failed to open.")
        return False

    # Create student-specific image folder
    image_folder = f"TrainingImage/{enrollment}"
    os.makedirs(image_folder, exist_ok=True)

    # Setup
    num_samples = 20
    face_encodings = []
    image_path = None
    movements = [
        "Look straight", "Look left", "Look right", 
        "Look up", "Look down", "Tilt left", "Tilt right"
    ]

    # Capture 20 samples with guided head movement
    for i in range(num_samples):
        instruction = movements[i % len(movements)]
        print(f"➡️ {instruction}")
        speak_instruction(instruction)

        time.sleep(1.5)  # Give the student time to move

        detected = False
        for attempt in range(3):  # Retry up to 3 times for each sample
            ret, img = cam.read()
            if not ret or img is None:
                print("❌ Camera read failed!")
                continue

            rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_img, model="cnn")  # Use "cnn" model for accuracy

            if face_locations:
                detected = True
                encoding = face_recognition.face_encodings(rgb_img, face_locations)
                if encoding:
                    face_encodings.append(encoding[0].tolist())

                # Save image
                image_path = os.path.join(image_folder, f"{enrollment}_{i+1}.jpg")
                cv2.imwrite(image_path, img)
                print(f"📸 Image {i+1}/{num_samples} saved: {image_path}")
                break  # Exit retry loop on success

            print(f"⚠️ No face detected in image {i+1}/{num_samples}, retrying ({attempt+1}/3)...")
            time.sleep(0.7)

        if not detected:
            print(f"❌ No face detected after 3 attempts for image {i+1}/{num_samples}.")

    # Cleanup
    cam.release()
    cv2.destroyAllWindows()

    if not face_encodings:
        print("❌ No valid face encodings found! Registration failed.")
        return False

    # Serialize encodings
    encoding_str = json.dumps(face_encodings)

    # Save student to DB
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO students (name, email, enrollment, password, face_encoding, professor_id) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, email, enrollment, password, encoding_str, professor_id))
        conn.commit()
        print(f"✅ Student {name} registered with {len(face_encodings)} encodings.")

    return True

# Retrieve student profile picture from the database
def get_student_image(enrollment):
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT profile_picture FROM students WHERE enrollment = ?", (enrollment,))
        student = cursor.fetchone()  # Get the student's image (if any)
    return student[0] if student else None  # Return image blob or None

# Authenticate student login credentials
def authenticate_student(enrollment, password):
    """
    Authenticates a student using their enrollment number and password.

    Args:
        enrollment (str): The student's enrollment ID.
        password (str): The plaintext password entered by the student.

    Returns:
        str or None:
            - Student's name (str) if authentication is successful.
            - "wrong_password" if password is incorrect.
            - None if student is not found.
    """

    with connect_db() as conn:
        cursor = conn.cursor()

        # Retrieve the hashed password and name for the given enrollment ID
        cursor.execute("SELECT password, name FROM students WHERE enrollment = ?", (enrollment,))
        student = cursor.fetchone()

    if student:
        stored_hashed_password = student[0].encode('utf-8')  # Convert stored password (str) to bytes
        entered_password = password.encode('utf-8')  # Convert entered password to bytes

        # Compare hashed password with the entered password
        if bcrypt.checkpw(entered_password, stored_hashed_password):
            return student[1]  # Successful login → return student name
        else:
            return "wrong_password"  # Password mismatch
    else:
        return None  # Student record not found

# Open the latest attendance record for a specific class
def open_latest_attendance(class_name):
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM attendance WHERE class_name = ? ORDER BY date DESC LIMIT 1", (class_name,))
        record = cursor.fetchone()
    return f"📌 Most recent attendance: {record}" if record else f"❌ No recent attendance records found for {class_name}."

# Get student data by enrollment number
def get_student_by_enrollment(enrollment):
    """
    Fetch a student’s enrollment ID and name from the database.

    Args:
        enrollment (str): The student’s unique enrollment ID.

    Returns:
        dict or None: A dictionary with keys 'Enrollment' and 'Name' if the student exists,
                      otherwise None.
    """
    with connect_db() as conn:
        cursor = conn.cursor()

        # Query student details based on enrollment ID
        cursor.execute("SELECT enrollment, name FROM students WHERE enrollment = ?", (enrollment,))
        row = cursor.fetchone()

    # Debugging output to trace what was returned from the DB
    print(f"🛠 Database Query Result for {enrollment}: {row}")

    # Return result as a dictionary if found
    return {"Enrollment": row[0], "Name": row[1]} if row else None

# Enroll a student in a class by class name
def enroll_student_in_class(enrollment, class_name):
    """
    Enroll a student into a class using class name.

    Args:
        enrollment (str): The student’s enrollment ID.
        class_name (str): The name of the class to enroll the student in.

    Returns:
        str: A success message or a warning if already enrolled.
    """
    with connect_db() as conn:
        cursor = conn.cursor()

        try:
            # Attempt to insert the enrollment into the student_classes table
            cursor.execute("INSERT INTO student_classes (enrollment, class_name) VALUES (?, ?)", (enrollment, class_name))
            conn.commit()

            return f"✅ Student {enrollment} enrolled in {class_name}."

        except sqlite3.IntegrityError:
            # Triggered if the student is already enrolled (violation of unique constraint)
            return f"⚠️ Student {enrollment} is already enrolled in {class_name}."

# Get all class names a student is enrolled in
def get_student_classes(enrollment):
    """
    Fetches all class names a student is enrolled in.

    Args:
        enrollment (str): The student's enrollment ID.

    Returns:
        list: A list of class names the student is enrolled in.
    """
    with connect_db() as conn:
        cursor = conn.cursor()

        # Query all class names for this enrollment ID
        cursor.execute("SELECT class_name FROM student_classes WHERE enrollment = ?", (enrollment,))
        classes = cursor.fetchall()

    # Return as a flat list of class names
    return [c[0] for c in classes] if classes else []

# Get student data by email address
def get_student_by_email(email):
    """
    Retrieve student details by email.

    Args:
        email (str): The student's email address.

    Returns:
        tuple or None: A tuple (id, name) if the student exists, otherwise None.
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()

        # Fetch student details based on email
        cursor.execute("SELECT id, name FROM students WHERE email = ?", (email,))
        student = cursor.fetchone()

    # Print for debugging
    print(f"🔍 Email Lookup for {email}: {student}")
    return student

# This function is deprecated or unused (has logic issue—password key not fetched from DB)
def verify_student_credentials(enrollment, password):
    """
    (Deprecated) Attempt to verify student credentials. This function has a logic error.

    Reason for deprecation:
        - `get_student_by_enrollment` does not return password, so bcrypt check fails.
    
    Fix:
        Use `authenticate_student()` instead.
    """
    student = get_student_by_enrollment(enrollment)

    # This will fail since "password" is not part of the dictionary returned above.
    if student and bcrypt.checkpw(password.encode('utf-8'), student["password"]):
        return student

    return None

# Fetch a student’s full attendance record
def calculate_attendance(enrollment):
    """
    Retrieves the attendance history for a student.

    Args:
        enrollment (str): The student's enrollment ID.

    Returns:
        list: A list of attendance records for the student.
    """
    return get_attendance_records(enrollment)  # Assumes this function is defined elsewhere

# Register a new admin with hashed password
def register_admin(email, password):
    """
    Registers a new admin in the database with a securely hashed password.

    Args:
        email (str): Admin's email address.
        password (str): Plaintext password.

    Returns:
        str: Success or error message.
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()

        # Hash password before storing
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        try:
            cursor.execute("INSERT INTO admins (email, password) VALUES (?, ?)", (email, hashed_password))
            conn.commit()
            return "✅ Admin registered successfully!"
        except sqlite3.IntegrityError:
            return "⚠️ Admin already exists!"

# Authenticate admin login
def authenticate_admin(email, password):
    """
    Verifies admin credentials for login.

    Args:
        email (str): Admin email.
        password (str): Plaintext password to verify.

    Returns:
        dict or None: Admin data as a dictionary if authentication succeeds, otherwise None.
    """
    admin = get_admin_by_email(email)

    if admin:
        stored_hashed_password = admin["password"]
        print(f"🛠 Stored Hashed Password: {stored_hashed_password}")

        # Compare provided password with hashed one from DB
        if bcrypt.checkpw(password.encode('utf-8'), stored_hashed_password.encode('utf-8')):
            print("✅ Password matches!")
            return admin
        else:
            print("❌ Password does not match.")
    else:
        print("❌ Admin not found in database.")
    
    return None

# Fetch admin details by email
def get_admin_by_email(email):
    """
    Retrieves admin information based on email address.

    Args:
        email (str): The email address of the admin.

    Returns:
        dict or None: A dictionary with admin details (id, email, password) if found, else None.
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, email, password FROM admins WHERE email = ?", (email,))
        admin = cursor.fetchone()

    # Return structured data if found
    return {"id": admin[0], "email": admin[1], "password": admin[2]} if admin else None

# Create a new classroom and associate it with a professor
def create_classroom(professor_id, class_name):
    """
    Creates a new classroom and assigns it to the professor.

    Args:
        professor_id (int): ID of the professor.
        class_name (str): Name of the classroom to be created.

    Returns:
        str: Success or error message.
    """
    with connect_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO classrooms (professor_id, class_name) VALUES (?, ?)", 
                (professor_id, class_name)
            )
            conn.commit()
            return "✅ Classroom created successfully!"
        except sqlite3.IntegrityError:
            return "❌ Error: Classroom already exists!"

# Add a student to a class after verifying professor ownership
def add_student_to_class(professor_id, enrollment, class_id):
    """
    Adds a student to a class if:
    - Student exists
    - Professor owns the class

    Args:
        professor_id (int): ID of the logged-in professor.
        enrollment (str): Student's enrollment ID.
        class_id (int): ID of the class.

    Returns:
        str: Status message indicating result of the operation.
    """
    with connect_db() as conn:
        cursor = conn.cursor()

        # Step 1: Verify the student exists
        cursor.execute("SELECT enrollment FROM students WHERE enrollment = ?", (enrollment,))
        student = cursor.fetchone()
        if not student:
            return "❌ Error: Student not found!"

        # Step 2: Check if professor owns the class
        cursor.execute("SELECT id FROM classrooms WHERE id = ? AND professor_id = ?", (class_id, professor_id))
        classroom = cursor.fetchone()
        if not classroom:
            return "❌ Error: Unauthorized to add students to this class!"

        # Step 3: Add the student to the class
        try:
            cursor.execute(
                "INSERT INTO student_classes (enrollment, class_id) VALUES (?, ?)", 
                (enrollment, class_id)
            )
            conn.commit()
            return "✅ Student added to class!"
        except sqlite3.IntegrityError:
            return "⚠️ Student is already in this class!"

# Generate a Unique Code for a Professor
def generate_professor_code(name):
    """
    Generates a unique professor code based on the professor's name.

    The code is composed of:
    - First 3 uppercase letters from the name (spaces removed)
    - Followed by 4 random digits

    Example:
        Input: "Robert Smith"
        Output: "ROB3842"

    Args:
        name (str): Professor's full name.

    Returns:
        str: A unique code in the format of 3 letters + 4 digits.
    """
    name_part = ''.join(name.split()).upper()[:3]  # First 3 letters in uppercase, no spaces
    number_part = ''.join(random.choices(string.digits, k=4))  # Random 4-digit string
    return f"{name_part}{number_part}"

# Register a Professor in the Database
def register_professor(name, email, password):
    """
    Registers a new professor in the system.

    Args:
        name (str): Full name of the professor.
        email (str): Unique email address.
        password (str): Plaintext password.

    Returns:
        str: Message indicating registration success or failure.
    """
    professor_code = generate_professor_code(name)

    # Hash the password before storing
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    with sqlite3.connect("attendance_system.db") as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO professors (name, email, password, professor_code) 
                VALUES (?, ?, ?, ?)
            """, (name, email, hashed_password, professor_code))
            conn.commit()
            return f"✅ Professor registered successfully! Assigned Code: {professor_code}"
        except sqlite3.IntegrityError:
            return "⚠️ Database Integrity Error: Email might already exist!"

# Retrieve a professor by email, name, and code (used in validation)
def get_professor_by_email_and_code(email, name, professor_code):
    """
    Retrieves a professor record matching the given email, name, and professor code.

    This is typically used during login to validate a professor's identity using a 3-field match.

    Args:
        email (str): The professor's email.
        name (str): The professor's full name.
        professor_code (str): The unique code assigned to the professor.

    Returns:
        tuple or None: (id, name, email, password, professor_code) if found, else None.
    """
    with sqlite3.connect("attendance_system.db") as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, name, email, password, professor_code 
            FROM professors 
            WHERE email = ? AND name = ? AND professor_code = ?
        """, (email, name, professor_code))
        professor = cursor.fetchone()
    return professor

# Get professor info by email (used for login or validation)
def get_professor_by_email(email):
    """
    Retrieves a professor's basic account information by email address.

    Args:
        email (str): The professor's email.

    Returns:
        tuple or None: (id, name, email, password) if found, else None.
    """
    with sqlite3.connect("attendance_system.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, email, password FROM professors WHERE email = ?", (email,))
        return cursor.fetchone()

# Update professor password securely
def update_professor_password(email, new_password):
    """
    Updates the professor's password securely in the database.

    Args:
        email (str): The professor's email address.
        new_password (str): The new hashed password to be saved.

    Note:
        Ensure the password is already hashed before calling this function.
    """
    with sqlite3.connect("attendance_system.db") as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE professors SET password = ? WHERE email = ?", (new_password, email))
        conn.commit()

# Get all students enrolled in a specific class
def get_students_in_class(class_id):
    """
    Returns a list of students enrolled in a specific class.

    Args:
        class_id (int): The ID of the classroom.

    Returns:
        list of tuples: Each tuple contains (enrollment, name).
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT students.enrollment, students.name
            FROM student_classes
            JOIN students ON student_classes.enrollment = students.enrollment
            WHERE student_classes.class_id = ?
        """, (class_id,))
        return cursor.fetchall()

# Get all classes created by a specific professor
def get_classes_for_professor(professor_id):
    """
    Retrieve all classroom IDs and names owned by the professor.
    Output: List of tuples (id, class_name)
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, class_name FROM classrooms WHERE professor_id = ?", (professor_id,))
        return cursor.fetchall()

# Get all attendance records submitted by a professor
def get_attendance_for_professor(professor_id):
    """
    Return all attendance entries recorded by this professor.
    Output: List of (enrollment, name, status, date)
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT students.enrollment, students.name, attendance.status, attendance.date
            FROM attendance
            JOIN students ON attendance.enrollment = students.enrollment
            WHERE attendance.professor_id = ?
            ORDER BY attendance.date DESC
        """, (professor_id,))
        return cursor.fetchall()

# Retrieve all messages sent to a specific professor
def get_messages_for_professor(professor_id):
    """
    Returns a list of messages sent to the professor, including:
    - Student name
    - Message content
    - Timestamp
    """
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT students.name, messages.message, messages.timestamp
            FROM messages
            JOIN students ON messages.student_enrollment = students.enrollment
            WHERE messages.professor_id = ?
            ORDER BY messages.timestamp DESC
        """, (professor_id,))
        return cursor.fetchall()

# Add a new absence message for a student to a professor
def send_absence_message(student_enrollment, professor_id, message):
    """
    Insert an absence message into the `messages` table.
    The `seen` flag is initially set to 0 (unread).
    """
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO messages (student_enrollment, professor_id, message, seen) 
            VALUES (?, ?, ?, 0)
        """, (student_enrollment, professor_id, message))
        conn.commit()

# Check if the professor has read the latest student message
def check_message_seen(student_enrollment):
    """
    Check the 'seen' status of the most recent message sent by a student.
    Returns:
        0 => Not seen
        1 => Seen
        None => No messages found
    """
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT seen FROM messages 
            WHERE student_enrollment = ? 
            ORDER BY timestamp DESC LIMIT 1
        """, (student_enrollment,))
        message = cursor.fetchone()
        return message[0] if message else None


# Route to retrieve attendance for a specific class and date
@app.route("/retrieve-attendance/<class_id>", methods=["GET"])
def retrieve_attendance(class_id):
    """
    Fetch attendance records for a given class ID on a specific date.
    If no date is provided via query parameter, defaults to today.
    Returns JSON response with attendance info.
    """
    selected_date = request.args.get("date")

    if not selected_date:
        # Default to today's date if none selected
        selected_date = datetime.now().strftime("%Y-%m-%d")

    students = []

    with sqlite3.connect("attendance_system.db") as conn:
        cursor = conn.cursor()

        print(f"📌 DEBUG: Fetching attendance for class_id={class_id} on date={selected_date}")

        # Optimize database performance and ensure latest data is read
        cursor.execute("PRAGMA synchronous = OFF")
        cursor.execute("PRAGMA cache_size = -2000")

        # Fetch attendance entries for this class on the selected date
        cursor.execute("""
            SELECT 
                a.enrollment, 
                sc.student_name, 
                a.status, 
                COALESCE(a.time_recognized, 'N/A'), 
                sc.class_name, 
                (
                    SELECT COUNT(*) 
                    FROM attendance 
                    WHERE class_id = ? AND enrollment = a.enrollment AND status = 'Absent'
                )
            FROM attendance a
            INNER JOIN student_classes sc 
                ON a.enrollment = sc.enrollment 
                AND sc.class_id = a.class_id
            WHERE a.class_id = ? AND a.date = ?
            ORDER BY a.time_recognized DESC
        """, (class_id, class_id, selected_date))

        fetched_records = cursor.fetchall()
        print(f"📌 DEBUG: Retrieved {len(fetched_records)} records")

        # Structure the response
        students = [
            {
                "enrollment": row[0],
                "name": row[1] if row[1] else "Unknown",
                "status": row[2],
                "time_recognized": row[3],
                "class_name": row[4],
                "absences": row[5]
            }
            for row in fetched_records
        ]

    print(f"📌 DEBUG: Final Response {students}")
    return jsonify({"recognized_students": students})

# Instantiate AI-powered attendance insights agent
insights_agent = AttendanceInsightsAgent()

# Generate AI report and summary for class
def generate_attendance_report(class_id):
    """
    Uses the AttendanceInsightsAgent to generate:
    - A DataFrame of attendance data
    - A GPT-generated summary of trends
    """
    class_name = get_class_name(class_id)
    return insights_agent.generate_attendance_report(class_id, class_name)

# Get the name of a class by its ID
def get_class_name(class_id):
    with connect_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT class_name FROM classrooms WHERE id = ?", (class_id,))
        result = cursor.fetchone()
        return result[0] if result else "This class"


@app.route('/generate-report', methods=['POST'])
def generate_report():
    """
    Handles the generation of attendance reports from professor dashboard.
    - Calls AI to generate insights
    - Saves a CSV
    - Re-renders the dashboard with report and messages
    """
    if "professor_id" not in session:
        return redirect(url_for("professor_login"))

    class_id = request.form.get("class_id")

    if not class_id:
        flash("Error: Please select a class!", "danger")
        return redirect(url_for("professor_dashboard"))

    # Get both the raw attendance data and GPT summary
    report_df, gpt_summary = generate_attendance_report(class_id)

    if report_df is None:
        flash("No attendance data found for this class.", "warning")
        return redirect(url_for("professor_dashboard"))

    # Ensure the reports folder exists
    report_dir = "static/reports"
    os.makedirs(report_dir, exist_ok=True)

    # Save report to CSV
    csv_filename = f"attendance_report_{class_id}.csv"
    csv_path = os.path.join(report_dir, csv_filename)
    report_df.to_csv(csv_path, index=False)

    flash("Report generated successfully!", "success")

    # Fetch necessary dashboard data again
    with connect_db() as conn:
        cursor = conn.cursor()

        # Retrieve professor’s classroom list
        cursor.execute("""
            SELECT id, class_name FROM classrooms WHERE professor_id = ?;
        """, (session["professor_id"],))
        professor_classes = cursor.fetchall()

        # Retrieve absence messages from students
        cursor.execute("""
            SELECT m.student_enrollment, c.class_name, m.message, m.timestamp, m.seen, m.id 
            FROM messages m
            JOIN classrooms c ON m.class_id = c.id
            WHERE m.recipient_type = 'professor'
            ORDER BY m.timestamp DESC;
        """)
        messages = [
            {
                "student_enrollment": row[0],
                "class_name": row[1],
                "message": row[2],
                "timestamp": row[3],
                "seen": row[4],
                "id": row[5]
            }
            for row in cursor.fetchall()
        ]

    # Render the full dashboard with AI report
    return render_template(
        "professor_dashboard.html",
        professor_classes=professor_classes,
        messages=messages,
        report=report_df.to_html(classes="table table-striped"),
        csv_path=csv_path,
        summary=gpt_summary
    )

if __name__ == '__main__':
    socketio.run(app, debug=True)
