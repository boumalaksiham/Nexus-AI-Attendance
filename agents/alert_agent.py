"""
alert_agent.py

This module contains the AbsenceAlertAgent class, which is part of the multi-agent  attendance management system. 
It handles logic for checking student absences in  specific classes and notifies professors when thresholds are exceeded.
"""

# === External Libraries ===
# sqlite3 is used to connect and interact with the local SQLite database
import sqlite3

# datetime is used to generate timestamps for message records
from datetime import datetime


# Path to the local SQLite database used to store attendance and messaging data
DATABASE_PATH = "attendance_system.db"


class AbsenceAlertAgent:
    """
    This autonomous agent monitors student attendance patterns for a specific class.
    It checks whether a student has exceeded a set absence threshold (e.g., 3 or more absences),
    and if so, sends an alert or message to the course professor.

    Main responsibilities:
    - Interprets student questions related to absences.
    - Queries the database to count absences for a specific class.
    - Determines whether the professor should be notified.
    - Sends automated notifications to the professor when needed.
    """

    def check_absence_threshold(self, student_id, user_message, coordinator):
        """
        Checks how many times a student has been absent from a specific class 
        and decides whether to notify the professor.

        Parameters:
            student_id (str): The unique ID (enrollment number) of the student.
            user_message (str): A message typed by the student (e.g., “How many times did I miss Math?”).
            coordinator (object): Another agent that helps extract info like class names from messages.
        
        Returns:
        str: A response message to send to the student, either confirming their attendance,
             asking for clarification, or stating that the professor has been notified.
        """
        print(f"🔍 DEBUG: check_absence_threshold() called for student {student_id}")  # Debug log

        # Step 1: Try to identify the class being referred to in the user's message
        detected_class = coordinator.query_agent.extract_class_from_text(
            user_message, student_id, coordinator
        )

        # If class is not detected, ask the student to specify it explicitly
        if not detected_class:
            return "❌ I couldn't detect which class you're asking about. Can you please specify the class name?"

        # Step 2: Connect to the database to retrieve attendance information
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()

            # Count how many times the student was marked 'Absent' in the detected class
            cursor.execute("""
                SELECT COUNT(*) 
                FROM attendance 
                WHERE enrollment = ? 
                AND class_id = (SELECT id FROM classrooms WHERE class_name = ?)
                AND status = 'Absent';
            """, (student_id, detected_class))
            total_absences = cursor.fetchone()[0]  # Fetch the count result

            print(f"🔍 DEBUG: Total absences for {detected_class} (Student {student_id}) = {total_absences}")

            # Fetch class ID and professor ID by joining relevant tables
            cursor.execute("""
                SELECT c.id, c.professor_id 
                FROM classrooms c
                JOIN student_classes sc ON c.id = sc.class_id
                WHERE sc.enrollment = ? AND c.class_name = ?;
            """, (student_id, detected_class))
            class_info = cursor.fetchone()

        # Step 3: If the class or enrollment details aren't found, return an error message
        if not class_info:
            return "❌ I couldn't find your class details. Please check with your professor."

        class_id, professor_id = class_info

        # Step 4: Construct a response message based on absence count

        # CASE 1: Student has no absences
        if total_absences == 0:
            print(f"✅ DEBUG: Student {student_id} has zero absences in {detected_class}")
            return (
                f"✅ **Great news! You have no absences in {detected_class}** and are **not at risk of failing**. 🎉\n\n"
                f"Would you like me to **ask your professor for confirmation?**\n"
                f"Reply **'yes'** to notify your professor."
            )

        # CASE 2: Student has exceeded the absence threshold (default: 3 absences)
        elif total_absences >= 3:
            print(f"⚠️ DEBUG: Student {student_id} has {total_absences} absences in {detected_class} — notifying professor")
            self.notify_professor(student_id, [(class_id, detected_class, professor_id)])
            return (
                f"⚠️ **Warning:** You have been absent **{total_absences} times** in {detected_class}. "
                f"This may put you at risk of failing.\n"
                f"✅ **I have notified your professor** about your attendance."
            )

        # CASE 3: Student has some absences, but not enough to trigger auto-alert (ask student)
        print(f"📊 DEBUG: Student {student_id} has {total_absences} absences in {detected_class} — asking if they want to notify")
        return (
            f"📊 **You have been absent {total_absences} times in {detected_class}.**\n"
            f"Would you like me to **ask your professor about your attendance?** (Reply 'yes' to send a message)"
        )

    def notify_professor(self, student_id, classes):
        """
        Notifies the professor when a student requests attendance confirmation.

        Parameters:
            student_id (str): The student’s enrollment ID.
            classes (list of tuples): A list of tuples like (class_id, class_name, professor_id).
        
        Returns:
            str: Confirmation that the message was inserted into the system.
        
        """
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()

            # Loop through all classes (even if there's just one)
            for class_data in classes:
                class_id, class_name, professor_id = class_data

                print(f"📌 DEBUG: Notifying professor — class_id={class_id}, class_name={class_name}, professor_id={professor_id}")

                # Get the student's name from the database
                cursor.execute("SELECT name FROM students WHERE enrollment = ?;", (student_id,))
                student_name_result = cursor.fetchone()
                student_name = student_name_result[0] if student_name_result else "Unknown Student"

                # Construct the message to be sent to the professor
                print(f"📌 DEBUG: Notifying — Student: {student_name}, Class: {class_name}, Class ID: {class_id}")
                message_text = (
                    f"📢 The student **{student_name}** ({student_id}) has requested confirmation "
                    f"about their attendance in **{class_name}**."
                )

                # Insert the message into the system's message table in the database
                cursor.execute("""
                    INSERT INTO messages (
                        student_enrollment, professor_id, class_id, message,
                        sender_type, recipient_type, timestamp, seen, replied
                    ) VALUES (?, ?, ?, ?, 'ai_agent', 'professor', datetime('now'), 0, 0);
                """, (student_id, professor_id, class_id, message_text))

            conn.commit() # Save changes to the database

        return "✅ Your professor has been notified about your attendance concern."
