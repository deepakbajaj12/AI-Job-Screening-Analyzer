<div align="center">

# 🧠 AI Job Screening & Talent Intelligence Platform

Smart, explainable, and extensible AI-powered resume + job description analysis with coaching, semantic matching, interview readiness, and recruiter automation.

[![Status](https://img.shields.io/badge/status-active-success)]() [![Python](https://img.shields.io/badge/Python-3.12+-blue)]() [![Flask](https://img.shields.io/badge/Backend-Flask-green)]() [![React](https://img.shields.io/badge/Frontend-React-61dafb)]() [![License](https://img.shields.io/badge/license-MIT-lightgrey)]()  

</div>


## 📑 Table of Contents
1. Overview  
2. Core Features  
3. Architecture  
4. Tech Stack  
5. Screens & Flows (Concept)  
6. Backend API  
7. Environment Variables  
8. Quick Start  
9. Development & Testing  
10. Data & Persistence  
11. Security & RBAC  
12. Roadmap  
13. Contributing  
14. License & Credits  

---

## 1. Overview
This platform accelerates candidate screening by extracting structured insight from resumes & job descriptions, scoring semantic fit, surfacing skill gaps, and coaching candidates toward higher match quality. Recruiters gain automated evaluation, version history, and auditability; candidates get personalized improvement pathways and interview prep.

---

## 2. Core Features
| Area | Capabilities |
|------|--------------|
| Resume + JD Analysis | AI-generated strengths, improvements, recommended roles, semantic & lexical matching |
| Semantic Matching | TF‑IDF + cosine overlay (embeddings-ready abstraction) |
| Coaching | Versioned resume metrics, skill gap detection, study resource packs |
| Diff Intelligence | Compare any two versions: added/removed skills, metric deltas |
| Interview Prep | Role-tailored question generation via unified LLM interface |
| Structured Parsing | Heuristic section extraction (skills, experience, projects, etc.) |
| RBAC & Audit | Role-based access + JSONL audit and event logs |
| Event System | Email + webhook dispatch on analyses and version saves |
| Rate Limiting | Sliding window protections per user/IP |
| Health & Observability | /health, /version endpoints; JSON structured logging |
| Dev Mode | Token bypass for rapid local iteration (`DEV_BYPASS_AUTH=1`) |

---

## 3. High-Level Architecture
```
┌─────────────┐       ┌────────────────┐        ┌─────────────────────┐
│  Frontend   │  -->  │  Flask Backend │  -->   │  LLM Providers       │
│ (React)     │       │  (REST API)    │        │ (Cohere / OpenAI)    │
└─────┬───────┘       ├────────────────┤        └─────────┬───────────┘
		│               │ Resume Parsing │                  │
		│               │ Semantic Match │ <─────────┐      │
		│               │ Coaching Store │            │      │
		│               │ Audit + Events │            │      │
		│               └──────┬─────────┘            │      │
		│                      │                      │      │
		│            JSONL Persistence (data/) <───────┘      │
		│                                                     │
		└───────── API Calls / Auth (Firebase) ───────────────┘
```

Pluggable design: current semantic layer uses TF‑IDF; can be upgraded to vector DB (FAISS/Pinecone/Qdrant) without changing clients.

---

## 4. Tech Stack
| Layer | Tools |
|-------|-------|
| Frontend | React, Tailwind CSS (planned integration) |
| Backend | Flask, Python 3.12 |
| AI / NLP | Cohere Chat, OpenAI (optional), spaCy model, TF‑IDF (scikit-learn) |
| Auth | Firebase Auth (client) + Firebase Admin (server) |
| Data Store | JSON files (audit, versions, roles) – upgrade path: Postgres / MongoDB / Vector DB |
| Email / Events | SMTP, Webhook POST |
| Testing | pytest |

---

## 5. Screens & Functional Flows (Conceptual)
Candidate Dashboard:
- Upload resume → get analysis → save version → view progress chart → request interview questions.
Recruiter View:
- Upload JD + resume → receive lexical, semantic, combined match + structured report.
Admin Console:
- Assign roles, view audits, monitor health.

---

## 6. Backend API (Current)
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| /analyze | POST | Yes | Analyze resume (jobSeeker / recruiter modes) |
| /coaching/save-version | POST | Yes | Persist resume version + metrics |
| /coaching/progress | GET | Yes | List stored versions |
| /coaching/diff | GET | Yes | Compare two versions (metrics & skills) |
| /coaching/study-pack | GET | Yes | Skill gaps + resources |
| /coaching/interview-questions | GET | Yes | LLM questions (targetRole param) |
| /admin/audit | GET | Admin | Recent audit entries (tail) |
| /admin/set-role | POST | Admin | Assign role to userId |
| /health | GET | No | Liveness JSON |
| /version | GET | No | Current backend version |
| /metrics | GET | No | Simple server metrics (uptime, counters, avg latency) |

### Analyze (Recruiter) Response (Fields)
```
{
  strengths: [],
  improvementAreas: [],
  recommendedRoles: [],
  generalFeedback: "Lexical Match: 62% | Semantic: 71% | Combined: 66.5% ...",
  lexicalMatchPercentage: 62.0,
  semanticMatchPercentage: 71.0,
  combinedMatchPercentage: 66.5,
  formattedReport: "..."
}
```

### Diff Endpoint Example
```
GET /coaching/diff?prev=1&curr=3
{
  "prevVersion": 1,
  "currVersion": 3,
  "addedSkills": ["docker"],
  "removedSkills": ["excel"],
  "metricDeltas": {"wordCount": 120, "skillCoverageRatio": 0.18},
  "currMetrics": {...},
  "prevMetrics": {...}
}
```

---

## 7. Environment Variables
Reference: `.env.example`.

| Key | Purpose | Default |
|-----|---------|---------|
| APP_VERSION | Version label surfaced at /version | 0.4.0 |
| FIREBASE_CREDENTIAL_PATH | Firebase admin service JSON | firebase-service-account.json |
| COHERE_API_KEY | Cohere chat model key | — |
| OPENAI_API_KEY | OpenAI key (optional) | — |
| LLM_MODEL | Provider:model (e.g. cohere:command-light-nightly) | cohere:command-light-nightly |
| DATA_DIR | Persistence root | data |
| DEV_BYPASS_AUTH | Local auth bypass (1=enabled) | 0 |
| SMTP_HOST/PORT/USER/PASS | Email sending | — |
| EMAIL_FROM | Sender address | no-reply@example.com |
| WEBHOOK_URL | Outbound event POST target | — |

NEVER commit real keys—use `.env` (gitignored).

---

## 8. Quick Start
### Backend
```bash
python -m venv venv
venv/Scripts/activate  # Windows PowerShell
pip install -r Backend_old/requirements.txt
copy .env.example .env  # then edit .env
python run.py
```
Or via Docker Compose:
```powershell
docker compose up --build
```

### Sample cURL (Job Seeker Mode)
```bash
curl -X POST http://localhost:5000/analyze \
  -H "Authorization: Bearer <FIREBASE_ID_TOKEN>" \
  -F mode=jobSeeker \
  -F resume=@sample_resume.pdf \
  -F jobDescription="Backend engineer building scalable services"
```

### Frontend (if present)
```bash
cd frontend
npm install
npm start
```

### Frontend (New)
- Vite + React + TypeScript app scaffolded under `frontend/`

Run locally:
```powershell
cd frontend
npm install
copy .env.example .env   # set VITE_API_BASE_URL and optional Firebase keys
npm run dev
```

Build for production:
```powershell
cd frontend
npm run build
```

Environment vars (`frontend/.env`):
- `VITE_API_BASE_URL` (default `http://localhost:5000`)
- Optional Firebase Auth: `VITE_FIREBASE_API_KEY`, `VITE_FIREBASE_AUTH_DOMAIN`, `VITE_FIREBASE_PROJECT_ID`, `VITE_FIREBASE_APP_ID`
 - Dev bypass (no Firebase): `VITE_DEV_BYPASS=1` enables a dummy token so protected endpoints can be tested locally.
 - CORS: set backend `ALLOWED_ORIGINS` (comma separated) in `.env` for production

Key Screens:
- Job Seeker: upload resume PDF + optional job description text → `/analyze` (jobSeeker)
- Recruiter: upload resume + JD PDFs + recruiter email → `/analyze` (recruiter)
- Health badge in navbar calls `/health` and `/version`
 - Coaching: save versions, view progress & study pack, fetch interview questions, and compute diffs
 - Coaching UX enhancements:
   - Study Pack: debounced search across skills/hosts/tags; copy link buttons
   - Metrics Chart: checkboxes to show/hide datasets (Word Count, Skill Coverage)

---

## 9. Development & Testing
Run base tests:
```bash
pytest -q
```
Add more integration tests under `tests/` (auth-protected tests can set `DEV_BYPASS_AUTH=1`).
Frontend lint/format:
```powershell
cd frontend
npm run lint
npm run format
```


Suggested future test areas:
- Mock pdfplumber for controlled resume extraction.
- Semantic score reproducibility tests.
- RBAC denial tests.

---

## 10. Data & Persistence
| Path | Contents |
|------|----------|
| data/coaching/resume_versions.json | Per-user version arrays |
| data/audit/audit.jsonl | Line-delimited audit entries |
| data/audit/events.jsonl | Emitted events (analysis, version saved) |
| data/roles.json | Simple role registry (admin/user) |

Upgrade path: move to relational DB (versions, analyses, roles, audit) + vector store for embeddings.

---

## 11. Security & RBAC
- Firebase token validation (with dev bypass option)  
- Role guard decorator for admin endpoints  
- Future Improvements:
  - Replace JSON role store with database / policy engine
  - Field-level encryption for PII
  - Request correlation IDs + structured logging
 - Security headers: CSP, HSTS, Referrer-Policy, Permissions-Policy, X-Content-Type-Options
 - CORS hardening: `ALLOWED_ORIGINS` env controls allowed origins

---

## 12. Roadmap (Short / Mid Term)
| Phase | Highlights |
|-------|-----------|
| 1 | Vector embeddings + similarity store |
| 2 | Async processing queue (Celery / RQ) |
| 3 | Prompt registry + evaluation harness |
| 4 | Advanced parsing (NER + classifier) |
| 5 | Multi-tenant org isolation |
| 6 | Full observability (OpenTelemetry) |

Extended Ideas: candidate mock interview simulator, career path forecasting, ATS connectors, bias diagnostics.

---

## 13. Contributing
1. Fork & clone
2. Create feature branch: `git checkout -b feat/your-feature`
3. Write tests for new logic
4. Run `pytest -q`
5. Submit PR with clear description & screenshots/logs if UI/API change

Code Style Guidelines:
- Keep endpoints RESTful & explicit.
- Avoid silent failures—log warnings.
- Keep public responses JSON schema-stable.
 - Pre-commit recommended:
   ```powershell
   pip install pre-commit
   pre-commit install
   ```

---

## 14. License & Credits
MIT License (add LICENSE file if not present).  
Built with Flask, Cohere, optional OpenAI, and community Python tooling.

---

## 15. Support / Questions
Open an Issue or start a Discussion. For security disclosures, do **not** file a public issue—email the maintainer.

---

## 16. Changelog Snapshot (v0.4.0)
See Milestone summary above: semantic match, structured parsing, coaching diff, RBAC, rate limiting, audit/events, health endpoints.

### Professional Enhancements Added
- Centralized configuration module (`Backend_old/config.py`)
- JSON structured logging (stdout + container-friendly)
- `.env.example` template and dotenv loading
- Dockerfile for reproducible deployments
- GitHub Actions CI pipeline (Python tests + Node placeholder)
- Expanded environment variable documentation & safer secret handling

Upcoming: linting (flake8/black, ESLint), metrics endpoint, security hardening & dependency scanning.

### Newly Added (Dec 2025)
- Frontend: Study Pack search + link copy actions
- Frontend: Metrics Chart dataset toggles
- Frontend: ESLint + Prettier configuration and scripts
- Backend: `/metrics` endpoint with uptime, request counters, average analyze latency

---

Happy building! 🚀

