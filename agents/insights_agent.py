"""
insights_agent.py

This module defines the AttendanceInsightsAgent class, which provides:
- Student attendance trend graphs
- Risk analysis
- GPT-powered class summary reports

It connects to an SQLite database, uses matplotlib for visualization,
and securely loads the OpenAI API key using environment variables.
"""

# === Standard Library ===
import os                                  # For accessing environment variables (e.g., API key)
import sqlite3                             # To connect and query the SQLite database

# === Third-Party Libraries ===
import pandas as pd                        # For data manipulation and tabular analysis
import matplotlib.pyplot as plt            # For creating charts and graphs
import matplotlib                          # For backend control when rendering charts
from dotenv import load_dotenv             # To load environment variables from a .env file
from openai import OpenAI                  # OpenAI API client for GPT-based summaries

# === Matplotlib Configuration ===
matplotlib.use('Agg')                      # Use a non-GUI backend (safe for servers, macOS, etc.)

# === Environment Setup ===
load_dotenv()                              # Load variables from .env file into environment
DATABASE_PATH = "attendance_system.db"     # Path to the local SQLite database
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # Read OpenAI key from environment variable


class AttendanceInsightsAgent:
    """
    This agent handles visualizations and analytics for student attendance.
    It uses GPT to generate class-level summary insights.
    """

    def __init__(self):
        """
        Initializes the OpenAI client using the API key loaded from the environment.
        """
        self.client = OpenAI(api_key=OPENAI_API_KEY)

    def generate_attendance_trends(self, student_id):
        """
        Generates a bar chart showing attendance over time for a student.

        Parameters:
            student_id (str): The student’s enrollment ID.

        Returns:
            str: HTML <img> tag linking to the saved chart.
        """
        with sqlite3.connect(DATABASE_PATH) as conn:
            df = pd.read_sql_query("""
                SELECT date, status FROM attendance WHERE enrollment = ?
            """, conn, params=(student_id,))

        if df.empty:
            return "❌ No attendance data available."

        df['date'] = pd.to_datetime(df['date'])
        df.sort_values(by='date', inplace=True)

        # Count number of Present/Absent sessions per date
        attendance_counts = df.groupby(['date', 'status']).size().unstack(fill_value=0)

        plt.figure(figsize=(8, 4))
        attendance_counts.plot(kind='bar', stacked=True, colormap='coolwarm')
        plt.title(f"📊 Attendance Trend for Student {student_id}")
        plt.xlabel("Date")
        plt.ylabel("Number of Sessions")
        plt.legend(["Absent", "Present"])

        image_path = f"static/attendance_trend_{student_id}.png"
        plt.savefig(image_path, bbox_inches='tight')
        plt.close()

        return f"<img src='/{image_path}' width='500'>"

    def check_attendance_risk(self, student_id, class_id, threshold=70):
        """
        Checks whether the student is at risk of failing due to low attendance.

        Parameters:
            student_id (str): Student’s ID.
            class_id (int): Class ID to check.
            threshold (int): Risk threshold (%), default is 70.

        Returns:
            str: Risk assessment message.
        """
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT status FROM attendance
                WHERE enrollment = ? AND class_id = ?;
            """, (student_id, class_id))
            records = cursor.fetchall()

        if not records:
            return "❌ No attendance records found for this class."

        total_sessions = len(records)
        absences = sum(1 for r in records if r[0] == 'Absent')
        attended = total_sessions - absences
        current_percentage = (attended / total_sessions) * 100

        # Predict impact of 2 more absences
        projected_total = total_sessions + 2
        projected_attended = attended
        projected_percentage = (projected_attended / projected_total) * 100

        if current_percentage < threshold:
            return f"⚠️ Your current attendance is **{current_percentage:.1f}%**, which is below the required {threshold}%."

        elif projected_percentage < threshold:
            return (
                f"⚠️ You're currently at **{current_percentage:.1f}%**. "
                f"If you miss 2 more classes, it will drop to **{projected_percentage:.1f}%**, "
                f"which is below the {threshold}% threshold."
            )

        return f"✅ You're at **{current_percentage:.1f}%** attendance. Keep it up!"

    def generate_attendance_report(self, class_id, class_name="This class"):
        """
        Generates a class attendance table and a GPT summary.

        Parameters:
            class_id (int): The class ID.
            class_name (str): The name of the class (optional).

        Returns:
            tuple: (pandas.DataFrame, str) — Table and HTML summary
        """
        with sqlite3.connect(DATABASE_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.enrollment, s.name, a.status, a.date
                FROM attendance a
                JOIN students s ON a.enrollment = s.enrollment
                WHERE a.class_id = ?
                ORDER BY s.enrollment, a.date;
            """, (class_id,))
            records = cursor.fetchall()

        df = pd.DataFrame(records, columns=["Enrollment", "Student Name", "Status", "Date"])
        if df.empty:
            return None, "No attendance records found for this class."

        summary = df.groupby(["Enrollment", "Student Name"])["Status"] \
                    .apply(lambda x: (x == "Absent").sum()).reset_index()
        summary.columns = ["Enrollment", "Student Name", "Total Absences"]

        total_classes = df["Date"].nunique()
        summary["Attendance %"] = ((total_classes - summary["Total Absences"]) / total_classes) * 100

        gpt_summary = self.summarize_class_report(class_name, summary)
        return summary, gpt_summary

    def summarize_class_report(self, class_name, report_df):
        """
        Uses GPT to summarize attendance report with HTML styling for low performers.

        Parameters:
            class_name (str): Name of the class.
            report_df (DataFrame): Table with attendance stats.

        Returns:
            str: GPT-generated HTML summary.
        """
        if report_df.empty:
            return "No data to summarize."

        report_df = report_df.copy()
        report_df["Attendance %"] = report_df["Attendance %"].round(1)

        # Highlight students with ≤70% attendance in red
        report_df["Student Name"] = report_df.apply(
            lambda row: f"<span style='color: red'>{row['Student Name']}</span>"
            if row["Attendance %"] <= 70 else row["Student Name"],
            axis=1
        )

        table_text = report_df.to_string(index=False)

        prompt = f"""
You are an AI academic assistant. A professor is reviewing attendance for their class: {class_name}.
Below is the attendance summary:

{table_text}

Generate a 2–3 sentence HTML summary:
- Mention students with <70% attendance.
- Mention students with 100% attendance.
- Keep span styling as-is.
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful academic assistant."},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            return f"⚠️ Could not generate summary: {str(e)}"

    def generate_classwise_attendance_trend(self, student_id):
        """
        Generates a class-wise stacked bar chart showing student absences.

        Parameters:
            student_id (str): The student’s enrollment ID.

        Returns:
            str: HTML <img> tag pointing to the saved chart.
        """
        with sqlite3.connect(DATABASE_PATH) as conn:
            df = pd.read_sql_query("""
                SELECT a.date, a.status, c.class_name
                FROM attendance a
                JOIN classrooms c ON a.class_id = c.id
                WHERE a.enrollment = ?
            """, conn, params=(student_id,))

        if df.empty:
            return "❌ No attendance data available."

        df['date'] = pd.to_datetime(df['date'])
        df.sort_values(by='date', inplace=True)

        # Only keep absences
        df = df[df['status'] == 'Absent']
        if df.empty:
            return "✅ Great news! No absences recorded for any class."

        grouped = df.groupby(['date', 'class_name']).size().reset_index(name='absences')
        pivot_df = grouped.pivot(index='date', columns='class_name', values='absences').fillna(0)

        if pivot_df.empty:
            return "❌ No numeric attendance data to plot."

        ax = pivot_df.plot(kind='bar', figsize=(10, 5), colormap='tab10')
        plt.title(f"Absences per Class Over Time (Student {student_id})")
        plt.xlabel("Date")
        plt.ylabel("Number of Absences")
        plt.xticks(rotation=45)
        plt.legend(title="Class")
        plt.tight_layout()

        image_path = f"static/attendance_classwise_trend_{student_id}.png"
        plt.savefig(image_path, bbox_inches='tight')
        plt.close()

        return f"<img src='/{image_path}' width='600'>"
