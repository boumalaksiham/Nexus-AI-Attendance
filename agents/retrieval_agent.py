"""
retrieval_agent.py

This module defines the AttendanceRetrievalAgent class. It is responsible for retrieving
basic attendance information from the database, such as the total number of times
a student has been marked 'Absent'.

This agent is used when a student simply wants to know how many classes they have missed.
"""

# === Standard Library ===
import sqlite3  # To connect to and query the SQLite database

# === Database Path ===
DATABASE_PATH = "attendance_system.db"  # Local path to the SQLite attendance database


class AttendanceRetrievalAgent:
    """
    This agent retrieves a student's attendance data from the database.
    """

    def get_absences(self, student_id):
        """
        Counts how many times a student has been marked as 'Absent' in the database.

        Parameters:
            student_id (str): The unique enrollment number of the student.

        Returns:
            str: A formatted message stating how many times the student has been absent.
        """
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()

            # Count the number of 'Absent' records for the given student
            cursor.execute("""
                SELECT COUNT(*) FROM attendance 
                WHERE enrollment = ? AND status = 'Absent'
            """, (student_id,))
            
            absences = cursor.fetchone()[0]  # Retrieve the result from the query

        return f"📊 You have been absent **{absences}** times."
