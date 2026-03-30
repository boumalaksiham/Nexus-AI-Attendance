"""
prediction_agent.py

This file defines the AttendancePredictionAgent class, which analyzes a student's
attendance records for a specific class. It calculates their attendance rate, checks
if they have been absent frequently (especially recently or on specific days),
and generates a natural-language explanation using GPT.

The goal is to help students understand if their current attendance behavior
may put them at risk of being absent again in the future.
"""

# === Standard Python Libraries ===
from datetime import datetime             # For converting date strings into weekday names
import os                                 # To read environment variables securely
import sqlite3                            # For accessing and reading data from the database

# === Third-Party Libraries ===
import numpy as np                        # Used for numerical operations (not used in this file yet)
from openai import OpenAI                 # To generate natural-language summaries using GPT
from dotenv import load_dotenv            # To load the API key from the .env file

# === Project-Specific Import ===
from database import connect_db           # Function to connect to the SQLite database

# === Environment Variable Setup ===
load_dotenv()                             # Load variables from the .env file into the system environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Read the OpenAI key securely (do NOT hardcode it)

class AttendancePredictionAgent:
    """
    This class checks a student's attendance pattern for a specific class and
    creates a summary that explains whether their attendance behavior suggests
    a risk of missing more classes in the future.
    """

    def __init__(self):
        """
        Initializes the GPT client by providing the OpenAI API key from the environment.
        """
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def predict_absenteeism(self, student_id, class_name):
        """
        Analyzes the student's attendance in a specific class. It calculates:
        - Total number of classes attended and missed
        - Attendance percentage
        - Number of absences in the last 3 classes
        - Whether the student frequently misses the same weekday (like Mondays)

        Then it sends this information to GPT, which writes a short summary message
        to help the student understand their current attendance status.

        Parameters:
            student_id (str): The student's enrollment number.
            class_name (str): The name of the class to check.

        Returns:
            str: A summary message describing the student's attendance status.
        """
        # Connect to the database
        with connect_db() as conn:
            cursor = conn.cursor()

            # Step 1: Find the class ID that matches the given class name
            cursor.execute("SELECT id FROM classrooms WHERE class_name = ?;", (class_name,))
            result = cursor.fetchone()

            if not result:
                return f"❌ Class '{class_name}' not found in the system."

            class_id = result[0]

            # Step 2: Get all attendance records for this student in the selected class
            cursor.execute("""
                SELECT date, status FROM attendance
                WHERE enrollment = ? AND class_id = ?
                ORDER BY date ASC;
            """, (student_id, class_id))

            records = cursor.fetchall()

            # If no attendance records are found, we cannot analyze the student's behavior
            if not records:
                return "❌ No attendance data available for this class."

            total_sessions = len(records)  # Total number of class sessions
            absences = sum(1 for r in records if r[1] == "Absent")  # Count number of absences
            attendance_rate = round((total_sessions - absences) / total_sessions * 100, 1)  # Calculate %

            # Step 3: Count how many of the last 3 classes were missed
            recent_records = records[-3:]  # Get the most recent 3 classes
            recent_absences = sum(1 for r in recent_records if r[1] == "Absent")

            # Step 4: Check if the student often misses a specific day of the week
            # For example, if they missed many Mondays
            day_absence_count = {}  # Dictionary to store how often each weekday was missed

            for record in records:
                date_string, status = record
                if status == "Absent":
                    weekday = datetime.strptime(date_string, "%Y-%m-%d").strftime("%A")
                    day_absence_count[weekday] = day_absence_count.get(weekday, 0) + 1

            # Find the weekday that was missed the most
            if day_absence_count:
                most_missed_day = max(day_absence_count, key=day_absence_count.get)
            else:
                most_missed_day = "N/A"

            # Step 5: Prepare a message to send to GPT to generate a summary
            prompt = f"""
You are an academic assistant AI. A student with ID {student_id} has attended the class '{class_name}'.

Here is a summary of their attendance:
- Total number of class sessions: {total_sessions}
- Number of absences: {absences}
- Attendance percentage: {attendance_rate}%
- Number of missed classes in the last 3 sessions: {recent_absences}
- Most frequently missed day of the week: {most_missed_day}

Write a short summary (2–3 sentences) to help the student understand their attendance situation.
If their attendance seems risky or low, kindly suggest that they should be more careful.
Avoid being harsh. Be clear and helpful.
"""

            # Step 6: Send the prompt to GPT and return the generated summary
            try:
                response = self.client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system", "content": "You are a helpful academic advisor."},
                        {"role": "user", "content": prompt}
                    ]
                )
                return response.choices[0].message.content.strip()

            except Exception as e:
                return f"⚠️ Could not generate summary because of an error: {str(e)}"
