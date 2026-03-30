"""
database.py

Purpose:
This script sets up the core database structure for the Nexus-AI Attendance System.

What It Does:
- Connects to a SQLite database (`attendance_system.db`)
- Creates key tables: students, professors, admins, classrooms, attendance, messages, and professor codes
- Ensures at least one default professor code ("PROF123") exists
- Part of the backend setup — run this once during initial deployment

Note:
Some tables may have been created manually through tools like DB Browser or other SQL scripts.
This script only guarantees the creation of the essential programmatic ones.

"""

# Imports
import sqlite3         # Built-in Python library to interact with SQLite databases
import bcrypt          # Used to securely hash passwords (not used directly in this file, but used elsewhere in the system)
import uuid            # Used for generating unique identifiers (for users or tokens)
import cv2             # OpenCV – used for webcam access and face detection
import face_recognition # For detecting and encoding facial features (used during student registration)
import os              # Provides functions for interacting with the operating system (e.g. file paths)
import json            # For reading/writing data in JSON format (not used directly in this file)
import random          # Used for generating random values, if needed (e.g. temporary codes)
import string          # For handling character sets when generating random strings


# Path to the database file
DATABASE_PATH = "attendance_system.db"

# Database Connection 
def connect_db():
    """
    Establishes a connection to the SQLite database.
    Returns a connection object that can be used to execute SQL statements.
    """
    return sqlite3.connect(DATABASE_PATH)

# Database Initialization
def initialize_database():
    """
    Creates all the essential tables used by Nexus-AI if they don't already exist.
    This function should be run once during setup or deployment.
    """
    with connect_db() as conn:
        cursor = conn.cursor()

        # Students Table: Stores all registered students
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                enrollment TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                profile_picture BLOB,        -- Stores the image data (optional)
                face_encoding BLOB           -- Stores the encoded facial features
            )
        ''')

        # Professors Table: Registered professors
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS professors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                professor_code TEXT UNIQUE NOT NULL -- A code used during registration
            )
        ''')

        # Admins Table: Admin credentials
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            )
        ''')

        # Classrooms Table: List of all created classes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS classrooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                class_name TEXT NOT NULL,
                professor_id INTEGER NOT NULL,
                FOREIGN KEY (professor_id) REFERENCES professors(id)
            )
        ''')

        # Student-Class Mapping Table: Links students to their enrolled classes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS student_classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                enrollment TEXT NOT NULL,
                class_id INTEGER NOT NULL,
                FOREIGN KEY (enrollment) REFERENCES students(enrollment),
                FOREIGN KEY (class_id) REFERENCES classrooms(id)
            )
        ''')

        # Attendance Table: Tracks daily attendance for students per class
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                enrollment TEXT NOT NULL,
                class_id INTEGER NOT NULL,
                date TEXT NOT NULL DEFAULT (DATE('now')), -- Automatically uses current date
                status TEXT NOT NULL,                     -- e.g., Present or Absent
                professor_id INTEGER NOT NULL,
                FOREIGN KEY (enrollment) REFERENCES students(enrollment),
                FOREIGN KEY (class_id) REFERENCES classrooms(id),
                FOREIGN KEY (professor_id) REFERENCES professors(id)
            )
        ''')
        
        # Student Activities Table: Tracks the student activity in their dashboard
        cursor.execute('''
                CREATE TABLE IF NOT EXISTS student_activities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        student_id TEXT NOT NULL,
                        activity TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (student_id) REFERENCES students(enrollment)
                )
                ''')

        # Messages Table: Stores student messages to professors (e.g. absence justifications)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_enrollment TEXT NOT NULL,
                professor_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                seen INTEGER DEFAULT 0, -- 0 = Unseen, 1 = Seen
                FOREIGN KEY (student_enrollment) REFERENCES students(enrollment),
                FOREIGN KEY (professor_id) REFERENCES professors(id)
            )
        ''')

        # Professor Codes Table: Used to verify professor identity at registration
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS professor_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL
            )
        ''')

        # Seed a default professor code if not already present
        cursor.execute("SELECT * FROM professor_codes WHERE code = 'PROF123'")
        if not cursor.fetchone():
            cursor.execute("INSERT INTO professor_codes (code) VALUES ('PROF123')")

        # Commit all changes to the database
        conn.commit()
        print("✅ Database initialized successfully!")

# Run the Initialization 
initialize_database()
