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

The published source is **incomplete and does not currently provide a clean runnable release**:

| Blocker | Evidence / action |
|---|---|
| Missing training module | `app.py` imports `train_model`, but that module is absent. Restore the original source. |
| Circular initialization | `app.py` imports `socketio` from itself before creating it. Resolve initialization before launch. |
| Incomplete environment | Imports include `face_recognition`, `flask_socketio`, `openai`, `dotenv` and `matplotlib`, which are absent from the root dependency list. Restore and verify the original environment. |
| Enrollment/model artifacts | Use authorized enrollment data and the original training workflow; do not assume an empty checkout includes usable face encodings. |

The setup below identifies intended entry points, rather than promising that these blockers are solved.

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

Use the thesis Python 3.12 environment as a starting point, then restore the missing dependencies/module and resolve initialization. dlib/face-recognition installation may require native build tools. OpenAI-dependent code also needs a compatible SDK and `OPENAI_API_KEY`; the repository does not pin a verified SDK version.

After restoration, the application entry point is `python app.py`. Database schema source is [database.py](database.py). Read it and the application initialization paths before creating tables; this README does not assume that a preexisting thesis database is available.

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

Treat this as research source until restoration and testing are complete. Before exposing a deployment, review the hardcoded session secret, debug configuration, permissive CORS, authentication paths and credential-related logging. Biometric enrollment and attendance records require appropriate handling; user initiation alone does not demonstrate privacy protection.

## Next steps

Restore source and environment; verify database initialization; test dashboard and recognition flows with consented test data; add reproducible evaluation artifacts and appropriate tests. Documentation improvements do not repair the absent implementation.
