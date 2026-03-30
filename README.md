#  Nexus-AI — Multi-Agent Attendance Management System

> **Senior thesis project** — an AI-powered attendance platform that combines facial recognition, autonomous agents, and natural language processing to modernize attendance tracking in educational settings.

![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat-square&logo=flask)
![OpenCV](https://img.shields.io/badge/OpenCV-4.9-5C3EE8?style=flat-square&logo=opencv)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--3.5-412991?style=flat-square&logo=openai)
![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=flat-square&logo=sqlite)

---

##  What is Nexus-AI?

Attendance tracking in universities is manual, time-consuming, and error-prone. Nexus-AI replaces that process with an intelligent multi-agent system that handles identity verification, absence detection, trend prediction, and natural language reporting — all while keeping humans in control.

**Nothing is triggered without user interaction.** Every AI decision is user-initiated, preserving privacy and accountability.

---

##  System Architecture
```
┌─────────────────────────────────────────────────────────────┐
│                      Web Interface                           │
│         Student │ Professor │ Admin Dashboards               │
│    HTML, CSS, JavaScript, Bootstrap, GSAP                    │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  Flask Backend (app.py)                      │
│         Routes, session management, auth, API calls          │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│               Agent Coordinator (coordinator.py)             │
│    Central hub — classifies intent, routes to correct agent  │
└──────┬──────────┬──────────┬───────────┬────────────────────┘
       │          │          │           │
       ▼          ▼          ▼           ▼
┌──────────┐ ┌─────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐
│  Alert   │ │Insights │ │Predict │ │  Query   │ │Retrieval │
│  Agent   │ │  Agent  │ │ Agent  │ │  Agent   │ │  Agent   │
└──────────┘ └─────────┘ └────────┘ └──────────┘ └──────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                Facial Recognition Layer                      │
│         OpenCV + Euclidean distance-based matching           │
└─────────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                    SQLite Database                           │
│         users │ attendance │ messages │ courses              │
└─────────────────────────────────────────────────────────────┘
```

---

##  Multi-Agent System Design

The core intelligence of Nexus-AI is a modular multi-agent architecture. Each agent has a single responsibility and is only invoked when needed — making the system modular, testable, and easy to extend.

### Agent Coordinator
The `AgentCoordinator` is the communication hub between the dashboard and all agents. It classifies user intent from natural language input and routes the request to the correct agent.
```python
coordinator = AgentCoordinator()
response = coordinator.handle(user_input, student_id, course_id)
```

### Specialized Agents

| Agent | Responsibility |
|-------|---------------|
| `alert_agent.py` | Sends alerts to professors when absences exceed a threshold |
| `insights_agent.py` | Generates attendance summaries and graphs using GPT-3.5 |
| `prediction_agent.py` | Predicts likelihood of future absences from historical data |
| `query_agent.py` | Classifies intent, extracts keywords, routes to correct module |
| `retrieval_agent.py` | Retrieves current absence counts per student per course |
| `coordinator.py` | Central router — orchestrates all agent communication |

---

##  Features

###  Admin Dashboard
- Assign professors to classrooms
- View system activity logs
- Create, edit, and delete users and courses
- Export full attendance reports as CSV

###  Professor Dashboard
- Start and stop live facial recognition attendance sessions
- View and filter attendance records
- Handle student absence messages (manual or AI-assisted replies)
- Generate GPT-powered attendance insights and trend reports

###  Student Dashboard
- Log in via **facial recognition** or password
- Submit absence justifications with messaging
- Chat with an AI agent about attendance
- Monitor personal attendance records
- Receive automated warnings after repeated absences

---

##  Facial Recognition Pipeline
```
Camera feed (OpenCV)
        │
        ▼
Frame capture + preprocessing
        │
        ▼
Face detection (Haar cascade / HOG)
        │
        ▼
Feature vector extraction
        │
        ▼
Euclidean distance matching against enrolled faces
        │
        ▼
Identity confirmed → attendance record created
```

Euclidean distance matching was chosen over deep learning embeddings to keep the system lightweight and deployable without GPU infrastructure, while still achieving reliable identity verification for classroom-scale use.

---

##  Key Engineering Decisions

**Why a multi-agent architecture?**
A monolithic approach would tightly couple attendance tracking, prediction, alerting, and NLP into one unmanageable script. The agent pattern gives each concern its own module — making the system easier to debug, test, and extend independently.

**Why user-triggered AI?**
Full automation raises privacy concerns in educational settings. Every AI action (insights, alerts, predictions) requires explicit user initiation — keeping professors and admins in control of when the system acts.

**Why Euclidean distance for facial recognition?**
Deep learning embeddings (FaceNet, ArcFace) require GPU infrastructure and large labeled datasets. Euclidean distance on OpenCV feature vectors achieves reliable matching at classroom scale with zero hardware requirements.

**Why SQLite?**
For a single-institution deployment, SQLite provides zero-configuration persistence with full SQL expressiveness. The schema is designed for easy migration to PostgreSQL for multi-institution scaling.

---

##  Project Structure
```
nexus-ai/
├── app.py                  # Flask entry point, all routes
├── agents/
│   ├── coordinator.py      # Intent classification and routing
│   ├── alert_agent.py      # Absence threshold alerts
│   ├── insights_agent.py   # GPT-powered attendance summaries
│   ├── prediction_agent.py # Future absence likelihood
│   ├── query_agent.py      # NLP intent + keyword extraction
│   └── retrieval_agent.py  # Absence count lookups
├── facial_recognition/
│   └── recognition.py      # OpenCV pipeline
├── templates/              # HTML dashboards (student, professor, admin)
├── static/                 # CSS, JS, GSAP animations
├── database/
│   └── nexus.db            # SQLite database
└── requirements.txt
```

---

##  Quick Start
```bash
# 1. Clone the repository
git clone https://github.com/boumalaksiham/nexus-ai-attendance.git
cd nexus-ai-attendance

# 2. Set up virtual environment
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your OpenAI API key
echo "OPENAI_API_KEY=your_key_here" > .env

# 5. Run the app
python app.py
```

Open **http://127.0.0.1:5000** in your browser.

---

##  Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML, CSS, JavaScript, Bootstrap, GSAP |
| Backend | Python, Flask |
| Database | SQLite |
| Facial Recognition | OpenCV, Euclidean distance matching |
| AI / NLP | GPT-3.5 (OpenAI API), scikit-learn |
| Auth | bcrypt password hashing |
| Other | pandas, uuid, threading, python-dotenv |

---

##  Roadmap

- [ ] Upgrade facial recognition to deep learning embeddings (FaceNet)
- [ ] Migrate to PostgreSQL for multi-institution support
- [ ] Real-time WebSocket attendance updates
- [ ] Mobile app for student check-in
- [ ] Export reports as PDF with embedded charts
- [ ] Role-based access control with JWT

---

##  Author

**Siham Boumalak**
B.A. Computer Science & Data Science — The College of Wooster
M.S. Artificial Intelligence — Northeastern University, Khoury College | Expected 2027

*This project was completed as a senior undergraduate thesis.*

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0077B5?style=flat-square&logo=linkedin)](linkedin.com/in/siham-boumalak-11014b210)
[![GitHub](https://img.shields.io/badge/GitHub-boumalaksiham-181717?style=flat-square&logo=github)](https://github.com/boumalaksiham)
