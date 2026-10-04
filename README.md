# Nexus-AI — Smart Attendance and Conversational Support

An undergraduate honors-thesis prototype combining face recognition, attendance records, and specialized conversational agents. Flask serves student, professor and administrator interfaces; SQLite stores application records.

## Research question and thesis scope

Can face-based attendance capture and conversational access to attendance records be combined in one classroom prototype, and where does the recognition workflow fail?

The project connects three concerns: identifying an enrolled student, storing attendance, and answering questions about those records. A successful conversational answer cannot compensate for a mistaken recognition event; each part needs its own evaluation.

The undergraduate thesis study involved **15 participants** and examined recognition under changing capture conditions. The public repository preserves application and agent source, but the study and a clean runnable release are different deliverables. The restoration requirements below describe the current checkout.

## What is included

- Flask application routes and HTML/CSS/JavaScript dashboards.
- Face-recognition source using OpenCV and dlib-based encodings.
- Agent modules for query handling, retrieval, alerts, prediction and insights.
- SQLite database initialization source.

## Current release status

The application source now has one definition per route endpoint, no circular `socketio` import, and no missing `train_model` import. Live recognition loads class-specific embeddings from SQLite, with each vector mapped directly to its owner rather than assuming 20 captures per person. Enrollment already stores pretrained face embeddings directly; it does not require training another classifier. The student password-change route checks bcrypt hashes and stores a new hash. Session secrets are configurable, SocketIO uses its default same-origin policy, and debug mode is opt-in.

The dependency manifest now includes the imported face-recognition, SocketIO, OpenAI, dotenv, matplotlib, and bcrypt packages. Database setup includes the `students.professor_id` field used by enrollment and adds it non-destructively to older databases.

**Verification scope:** public-page startup and password-change regression tests use a stub for the native face-recognition import and a temporary SQLite database. They do not exercise camera capture, real biometric matching, or provider API calls. Other dashboard/message schema paths and live workflows still need integration testing before a clean runnable release can be claimed.

## Recognition and agent design

Faces are represented by 128-dimensional embeddings. Matching compares Euclidean distance between enrolled and observed embeddings; distance matching is **performed on learned embeddings**, not an alternative to using them. The thesis used a 0.6 threshold, which must be validated for any new capture conditions.

| Module | Responsibility |
|---|---|
| [agents/query_agent.py](agents/query_agent.py) | Interpret attendance questions |
| [agents/retrieval_agent.py](agents/retrieval_agent.py) | Retrieve attendance information |
| [agents/alert_agent.py](agents/alert_agent.py) | Repeated-absence alerts |
| [agents/prediction_agent.py](agents/prediction_agent.py) | Attendance prediction logic |
| [agents/insights_agent.py](agents/insights_agent.py) | Attendance summaries and insights |
| [agents/coordinator.py](agents/coordinator.py) | Route requests among components |

## Setup and restoration

```bash
git clone https://github.com/boumalaksiham/Nexus-AI-Attendance.git
cd Nexus-AI-Attendance
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Use Python 3.12 as a starting point and install the updated manifest. dlib/face-recognition installation may require native build tools. OpenAI-dependent code also needs a compatible SDK and `OPENAI_API_KEY`; the repository does not pin a verified SDK version.

Set `OPENAI_API_KEY` for the agent clients and a persistent `FLASK_SECRET_KEY` for local sessions. The application entry point is `python app.py`; `FLASK_DEBUG=1` enables development debug mode. Database schema source is [database.py](database.py). Read it and the application initialization paths before creating tables; this README does not assume that a preexisting thesis database is available.

## Repository map

| Path | Contents |
|---|---|
| [app.py](app.py) | Flask application and supporting logic |
| [database.py](database.py) | Database setup source |
| [recognize_student_face.py](recognize_student_face.py) | Recognition workflow |
| [agents/](agents/) | Conversational/attendance components |
| [templates/](templates/) | Dashboard and authentication templates |
| [static/](static/) | Styles, scripts and images |

## Evaluation and limitations

The thesis study involved 15 participants. Recognition was sensitive to lighting, distance, angle and masks; it does not establish reliability across other classrooms or populations. A new evaluation should report capture conditions, counts, false accepts/rejects, attendance errors and failure cases separately. Prediction performance and face recognition are different tasks and should not share a single accuracy claim.

Treat this as research source until restoration and testing are complete. Before exposing a deployment, review authentication, authorization, database schema coverage, and remaining account-data logging. Biometric enrollment and attendance records require appropriate handling; user initiation alone does not demonstrate privacy protection.

## Next steps

Test every dashboard/message schema path, camera enrollment, and recognition flow with consented test data. Add reproducible study artifacts and evaluate provider-dependent agent behavior separately from recognition.

## Regression checks

```bash
python -m unittest discover -s tests -v
```

The checks use temporary records, verify a rejected old password leaves its hash unchanged, and verify a successful change stores a bcrypt hash. Embedding ownership is checked with unequal capture counts. Enrollment coverage is labeled separately from biometric accuracy. No cameras or billable provider requests are used.
