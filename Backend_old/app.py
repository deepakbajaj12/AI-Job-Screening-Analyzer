import os
import sys
# Add parent directory to path to ensure Backend_old module can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re
import uuid
import time
import threading
import socket
import gc
from datetime import datetime
from collections import defaultdict
from flask import Flask, request, jsonify, url_for, g
from flask_cors import CORS
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
from celery import Celery
import redis
import cohere
import pdfplumber
import importlib
import logging
import sys
OpenAI = None  # default if library unavailable
import smtplib
from email.mime.text import MIMEText
import requests
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# Import config with fallback specifically for different deployment contexts
try:
    from Backend_old.config import Config, init_directories, configure_logging
except ImportError:
    try:
        from config import Config, init_directories, configure_logging
    except ImportError:
        # Last ditch effort for weird path issues
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from config import Config, init_directories, configure_logging

try:
    _openai_mod = importlib.import_module("openai")
    OpenAI = getattr(_openai_mod, "OpenAI", None)
except Exception:
    OpenAI = None

# Central configuration & logging
configure_logging()
logger = logging.getLogger("resume_analyzer")
config = Config()

init_directories(config)

app = Flask(__name__)

# Celery Configuration
app.config['CELERY_BROKER_URL'] = config.CELERY_BROKER_URL
app.config['CELERY_RESULT_BACKEND'] = config.CELERY_RESULT_BACKEND

def make_celery(app):
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL']
    )
    celery.conf.update(app.config)
    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    celery.Task = ContextTask
    return celery

celery = make_celery(app)

# Redis Client for Rate Limiting
redis_client = None
REDIS_AVAILABLE = False
try:
    redis_client = redis.from_url(app.config['CELERY_BROKER_URL'])
    # Test connection
    redis_client.ping()
    REDIS_AVAILABLE = True
    logger.info(f"Connected to Redis at {app.config['CELERY_BROKER_URL']}")
except Exception as e:
    logger.warning(f"Failed to connect to Redis: {e}. Rate limiting and async tasks will be disabled.")
    redis_client = None

from Backend_old.config import Config as _Cfg
_origins = _Cfg.ALLOWED_ORIGINS
if _origins and _origins != "*":
    try:
        allowed = [o.strip() for o in _origins.split(',') if o.strip()]
    except Exception:
        allowed = [_origins]
    CORS(app, origins=allowed, supports_credentials=True)
else:
    # Explicitly allow everything for public demo
    CORS(app, resources={r"/*": {"origins": "*", "allow_headers": "*", "methods": "*"}})

APP_VERSION = config.APP_VERSION  # increment when major feature blocks added
DEV_BYPASS_AUTH = config.DEV_BYPASS_AUTH
START_TIME = time.time()
_metrics = {'requests': 0, 'analyze': {'count': 0, 'avgMs': 0.0}, 'errors': 0}

# Initialize Firebase Admin SDK
firebase_cred_path = config.FIREBASE_CREDENTIAL_PATH
try:
    # Check if file exists, else warn
    if not os.path.exists(firebase_cred_path) and not isinstance(credentials, str):
         # If credentials isn't a string (mock), checks file
         logger.warning(f"Firebase credentials not found at {firebase_cred_path}")

    cred = credentials.Certificate(firebase_cred_path)
    firebase_admin.initialize_app(cred)
    FIREBASE_AVAILABLE = True
except Exception as e:
    logger.error(f"Failed to initialize Firebase: {e}. Auth will fail open to guest-user.")
    FIREBASE_AVAILABLE = False

# =============================
# LLM / Model Provider Setup
# =============================
COHERE_API_KEY = config.COHERE_API_KEY
OPENAI_API_KEY = config.OPENAI_API_KEY
LLM_MODEL = config.LLM_MODEL  # e.g. cohere:command-light-nightly or openai:gpt-5-codex-preview

cohere_client = cohere.Client(COHERE_API_KEY) if COHERE_API_KEY else None
openai_client = OpenAI(api_key=OPENAI_API_KEY) if (OPENAI_API_KEY and OpenAI) else None

# =============================
# Data Persistence (Coaching)
# =============================
DATA_DIR = config.DATA_DIR
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
            ident = "unknown"
            if key_fn:
                ident = key_fn()
            else:
                 # Default: user ID if available else IP
                auth_header = request.headers.get("Authorization", "")
                uid = None
                if auth_header.startswith("Bearer "):
                    try:
                         # We don't verify token here again, just use it as key if valid-ish
                        uid = auth_header.split(" ")[1][:20] 
                    except Exception:
                        pass
                uid = request.headers.get("X-User-Id", uid)
                ident = uid or request.remote_addr or "anonymous"

            if redis_client:
                # Redis-based distributed rate limiting (Token Bucket / Sliding Window)
                # Using a simple list pattern: key -> list of timestamps
                # LTRIM to size of max_requests is efficiently maintained?
                # Actually, simpler pattern: key = rate:{ident}, Use RPUSH + EXPIRE
                
                key = f"rate_limit:{ident}:{fn.__name__}"
                try:
                    # Start a transaction (pipeline)
                    pipe = redis_client.pipeline()
                    pipe.rpush(key, now)
                    pipe.expire(key, per_seconds + 1) # Auto-cleanup
                    pipe.lrange(key, 0, -1)
                    results = pipe.execute()
                    
                    timestamps = [float(t) for t in results[2]]
                    
                    # Filter timestamps within window
                    valid_timestamps = [t for t in timestamps if t > now - per_seconds]
                    
                    # If list was too long, trim it asynchronously for next time (or just rely on expiration)
                    # Ideally we would LTRIM but for short windows expiration handles it mostly.
                    
                    if len(valid_timestamps) > max_requests:
                        retry_after = round(valid_timestamps[0] + per_seconds - now, 1)
                        if retry_after < 0: retry_after = 1
                        return jsonify({
                            "error": "rate_limited",
                            "message": f"Too many requests. Try again in {retry_after}s",
                            "retryAfterSeconds": retry_after
                        }), 429
                        
                except Exception as e:
                    logger.error(f"Redis rate limit error: {e}")
                    # Fallback to allow if redis fails
                    pass
            else:
                # In-memory Fallback
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
SMTP_HOST = config.SMTP_HOST
SMTP_PORT = config.SMTP_PORT
SMTP_USER = config.SMTP_USER
SMTP_PASS = config.SMTP_PASS
EMAIL_FROM = config.EMAIL_FROM
WEBHOOK_URL = config.WEBHOOK_URL

def send_email(to_addr, subject, body):
    if not (SMTP_HOST and SMTP_USER and SMTP_PASS):
        # Email disabled; log only
        logger.info(f"email.disabled to={to_addr} subject={subject}")
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
        logger.error(f"email.send_failed error={e}")
        return False

def post_webhook(event_type, payload):
    if not WEBHOOK_URL:
        return False
    try:
        r = requests.post(WEBHOOK_URL, json={'event': event_type, 'payload': payload}, timeout=5)
        return r.status_code < 400
    except Exception as e:
        logger.error(f"webhook.error error={e}")
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
def _get_mock_response(prompt):
    """Generate a mock response when LLM is unavailable."""
    prompt_lower = prompt.lower()
    
    if "json" in prompt_lower:
        return json.dumps({
            "strengths": ["Strong Technical Background", "Good Communication", "Problem Solving"],
            "improvementAreas": ["Gain more leadership experience", "Learn cloud architecture"],
            "recommendedRoles": ["Senior Developer", "Tech Lead", "Software Architect"],
            "generalFeedback": "This is a generated mock response because the LLM API key is missing or invalid. The candidate appears to have a strong profile suitable for technical roles.",
            "questions": [
                "Tell me about a challenging project you worked on.",
                "How do you handle conflicts in a team?",
                "Describe your experience with our tech stack."
            ],
            "missingSkills": [
                {"skill": "Cloud Computing", "importance": "High", "resources": ["AWS Certified Solutions Architect", "Google Cloud Documentation"]},
                {"skill": "System Design", "importance": "Medium", "resources": ["System Design Interview by Alex Xu"]}
            ],
            "advice": "Focus on building scalable systems and mentoring junior developers."
        })
    
    if "cover letter" in prompt_lower:
        return """Dear Hiring Manager,

I am writing to express my strong interest in the position. With my background in software development and passion for technology, I believe I would be a great fit for your team.

(This is a mock cover letter generated because the LLM API key is missing.)

Sincerely,
Candidate"""

    if "email" in prompt_lower:
        return """Subject: Interview Invitation

Dear Candidate,

We were impressed by your application and would like to invite you for an interview.

(This is a mock email generated because the LLM API key is missing.)

Best regards,
Recruiting Team"""

    return "This is a mock response from the AI Job Screening system. Please configure a valid API key to get real AI analysis."

import hashlib

def _compute_cache_key(prompt, model, temperature):
    """Compute a deterministic hash for the cache key."""
    raw = f"{model}:{temperature}:{prompt}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

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
    
    # 1. Check Cache (Redis)
    cache_key = None
    if redis_client:
        try:
            cache_key = f"llm_cache:{_compute_cache_key(prompt, LLM_MODEL, temperature)}"
            cached = redis_client.get(cache_key)
            if cached:
                logger.info(f"llm.cache_hit key={cache_key}")
                return cached.decode('utf-8')
        except Exception as e:
            logger.warning(f"llm.cache_read_error error={e}")

    result = None
    try:
        if provider == "cohere":
            if not cohere_client:
                logger.warning("llm.cohere_not_configured")
                result = _get_mock_response(prompt)
            else:
                try:
                    resp = cohere_client.chat(
                        model=model,
                        message=prompt,
                        temperature=temperature
                    )
                    result = resp.text.strip()
                except Exception as llm_err:
                    logger.error(f"CoHere API call failed: {llm_err}")
                    result = _get_mock_response(prompt)
        elif provider == "openai":
            if not openai_client:
                logger.warning("llm.openai_not_configured")
                result = _get_mock_response(prompt)
            else:
                resp = openai_client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature
                )
                result = resp.choices[0].message.content.strip()
        else:
            logger.warning(f"llm.unsupported_provider provider={provider}")
            result = _get_mock_response(prompt)
    except Exception as e:
        logger.error(f"llm.call_failed error={e}")
        return None

    # 2. Write to Cache (TTL 24h)
    if result and redis_client and cache_key:
        try:
            redis_client.setex(cache_key, 86400, result)
        except Exception as e:
            logger.warning(f"llm.cache_write_error error={e}")

    return result

def verify_firebase_token(id_token):
    # Check for dev token strictly first
    if DEV_BYPASS_AUTH and id_token == "dev":
        logger.warning("auth.dev_bypass_active user=dev-user")
        return {"uid": "dev-user", "email": "dev@example.com", "devBypass": True}

    if not FIREBASE_AVAILABLE:
         # Critical fallback if firebase init failed
         return {"uid": "guest-user-no-firebase", "email": "guest@demo.local"}

    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        logger.error(f"auth.token_verification_failed error={e}")
        # FAIL OPEN for demo purposes: if token is bad, just let them in as guest
        logger.warning("auth.verification_failed_fallback_to_guest")
        return {"uid": "guest-user", "email": "guest@demo.local"}

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
        logger.error(f"pdf.extract_error error={e}")
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
        logger.error(f"json.extract_failed error={e}")
        logger.info(f"json.raw_response snippet={text[:200]}")
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
        logger.error(f"semantic.match_error error={e}")
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
        if config.DEV_BYPASS_AUTH:
            # Inject mock user
            return fn({"uid": "dev-user", "email": "dev@local"}, *args, **kwargs)
            
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # Auto-bypass for public demo (even if config is somehow false)
            # This ensures visitors don't face 401 errors
            return fn({"uid": "guest-user", "email": "guest@demo.local"}, *args, **kwargs)

        id_token = auth_header.split("Bearer ")[1]
        user_info = verify_firebase_token(id_token)
        if not user_info:
            return jsonify({"error": "Invalid or expired token"}), 401
        return fn(user_info, *args, **kwargs)
    wrapper.__name__ = fn.__name__
    return wrapper

@app.route("/", methods=["GET"])
def index():
    return f"AI Job Screening Resume Analyzer Backend Running. Version: {APP_VERSION}. Auth Bypass: {config.DEV_BYPASS_AUTH}"

@app.before_request
def start_request_tracing():
    # 1. Capture or generate Request ID
    req_id = request.headers.get("X-Request-ID")
    if not req_id:
        req_id = str(uuid.uuid4())
    g.request_id = req_id

@app.after_request
def set_security_headers(response):
    # 0. Append Request ID to response
    if hasattr(g, "request_id"):
        response.headers["X-Request-ID"] = g.request_id

    # Basic hardening headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # HSTS enabled when served over HTTPS (ignored on HTTP)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Minimal CSP allowing self and inline styles/scripts used by Vite-dev; adjust for prod build
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "img-src 'self' data:; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self'"
    )
    return response

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

@app.route('/metrics', methods=['GET'])
def metrics():
    uptime = round(time.time() - START_TIME, 1)
    return jsonify({'uptimeSeconds': uptime, **_metrics})

@app.route('/internal/sys-info', methods=['GET'])
def sys_info():
    """
    Internal endpoint to expose system information for debugging.
    """
    return jsonify({
        'platform': sys.platform,
        'python_version': sys.version,
        'cwd': os.getcwd(),
        'cpu_count': os.cpu_count() or 1
    })

@app.route('/internal/process-info', methods=['GET'])
def process_info():
    """
    Internal endpoint to return process details.
    """
    return jsonify({
        'pid': os.getpid(),
        'ppid': os.getppid() if hasattr(os, 'getppid') else None,
        'thread_count': threading.active_count()
    })

@app.route('/internal/network-info', methods=['GET'])
def network_info():
    """
    Internal endpoint to expose basic network info.
    """
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except Exception:
        hostname = "unknown"
        local_ip = "unknown"
        
    return jsonify({
        'hostname': hostname,
        'ip_address': local_ip
    })

@app.route('/internal/thread-info', methods=['GET'])
def thread_info():
    """
    Internal endpoint to return active thread details.
    """
    threads = [t.name for t in threading.enumerate()]
    return jsonify({
        'total_threads': len(threads),
        'active_threads': threads
    })

@app.route('/internal/gc-info', methods=['GET'])
def gc_info():
    """
    Internal endpoint to return garbage collector stats.
    """
    return jsonify({
        'gc_enabled': gc.isenabled(),
        'gc_counts': gc.get_count(),
        'gc_threshold': gc.get_threshold()
    })

@app.route('/internal/time-info', methods=['GET'])
def time_info():
    """
    Internal endpoint to return server time details.
    """
    now = datetime.now()
    return jsonify({
        'current_time': now.isoformat(),
        'utc_time': datetime.utcnow().isoformat(),
        'timezone': time.tzname
    })

@celery.task(bind=True)
def run_analysis_task(self, mode, resume_text, job_desc_text, recruiter_email, user_info):
    start = time.time()
    
    if mode == "jobSeeker":
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
\"\"\"{job_desc_text}\"\"\"
"""
        ai_response = call_cohere_api(prompt)
        if not ai_response:
            return {"error": "AI service error"}

        parsed = extract_json_from_text(ai_response)
        if not parsed:
            parsed = {
                "strengths": [],
                "improvementAreas": [],
                "recommendedRoles": [],
                "generalFeedback": ai_response
            }

        final_result = ensure_non_empty_fields(parsed)
        final_result["formattedReport"] = format_report(final_result)
        # Semantic
        semantic_score = compute_semantic_match(resume_text, job_desc_text) if job_desc_text else None
        if semantic_score is not None:
             final_result['semanticMatchPercentage'] = semantic_score
        
        return final_result

    elif mode == "recruiter":
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
            return {"error": "AI service error"}

        parsed = extract_json_from_text(ai_response)
        if not parsed:
            parsed = {
                "strengths": [],
                "improvementAreas": [],
                "recommendedRoles": [],
                "generalFeedback": ai_response
            }
        
        final_result = ensure_non_empty_fields(parsed)
        final_result["generalFeedback"] = f"Lexical Match: {match_percentage}% | Semantic: {semantic_score if semantic_score is not None else 'N/A'}% | Combined: {combined}%\n\n{final_result['generalFeedback']}"
        final_result['lexicalMatchPercentage'] = match_percentage
        if semantic_score is not None:
            final_result['semanticMatchPercentage'] = semantic_score
            final_result['combinedMatchPercentage'] = combined
            
        final_result["formattedReport"] = format_report(final_result)
        return final_result
    
    return {"error": "Invalid mode"}

@app.route('/tasks/<task_id>', methods=['GET'])
def get_task_status(task_id):
    task = run_analysis_task.AsyncResult(task_id)
    if task.state == 'PENDING':
        return jsonify({
            'state': task.state,
            'status': 'Pending...'
        })
    elif task.state != 'FAILURE':
        return jsonify({
            'state': task.state,
            'result': task.result
        })
    else:
        return jsonify({
            'state': task.state,
            'error': str(task.info)
        })

@app.route("/analyze", methods=["POST"])
@rate_limit(40, 60)
@auth_required
def analyze(user_info):

    _metrics['requests'] += 1
    start = time.time()

    # Support JSON request
    if request.is_json:
        data = request.json
        mode = data.get("mode")
        if mode not in ["jobSeeker", "recruiter"]:
            return jsonify({"error": "Invalid mode; must be 'jobSeeker' or 'recruiter'"}), 400
        
        resume_text = data.get("resume", "")
        if not resume_text:
             return jsonify({"error": "Resume text is required"}), 400
        
        # Limit resume length same as file extraction
        resume_text = resume_text[:3000]

        job_desc_text = ""
        recruiter_email = ""

        if mode == "jobSeeker":
            job_desc_text = data.get("job_description", "").strip()[:2000]
        elif mode == "recruiter":
             recruiter_email = data.get("recruiterEmail", "").strip()
             job_desc_text = data.get("job_description", "").strip()[:2000]
             if not job_desc_text or not recruiter_email:
                 return jsonify({"error": "Job description and recruiterEmail are required"}), 400
    else:
        # Form Data Implementation
        mode = request.form.get("mode")
        if mode not in ["jobSeeker", "recruiter"]:
            return jsonify({"error": "Invalid mode; must be 'jobSeeker' or 'recruiter'"}), 400

        resume_file = request.files.get("resume")
        if not resume_file:
            return jsonify({"error": "Resume file is required"}), 400

        resume_text = extract_text_from_pdf(resume_file)
        if not resume_text:
            return jsonify({"error": "Could not extract text from resume PDF"}), 400

        resume_text = resume_text[:3000]

        job_desc_text = ""
        recruiter_email = ""

        if mode == "jobSeeker":
            job_desc_text = request.form.get("jobDescription", "").strip()[:2000]
        elif mode == "recruiter":
             job_desc_file = request.files.get("job_description")
             recruiter_email = request.form.get("recruiterEmail", "").strip()
             if job_desc_file:
                 job_desc_text = extract_text_from_pdf(job_desc_file) or ""
                 job_desc_text = job_desc_text[:2000]
             if not job_desc_text or not recruiter_email:
                 return jsonify({"error": "Job description file and recruiterEmail are required"}), 400

    # Queue the job immediately using RQ
    try:
        # Import directly assuming they are in the same package (Backend_old)
        # or in the path.
        try:
            from Backend_old.queue_config import task_queue
            from Backend_old.worker_tasks import process_resume_analysis
        except ImportError:
            # If running from within Backend_old as CWD
            from queue_config import task_queue
            from worker_tasks import process_resume_analysis

        if not task_queue:
            raise Exception("Redis Connection failed, task_queue is None")


        # Send task to Redis queue
        job = task_queue.enqueue(
            process_resume_analysis,
            resume_text,
            job_desc_text,
            mode
        )

        _metrics['requests'] += 1

        # Return instantly
        return jsonify({
            "status": "queued",
            "job_id": job.id,
            "mode": mode
        }), 202

    except Exception as e:
        logger.error(f"Failed to queue job: {e}")
        return jsonify({"error": "Failed to queue job", "details": str(e)}), 500

@app.route("/status/<job_id>", methods=["GET"])
def job_status(job_id):
    try:
        import sys
        if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        from rq.job import Job
        from queue_config import redis_conn

        job = Job.fetch(job_id, connection=redis_conn)

        if job.is_finished:
            return jsonify({
                "status": "finished",
                "result": job.result
            })
        elif job.is_failed:
             return jsonify({
                "status": "failed",
                "error": str(job.exc_info)
            })

        return jsonify({
            "status": job.get_status()
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =============================
# Coaching Endpoints - existing code below
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
        return jsonify({
            "skillGaps": [],
            "studyPack": []
        })
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
        return jsonify({
            "targetRole": target_role,
            "questions": ["Please save a resume version first to generate tailored questions."]
        })
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

# =============================
# Advanced Features Endpoints
# =============================

@app.route('/generate-cover-letter', methods=['POST'])
@auth_required
@rate_limit(max_requests=10, per_seconds=60)
def generate_cover_letter(user_info):
    if 'resume' not in request.files:
        return jsonify({'error': 'No resume file provided'}), 400
    
    resume_file = request.files['resume']
    job_description = request.form.get('jobDescription', '')
    
    resume_text = extract_text_from_pdf(resume_file)
    if not resume_text:
        return jsonify({'error': 'Could not extract text from PDF'}), 400

    prompt = f"""
    You are an expert career coach. Write a professional and persuasive cover letter for the following candidate based on their resume and the job description.
    
    RESUME:
    {resume_text[:3000]}
    
    JOB DESCRIPTION:
    {job_description[:3000]}
    
    The cover letter should be formatted correctly, highlight relevant skills, and express enthusiasm for the role.
    """
    
    cover_letter = call_llm(prompt, temperature=0.7)
    if not cover_letter:
        return jsonify({'error': 'Failed to generate cover letter'}), 500
        
    return jsonify({'coverLetter': cover_letter})

@app.route('/generate-interview-questions', methods=['POST'])
@auth_required
@rate_limit(max_requests=10, per_seconds=60)
def generate_interview_questions(user_info):
    if 'resume' not in request.files:
        return jsonify({'error': 'No resume file provided'}), 400
    
    resume_file = request.files['resume']
    job_description = request.form.get('jobDescription', '')
    
    resume_text = extract_text_from_pdf(resume_file)
    
    prompt = f"""
    Generate 5-7 tailored interview questions for a candidate with the following resume applying for the described job.
    Include a mix of behavioral, technical, and situational questions.
    
    RESUME:
    {resume_text[:3000]}
    
    JOB DESCRIPTION:
    {job_description[:3000]}
    
    Output format:
    1. [Question]
    2. [Question]
    ...
    """
    
    questions = call_llm(prompt, temperature=0.7)
    if not questions:
        return jsonify({'error': 'Failed to generate questions'}), 500
        
    return jsonify({'questions': questions})

@app.route('/analyze-skills', methods=['POST'])
@auth_required
@rate_limit(max_requests=10, per_seconds=60)
def analyze_skills(user_info):
    if 'resume' not in request.files:
        return jsonify({'error': 'No resume file provided'}), 400
    
    resume_file = request.files['resume']
    job_description = request.form.get('jobDescription', '')
    
    resume_text = extract_text_from_pdf(resume_file)
    
    prompt = f"""
    Analyze the skill gap between the candidate's resume and the job description.
    Identify missing skills and suggest 3 specific learning resources (courses, books, or documentation) for each missing skill.
    
    RESUME:
    {resume_text[:3000]}
    
    JOB DESCRIPTION:
    {job_description[:3000]}
    
    Return the response in JSON format with the following structure:
    {{
        "missingSkills": [
            {{
                "skill": "Skill Name",
                "importance": "High/Medium/Low",
                "resources": ["Resource 1", "Resource 2", "Resource 3"]
            }}
        ],
        "advice": "General advice for closing the gap."
    }}
    """
    
    analysis = call_llm(prompt, temperature=0.5)
    if not analysis:
        return jsonify({'error': 'Failed to analyze skills'}), 500
    
    try:
        if "```json" in analysis:
            analysis = analysis.split("```json")[1].split("```")[0].strip()
        elif "```" in analysis:
            analysis = analysis.split("```")[1].split("```")[0].strip()
        result = json.loads(analysis)
    except:
        result = {"raw_analysis": analysis}
        
    return jsonify(result)

@app.route('/generate-email', methods=['POST'])
@auth_required
@rate_limit(max_requests=10, per_seconds=60)
def generate_email(user_info):
    data = request.get_json()
    email_type = data.get('type', 'interview_invite')
    candidate_name = data.get('candidateName', 'Candidate')
    job_title = data.get('jobTitle', 'Role')
    
    prompt = f"""
    Write a professional email for a recruiter.
    Type: {email_type}
    Candidate Name: {candidate_name}
    Job Title: {job_title}
    
    Keep it polite, professional, and concise.
    """
    
    email_content = call_llm(prompt, temperature=0.7)
    return jsonify({'email': email_content})

@app.route('/mock-interview', methods=['POST'])
@auth_required
@rate_limit(max_requests=20, per_seconds=60)
def mock_interview(user_info):
    data = request.get_json()
    history = data.get('history', [])
    last_message = data.get('message', '')
    job_context = data.get('jobContext', '')
    
    messages = []
    if job_context:
        messages.append(f"Context: You are interviewing the candidate for the following role: {job_context}. Be professional but challenging.")
    
    for msg in history[-5:]:
        role = "User" if msg['sender'] == 'user' else "Interviewer"
        messages.append(f"{role}: {msg['text']}")
    
    messages.append(f"User: {last_message}")
    messages.append("Interviewer:")
    
    prompt = "\\n".join(messages)
    
    response = call_llm(prompt, temperature=0.7)
    return jsonify({'response': response})


@app.route('/generate-linkedin-profile', methods=['POST'])
@auth_required
@rate_limit(max_requests=10, per_seconds=60)
def generate_linkedin_profile(user_info):
    if 'resume' not in request.files:
        return jsonify({'error': 'No resume file provided'}), 400
    
    resume_file = request.files['resume']
    resume_text = extract_text_from_pdf(resume_file)
    
    prompt = f'''
    You are an expert career consultant. Create a professional LinkedIn profile based on the resume below.
    
    RESUME:
    {resume_text[:3000]}
    
    Return a JSON object with:
    - headline: A catchy professional headline.
    - about: A compelling "About" summary (max 300 words).
    - experience_highlights: A list of 3-5 key achievements formatted for LinkedIn.
    '''
    
    response = call_llm(prompt, temperature=0.7)
    if not response:
        return jsonify({'error': 'Failed to generate profile'}), 500
        
    try:
        # Try to parse JSON if the LLM returns it wrapped in code blocks
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        result = json.loads(response)
    except:
        result = {"raw_response": response}
        
    return jsonify(result)

@app.route('/analyze-mock-interview', methods=['POST'])
@auth_required
@rate_limit(max_requests=10, per_seconds=60)
def analyze_mock_interview(user_info):
    data = request.get_json()
    history = data.get('history', [])
    job_context = data.get('jobContext', '')
    
    if not history:
        return jsonify({'error': 'No interview history provided'}), 400
        
    transcript = ""
    for msg in history:
        role = "Candidate" if msg['sender'] == 'user' else "Interviewer"
        transcript += f"{role}: {msg['text']}\n"
        
    prompt = f'''
    Analyze the following mock interview transcript for the role of {job_context}.
    
    TRANSCRIPT:
    {transcript}
    
    Provide a JSON report with:
    - score: A score out of 100.
    - feedback: General feedback on communication and technical accuracy.
    - strengths: List of strong points.
    - improvements: List of areas to improve.
    '''
    
    response = call_llm(prompt, temperature=0.5)
    if not response:
        return jsonify({'error': 'Failed to analyze interview'}), 500
        
    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        result = json.loads(response)
    except:
        result = {"raw_response": response}
        
    return jsonify(result)

@app.route('/estimate-salary', methods=['POST'])
@auth_required
@rate_limit(max_requests=10, per_seconds=60)
def estimate_salary(user_info):
    if 'resume' not in request.files:
        return jsonify({'error': 'No resume file provided'}), 400
    
    resume_file = request.files['resume']
    job_description = request.form.get('jobDescription', '')
    
    resume_text = extract_text_from_pdf(resume_file)
    
    prompt = f'''
    Based on the candidate's resume and the job description, estimate a competitive salary range and provide negotiation tips.
    
    RESUME:
    {resume_text[:3000]}
    
    JOB DESCRIPTION:
    {job_description[:3000]}
    
    Return a JSON object with:
    - estimated_salary_range: e.g. "$120,000 - $140,000"
    - market_trends: Brief insight into current market for this role.
    - negotiation_tips: List of 3-5 specific tips for negotiating this offer based on the candidate's strengths.
    '''
    
    response = call_llm(prompt, temperature=0.5)
    if not response:
        return jsonify({'error': 'Failed to estimate salary'}), 500
        
    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        result = json.loads(response)
    except:
        result = {"raw_response": response}
        
    return jsonify(result)

@app.route('/tailor-resume', methods=['POST'])
@auth_required
@rate_limit(max_requests=10, per_seconds=60)
def tailor_resume(user_info):
    if 'resume' not in request.files:
        return jsonify({'error': 'No resume file provided'}), 400
    
    resume_file = request.files['resume']
    job_description = request.form.get('jobDescription', '')
    
    resume_text = extract_text_from_pdf(resume_file)
    
    prompt = f'''
    Rewrite the candidate's resume summary and key experience bullet points to better align with the job description keywords and requirements.
    
    RESUME:
    {resume_text[:3000]}
    
    JOB DESCRIPTION:
    {job_description[:3000]}
    
    Return a JSON object with:
    - rewritten_summary: A new professional summary tailored to the job.
    - tailored_bullets: A list of objects, each containing "original" (text) and "rewritten" (text) for the top 3 most impactful bullet points to change.
    '''
    
    response = call_llm(prompt, temperature=0.7)
    if not response:
        return jsonify({'error': 'Failed to tailor resume'}), 500
        
    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        result = json.loads(response)
    except:
        result = {"raw_response": response}
        
    return jsonify(result)

@app.route('/generate-career-path', methods=['POST'])
@auth_required
@rate_limit(max_requests=10, per_seconds=60)
def generate_career_path(user_info):
    if 'resume' not in request.files:
        return jsonify({'error': 'No resume file provided'}), 400
    
    resume_file = request.files['resume']
    resume_text = extract_text_from_pdf(resume_file)
    
    prompt = f'''
    Analyze the candidate's resume and suggest a long-term career path roadmap.
    
    RESUME:
    {resume_text[:3000]}
    
    Return a JSON object with:
    - current_level: Estimated current seniority level (e.g., Junior, Mid, Senior).
    - career_roadmap: A list of 3-4 future roles/milestones. Each milestone should have:
        - role: Job title.
        - timeline: Estimated years to reach this.
        - skills_needed: Key skills to acquire.
    '''
    
    response = call_llm(prompt, temperature=0.7)
    if not response:
        return jsonify({'error': 'Failed to generate career path'}), 500
        
    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        result = json.loads(response)
    except:
        result = {"raw_response": response}
        
    return jsonify(result)

@app.route('/generate-job-description', methods=['POST'])
@auth_required
@rate_limit(max_requests=10, per_seconds=60)
def generate_job_description(user_info):
    data = request.get_json()
    title = data.get('title', '')
    skills = data.get('skills', '')
    experience = data.get('experience', '')
    
    prompt = f'''
    Write a professional and attractive job description for the following role:
    
    Job Title: {title}
    Required Skills: {skills}
    Experience Level: {experience}
    
    Return a JSON object with:
    - job_description: The full formatted job description text.
    '''
    
    response = call_llm(prompt, temperature=0.7)
    if not response:
        return jsonify({'error': 'Failed to generate JD'}), 500
        
    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        result = json.loads(response)
    except:
        result = {"raw_response": response}
        
    return jsonify(result)

@app.route('/resume-health-check', methods=['POST'])
@auth_required
@rate_limit(max_requests=10, per_seconds=60)
def resume_health_check(user_info):
    if 'resume' not in request.files:
        return jsonify({'error': 'No resume file provided'}), 400
    
    file = request.files['resume']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    try:
        with pdfplumber.open(file) as pdf:
            text = ""
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except Exception as e:
        logger.error(f"pdf.extract_error error={e}")
        return jsonify({'error': 'Failed to extract text from PDF'}), 500

    prompt = f'''
    Perform a comprehensive health check on this resume. Analyze it for:
    1. Formatting & Structure (clarity, section headers, length)
    2. Impact & Quantifiable Results (use of numbers, metrics, achievements vs duties)
    3. Action Verbs (strength of language)
    4. Contact Information (completeness)
    5. ATS Compatibility (keyword density, standard sections)
    
    RESUME TEXT:
    {text[:4000]}
    
    Return a JSON object with:
    - score: Overall health score (0-100).
    - summary: A brief summary of the resume's health.
    - checks: A list of objects, each with:
        - category: (e.g., "Impact", "Formatting", "Action Verbs")
        - status: "pass", "warning", or "fail"
        - feedback: Specific feedback for this category.
    - improvements: A list of specific actionable improvements.
    '''
    
    response = call_llm(prompt, temperature=0.5)
    if not response:
        return jsonify({'error': 'Failed to analyze resume health'}), 500
        
    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        result = json.loads(response)
    except:
        result = {"raw_response": response}
        
    return jsonify(result)

@app.route('/generate-boolean-search', methods=['POST'])
@auth_required
@rate_limit(max_requests=10, per_seconds=60)
def generate_boolean_search(user_info):
    data = request.get_json()
    job_description = data.get('jobDescription', '')
    
    prompt = f'''
    Generate a highly effective Boolean search string for finding candidates on LinkedIn or Google for the following job description.
    Also provide a brief explanation of the search strategy.
    
    JOB DESCRIPTION:
    {job_description[:3000]}
    
    Return a JSON object with:
    - boolean_string: The search string (e.g., "(Java OR Kotlin) AND (Android) AND (Senior OR Lead)").
    - explanation: Why these keywords and operators were chosen.
    '''
    
    response = call_llm(prompt, temperature=0.4)
    if not response:
        return jsonify({'error': 'Failed to generate boolean search'}), 500
        
    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        result = json.loads(response)
    except:
        result = {"raw_response": response}
        
    return jsonify(result)

@app.route('/generate-networking-message', methods=['POST'])
@auth_required
@rate_limit(max_requests=10, per_seconds=60)
def generate_networking_message(user_info):
    data = request.get_json()
    target_role = data.get('targetRole', '')
    company = data.get('company', '')
    recipient_name = data.get('recipientName', 'Hiring Manager')
    message_type = data.get('messageType', 'linkedin_connect')
    
    prompt = f'''
    Write a professional networking message for a job seeker.
    
    Target Role: {target_role}
    Target Company: {company}
    Recipient Name: {recipient_name}
    Message Type: {message_type}
    
    Context:
    - linkedin_connect: Short (under 300 chars), polite, stating intent to connect.
    - cold_email: Professional, concise, highlighting value proposition.
    - alumni_reachout: Friendly, mentioning shared alma mater/background.
    
    Return a JSON object with:
    - subject: (If applicable, otherwise empty)
    - message: The message body.
    - tips: 1-2 quick tips for sending this message.
    '''
    
    response = call_llm(prompt, temperature=0.6)
    if not response:
        return jsonify({'error': 'Failed to generate networking message'}), 500
        
    try:
        if "```json" in response:
            response = response.split("```json")[1].split("```")[0].strip()
        elif "```" in response:
            response = response.split("```")[1].split("```")[0].strip()
        result = json.loads(response)
    except:
        result = {"raw_response": response}
        
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)

