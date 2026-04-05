# Project Files - Quick Feature Reference

## Backend Files (Python)

| File | Feature |
|------|---------|
| `backend/app.py` | **MAIN APPLICATION**: Flask server with 30+ endpoints for AI-powered resume analysis, recruiter tools, and coaching |
| `backend/mongo_db.py` | **DATABASE LAYER**: MongoDB integration for persisting user analysis history and coaching version data |
| `backend/pdf_generator.py` | **PDF REPORT GENERATION**: Creates professional formatted PDFs for all reports using ReportLab |
| `backend/worker_tasks.py` | **ASYNC TASK WORKER**: Processes resume analysis jobs in background queue with user association |
| `backend/queue_config.py` | **BACKGROUND JOB QUEUE**: Redis-based task queue (RQ) for handling long-running analysis jobs |
| `backend/config.py` | **CONFIGURATION**: Environment setup, logging configuration, and directory initialization |
| `backend/requirements.txt` | **PYTHON DEPENDENCIES**: Flask, MongoDB, Redis, Celery, Cohere/OpenAI APIs, PDFPlumber, Spacy NLP, Firebase |

## Frontend Files (React + TypeScript)

| File | Feature |
|------|---------|
| `frontend/src/main.tsx` | **ENTRY POINT**: React 18 application initialization with Router setup |
| `frontend/src/App.tsx` | **MAIN ROUTER**: Navigation between Job Seeker, Recruiter, Coaching, History with Firebase auth |
| `frontend/src/api/client.ts` | **API CLIENT**: Centralized HTTP client with retry logic and all endpoints |
| `frontend/src/context/AuthContext.tsx` | **AUTHENTICATION CONTEXT**: Firebase state management accessible across all components |
| `frontend/src/pages/JobSeeker.tsx` | **JOB SEEKER PAGE**: Multiple AI tools - resume matching, cover letter, interview prep, salary estimation |
| `frontend/src/pages/Recruiter.tsx` | **RECRUITER PAGE**: Shortlist dashboard, decision reasoning, evidence, risk flags, email/JD assistant |
| `frontend/src/pages/Coaching.tsx` | **COACHING DASHBOARD**: Version tracking, progress metrics, skill gaps, study pack, interview prep |
| `frontend/src/pages/History.tsx` | **HISTORY PAGE**: All past analyses sorted by date with match scores and improvement areas |
| `frontend/src/components/DragAndDropUpload.tsx` | **DRAG-DROP UPLOAD**: Reusable component for PDF uploads with drag-and-drop UI |
| `frontend/src/components/MetricsChart.tsx` | **PROGRESS VISUALIZATION**: Renders coaching metrics over versions using Chart.js |
| `frontend/src/components/HealthBadge.tsx` | **HEALTH STATUS**: Displays API health and system version in navbar |
| `frontend/src/components/NavBar.tsx` | **NAVIGATION**: Top navigation bar with user authentication and menu |
| `frontend/src/components/Footer.tsx` | **FOOTER**: Bottom section with legal links and branding |

## Configuration Files

| File | Feature |
|------|---------|
| `frontend/vite.config.ts` | **VITE BUILD CONFIG**: Frontend bundler with React plugin and production optimization |
| `frontend/tsconfig.json` | **TYPESCRIPT CONFIG**: Type checking for React 18 with JSX and strict null checks |
| `frontend/package.json` | **NPM DEPENDENCIES**: React, TypeScript, Firebase, Chart.js, API clients |
| `pytest.ini` | **TEST CONFIG**: Python pytest configuration for running backend tests |

## Docker & Deployment

| File | Feature |
|------|---------|
| `Dockerfile` | **CONTAINERIZATION**: Docker image for backend with Python 3.12 and Flask server |
| `docker-compose.yml` | **ORCHESTRATION**: Docker Compose setup for backend, MongoDB, and Redis services |
| `render.yaml` | **RENDER DEPLOYMENT**: Configuration for deploying backend on Render cloud platform |
| `app.yaml` | **APP CONFIGURATION**: Flask app configuration and settings |
| `wsgi.py` | **WSGI SERVER**: WSGI application entry point for production deployment |

## Root Scripts

| File | Feature |
|------|---------|
| `run.py` | **DEVELOPMENT SERVER**: Runs Flask backend locally during development |
| `run_worker.py` | **BACKGROUND WORKER**: Starts the Redis/RQ worker for async job processing |
| `conftest.py` | **PYTEST SETUP**: Shared pytest configuration and fixtures for testing |

## Data & Storage

| File | Feature |
|------|---------|
| `data/roles.json` | **JOB ROLES DATA**: Catalog of job titles for scoring and recommendations |
| `data/audit/audit.jsonl` | **AUDIT LOG**: User activity logged for security and monitoring |
| `data/audit/events.jsonl` | **EVENT LOG**: System events and analysis completion records |
| `data/coaching/resume_versions.json` | **COACHING VERSIONS**: User resume versions and coaching progress data |

---

## 🎯 Key Technologies Summary

- **Frontend**: React 18, TypeScript, Vite, Firebase Auth
- **Backend**: Python, Flask, MongoDB, Redis, Celery
- **AI/ML**: Cohere API, OpenAI API, Spacy NLP, scikit-learn (TF-IDF)
- **Deployment**: Docker, Render (backend), Vercel (frontend)
- **Reports**: ReportLab for PDF generation
- **Testing**: Pytest, Chart.js for visualization

---

## 📍 Quick Reference for Presentation

When asked about a file:
1. **Find the file name** from the table above
2. **Read the feature description** - it's a single line that explains what the file does
3. **Mention the technology** used in that file

**Example Response:**
- **Q: What does `backend/app.py` do?**
- **A:** "This is the main Flask application server that handles all 30+ API endpoints for resume analysis, recruiter tools, and coaching features. It orchestrates requests from the frontend to MongoDB, Redis, and AI APIs."
