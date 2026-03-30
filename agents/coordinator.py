"""
coordinator.py

This module defines the AgentCoordinator class, which acts as a central router
for the attendance management system. It connects and manages multiple agents—
including query understanding, alerting, prediction, retrieval, and insights agents—
to respond intelligently to user messages based on detected intent.
"""

# === Agent Imports ===
from agents.query_agent import QueryUnderstandingAgent  # Handles understanding user intent and extracting class names
from agents.retrieval_agent import AttendanceRetrievalAgent  # Retrieves attendance records
from agents.prediction_agent import AttendancePredictionAgent  # Predicts absenteeism risk
from agents.alert_agent import AbsenceAlertAgent  # Triggers alerts based on absence thresholds
from agents.insights_agent import AttendanceInsightsAgent  # Provides data insights on attendance

# === External Libraries ===
from flask import session  # Flask session for tracking user-specific context across requests
import sqlite3  # To connect and interact with the SQLite database

# === Database Configuration ===
DATABASE_PATH = "attendance_system.db"  # Path to the SQLite database file


class AgentCoordinator:
    """
    Central coordinating agent that routes user messages to appropriate agents
    based on their detected intent. Also manages conversation memory via Flask sessions.
    
    It integrates:
    - QueryUnderstandingAgent
    - AttendanceRetrievalAgent
    - AttendancePredictionAgent
    - AbsenceAlertAgent
    - AttendanceInsightsAgent
    """

    def __init__(self):
        """
        Initializes the coordinator by creating one instance of each agent.
        The goal is the coordinator to be able to call methods from any agent easily.
        """    
        self.query_agent = QueryUnderstandingAgent()
        self.attendance_agent = AttendanceRetrievalAgent()
        self.prediction_agent = AttendancePredictionAgent()
        self.alert_agent = AbsenceAlertAgent()
        self.insights_agent = AttendanceInsightsAgent()

    def handle_user_request(self, user_message, student_id=None, professor_id=None):
        """
        Routes the incoming student message to the correct agent, depending on
        the user's intent.

        Parameters:
            user_message (str): The message input from the user.
            student_id (str): The ID of the student sending the message.
            professor_id (str, optional): The professor's ID, used in some interactions.

        Returns:
            str: A natural language response for the chatbot to return to the user.
        """

        # Step 1: Use NLP to classify intent from the user's message
        intent = self.query_agent.classify_intent(user_message)

        # Step 2: Handle a simple "yes" message, based on saved context
        if user_message.strip().lower() in ["yes", "yeah", "sure", "please do"]:
            last_intent = session.get("last_intent") # Check previous intent
            last_class = session.get("last_class_mentioned") # Check previously detected class

            # Use saved class and intent context to notify professor
            if last_intent == "check_attendance_risk" and last_class:
                # Get list of student’s enrolled classes
                classes = self.get_student_classes(student_id)

                # Try to match the last class mentioned
                matched = [c for c in classes if c[1].lower() == last_class.lower()]
                
                if matched:
                    class_id, class_name, professor_id = matched[0]

                    # Notify professor using the alert agent
                    return self.alert_agent.notify_professor(student_id, [(class_id, class_name, professor_id)])

                return "❌ Sorry, I couldn't match the class to your profile."

            # If intent or class isn’t clear
            return "❓ I’m not sure what you mean by 'yes'. Could you clarify?"

        # Step 3: Store intent in session memory for future reference
        session["last_intent"] = intent  

        # INTENT: Check if student is at risk of failing
        if intent == "check_attendance_risk":
            return self.alert_agent.check_absence_threshold(student_id, user_message, self)

        # INTENT: Manually notify professor
        elif intent == "notify_professor":
            last_class = session.get("last_class_mentioned") # Get class name from session
            if not last_class:
                return "❌ I couldn’t detect which class you're referring to. Can you please clarify?"

            classes = self.get_student_classes(student_id) # Get student’s classes

            # Try to match the stored class name
            matched = [c for c in classes if c[1].lower() == last_class.lower()]
            if not matched:
                return f"❌ Could not identify a class from your request. Please specify the class name."

            class_id, class_name, professor_id = matched[0]
            return self.alert_agent.notify_professor(student_id, [(class_id, class_name, professor_id)])

        # INTENT: General attendance question
        elif intent == "general_attendance_question":
            # Try to detect class name directly from the message
            for class_id, class_name, professor_id in self.get_student_classes(student_id):
                if class_name.lower() in user_message.lower():

                    # Save this class in session for context and check attendance
                    session["last_class_mentioned"] = class_name
                    return self.alert_agent.check_absence_threshold(student_id, user_message, self)

            # If no class name found in message, fall back to stored context
            last_class = session.get("last_class_mentioned")
            if last_class:
                return f"📌 You previously asked about **{last_class}**. Would you like me to check your attendance for that class?"

            # If still no class found
            return "📚 Please specify the class you're asking about."

        # INTENT: Generate a graph showing attendance trend
        elif intent == "generate_attendance_graph":
            # Try to detect class name from message
            for class_id, class_name, _ in self.get_student_classes(student_id):
                if class_name.lower() in user_message.lower():
                    session["last_class_mentioned"] = class_name
                    return self.insights_agent.generate_classwise_attendance_trend(student_id)

            # Fall back to last mentioned class
            last_class = session.get("last_class_mentioned")
            if last_class:
                return self.insights_agent.generate_classwise_attendance_trend(student_id)

            # If no class context found
            return "📚 Please specify the class you'd like the graph for."

        # INTENT: Predict risk of future absences
        elif intent == "attendance_prediction":
            detected_class = self.query_agent.extract_class_from_text(user_message, student_id, self)
            if detected_class:
                return self.prediction_agent.predict_absenteeism(student_id, detected_class)
            else:
                return "❌ I couldn't detect the class. Please mention the class name for prediction."


        # INTENT: Greetings
        elif intent == "greeting":
            return "👋 Hello! How can I assist you with your attendance today?"

        # INTENT: Thank you message
        elif intent == "thanks":
            return "😊 You're welcome! Let me know if you have more questions."

        # INTENT: Unknown or fallback — use GPT to respond generically
        else:
            return self.query_agent.process_query(user_message, student_id, self)

    def handle_professor_response(self, professor_id, student_id, class_id, professor_message):
        """
        Handles a professor’s reply and sends a summarized version of it to the student.
        It also records both the professor's and AI agent's messages in the database.

        Parameters:
            professor_id (str): The professor’s ID.
            student_id (str): The student’s enrollment number.
            class_id (str): The class ID.
            professor_message (str): The message text the professor has entered.

        Returns:
            str: Confirmation that the student has been notified.
        """

        class_name = self.get_class_name(class_id)
        ai_response = f"📢 Your professor for **{class_name}** has reviewed your attendance and said: **'{professor_message}'**."

        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()

            # Try to find the latest message from the student to link replies
            cursor.execute("SELECT id FROM messages WHERE student_enrollment = ? AND class_id = ? ORDER BY timestamp DESC LIMIT 1;",
            (student_id, class_id))
            original_message = cursor.fetchone()

            if original_message:
                response_to_message_id = original_message[0]  # ✅ Link reply to the latest student question
            else:
                response_to_message_id = None

            # Insert the professor’s response into the message table
            cursor.execute("""
                INSERT INTO messages (student_enrollment, professor_id, class_id, message, timestamp, sender_type, recipient_type, replied, response_to_message_id)
                VALUES (?, ?, ?, ?, datetime('now'), 'professor', 'ai_agent', 1, ?);
            """, (student_id, professor_id, class_id, professor_message, response_to_message_id))

            # Insert the AI's generated reply to the student
            cursor.execute("""
                INSERT INTO messages (student_enrollment, professor_id, class_id, message, timestamp, sender_type, recipient_type, replied, response_to_message_id)
                VALUES (?, ?, ?, ?, datetime('now'), 'ai_agent', 'student', 0, ?);
            """, (student_id, professor_id, class_id, ai_response, response_to_message_id))

            conn.commit()

        return "AI has notified the student about the professor’s response."

    def get_student_classes(self, student_id):
        """
        Retrieves all classes that a student is enrolled in.

        Parameters:
            student_id (str): The student’s enrollment number.

        Returns:
            list of tuples: Each tuple contains (class_id, class_name, professor_id).
        """
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()

            # Join student_classes with classrooms to get full info
            cursor.execute("""
                SELECT sc.class_id, c.class_name, c.professor_id
                FROM student_classes sc
                JOIN classrooms c ON sc.class_id = c.id
                WHERE sc.enrollment = ?
            """, (student_id,))
            
            results = cursor.fetchall()
            print(f"📌 DEBUG: Retrieved student classes -> {results}")  # Debugging
            return results

    def get_class_name(self, class_id):
        """
        Retrieves the name of a class given its ID.

        Parameters:
            class_id (int): The unique class identifier.

        Returns:
            str: The name of the class, or "Unknown Class" if not found.
        """
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT class_name FROM classrooms WHERE id = ?;", (class_id,))
            result = cursor.fetchone()
            return result[0] if result else "Unknown Class"
