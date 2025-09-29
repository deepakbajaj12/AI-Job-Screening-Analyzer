import os
import json
import re
import time
import threading
from datetime import datetime
from collections import defaultdict
from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
import cohere
import pdfplumber
from dotenv import load_dotenv
import importlib
OpenAI = None  # default if library unavailable
import smtplib
from email.mime.text import MIMEText
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
try:
    _openai_mod = importlib.import_module("openai")
    OpenAI = getattr(_openai_mod, "OpenAI", None)
except Exception:
    OpenAI = None

load_dotenv()

app = Flask(__name__)
CORS(app)

APP_VERSION = os.getenv("APP_VERSION", "0.4.0")  # increment when major feature blocks added
DEV_BYPASS_AUTH = os.getenv("DEV_BYPASS_AUTH", "0") == "1"

# Initialize Firebase Admin SDK
firebase_cred_path = os.getenv("FIREBASE_CREDENTIAL_PATH", "firebase-service-account.json")
cred = credentials.Certificate(firebase_cred_path)
firebase_admin.initialize_app(cred)

# =============================
# LLM / Model Provider Setup
# =============================
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "cohere:command-light-nightly")  # e.g. cohere:command-light-nightly or openai:gpt-5-codex-preview

cohere_client = cohere.Client(COHERE_API_KEY) if COHERE_API_KEY else None
openai_client = OpenAI(api_key=OPENAI_API_KEY) if (OPENAI_API_KEY and OpenAI) else None

# =============================
# Data Persistence (Coaching)
# =============================
DATA_DIR = os.getenv("DATA_DIR", "data")
COACHING_DIR = os.path.join(DATA_DIR, "coaching")
VERSIONS_FILE = os.path.join(COACHING_DIR, "resume_versions.json")
AUDIT_DIR = os.path.join(DATA_DIR, "audit")
EVENTS_LOG = os.path.join(AUDIT_DIR, "events.jsonl")
AUDIT_LOG = os.path.join(AUDIT_DIR, "audit.jsonl")
ROLES_FILE = os.path.join(DATA_DIR, "roles.json")
os.makedirs(COACHING_DIR, exist_ok=True)
os.makedirs(AUDIT_DIR, exist_ok=True)

# Initialize roles file if absent
if not os.path.exists(ROLES_FILE):
    with open(ROLES_FILE, 'w', encoding='utf-8') as f:
        json.dump({}, f)

_versions_lock = threading.Lock()
_audit_lock = threading.Lock()
_event_lock = threading.Lock()
_rate_lock = threading.Lock()
_rate_buckets = defaultdict(list)  # key -> list[timestamps]

def rate_limit(max_requests=30, per_seconds=60, key_fn=None):
    def decorator(fn):
        def inner(*args, **kwargs):
            now = time.time()
            if key_fn:
                ident = key_fn()
            else:
                # Default: user ID if available else IP
                auth_header = request.headers.get("Authorization", "")
                uid = None
                if auth_header.startswith("Bearer "):
                    try:
                        # Lightweight decode attempt will still rely on normal path
                        pass
                    except Exception:
                        pass
                uid = request.headers.get("X-User-Id")  # fallback header hint
                ident = uid or request.remote_addr or "anonymous"
            with _rate_lock:
                bucket = _rate_buckets[ident]
                # purge old
                cutoff = now - per_seconds
                while bucket and bucket[0] < cutoff:
                    bucket.pop(0)
                if len(bucket) >= max_requests:
                    retry_after = round(bucket[0] + per_seconds - now, 1)
                    return jsonify({
                        "error": "rate_limited",
                        "message": f"Too many requests. Try again in {retry_after}s",
                        "retryAfterSeconds": retry_after
                    }), 429
                bucket.append(now)
            return fn(*args, **kwargs)
        inner.__name__ = fn.__name__
        return inner
    return decorator

def _read_versions_store():
    if not os.path.exists(VERSIONS_FILE):
        return {}
    try:
        with open(VERSIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _write_versions_store(store):
    tmp_path = VERSIONS_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, VERSIONS_FILE)

def list_versions(user_id):
    store = _read_versions_store()
    return store.get(user_id, [])

def add_version(user_id, record):
    with _versions_lock:
        store = _read_versions_store()
        versions = store.get(user_id, [])
        record["version"] = len(versions) + 1
        versions.append(record)
        store[user_id] = versions
        _write_versions_store(store)
        return record

# =============================
# RBAC & Audit Logging
# =============================
def get_user_role(user_id):
    try:
        with open(ROLES_FILE, 'r', encoding='utf-8') as f:
            roles = json.load(f)
        return roles.get(user_id, 'user')
    except Exception:
        return 'user'

def write_audit(user_id, action, meta=None):
    entry = {
        'ts': datetime.utcnow().isoformat() + 'Z',
        'user': user_id,
        'action': action,
        'meta': meta or {}
    }
    with _audit_lock:
        with open(AUDIT_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

def require_role(required_roles):
    def decorator(fn):
        def inner(user_info, *args, **kwargs):
            role = get_user_role(user_info.get('uid'))
            if role not in required_roles:
                return jsonify({'error': 'Forbidden: insufficient role'}), 403
            return fn(user_info, *args, **kwargs)
        inner.__name__ = fn.__name__
        return inner
    return decorator

# =============================
# Event Bus (Email + Webhook stubs)
# =============================
SMTP_HOST = os.getenv('SMTP_HOST')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER')
SMTP_PASS = os.getenv('SMTP_PASS')
EMAIL_FROM = os.getenv('EMAIL_FROM', 'no-reply@example.com')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')

def send_email(to_addr, subject, body):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        # Email disabled; log only
        print(f"[email-disabled] Would send to {to_addr}: {subject}")
        return False
    try:
        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = EMAIL_FROM
        msg['To'] = to_addr
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.send_message(msg)
        return True
    except Exception as e:
        print(f"Email send failed: {e}")
        return False

def post_webhook(event_type, payload):
    if not WEBHOOK_URL:
        return False
    try:
        r = requests.post(WEBHOOK_URL, json={'event': event_type, 'payload': payload}, timeout=5)
        return r.status_code < 400
    except Exception as e:
        print(f"Webhook error: {e}")
        return False

def dispatch_event(event_type, payload):
    entry = {
        'ts': datetime.utcnow().isoformat() + 'Z',
        'event': event_type,
        'payload': payload
    }
    with _event_lock:
        with open(EVENTS_LOG, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    # Fire and forget email / webhook based on event
    if event_type == 'analysis.completed' and payload.get('notifyEmail'):
        send_email(payload['notifyEmail'], 'Analysis Completed', f"Match: {payload.get('matchPercentage')}%\nMode: {payload.get('mode')}")
    post_webhook(event_type, payload)

# =============================
# LLM Abstraction
# =============================
def call_llm(prompt, temperature=0.6):
    """Unified LLM call supporting Cohere and OpenAI.
    LLM_MODEL format examples:
      cohere:command-light-nightly
      openai:gpt-4o
      openai:gpt-5-codex-preview  (placeholder / preview)
    Returns plaintext string or None on failure.
    """
    provider, model = (LLM_MODEL.split(":", 1) + [""])[:2]
    provider = provider.lower()
    try:
        if provider == "cohere":
            if not cohere_client:
                print("Cohere client not configured")
                return None
            resp = cohere_client.chat(
                model=model,
                message=prompt,
                temperature=temperature
            )
            return resp.text.strip()
        elif provider == "openai":
            if not openai_client:
                print("OpenAI client not configured")
                return None
            resp = openai_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature
            )
            return resp.choices[0].message.content.strip()
        else:
            print(f"Unsupported LLM provider: {provider}")
            return None
    except Exception as e:
        print(f"LLM call failed: {e}")
        return None

def verify_firebase_token(id_token):
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        print(f"Token verification failed: {e}")
        if DEV_BYPASS_AUTH:
            # Provide a synthetic user in dev mode
            return {"uid": "dev-user", "email": "dev@example.com", "devBypass": True}
        return None

def extract_text_from_pdf(file_storage):
    try:
        file_storage.seek(0)
        with pdfplumber.open(file_storage) as pdf:
            full_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
        return full_text.strip()
    except Exception as e:
        print(f"PDF text extraction error: {e}")
        return None

def call_cohere_api(prompt):
    """Backward compatibility wrapper using unified call."""
    return call_llm(prompt, temperature=0.6)

def extract_json_from_text(text):
    try:
        # Extract JSON object from AI response text
        json_str = re.search(r"\{.*\}", text, re.DOTALL).group(0)
        return json.loads(json_str)
    except Exception as e:
        print(f"JSON extraction failed: {e}")
        print("Raw response:", text)
        return None

def ensure_non_empty_fields(data):
    # Provide fallback defaults if empty or missing fields
    defaults = {
        "strengths": [
            "Strong foundation in relevant skills and knowledge.",
            "Demonstrates eagerness to learn and adapt to new challenges."
        ],
        "improvementAreas": [
            "Continue to develop technical expertise in key areas.",
            "Improve communication and teamwork skills."
        ],
        "recommendedRoles": [
            "Software Developer",
            "Junior Engineer"
        ],
        "generalFeedback": "Your profile shows promise with a solid skill set. Focus on continuous learning and collaboration to advance your career."
    }
    for key in defaults:
        if key not in data or not data[key]:
            data[key] = defaults[key]
    return data

def format_general_feedback(feedback_text):
    if not feedback_text:
        return "- No feedback provided."

    # Split feedback by lines or common separators (numbers, dashes, newlines)
    lines = re.split(r"\n+|\d+\.\s+|- ", feedback_text)
    cleaned = [line.strip("-• \n\t").strip() for line in lines if line.strip()]

    # Return bullet points for each meaningful line
    return "\n".join(f"- {line}" for line in cleaned)

def format_report(data):
    strengths = "\n".join(f"- {s}" for s in data["strengths"])
    improvements = "\n".join(f"- {i}" for i in data["improvementAreas"])
    recommended = "\n".join(f"- {r}" for r in data["recommendedRoles"])
    feedback = format_general_feedback(data["generalFeedback"])

    report = f"""
📈 Detailed Candidate Report

🟢 Strengths:
{strengths}

🟡 Areas to Improve:
{improvements}

🔵 Recommended Roles:
{recommended}

📝 General Feedback:
{feedback}
"""
    return report.strip()

# =============================
# Coaching / Resume Enhancement Utilities
# =============================
KNOWN_SKILLS = {
    "python", "java", "javascript", "react", "node", "node.js", "typescript", "sql", "mysql", "postgres", "mongodb",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "linux", "git", "c", "c++", "go", "rust",
    "tensorflow", "pytorch", "nlp", "machine learning", "deep learning", "django", "flask", "spring", "html", "css"
}

# =============================
# Structured Resume Parsing
# =============================
SECTION_HEADERS = [
    'experience', 'work experience', 'professional experience', 'education', 'projects', 'skills', 'certifications',
    'achievements', 'summary', 'profile'
]

def parse_resume_sections(text):
    sections = {}
    current = 'summary'
    sections[current] = []
    for line in text.splitlines():
        clean = line.strip()
        low = clean.lower()
        if any(re.fullmatch(rf"{h}\:?", low) for h in SECTION_HEADERS):
            current = low.split(':')[0]
            if current not in sections:
                sections[current] = []
            continue
        if clean:
            sections.setdefault(current, []).append(clean)
    # Join lines
    joined = {k: '\n'.join(v) for k, v in sections.items() if v}
    # Extract skills tokens if skills section present
    if 'skills' in joined:
        skill_line = joined['skills']
        tokens = re.split(r"[,;\n]\s*", skill_line)
        joined['skills_list_raw'] = [t.strip() for t in tokens if t.strip()]
    return joined

STUDY_RESOURCES = {
    "python": ["https://docs.python.org/3/", "https://realpython.com/"],
    "docker": ["https://docs.docker.com/get-started/", "https://www.youtube.com/watch?v=gAkwW2tuIqE"],
    "kubernetes": ["https://kubernetes.io/docs/home/", "https://www.cncf.io/training/"],
    "react": ["https://react.dev/learn", "https://beta.reactjs.org/"],
    "aws": ["https://aws.amazon.com/training/", "https://explore.skillbuilder.aws/"],
    "sql": ["https://www.sqltutorial.org/", "https://mode.com/sql-tutorial/"],
    "machine learning": ["https://scikit-learn.org/stable/", "https://www.deeplearning.ai/"],
}

def extract_bullets(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    bullets = []
    for line in lines:
        if re.match(r"^[-*•]", line) or len(line.split()) > 4:
            bullets.append(line.lstrip("-*• ").strip())
    return bullets[:100]

def detect_skills(text):
    lower = text.lower()
    found = set()
    for skill in KNOWN_SKILLS:
        if skill in lower:
            found.add(skill)
    return sorted(found)

def detect_skill_gaps(resume_skills, job_text):
    if not job_text:
        return []
    job_lower = job_text.lower()
    needed = {s for s in KNOWN_SKILLS if s in job_lower}
    gaps = sorted(list(needed - set(resume_skills)))
    return gaps

def build_study_pack(gaps):
    pack = []
    for g in gaps:
        pack.append({
            "skill": g,
            "resources": STUDY_RESOURCES.get(g, ["https://www.google.com/search?q=" + g + "+tutorial"])
        })
    return pack

def compute_basic_metrics(text, bullets, skills, gaps):
    words = re.findall(r"\w+", text)
    word_count = len(words)
    avg_bullet_len = round(sum(len(b.split()) for b in bullets) / max(len(bullets), 1), 2)
    coverage_ratio = round(len(skills) / max(len(skills) + len(gaps), 1), 2)
    return {
        "wordCount": word_count,
        "bulletCount": len(bullets),
        "avgBulletWordCount": avg_bullet_len,
        "skillCount": len(skills),
        "skillCoverageRatio": coverage_ratio
    }

def compute_semantic_match(resume_text, job_text):
    if not job_text or not resume_text:
        return None
    try:
        vect = TfidfVectorizer(max_features=4000, ngram_range=(1,2))
        docs = [resume_text, job_text]
        X = vect.fit_transform(docs)
        sim = cosine_similarity(X[0:1], X[1:2])[0][0]
        return round(float(sim) * 100, 2)
    except Exception as e:
        print(f"Semantic match error: {e}")
        return None

def generate_interview_questions(resume_excerpt, target_role, top_skills):
    prompt = f'''
You are an expert technical interviewer.
Generate a JSON object with an array field "questions" of 8 high-quality interview questions.
Tailor them to the target role: {target_role}
Incorporate the candidate's highlighted experience excerpt and top skills.
Respond ONLY with JSON of the form: {{"questions": ["..."]}}

Resume Excerpt (delimited by triple backticks):
```
{resume_excerpt}
```

Top Skills: {', '.join(top_skills)}
'''
    resp = call_llm(prompt, temperature=0.7)
    if not resp:
        return ["Describe a challenging project you've worked on."]
    try:
        obj = json.loads(re.search(r"\{.*\}", resp, re.DOTALL).group(0))
        return obj.get("questions", [])[:12] or ["Describe a challenging project you've worked on."]
    except Exception:
        return [q.strip() for q in re.split(r"\n+", resp) if q.strip()][:8]

def auth_required(fn):
    """Decorator-like helper for token verification inside route bodies."""
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            if DEV_BYPASS_AUTH:
                fake = {"uid": "dev-user", "email": "dev@example.com", "devBypass": True}
                return fn(fake, *args, **kwargs)
            return jsonify({"error": "Authorization header missing or malformed"}), 401
        id_token = auth_header.split("Bearer ")[1]
        user_info = verify_firebase_token(id_token)
        if not user_info:
            return jsonify({"error": "Invalid or expired token"}), 401
        return fn(user_info, *args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper

@app.route("/", methods=["GET"])
def index():
    return "AI Job Screening Resume Analyzer Backend Running."

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'version': APP_VERSION,
        'time': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/version', methods=['GET'])
def version():
    return jsonify({'version': APP_VERSION})

@app.route("/analyze", methods=["POST"])
@rate_limit(40, 60)
def analyze():
    start = time.time()

    # Verify Firebase token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return jsonify({"error": "Authorization header missing or malformed"}), 401

    id_token = auth_header.split("Bearer ")[1]
    user_info = verify_firebase_token(id_token)
    if not user_info:
        return jsonify({"error": "Invalid or expired token"}), 401

    mode = request.form.get("mode")
    if mode not in ["jobSeeker", "recruiter"]:
        return jsonify({"error": "Invalid mode; must be 'jobSeeker' or 'recruiter'"}), 400

    resume_file = request.files.get("resume")
    if not resume_file:
        return jsonify({"error": "Resume file is required"}), 400

    resume_text = extract_text_from_pdf(resume_file)
    if not resume_text:
        return jsonify({"error": "Could not extract text from resume PDF"}), 400

    resume_text = resume_text[:3000]  # Limit length for prompt

    if mode == "jobSeeker":
        job_desc = request.form.get("jobDescription", "").strip()[:2000]

        prompt = f"""
You are an expert AI career coach and HR specialist.

Analyze the candidate's resume and job description below and generate a detailed, professional JSON report.

The JSON must include:
- strengths: A detailed list of the candidate's key strengths and skills.
- improvementAreas: A detailed list of areas to improve professionally.
- recommendedRoles: A detailed list of specific job titles or career paths suitable for the candidate.
- generalFeedback: A well-written paragraph summarizing overall feedback and advice tailored to the candidate.

If any data is missing, infer plausible, helpful, and professional content.

Respond ONLY with the JSON object.

Resume:
\"\"\"{resume_text}\"\"\"

Job Description:
\"\"\"{job_desc}\"\"\"
"""

        ai_response = call_cohere_api(prompt)
        if not ai_response:
            return jsonify({"error": "AI service error"}), 500

        parsed = extract_json_from_text(ai_response)
        if not parsed:
            # fallback with raw AI response in generalFeedback only
            parsed = {
                "strengths": [],
                "improvementAreas": [],
                "recommendedRoles": [],
                "generalFeedback": ai_response
            }

        final_result = ensure_non_empty_fields(parsed)
        final_result["formattedReport"] = format_report(final_result)
        # Semantic (if job_desc provided)
        semantic_score = compute_semantic_match(resume_text, job_desc) if job_desc else None
        if semantic_score is not None:
            final_result['semanticMatchPercentage'] = semantic_score
        write_audit(user_info.get('uid'), 'analyze.jobSeeker', {'semantic': semantic_score is not None})
        dispatch_event('analysis.completed', {
            'userId': user_info.get('uid'),
            'mode': 'jobSeeker',
            'semanticMatch': semantic_score,
            'notifyEmail': None
        })
        return jsonify(final_result)

    elif mode == "recruiter":
        job_desc_file = request.files.get("job_description")
        recruiter_email = request.form.get("recruiterEmail", "").strip()

        if not job_desc_file or not recruiter_email:
            return jsonify({"error": "Job description file and recruiterEmail are required for recruiter mode"}), 400

        job_desc_text = extract_text_from_pdf(job_desc_file)
        if not job_desc_text:
            return jsonify({"error": "Could not extract text from job description PDF"}), 400

        job_desc_text = job_desc_text[:2000]

        # Simple lexical match percentage calculation
        resume_words = set(re.findall(r"\w+", resume_text.lower()))
        job_words = set(re.findall(r"\w+", job_desc_text.lower()))
        common_words = resume_words.intersection(job_words)
        match_percentage = round(len(common_words) / max(len(job_words), 1) * 100, 2)
        semantic_score = compute_semantic_match(resume_text, job_desc_text)
        if semantic_score is not None:
            combined = round((semantic_score + match_percentage) / 2, 2)
        else:
            combined = match_percentage

        prompt = f"""
You are an AI recruitment expert.

Analyze the candidate's resume versus the job description below and provide a detailed professional JSON report including:

- strengths: detailed list of the candidate's main strengths.
- improvementAreas: detailed list of areas for improvement.
- recommendedRoles: relevant job roles for the candidate.
- generalFeedback: a detailed paragraph including a summary and recommendations.

Include professional inferences if information is missing.

Respond ONLY with the JSON object.

Resume:
\"\"\"{resume_text}\"\"\"

Job Description:
\"\"\"{job_desc_text}\"\"\"
"""

        ai_response = call_cohere_api(prompt)
        if not ai_response:
            return jsonify({"error": "AI service error"}), 500

        parsed = extract_json_from_text(ai_response)
        if not parsed:
            parsed = {
                "strengths": [],
                "improvementAreas": [],
                "recommendedRoles": [],
                "generalFeedback": ai_response
            }

        final_result = ensure_non_empty_fields(parsed)
        # Prepend match percentage to general feedback
        final_result["generalFeedback"] = f"Lexical Match: {match_percentage}% | Semantic: {semantic_score if semantic_score is not None else 'N/A'}% | Combined: {combined}%\n\n{final_result['generalFeedback']}"
        final_result['lexicalMatchPercentage'] = match_percentage
        if semantic_score is not None:
            final_result['semanticMatchPercentage'] = semantic_score
            final_result['combinedMatchPercentage'] = combined
        write_audit(user_info.get('uid'), 'analyze.recruiter', {'lexical': match_percentage, 'semantic': semantic_score})
        dispatch_event('analysis.completed', {
            'userId': user_info.get('uid'),
            'mode': 'recruiter',
            'matchPercentage': match_percentage,
            'semanticMatch': semantic_score,
            'combined': combined,
            'notifyEmail': recruiter_email if recruiter_email else None
        })
        final_result["formattedReport"] = format_report(final_result)
        return jsonify(final_result)

    else:
        return jsonify({"error": "Unhandled mode"}), 400

# =============================
# Coaching Endpoints
# =============================

@app.route("/coaching/save-version", methods=["POST"])
@auth_required
@rate_limit(25, 300)
def coaching_save_version(user_info):
    user_id = user_info.get("uid")

    resume_file = request.files.get("resume")
    if not resume_file:
        return jsonify({"error": "Resume file is required"}), 400
    resume_text = extract_text_from_pdf(resume_file) or ""
    resume_text = resume_text[:6000]

    # Optional job description (text field or file)
    job_desc_text = ""
    if "jobDescription" in request.form:
        job_desc_text = request.form.get("jobDescription", "")[:4000]
    elif request.files.get("job_description"):
        job_desc_text = extract_text_from_pdf(request.files["job_description"]) or ""
        job_desc_text = job_desc_text[:4000]

    bullets = extract_bullets(resume_text)
    skills = detect_skills(resume_text)
    gaps = detect_skill_gaps(skills, job_desc_text)
    metrics = compute_basic_metrics(resume_text, bullets, skills, gaps)
    sections = parse_resume_sections(resume_text)

    record = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "metrics": metrics,
        "skills": skills,
        "skillGaps": gaps,
        "studyPack": build_study_pack(gaps),
        "bullets": bullets[:30],
        "resumeExcerpt": resume_text[:1200],
        "sections": sections
    }
    saved = add_version(user_id, record)
    write_audit(user_id, 'coaching.save_version', {'version': saved['version']})
    dispatch_event('version.saved', {'userId': user_id, 'version': saved['version']})
    return jsonify({"saved": saved})

@app.route("/coaching/progress", methods=["GET"])
@auth_required
def coaching_progress(user_info):
    user_id = user_info.get("uid")
    versions = list_versions(user_id)
    write_audit(user_id, 'coaching.progress', {'count': len(versions)})
    return jsonify({"versions": versions})

@app.route("/coaching/study-pack", methods=["GET"])
@auth_required
def coaching_study_pack(user_info):
    user_id = user_info.get("uid")
    versions = list_versions(user_id)
    if not versions:
        return jsonify({"error": "No versions found"}), 404
    latest = versions[-1]
    write_audit(user_id, 'coaching.study_pack', {'gaps': len(latest.get('skillGaps', []))})
    return jsonify({
        "skillGaps": latest.get("skillGaps", []),
        "studyPack": latest.get("studyPack", [])
    })

@app.route("/coaching/interview-questions", methods=["GET"])
@auth_required
def coaching_interview_questions(user_info):
    user_id = user_info.get("uid")
    target_role = request.args.get("targetRole", "Software Engineer")[:100]
    versions = list_versions(user_id)
    if not versions:
        return jsonify({"error": "No versions found"}), 404
    latest = versions[-1]
    questions = generate_interview_questions(
        latest.get("resumeExcerpt", ""),
        target_role,
        latest.get("skills", [])[:10]
    )
    write_audit(user_id, 'coaching.interview_questions', {'role': target_role, 'count': len(questions)})
    return jsonify({
        "targetRole": target_role,
        "questions": questions
    })

# =============================
# Diff Endpoint
# =============================
@app.route('/coaching/diff', methods=['GET'])
@auth_required
def coaching_diff(user_info):
    user_id = user_info.get('uid')
    versions = list_versions(user_id)
    if len(versions) < 2:
        return jsonify({'error': 'Need at least 2 versions'}), 400
    try:
        prev_idx = int(request.args.get('prev', len(versions)-1)) - 1
        curr_idx = int(request.args.get('curr', len(versions))) - 1
    except ValueError:
        return jsonify({'error': 'Invalid indices'}), 400
    if not (0 <= prev_idx < len(versions) and 0 <= curr_idx < len(versions)):
        return jsonify({'error': 'Index out of range'}), 400
    if prev_idx == curr_idx:
        return jsonify({'error': 'prev and curr must differ'}), 400
    prev = versions[prev_idx]
    curr = versions[curr_idx]
    prev_sk = set(prev.get('skills', []))
    curr_sk = set(curr.get('skills', []))
    added = sorted(list(curr_sk - prev_sk))
    removed = sorted(list(prev_sk - curr_sk))
    metrics_prev = prev.get('metrics', {})
    metrics_curr = curr.get('metrics', {})
    metric_deltas = {}
    for k in set(metrics_prev.keys()).union(metrics_curr.keys()):
        v0 = metrics_prev.get(k)
        v1 = metrics_curr.get(k)
        if isinstance(v0, (int, float)) and isinstance(v1, (int, float)):
            metric_deltas[k] = round(v1 - v0, 2)
    result = {
        'prevVersion': prev.get('version'),
        'currVersion': curr.get('version'),
        'addedSkills': added,
        'removedSkills': removed,
        'metricDeltas': metric_deltas,
        'currMetrics': metrics_curr,
        'prevMetrics': metrics_prev
    }
    write_audit(user_id, 'coaching.diff', {'prev': prev.get('version'), 'curr': curr.get('version')})
    return jsonify(result)

# =============================
# Admin: Fetch recent audit entries
# =============================
@app.route('/admin/audit', methods=['GET'])
@auth_required
@require_role(['admin'])
def admin_audit(user_info):
    limit = int(request.args.get('limit', '50'))
    lines = []
    try:
        with open(AUDIT_LOG, 'r', encoding='utf-8') as f:
            for line in f:
                lines.append(line.strip())
    except FileNotFoundError:
        return jsonify({'entries': []})
    entries = [json.loads(l) for l in lines[-limit:]]
    write_audit(user_info.get('uid'), 'admin.audit_view', {'count': len(entries)})
    return jsonify({'entries': entries})

# =============================
# Admin: Set Role Endpoint (admin only)
# =============================
@app.route('/admin/set-role', methods=['POST'])
@auth_required
@require_role(['admin'])
def admin_set_role(user_info):
    data = request.get_json(silent=True) or {}
    target_uid = data.get('userId')
    new_role = data.get('role')
    if not target_uid or new_role not in ['user', 'admin']:
        return jsonify({'error': 'Invalid payload'}), 400
    try:
        with open(ROLES_FILE, 'r', encoding='utf-8') as f:
            roles = json.load(f)
    except Exception:
        roles = {}
    roles[target_uid] = new_role
    with open(ROLES_FILE, 'w', encoding='utf-8') as f:
        json.dump(roles, f, ensure_ascii=False, indent=2)
    write_audit(user_info.get('uid'), 'admin.set_role', {'target': target_uid, 'role': new_role})
    return jsonify({'updated': True, 'userId': target_uid, 'role': new_role})


if __name__ == "__main__":
    app.run(debug=True)
