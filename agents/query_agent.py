"""
query_agent.py

This module defines the QueryUnderstandingAgent class. It acts as the language interpreter
for student messages in the attendance system. It uses GPT to:
- Understand the type of question a student is asking.
- Detect which class they are referring to.
- Fetch attendance summaries from the database.
- Generate helpful natural language responses.

This agent helps coordinate responses across the entire multi-agent system.
"""

# === Third-Party and Standard Library Imports ===
from openai import OpenAI                   # To generate and classify student messages using GPT
import sqlite3                              # To access attendance records from the database
from flask import session                   # To store recent user context (like last class asked about)
import re                                   # For basic pattern detection (like class name extraction)
import os                                   # To access environment variables securely
from dotenv import load_dotenv              # To load API key from .env file

# === Environment Setup ===
load_dotenv()
DATABASE_PATH = "attendance_system.db"      # Path to the local SQLite database file
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Load OpenAI key from environment


class QueryUnderstandingAgent:
    """
    This agent interprets natural language messages from students.
    It identifies what the student is asking and responds using GPT.
    """

    def __init__(self):
        """
        Initializes the GPT client using the API key stored in the environment file.
        """
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def classify_intent(self, user_message):
        """
        This method determines what the student is trying to ask.

        For example:
        - "Am I at risk of failing Math?" → check_attendance_risk
        - "Can you tell my professor?" → notify_professor

        Parameters:
            user_message (str): The question typed by the student.

        Returns:
            str: A keyword label that describes the question type (e.g., "greeting", "thanks", "attendance_prediction").
        """
        prompt = f"""
You are an AI classifier in an educational attendance system.
Given the student's message, identify the **intent** behind the message.
Only return ONE of the following categories:

- check_attendance_risk
- notify_professor
- general_attendance_question
- generate_attendance_graph
- attendance_prediction
- greeting
- thanks
- other

Message: "{user_message}"

Respond ONLY with the category name.
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You classify student queries for an attendance assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            intent = response.choices[0].message.content.strip().lower()
            print(f"🧠 DEBUG: Intent classified as -> {intent}")
            return intent
        except Exception as e:
            print(f"⚠️ Intent classification error: {e}")
            return "other"

    def process_query(self, user_message, student_id, coordinator):
        """
        Responds to a student's question by:
        - Trying to detect which class the message is referring to.
        - Retrieving attendance summary from the database.
        - Generating a helpful message using GPT.
        - Notifying the professor if requested.

        Parameters:
            user_message (str): Message written by the student.
            student_id (str): The student's enrollment ID.
            coordinator (object): The central agent coordinator (needed to call other agents).

        Returns:
            str: A response message to the student.
        """
        # Step 1: Detect the class being asked about
        detected_class = self.extract_class_from_text(user_message, student_id, coordinator)

        if not detected_class:
            return "❌ I couldn't detect which class you're asking about. Can you please specify the class name?"

        # Step 2: Get a summary of the student’s attendance in that class
        attendance_data = self.get_attendance_summary(student_id)

        # Step 3: Prepare a GPT prompt to generate the response
        prompt = f"""
You are an AI assistant helping students with their attendance queries. 
The student (ID: {student_id}) is asking about **{detected_class}**.
Their attendance record for **{detected_class}** is:
{attendance_data}

- If the student asks whether they are at risk of failing, analyze **{detected_class}** only.
- If the student asks you to notify their professor, **do not reply directly**. Instead, return `"notify_professor"`.
"""

        # Step 4: Get GPT response
        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message}
            ]
        )

        gpt_response = response.choices[0].message.content.strip()

        # Step 5: If GPT says to notify professor, handle that
        if "notify_professor" in gpt_response.lower():
            class_info = coordinator.get_class_info(student_id, detected_class)
            if not class_info:
                return "❌ I couldn't find your class information. Please check with your professor."

            # Use alert agent to send message to professor
            coordinator.alert_agent.notify_professor(student_id, class_info)
            return f"✅ I have successfully notified your professor for **{detected_class}**."

        # Step 6: Save AI response to database and link it to student’s last message
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id FROM messages 
                WHERE student_enrollment = ? 
                AND sender_type = 'student' 
                ORDER BY timestamp DESC LIMIT 1;
            """, (student_id,))
            
            original_message = cursor.fetchone()
            response_to_message_id = original_message[0] if original_message else None

            cursor.execute("""
                INSERT INTO messages (
                    student_enrollment, class_id, message, sender_type, recipient_type,
                    timestamp, seen, replied, response_to_message_id
                ) VALUES (?, ?, ?, 'ai_agent', 'student', CURRENT_TIMESTAMP, 0, 1, ?);
            """, (student_id, detected_class, gpt_response, response_to_message_id))

            conn.commit()

        return gpt_response

    def extract_class_from_text(self, user_message, student_id, coordinator):
        """
        Tries to identify which class the student is referring to in their message.

        It compares the student's words to the list of classes they are enrolled in.

        Parameters:
            user_message (str): What the student wrote.
            student_id (str): Their unique enrollment number.
            coordinator (object): Needed to fetch the student’s class list.

        Returns:
            str or None: The detected class name, or None if nothing matches.
        """
        student_classes = coordinator.get_student_classes(student_id)

        # Convert list to dictionary: { "math101": "MATH101", "cs102": "CS102" }
        class_names = {c[1].lower(): c[1] for c in student_classes}

        for class_key in class_names:
            if class_key in user_message.lower():
                return class_names[class_key]

        return None

    def get_attendance_summary(self, student_id):
        """
        Retrieves the student's attendance data for each class from the database.

        Parameters:
            student_id (str): The student’s enrollment number.

        Returns:
            str: A formatted text summary (e.g., “Math101: 2 absences, 10/12 attended”).
        """
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT sc.class_name, COUNT(a.status) AS absences,
                    (SELECT COUNT(*) FROM attendance WHERE enrollment = ? AND status = 'Present') AS attended,
                    (SELECT COUNT(*) FROM attendance WHERE enrollment = ?) AS total
                FROM attendance a
                JOIN student_classes sc ON a.class_id = sc.class_id
                WHERE a.enrollment = ? AND a.status = 'Absent'
                GROUP BY a.class_id
            """, (student_id, student_id, student_id))
            
            records = cursor.fetchall()

        if not records:
            return "The student has no absences recorded."

        # Format each row into a readable line
        summary = "\n".join([
            f"- {row[0]}: {row[1]} absences, {row[2]}/{row[3]} attended"
            for row in records
        ])
        return summary
