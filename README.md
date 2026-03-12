<div align="center">

# 🧠 AI Job Screening & Talent Intelligence Platform

A full-stack AI-powered career platform with **17 distinct AI features**, built using **React, Flask, Firebase, Redis, MongoDB, Docker**, and integrated with **Cohere/OpenAI LLMs**. It supports both **Job Seekers** (10 tools) and **Recruiters** (4 tools), includes a **Coaching system** with progress tracking, and a **Mock Interview simulator with Speech Recognition**.

[![CI](https://github.com/deepakbajaj12/AI-Job-Screening-Analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/deepakbajaj12/AI-Job-Screening-Analyzer/actions)
[![Python](https://img.shields.io/badge/Python-3.12+-blue)]()
[![Flask](https://img.shields.io/badge/Backend-Flask-green)]()
[![React](https://img.shields.io/badge/Frontend-React_+_TypeScript-61dafb)]()
[![MongoDB](https://img.shields.io/badge/Database-MongoDB-47A248)]()
[![Redis](https://img.shields.io/badge/Queue-Redis_+_Celery-DC382D)]()
[![Docker](https://img.shields.io/badge/Container-Docker-2496ED)]()
[![License](https://img.shields.io/badge/license-MIT-lightgrey)]()

</div>

---

## 📑 Table of Contents

1. [Overview](#1-overview)
2. [Key Features](#2-key-features)
3. [System Architecture](#3-system-architecture)
4. [Tech Stack](#4-tech-stack)
5. [Screenshots & Flows](#5-screenshots--flows)
6. [Complete API Reference (33+ Endpoints)](#6-complete-api-reference-33-endpoints)
7. [AI / ML Capabilities](#7-ai--ml-capabilities)
8. [Environment Variables](#8-environment-variables)
9. [Quick Start](#9-quick-start)
10. [Testing](#10-testing)
11. [Deployment](#11-deployment)
12. [Database & Persistence](#12-database--persistence)
13. [Security](#13-security)
14. [Roadmap](#14-roadmap)
15. [Contributing](#15-contributing)
16. [License](#16-license)

---

## 1. Overview

This platform accelerates candidate screening by extracting structured insight from resumes and job descriptions, scoring semantic fit, surfacing skill gaps, and coaching candidates toward higher match quality.

**For Job Seekers:** 10 AI-powered tools including resume analysis, cover letter generation, mock interviews with speech recognition, salary estimation, career path planning, LinkedIn profile generation, and more.

**For Recruiters:** Automated candidate evaluation with lexical + semantic matching, email generation, job description authoring, and boolean search string generation.

**For Coaching:** Versioned resume tracking with progress charts, skill gap detection, study resource packs, and AI-generated interview preparation.

---

## 2. Key Features

| Area | Capabilities |
|------|-------------|
| **Resume + JD Analysis** | AI-generated strengths, improvements, recommended roles, semantic & lexical matching |
| **Semantic Matching** | TF-IDF + Cosine Similarity scoring (embeddings-ready abstraction) |
| **Cover Letter Generator** | AI-crafted cover letters tailored to specific job descriptions |
| **Mock Interview** | Conversational AI interviewer with **Speech-to-Text** (Web Speech API) and **Text-to-Speech** |
| **Salary Estimator** | Market-based salary range estimation with negotiation tips |
| **Career Path Generator** | Long-term career roadmap with milestones and skills needed |
| **LinkedIn Profile Builder** | AI-generated headline, about section, and experience highlights |
| **Resume Tailor** | Rewrite resume bullets to match specific job description keywords |
| **Resume Health Check** | ATS compatibility scoring, formatting analysis, impact assessment |
| **Skill Gap Analysis** | Missing skills identification with curated learning resources |
| **Coaching System** | Versioned resume metrics, progress charts, diff comparison |
| **Recruiter Email Generator** | Interview invites, rejections, and offer emails |
| **Job Description Generator** | Professional JD authoring from title + skills + experience |
| **Boolean Search Generator** | LinkedIn/Google sourcing boolean search strings |
| **Networking Messages** | LinkedIn connect, cold email, and alumni outreach messages |
| **RBAC & Audit** | Role-based access control + JSONL audit and event logs |
| **History Dashboard** | MongoDB-backed analysis history with per-user tracking |
| **Rate Limiting** | Sliding window protections per user/IP (Redis + in-memory fallback) |

---

## 3. System Architecture

```
┌──────────────────────┐         ┌──────────────────────┐
│    Frontend (React)   │  HTTP   │   Flask Backend API   │
│  Vite + TypeScript    │────────>│   Gunicorn (WSGI)     │
│  Vercel / Static      │<────────│   DigitalOcean / DO   │
└──────────────────────┘         └──────────┬───────────┘
                                            │
                    ┌───────────────────────┼───────────────────────┐
                    │                       │                       │
            ┌───────▼───────┐     ┌─────────▼────────┐   ┌─────────▼─────────┐
            │  LLM Providers │     │   Redis Queue     │   │   MongoDB Atlas   │
            │  Cohere / OpenAI│    │   Celery Worker   │   │   Analysis History │
            │  (AI Features)  │    │   Rate Limiting   │   │   User Data        │
            └────────────────┘    │   LLM Caching     │   └───────────────────┘
                                  └──────────────────┘
                                            │
                                  ┌─────────▼─────────┐
                                  │   Firebase Auth    │
                                  │   Google Sign-In   │
                                  └───────────────────┘
```

**Key Architectural Decisions:**
- **Pluggable LLM:** Unified `call_llm()` supports Cohere and OpenAI via a `provider:model` config string
- **Graceful Degradation:** Works without Redis (sync mode), without MongoDB (JSON files), without Firebase (guest mode)
- **LLM Response Caching:** Redis-backed 24h cache to reduce API costs and latency
- **Synchronous Fallback:** When Redis is unavailable, analysis runs synchronously instead of failing

---

## 4. Tech Stack

| Layer | Technology |
|-------|-----------|
| **Frontend** | React 18, TypeScript, Vite, Chart.js, Web Speech API |
| **Backend** | Python 3.12, Flask, Gunicorn |
| **AI / NLP** | Cohere Chat API, OpenAI API (optional), TF-IDF (scikit-learn), spaCy |
| **Authentication** | Firebase Auth (Google Sign-In) + Firebase Admin SDK |
| **Database** | MongoDB Atlas (analysis history, user data) |
| **Queue** | Redis + Celery (async task processing) |
| **Containerization** | Docker, Docker Compose |
| **CI/CD** | GitHub Actions |
| **Deployment** | DigitalOcean App Platform / Render + Vercel |
| **Monitoring** | Structured JSON logging, Health endpoints, Audit trail |

---

## 5. Screenshots & Flows

### Application Flow

```
Job Seeker Flow:
Upload Resume → AI Analysis → View Strengths/Gaps → Generate Cover Letter
                                                  → Mock Interview (Speech)
                                                  → Salary Estimation
                                                  → Career Path Roadmap
                                                  → LinkedIn Profile
                                                  → Save to History

Recruiter Flow:
Upload Resume + JD → Lexical/Semantic Match → AI Report → Email Candidate
                                                        → Generate JD
                                                        → Boolean Search

Coaching Flow:
Upload Resume → Save Version → View Progress Chart → Study Pack
                                                   → Interview Questions
                                                   → Version Diff
```

### Pages
| Page | Description |
|------|-------------|
| **Home** | Landing page with feature cards and navigation |
| **Job Seeker** | 10 AI tools with drag-and-drop PDF upload |
| **Recruiter** | 4 tools for candidate evaluation and outreach |
| **Coaching** | Version tracking, progress charts, study packs |
| **Mock Interview** | Chat-based AI interviewer with speech recognition |
| **History** | Past analysis results dashboard (MongoDB) |

---

## 6. Complete API Reference (33+ Endpoints)

### Public Endpoints (No Auth Required)

| # | Endpoint | Method | Description |
|---|----------|--------|-------------|
| 1 | `/` | GET | Root — running status and version |
| 2 | `/health` | GET | Liveness check (status, version, time) |
| 3 | `/version` | GET | Current `APP_VERSION` |
| 4 | `/metrics` | GET | Server metrics (uptime, request count, avg latency) |
| 5 | `/internal/sys-info` | GET | Platform, Python version, CPU count |
| 6 | `/internal/process-info` | GET | PID, PPID, thread count |
| 7 | `/internal/network-info` | GET | Hostname, IP address |
| 8 | `/internal/thread-info` | GET | Active thread list |
| 9 | `/internal/gc-info` | GET | Garbage collector stats |
| 10 | `/internal/time-info` | GET | Server time and timezone |

### Core Analysis Endpoints (Auth Required)

| # | Endpoint | Method | Description |
|---|----------|--------|-------------|
| 11 | `/analyze` | POST | Resume analysis (jobSeeker / recruiter mode) — queued or sync |
| 12 | `/status/<job_id>` | GET | Poll async job status (RQ) |
| 13 | `/tasks/<task_id>` | GET | Celery task status polling |
| 14 | `/history` | GET | User's past analysis results (MongoDB) |

### Job Seeker AI Tools (Auth Required)

| # | Endpoint | Method | Description |
|---|----------|--------|-------------|
| 15 | `/generate-cover-letter` | POST | AI-generated cover letter from resume + JD |
| 16 | `/generate-interview-questions` | POST | Tailored interview questions |
| 17 | `/analyze-skills` | POST | Skill gap analysis with learning resources |
| 18 | `/mock-interview` | POST | Conversational AI mock interviewer |
| 19 | `/analyze-mock-interview` | POST | Post-interview performance scoring |
| 20 | `/generate-linkedin-profile` | POST | LinkedIn headline, about, highlights |
| 21 | `/estimate-salary` | POST | Salary range + negotiation tips |
| 22 | `/tailor-resume` | POST | Rewrite resume bullets to match JD |
| 23 | `/generate-career-path` | POST | Career roadmap with milestones |
| 24 | `/resume-health-check` | POST | ATS compatibility and formatting score |
| 25 | `/generate-networking-message` | POST | LinkedIn/email networking messages |

### Recruiter Tools (Auth Required)

| # | Endpoint | Method | Description |
|---|----------|--------|-------------|
| 26 | `/generate-email` | POST | Recruiter email (invite/rejection/offer) |
| 27 | `/generate-job-description` | POST | Professional job description |
| 28 | `/generate-boolean-search` | POST | Boolean search string for sourcing |

### Coaching System (Auth Required)

| # | Endpoint | Method | Description |
|---|----------|--------|-------------|
| 29 | `/coaching/save-version` | POST | Save resume version with metrics |
| 30 | `/coaching/progress` | GET | List all saved resume versions |
| 31 | `/coaching/study-pack` | GET | Skill gaps + curated resources |
| 32 | `/coaching/interview-questions` | GET | Role-tailored interview questions |
| 33 | `/coaching/diff` | GET | Compare two versions (skills + metrics) |

### Admin Endpoints (Admin Role Required)

| # | Endpoint | Method | Description |
|---|----------|--------|-------------|
| 34 | `/admin/audit` | GET | View recent audit log entries |
| 35 | `/admin/set-role` | POST | Assign user/admin role |

### Example: Analyze (Recruiter) Response
```json
{
  "strengths": ["Strong Python background", "ML experience"],
  "improvementAreas": ["Cloud infrastructure", "System design"],
  "recommendedRoles": ["Senior Developer", "ML Engineer"],
  "generalFeedback": "Lexical Match: 62% | Semantic: 71% | Combined: 66.5%...",
  "lexicalMatchPercentage": 62.0,
  "semanticMatchPercentage": 71.0,
  "combinedMatchPercentage": 66.5,
  "formattedReport": "📈 Detailed Candidate Report..."
}
```

---

## 7. AI / ML Capabilities

| # | Feature | Method | Model |
|---|---------|--------|-------|
| 1 | Resume Analysis | LLM + TF-IDF | Cohere / OpenAI |
| 2 | Semantic Matching | TF-IDF + Cosine Similarity | scikit-learn |
| 3 | Lexical Matching | Word set intersection | Pure Python |
| 4 | Skill Detection | Keyword matching vs known skill set | Heuristic (30+ skills) |
| 5 | Resume Section Parsing | Regex-based section extraction | Pure Python |
| 6 | Cover Letter Generation | LLM | Cohere / OpenAI |
| 7 | Interview Question Generation | LLM | Cohere / OpenAI |
| 8 | Mock Interview | Conversational LLM | Cohere / OpenAI |
| 9 | Interview Scoring | LLM Analysis | Cohere / OpenAI |
| 10 | Skill Gap Analysis | LLM + Heuristic | Cohere / OpenAI |
| 11 | LinkedIn Profile Generation | LLM | Cohere / OpenAI |
| 12 | Salary Estimation | LLM | Cohere / OpenAI |
| 13 | Resume Tailoring | LLM | Cohere / OpenAI |
| 14 | Career Path Generation | LLM | Cohere / OpenAI |
| 15 | Resume Health Check | LLM | Cohere / OpenAI |
| 16 | Job Description Generation | LLM | Cohere / OpenAI |
| 17 | Boolean Search Generation | LLM | Cohere / OpenAI |

**LLM Abstraction:** The `call_llm()` function provides a unified interface. Configuration is via `LLM_MODEL` env var (e.g., `cohere:command-r-08-2024` or `openai:gpt-4o`). Includes mock response fallback when API keys are not configured.

---

## 8. Environment Variables

| Key | Purpose | Default |
|-----|---------|---------|
| `APP_VERSION` | Version label | `1.0.0` |
| `DEV_BYPASS_AUTH` | Dev auth bypass (`1`=enabled) | `0` |
| `ALLOWED_ORIGINS` | CORS origins (comma separated) | `*` |
| `FIREBASE_CREDENTIAL_PATH` | Firebase admin JSON path | `backend/firebase-service-account.json` |
| `COHERE_API_KEY` | Cohere API key | — |
| `OPENAI_API_KEY` | OpenAI API key (optional) | — |
| `LLM_MODEL` | Provider:model string | `cohere:command-r-08-2024` |
| `MONGO_URI` | MongoDB Atlas connection string | — |
| `REDIS_URL` | Redis URL for queue/cache | `redis://localhost:6379/0` |
| `CELERY_BROKER_URL` | Celery broker URL | Falls back to `REDIS_URL` |
| `DATA_DIR` | Local data persistence directory | `data` |
| `SMTP_HOST` | Email SMTP host | — |
| `SMTP_PORT` | Email SMTP port | `587` |
| `SMTP_USER` / `SMTP_PASS` | Email credentials | — |
| `WEBHOOK_URL` | Outbound event webhook | — |

**Never commit real keys.** Use `.env` (gitignored).

---

## 9. Quick Start

### Backend (Local)
```bash
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -r backend/requirements.txt
cp .env.example .env          # Edit with your API keys
python run.py
```

### Frontend (Local)
```bash
cd frontend
npm install
npm run dev
```

### Docker Compose (Full Stack)
```bash
docker compose up --build
```
This starts: Backend (port 5000), Frontend (port 5173), Redis (port 6379), Celery Worker.

### Sample cURL (Job Seeker Mode)
```bash
curl -X POST http://localhost:5000/analyze \
  -H "Authorization: Bearer <FIREBASE_ID_TOKEN>" \
  -F mode=jobSeeker \
  -F resume=@sample_resume.pdf \
  -F jobDescription="Backend engineer building scalable services"
```

---

## 10. Testing

```bash
# Run all tests (56 tests)
pytest tests/ -v

# Run only core feature tests (48 tests)
pytest tests/test_core_features.py -v

# Run health endpoint tests (8 tests)
pytest tests/test_health_and_version.py -v
```

**Test Coverage:**
- Health & system endpoints (10 tests)
- Authentication & security headers (4 tests)
- Resume parsing & skill detection (5 tests)
- Semantic matching (3 tests)
- Analysis endpoint (4 tests)
- Cover letter generation (2 tests)
- Mock interview (3 tests)
- Coaching endpoints (4 tests)
- Utility functions (6 tests)
- Recruiter features (2 tests)
- History/Dashboard (2 tests)
- MongoDB integration (3 tests)

---

## 11. Deployment

### DigitalOcean App Platform
The repository includes `app.yaml` for one-click deployment:
```bash
# Push to GitHub, then import in DigitalOcean App Platform
# The app.yaml configures: backend, worker, and Redis database
```

### Render
```bash
# render.yaml is also included for Render deployment
```

### Vercel (Frontend)
```bash
cd frontend
npm run build
# Deploy dist/ to Vercel
# Set VITE_API_BASE_URL to your backend URL
```

---

## 12. Database & Persistence

| Storage | Purpose | Location |
|---------|---------|----------|
| **MongoDB Atlas** | Analysis history, user data | Cloud (MONGO_URI) |
| **Redis** | Task queue, LLM cache, rate limiting | Cloud or local |
| **JSON Files** | Coaching versions, audit logs, roles | `data/` directory |

| File Path | Contents |
|-----------|----------|
| `data/coaching/resume_versions.json` | Per-user resume version arrays |
| `data/audit/audit.jsonl` | Line-delimited audit entries |
| `data/audit/events.jsonl` | Emitted events (analysis, version saved) |
| `data/roles.json` | RBAC role registry (admin/user) |

---

## 13. Security

- **Firebase Auth** — Token validation with Google Sign-In
- **RBAC** — Role-based access control for admin endpoints
- **Rate Limiting** — Sliding window per user/IP (Redis + in-memory fallback)
- **Security Headers** — CSP, HSTS, Referrer-Policy, Permissions-Policy, X-Content-Type-Options
- **CORS** — Configurable allowed origins via `ALLOWED_ORIGINS`
- **Request Tracing** — X-Request-ID propagation for debugging
- **Audit Logging** — JSONL audit trail for all sensitive actions
- **Graceful Auth Degradation** — Guest mode configurable via `DEV_BYPASS_AUTH`

---

## 14. Roadmap

| Phase | Status | Highlights |
|-------|--------|-----------|
| 1 | ✅ Done | Core analysis, coaching, mock interview |
| 2 | ✅ Done | 17 AI features, Docker, CI/CD |
| 3 | ✅ Done | MongoDB integration, 56 tests, Auth system |
| 4 | 🔜 Next | Vector embeddings (FAISS/Pinecone) |
| 5 | 🔜 Next | Multi-tenant org isolation |
| 6 | 🔜 Next | Full observability (OpenTelemetry) |
| 7 | 🔜 Next | ATS connectors, bias diagnostics |

---

## 15. Contributing

1. Fork & clone
2. Create feature branch: `git checkout -b feat/your-feature`
3. Write tests for new logic
4. Run `pytest tests/ -v`
5. Submit PR with clear description

---

## 16. License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
  <b>Built by Deepak Bajaj</b><br>
  <i>8th Semester Major Project — AI-Powered Career Intelligence Platform</i>
</div>

