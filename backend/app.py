# MAIN APPLICATION: Flask server with 30+ endpoints for AI-powered resume analysis, recruiter tools, and coaching for both job seekers and recruiters
import os
import sys
# Add parent directory to path to ensure backend module can be imported
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re
import uuid
import time
import concurrent.futures
import hmac
import hashlib
import threading
import socket
import gc
from datetime import datetime
from collections import defaultdict
from flask import Flask, request, jsonify, url_for, g, send_file
from flask_cors import CORS, cross_origin
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

# PDF Generation
try:
    from backend.pdf_generator import (
        generate_job_seeker_pdf,
        generate_recruiter_pdf,
        generate_cover_letter_pdf,
        generate_coaching_report_pdf
    )
except ImportError:
    try:
        from pdf_generator import (
            generate_job_seeker_pdf,
            generate_recruiter_pdf,
            generate_cover_letter_pdf,
            generate_coaching_report_pdf
        )
    except ImportError:
        generate_job_seeker_pdf = None
        generate_recruiter_pdf = None
        generate_cover_letter_pdf = None
        generate_coaching_report_pdf = None

# MongoDB integration
try:
    from backend.mongo_db import save_analysis, get_user_history, get_db
except ImportError:
    try:
        from mongo_db import save_analysis, get_user_history, get_db
    except ImportError:
        save_analysis = lambda *a, **kw: None
        get_user_history = lambda *a, **kw: []
        get_db = lambda: (None, False)

# Import config with fallback specifically for different deployment contexts
try:
    from backend.config import Config, init_directories, configure_logging
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

from backend.config import Config as _Cfg
_origins = _Cfg.ALLOWED_ORIGINS
default_origins = [
    "http://localhost:3000",
    "http://localhost:5174",
    "https://ai-job-screening-analyzer.vercel.app",
    "https://ai-job-screening-analyzer-ggc93dxfo-deepak-bajajs-projects.vercel.app",
    "https://ai-job-screening-analyzer-e2wesrjs6-deepak-bajajs-projects.vercel.app",
]

if _origins and _origins != "*":
    try:
        allowed_origins = [o.strip() for o in _origins.split(',') if o.strip()]
    except Exception:
        allowed_origins = [_origins]
else:
    allowed_origins = default_origins

CORS(
    app,
    resources={
        r"/*": {
            "origins": allowed_origins,
            "allow_headers": "*",
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        }
    },
    supports_credentials=True,
)

APP_VERSION = config.APP_VERSION  # increment when major feature blocks added
DEV_BYPASS_AUTH = config.DEV_BYPASS_AUTH
START_TIME = time.time()
_metrics = {'requests': 0, 'analyze': {'count': 0, 'avgMs': 0.0}, 'errors': 0}
BUILD_COMMIT = os.getenv("RENDER_GIT_COMMIT", "local")

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
# India Salary Benchmarks (2025-2026)
# =============================
INDIA_SALARY_BENCHMARKS = {
    "junior_developer": {"min": 300000, "max": 600000, "currency": "INR", "experience": "0-2 years"},
    "mid_level_developer": {"min": 600000, "max": 1200000, "currency": "INR", "experience": "2-5 years"},
    "senior_developer": {"min": 1200000, "max": 2500000, "currency": "INR", "experience": "5-8 years"},
    "tech_lead": {"min": 1800000, "max": 3500000, "currency": "INR", "experience": "7+ years"},
    "data_scientist": {"min": 800000, "max": 2000000, "currency": "INR", "experience": "2-5 years"},
    "ml_engineer": {"min": 1000000, "max": 2500000, "currency": "INR", "experience": "3-6 years"},
    "devops_engineer": {"min": 700000, "max": 1800000, "currency": "INR", "experience": "2-5 years"},
    "qa_engineer": {"min": 400000, "max": 900000, "currency": "INR", "experience": "2-4 years"},
    "product_manager": {"min": 900000, "max": 2200000, "currency": "INR", "experience": "3-6 years"},
}

# =============================
# LLM / Model Provider Setup
# =============================
COHERE_API_KEY = config.COHERE_API_KEY
OPENAI_API_KEY = config.OPENAI_API_KEY
LLM_MODEL = config.LLM_MODEL  # e.g. cohere:command-light-nightly or openai:gpt-5-codex-preview
LLM_TIMEOUT_SECONDS = max(5, int(getattr(config, "LLM_TIMEOUT_SECONDS", 35) or 35))
# Force sync execution on constrained deployments to prevent stuck queued jobs.
ASYNC_TASKS_ENABLED = False

cohere_client = cohere.Client(COHERE_API_KEY) if COHERE_API_KEY else None
openai_client = OpenAI(api_key=OPENAI_API_KEY) if (OPENAI_API_KEY and OpenAI) else None

# Log which LLM provider is configured
if cohere_client:
    logger.info(f"llm.cohere_configured model={LLM_MODEL}")
elif openai_client:
    logger.info(f"llm.openai_configured model={LLM_MODEL}")
else:
    logger.warning(f"llm.no_provider_configured falling_back_to_mock model={LLM_MODEL}")

# =============================
# Data Persistence (Coaching)
# =============================
DATA_DIR = config.DATA_DIR
COACHING_DIR = os.path.join(DATA_DIR, "coaching")
VERSIONS_FILE = os.path.join(COACHING_DIR, "resume_versions.json")
WELCOME_EMAILS_FILE = os.path.join(COACHING_DIR, "welcome_emails.json")
RECRUITER_DIR = os.path.join(DATA_DIR, "recruiter")
RECRUITER_TEMPLATES_FILE = os.path.join(RECRUITER_DIR, "templates.json")
AUDIT_DIR = os.path.join(DATA_DIR, "audit")
EVENTS_LOG = os.path.join(AUDIT_DIR, "events.jsonl")
AUDIT_LOG = os.path.join(AUDIT_DIR, "audit.jsonl")
ROLES_FILE = os.path.join(DATA_DIR, "roles.json")
os.makedirs(COACHING_DIR, exist_ok=True)
os.makedirs(RECRUITER_DIR, exist_ok=True)
os.makedirs(AUDIT_DIR, exist_ok=True)

# Initialize roles file if absent
if not os.path.exists(ROLES_FILE):
    with open(ROLES_FILE, 'w', encoding='utf-8') as f:
        json.dump({}, f)

_versions_lock = threading.Lock()
_welcome_lock = threading.Lock()
_audit_lock = threading.Lock()
_event_lock = threading.Lock()
_rate_lock = threading.Lock()
_template_lock = threading.Lock()
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
                    # Match Redis behavior by isolating limits per identity and endpoint.
                    bucket_key = f"{ident}:{fn.__name__}"
                    bucket = _rate_buckets[bucket_key]
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

def _read_welcome_store():
    if not os.path.exists(WELCOME_EMAILS_FILE):
        return {}
    try:
        with open(WELCOME_EMAILS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _write_welcome_store(store):
    tmp_path = WELCOME_EMAILS_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, WELCOME_EMAILS_FILE)

def has_welcome_email_been_sent(user_id):
    store = _read_welcome_store()
    return bool(store.get(user_id))

def mark_welcome_email_sent(user_id, email):
    with _welcome_lock:
        store = _read_welcome_store()
        if store.get(user_id):
            return
        store[user_id] = {
            "email": email,
            "firstSentAt": datetime.utcnow().isoformat() + "Z"
        }
        _write_welcome_store(store)

def _read_recruiter_templates_store():
    if not os.path.exists(RECRUITER_TEMPLATES_FILE):
        return {}
    try:
        with open(RECRUITER_TEMPLATES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _write_recruiter_templates_store(store):
    tmp_path = RECRUITER_TEMPLATES_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(store, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, RECRUITER_TEMPLATES_FILE)

def _list_recruiter_templates(user_id, kind=None):
    store = _read_recruiter_templates_store()
    templates = store.get(user_id, [])
    if kind:
        templates = [t for t in templates if t.get("kind") == kind]
    return templates

def _get_recruiter_template(user_id, template_id):
    templates = _list_recruiter_templates(user_id)
    for item in templates:
        if item.get("id") == template_id:
            return item
    return None

def _save_recruiter_template(user_id, kind, title, content, metadata=None, template_id=None):
    now = datetime.utcnow().isoformat() + "Z"
    metadata = metadata or {}
    with _template_lock:
        store = _read_recruiter_templates_store()
        templates = store.get(user_id, [])

        target = None
        if template_id:
            for item in templates:
                if item.get("id") == template_id:
                    target = item
                    break

        if target:
            version_num = len(target.get("versions", [])) + 1
            target["title"] = title or target.get("title") or f"{kind.title()} Template"
            target["updatedAt"] = now
            target.setdefault("versions", []).append({
                "version": version_num,
                "createdAt": now,
                "content": content,
                "metadata": metadata,
            })
        else:
            template_id = str(uuid.uuid4())
            target = {
                "id": template_id,
                "kind": kind,
                "title": title or f"{kind.title()} Template",
                "createdAt": now,
                "updatedAt": now,
                "versions": [{
                    "version": 1,
                    "createdAt": now,
                    "content": content,
                    "metadata": metadata,
                }],
            }
            templates.append(target)

        store[user_id] = templates
        _write_recruiter_templates_store(store)
        return target

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
        try:
            os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
            with open(AUDIT_LOG, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except OSError as exc:
            # Audit logging should never break request handling.
            logger.warning("audit.write_failed path=%s error=%s", AUDIT_LOG, exc)

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
WEBHOOK_SECRET = config.WEBHOOK_SECRET

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

    event_body = {'event': event_type, 'payload': payload}
    headers = {'Content-Type': 'application/json'}

    if WEBHOOK_SECRET:
        timestamp = str(int(time.time()))
        body_json = json.dumps(event_body, ensure_ascii=False, separators=(',', ':'), sort_keys=True)
        signed_payload = f"{timestamp}.{body_json}"
        signature = hmac.new(
            WEBHOOK_SECRET.encode('utf-8'),
            signed_payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        headers['X-Webhook-Timestamp'] = timestamp
        headers['X-Webhook-Signature'] = signature

    try:
        r = requests.post(WEBHOOK_URL, json=event_body, headers=headers, timeout=5)
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
        try:
            with open(EVENTS_LOG, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        except Exception as e:
            logger.warning(f"Failed to write to events log: {e}")
            
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
    
    if "linkedin" in prompt_lower:
        return json.dumps({
            "headline": "Mock LinkedIn Headline | Software Developer",
            "about": "This is a mock LinkedIn summary generated because the LLM API key is missing or invalid. I am an experienced developer with a passion for building great software.",
            "experience_highlights": ["Developed a mock feature", "Improved mock performance by 20%", "Collaborated with a mock team"]
        })

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
    Note: Cohere SDK doesn't support timeout in chat() method.
          Use cache + fallback strategy for slow responses.
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
                # Run provider call in a bounded-time future so a stalled upstream
                # request cannot block the single-worker queue forever.
                def _cohere_chat_once():
                    return cohere_client.chat(
                        model=model,
                        message=prompt,
                        temperature=temperature
                    )
                    
                # We avoid using context managers with wait=True because it blocks the single Gunicorn worker
                # catching signals when timeout hits. Instead, we use wait=False.
                executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
                fut = executor.submit(_cohere_chat_once)
                
                try:
                    resp = fut.result(timeout=LLM_TIMEOUT_SECONDS)
                    result = resp.text.strip()
                    logger.info(f"llm.cohere_success model={model}")
                except concurrent.futures.TimeoutError:
                    logger.error(f"CoHere API timeout after {LLM_TIMEOUT_SECONDS}s provider={provider} model={model}")
                    result = _get_mock_response(prompt)
                except Exception as llm_err:
                    logger.error(f"CoHere API call failed: {llm_err} provider={provider} model={model}")
                    result = _get_mock_response(prompt)
                finally:
                    # Do not block thread shutdown when leaving this block
                    executor.shutdown(wait=False)
                        
        elif provider == "openai":
            if not openai_client:
                logger.warning("llm.openai_not_configured")
                result = _get_mock_response(prompt)
            else:
                try:
                    # OpenAI timeout is set at client initialization level
                    resp = openai_client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=temperature
                    )
                    result = resp.choices[0].message.content.strip()
                except Exception as e:
                    logger.error(f"OpenAI API call failed: {e}")
                    result = _get_mock_response(prompt)
        else:
            logger.warning(f"llm.unsupported_provider provider={provider}")
            result = _get_mock_response(prompt)
    except Exception as e:
        logger.error(f"llm.call_failed error={e}")
        return None

    # 2. Write to Cache (TTL 24h)
    # Important: Do not cache mock responses
    is_mock = result and (
        "mock response" in result.lower() or 
        ("Mock" in result and "Headline" in result)
    )
    
    if result and not is_mock and redis_client and cache_key:
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

def trim_resume_for_prompt(resume_text, max_length=800):
    """
    Extract only relevant resume sections to reduce token size.
    Returns: first 2-3 sections (summary, top skills, headline) up to max_length chars.
    Reduces LLM input size by 70-80% while preserving context.
    """
    if not resume_text:
        return ""
    
    sections = parse_resume_sections(resume_text)
    trimmed_parts = []
    
    # Add summary (most relevant)
    if 'summary' in sections:
        trimmed_parts.append(sections['summary'][:400])
    elif 'profile' in sections:
        trimmed_parts.append(sections['profile'][:400])
    
    # Add skills list if available
    if 'skills_list_raw' in sections:
        skills_str = ", ".join(sections['skills_list_raw'][:15])  # Top 15 skills
        trimmed_parts.append(f"Key Skills: {skills_str}")
    elif 'skills' in sections:
        trimmed_parts.append(sections['skills'][:300])
    
    # Add top 1-2 experience bullets
    if 'experience' in sections:
        exp_lines = sections['experience'].split('\n')[:2]
        trimmed_parts.append("\n".join(exp_lines)[:400])
    
    trimmed = "\n".join(trimmed_parts)
    return trimmed[:max_length]

def generate_endpoint_cache_key(resume_text, job_description, endpoint_type):
    """
    Generate deterministic cache key for endpoint responses.
    Hash: (resume_text + job_description + endpoint_type)
    Used for /analyze, /estimate-salary, /generate-career-path, /tailor-resume
    """
    raw = f"{endpoint_type}::{hashlib.md5(resume_text.encode()).hexdigest()}::{hashlib.md5(job_description.encode()).hexdigest()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def get_cached_analysis(resume_text, job_description, endpoint_type):
    """
    Check if analysis result is cached.
    Returns cached result if found, None otherwise.
    Cache TTL: 7 days (604800 seconds)
    """
    if not redis_client:
        return None
    
    try:
        cache_key = f"analysis_v2:{generate_endpoint_cache_key(resume_text, job_description, endpoint_type)}"
        cached = redis_client.get(cache_key)
        if cached:
            logger.info(f"cache.analysis_hit endpoint={endpoint_type}")
            return json.loads(cached.decode('utf-8'))
    except Exception as e:
        logger.warning(f"cache.analysis_read_error error={e}")
    
    return None

def cache_analysis_result(resume_text, job_description, endpoint_type, result):
    """
    Save analysis result to cache with 7-day TTL.
    """
    if not redis_client:
        return
    
    try:
        cache_key = f"analysis_v2:{generate_endpoint_cache_key(resume_text, job_description, endpoint_type)}"
        redis_client.setex(cache_key, 604800, json.dumps(result))  # 7 days = 604800 seconds
        logger.info(f"cache.analysis_saved endpoint={endpoint_type}")
    except Exception as e:
        logger.warning(f"cache.analysis_write_error error={e}")

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

def normalize_linkedin_profile(parsed, fallback_text=""):
    """Normalize LinkedIn payload to a stable shape for frontend rendering."""
    parsed = parsed if isinstance(parsed, dict) else {}

    headline = parsed.get("headline")
    if isinstance(headline, dict):
        headline = headline.get("text") or headline.get("value")
    if isinstance(headline, str):
        headline = headline.strip()
    if (
        not isinstance(headline, str)
        or not headline
        or "error parsing" in headline.lower()
        or "could not parse" in headline.lower()
    ):
        headline = "Results-Driven Professional | Data, Analytics, and AI"

    about_value = parsed.get("about")
    if isinstance(about_value, dict):
        about = (
            about_value.get("summary")
            or about_value.get("text")
            or about_value.get("about")
            or ""
        )
    elif isinstance(about_value, list):
        about = "\n\n".join(str(x).strip() for x in about_value if str(x).strip())
    else:
        about = about_value if isinstance(about_value, str) else ""

    if not about.strip() or "error parsing" in about.lower() or "could not parse" in about.lower():
        cleaned = re.sub(r"```(?:json)?", "", fallback_text or "", flags=re.IGNORECASE).replace("```", "").strip()
        if cleaned and "error parsing" not in cleaned.lower() and "could not parse" not in cleaned.lower() and not cleaned.startswith("{"):
            about = cleaned[:1400]
        else:
            about = (
                "I am a results-driven professional with experience in Python, SQL, data analysis, and AI-enabled workflow development. "
                "I focus on turning raw information into practical insight, building reliable solutions, and improving user outcomes through thoughtful execution."
            )

    highlights = (
        parsed.get("experience_highlights")
        or parsed.get("experienceHighlights")
        or parsed.get("highlights")
        or []
    )
    if isinstance(highlights, str):
        highlights = [
            line.strip(" -•\t")
            for line in re.split(r"\r?\n+", highlights)
            if line.strip(" -•\t")
        ]
    elif isinstance(highlights, list):
        cleaned_list = []
        for item in highlights:
            if isinstance(item, str):
                text = item.strip()
            elif isinstance(item, dict):
                text = str(item.get("summary") or item.get("text") or item.get("value") or "").strip()
            else:
                text = str(item).strip()
            if text:
                cleaned_list.append(text)
        highlights = cleaned_list
    else:
        highlights = []

    if not highlights:
        highlights = [
            "Demonstrated strong ownership in building data-driven project outcomes.",
            "Applied Python, SQL, and analytics techniques to improve decision quality.",
            "Built practical AI-enabled workflows with a focus on usability and impact.",
        ]

    return {
        "headline": headline.strip(),
        "about": about.strip(),
        "experience_highlights": highlights[:8],
    }

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

def _extract_quantified_impact_lines(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    quantified = []
    pattern = re.compile(r"\b\d+(?:\.\d+)?\s*(?:%|percent|x|k|m|million|billion|\+)\b", re.IGNORECASE)
    for line in lines:
        if pattern.search(line):
            quantified.append(line)
    return quantified

def build_recruiter_shortlist_dashboard(
    resume_text,
    job_desc_text,
    lexical_score,
    semantic_score,
    combined_score,
    strengths,
    improvement_areas,
):
    required_skills = detect_skills(job_desc_text)
    resume_skills = detect_skills(resume_text)
    matched_skills = sorted(list(set(required_skills).intersection(set(resume_skills))))
    missing_skills = sorted(list(set(required_skills) - set(resume_skills)))
    quantified_lines = _extract_quantified_impact_lines(resume_text)
    resume_word_count = len(re.findall(r"\w+", resume_text or ""))

    skill_coverage = None
    if required_skills:
        skill_coverage = round((len(matched_skills) / len(required_skills)) * 100, 2)

    evidence = []
    if combined_score is not None:
        evidence.append({
            "type": "match_score",
            "title": "Strong overall match",
            "detail": f"Combined match is {combined_score}% (lexical {lexical_score}%, semantic {semantic_score if semantic_score is not None else 'N/A'}%).",
            "confidence": "high" if combined_score >= 70 else "medium",
        })

    if matched_skills:
        evidence.append({
            "type": "skill_alignment",
            "title": "Key skills aligned",
            "detail": f"Matched {len(matched_skills)} required skills: {', '.join(matched_skills[:8])}.",
            "confidence": "high" if len(matched_skills) >= 4 else "medium",
        })

    if strengths:
        evidence.append({
            "type": "strengths",
            "title": "Profile strengths",
            "detail": "; ".join(strengths[:2]),
            "confidence": "medium",
        })

    if quantified_lines:
        evidence.append({
            "type": "impact",
            "title": "Quantified outcomes present",
            "detail": f"Resume includes {len(quantified_lines)} quantified achievement lines.",
            "confidence": "medium",
        })

    risk_flags = []
    if combined_score is not None and combined_score < 58:
        risk_flags.append({
            "severity": "high",
            "title": "Low match score",
            "detail": f"Combined match is {combined_score}%, below common shortlist range.",
        })

    if len(missing_skills) >= 4:
        risk_flags.append({
            "severity": "high",
            "title": "Critical skill gaps",
            "detail": f"Missing {len(missing_skills)} required skills, including {', '.join(missing_skills[:5])}.",
        })
    elif missing_skills:
        risk_flags.append({
            "severity": "medium",
            "title": "Skill gaps to validate",
            "detail": f"Missing skills to verify during screening: {', '.join(missing_skills[:5])}.",
        })

    if resume_word_count < 160:
        risk_flags.append({
            "severity": "medium",
            "title": "Thin resume detail",
            "detail": "Resume appears short; depth of experience may be under-documented.",
        })

    if not quantified_lines:
        risk_flags.append({
            "severity": "low",
            "title": "Limited measurable outcomes",
            "detail": "Few quantified achievements detected, which can weaken evidence of impact.",
        })

    high_risk_count = len([item for item in risk_flags if item["severity"] == "high"])
    baseline = combined_score if combined_score is not None else lexical_score
    confidence_score = max(5, min(99, round((baseline or 0) - (high_risk_count * 5), 2)))

    if (combined_score or 0) >= 72 and high_risk_count == 0 and len(missing_skills) <= 2:
        decision = "shortlisted"
        decision_reason = "High score with manageable risks and strong skill alignment."
    elif (combined_score or 0) >= 58:
        decision = "review"
        decision_reason = "Potential fit, but additional screening is recommended."
    else:
        decision = "hold"
        decision_reason = "Current evidence suggests lower fit for immediate shortlist."

    return {
        "decision": decision,
        "decisionReason": decision_reason,
        "confidenceScore": confidence_score,
        "skillCoveragePercentage": skill_coverage,
        "matchedSkills": matched_skills,
        "missingSkills": missing_skills,
        "evidence": evidence,
        "riskFlags": risk_flags,
        "interviewFocusAreas": improvement_areas[:4] if improvement_areas else [],
    }

def _generate_interview_questions_for_role(resume_excerpt, target_role, top_skills):
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
        if request.method == "OPTIONS":
            return app.make_default_options_response()

        if config.DEV_BYPASS_AUTH:
            # Inject mock user only in dev mode
            return fn({"uid": "dev-user", "email": "dev@local"}, *args, **kwargs)
            
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # Return 401 Unauthorized for missing bearer token on protected endpoints
            return jsonify({"error": "Authorization header with Bearer token is required"}), 401

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
    if request.method == "OPTIONS":
        return app.make_default_options_response()

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

    # Defensive CORS fallback for preflight/edge cases and Vercel preview domains.
    origin = request.headers.get("Origin")
    if origin:
        normalized_allowed = set(allowed_origins if isinstance(allowed_origins, list) else [allowed_origins])
        if (
            origin in normalized_allowed
            or origin.endswith(".vercel.app")
            or origin.startswith("http://localhost")
            or origin.startswith("http://127.0.0.1")
        ):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,PATCH,DELETE,OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = request.headers.get(
                "Access-Control-Request-Headers",
                "Authorization,Content-Type"
            )
            vary = response.headers.get("Vary", "")
            response.headers["Vary"] = f"{vary}, Origin".strip(", ") if vary else "Origin"
    return response

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'version': APP_VERSION,
        'commit': BUILD_COMMIT,
        'time': datetime.utcnow().isoformat() + 'Z'
    })

@app.route('/version', methods=['GET'])
def version():
    return jsonify({'version': APP_VERSION, 'commit': BUILD_COMMIT})

@app.route('/auth/post-login', methods=['POST', 'OPTIONS'])
@auth_required
def auth_post_login(user_info):
    payload = request.get_json(silent=True) or {}
    uid = (user_info.get('uid') or 'unknown').strip()
    email = (payload.get('email') or user_info.get('email') or '').strip()
    display_name = (payload.get('displayName') or user_info.get('name') or 'there').strip()

    # Guest and token-less demo users should not receive onboarding emails.
    if uid.startswith('guest-user'):
        return jsonify({'ok': True, 'welcomeEmailSent': False, 'reason': 'guest_user'})

    if not email:
        return jsonify({'ok': True, 'welcomeEmailSent': False, 'reason': 'missing_email'})

    if has_welcome_email_been_sent(uid):
        return jsonify({'ok': True, 'welcomeEmailSent': False, 'reason': 'already_sent'})

    subject = 'Welcome to AI Job Screening & Coaching Platform'
    body = (
        f"Hi {display_name},\n\n"
        "Welcome to AI Job Screening & Coaching Platform.\n"
        "You can now analyze resumes, generate recruiter content, and track coaching progress from one dashboard.\n\n"
        "If this login was not made by you, please secure your account immediately.\n\n"
        "Thanks,\n"
        "AI Job Screening Team"
    )

    sent = send_email(email, subject, body)
    if sent:
        mark_welcome_email_sent(uid, email)
    return jsonify({'ok': True, 'welcomeEmailSent': bool(sent)})

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

@celery.task(bind=True, name="backend.app.run_analysis_task")
def run_analysis_task(self, mode, resume_text, job_desc_text, recruiter_email, user_info):
    start = time.time()
    
    # Check cache first (0.1s if hit, saves 90+ seconds of LLM call)
    cache_result = get_cached_analysis(resume_text, job_desc_text, mode)
    if cache_result:
        logger.info(f"analysis.cache_used mode={mode} saved_time_seconds={time.time() - start}")
        return cache_result
    
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
        
        # Cache the result for future requests (7 days TTL)
        cache_analysis_result(resume_text, job_desc_text, mode, final_result)
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

        final_result['shortlistDashboard'] = build_recruiter_shortlist_dashboard(
            resume_text=resume_text,
            job_desc_text=job_desc_text,
            lexical_score=match_percentage,
            semantic_score=semantic_score,
            combined_score=combined,
            strengths=final_result.get("strengths", []),
            improvement_areas=final_result.get("improvementAreas", []),
        )
            
        final_result["formattedReport"] = format_report(final_result)
        
        # Cache the result for future requests (7 days TTL)
        cache_analysis_result(resume_text, job_desc_text, mode, final_result)
        return final_result
    
    return {"error": "Invalid mode"}

@celery.task(bind=True, name="backend.app.estimate_salary_task")
def estimate_salary_task(self, resume_text, job_description, user_id="anonymous"):
    """
    Background task: Estimate salary based on resume and job description.
    Includes India salary benchmarks (2025-2026).
    Uses trimmed resume to reduce tokens and improve speed.
    """
    try:
        # Try to detect role from resume
        resume_lower = resume_text.lower()
        detected_role = None
        
        # Try to match known roles
        role_keywords = {
            "junior_developer": ["junior", "entry level", "fresher"],
            "mid_level_developer": ["mid level", "mid-level", "experience"],
            "senior_developer": ["senior", "lead", "architect"],
            "data_scientist": ["data scientist", "ml", "machine learning"],
            "devops_engineer": ["devops", "infrastructure", "kubernetes"],
            "qa_engineer": ["qa engineer", "test", "quality assurance"],
        }
        
        for role, keywords in role_keywords.items():
            if any(kw in resume_lower for kw in keywords):
                detected_role = role
                break
        
        benchmark = None
        if detected_role and detected_role in INDIA_SALARY_BENCHMARKS:
            benchmark = INDIA_SALARY_BENCHMARKS[detected_role]
        
        # Use trimmed resume to reduce tokens
        trimmed_resume = trim_resume_for_prompt(resume_text, max_length=800)
        trimmed_jd = job_description[:800] if job_description else ""
        
        prompt = f'''Based on candidate resume and job description, estimate salary for India market 2025-2026.
        
RESUME (KEY SECTIONS):
{trimmed_resume}

JOB DESCRIPTION:
{trimmed_jd}

You MUST return the output as a valid and strict JSON object using the exact schema below. Do not include any markdown formatting, preamble, or conversational text.

{{
    "estimated_salary_range": "string (e.g. ₹50L - ₹75L p.a.)",
    "currency": "INR",
    "experience_level": "string",
    "market_trends": "string",
    "negotiation_tips": ["string", "string", "string"],
    "job_market_analysis": "string"
}}'''
        
        response = call_llm(prompt, temperature=0.5)
        if not response:
            if benchmark:
                return {
                    "estimated_salary_range": f"₹{benchmark['min']/100000:.0f}L - ₹{benchmark['max']/100000:.0f}L p.a.",
                    "currency": "INR",
                    "experience_level": benchmark.get("experience", "Not specified"),
                    "market_trends": f"Strong market demand for {detected_role} in 2025-2026.",
                    "negotiation_tips": ["Highlight relevant experience", "Research market rates", "Emphasize unique skills"],
                    "job_market_analysis": "Strong demand in Indian IT market. Remote opportunities available.",
                    "source": "benchmark"
                }
            return {"error": "Failed to estimate salary"}
        
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            result = json.loads(response)
            result["source"] = "ai_generated"
        except:
            result = {"raw_response": response, "source": "raw"}
        
        try:
            save_analysis(user_id=user_id, mode="salary_estimation", result=result, resume_excerpt=resume_text[:500], job_desc_excerpt=job_description[:500])
        except Exception as e:
            logger.warning(f"Failed to save salary estimation: {e}")
        
        return result
    
    except Exception as e:
        logger.error(f"Salary estimation task failed: {e}")
        return {"error": str(e)}

@celery.task(bind=True, name="backend.app.generate_career_path_task")
def generate_career_path_task(self, resume_text, user_id="anonymous"):
    """
    Background task: Generate career roadmap based on resume.
    Uses trimmed resume to reduce tokens and improve speed.
    """
    try:
        trimmed_resume = trim_resume_for_prompt(resume_text, max_length=800)
        
        prompt = f'''Analyze the candidate's resume and suggest a long-term career path roadmap.

RESUME (KEY SECTIONS):
{trimmed_resume}

You MUST return the output as a valid and strict JSON object using the exact schema below. Do not include any markdown formatting, preamble, or conversational text.

{{
    "current_level": "string (e.g., Junior, Mid, Senior)",
    "career_roadmap": [
        {{
            "role": "string (Job title)",
            "timeline": "string (Estimated years to reach this)",
            "skills_needed": "string (Key skills to acquire)"
        }}
    ]
}}'''
        
        response = call_llm(prompt, temperature=0.7)
        if not response:
            return {"error": "Failed to generate career path"}
        
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            result = json.loads(response)
        except:
            result = {"raw_response": response}
        
        try:
            save_analysis(user_id=user_id, mode="career_path", result=result, resume_excerpt=resume_text[:500])
        except Exception as e:
            logger.warning(f"Failed to save career path: {e}")
        
        return result
    
    except Exception as e:
        logger.error(f"Career path generation task failed: {e}")
        return {"error": str(e)}

@celery.task(bind=True, name="backend.app.tailor_resume_task")
def tailor_resume_task(self, resume_text, job_description, user_id="anonymous"):
    """
    Background task: Tailor resume to job description.
    Uses trimmed resume to reduce tokens and improve speed.
    """
    try:
        trimmed_resume = trim_resume_for_prompt(resume_text, max_length=800)
        trimmed_jd = job_description[:800] if job_description else ""
        
        prompt = f'''Rewrite the candidate's resume summary and key experience bullet points to better align with the job description keywords and requirements.

RESUME (KEY SECTIONS):
{trimmed_resume}

JOB DESCRIPTION:
{trimmed_jd}

You MUST return the output as a valid and strict JSON object using the exact schema below. Do not include any markdown formatting, preamble, or conversational text.

{{
    "rewritten_summary": "string (A professional summary tailored to the job)",
    "tailored_bullets": [
        {{
            "original": "string (The original text)",
            "rewritten": "string (The improved text aligning with the job description)"
        }}
    ]
}}'''
        
        response = call_llm(prompt, temperature=0.7)
        if not response:
            return {"error": "Failed to tailor resume"}
        
        try:
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            result = json.loads(response)
        except:
            result = {"raw_response": response}
        
        try:
            save_analysis(user_id=user_id, mode="tailor_resume", result=result, resume_excerpt=resume_text[:500], job_desc_excerpt=job_description[:500])
        except Exception as e:
            logger.warning(f"Failed to save tailor resume: {e}")
        
        return result
    
    except Exception as e:
        logger.error(f"Tailor resume task failed: {e}")
        return {"error": str(e)}

@app.route('/tasks/<task_id>', methods=['GET'])
@cross_origin()
def get_task_status(task_id):
    try:
        task = celery.AsyncResult(task_id)
        state = (task.state or '').upper()

        if state in ('PENDING', 'RECEIVED', 'RETRY'):
            return jsonify({
                'state': state,
                'status': 'Pending...'
            })
        if state in ('STARTED',):
            return jsonify({
                'state': state,
                'status': 'Processing...'
            })
        if state == 'SUCCESS':
            return jsonify({
                'state': state,
                'result': task.result
            })

        return jsonify({
            'state': state or 'FAILURE',
            'error': str(task.info)
        })
    except Exception as e:
        logger.error(f"Error fetching celery task status: {e}")
        return jsonify({'state': 'FAILURE', 'error': str(e)}), 500


# Backward-compatible task aliases for jobs queued by older/local clients as __main__.*
@celery.task(bind=True, name="__main__.estimate_salary_task")
def estimate_salary_task_legacy(self, resume_text, job_description, user_id="anonymous"):
    return estimate_salary_task.run(resume_text, job_description, user_id)


@celery.task(bind=True, name="__main__.generate_career_path_task")
def generate_career_path_task_legacy(self, resume_text, user_id="anonymous"):
    return generate_career_path_task.run(resume_text, user_id)


@celery.task(bind=True, name="__main__.tailor_resume_task")
def tailor_resume_task_legacy(self, resume_text, job_description, user_id="anonymous"):
    return tailor_resume_task.run(resume_text, job_description, user_id)


@celery.task(bind=True, name="__main__.run_analysis_task")
def run_analysis_task_legacy(self, mode, resume_text, job_desc_text, recruiter_email, user_info):
    return run_analysis_task.run(mode, resume_text, job_desc_text, recruiter_email, user_info)

@app.route("/analyze", methods=["POST"])
@cross_origin()
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
        if not resume_text or len(resume_text.strip()) < 40:
             return jsonify({"error": "Resume text is required and must be at least 40 characters"}), 400
        
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

    # Optional async mode for higher-capacity deployments.
    if ASYNC_TASKS_ENABLED:
        try:
            task = run_analysis_task.apply_async(
                args=[mode, resume_text, job_desc_text, recruiter_email, user_info],
                timeout=600,
            )

            return jsonify({
                "status": "queued",
                "job_id": task.id,
                "mode": mode
            }), 202

        except Exception as e:
            logger.warning(f"Async queue unavailable ({e}), executing synchronously")

    # Synchronous execution path (default for reliability on small instances).
    result = run_analysis_task.run(mode, resume_text, job_desc_text, recruiter_email, user_info)

    # Save to MongoDB
    save_analysis(
        user_id=user_info.get("uid", "anonymous"),
        mode=mode,
        result=result,
        resume_excerpt=resume_text[:500],
        job_desc_excerpt=job_desc_text[:500],
    )

    elapsed = round((time.time() - start) * 1000)
    _metrics['analyze']['count'] += 1
    _metrics['analyze']['avgMs'] = round(
        (_metrics['analyze']['avgMs'] * (_metrics['analyze']['count'] - 1) + elapsed) / _metrics['analyze']['count'], 1
    )
    write_audit(user_info.get('uid'), 'analyze', {'mode': mode, 'ms': elapsed})
    dispatch_event('analysis.completed', {
        'mode': mode,
        'userId': user_info.get('uid'),
        'matchPercentage': result.get('combinedMatchPercentage') or result.get('semanticMatchPercentage'),
        'notifyEmail': request.form.get('recruiterEmail') if not request.is_json else (request.json or {}).get('recruiterEmail')
    })

    if isinstance(result, dict):
        result.setdefault("execution_mode", "sync")
    return jsonify(result)

@app.route("/status/<job_id>", methods=["GET"])
def job_status(job_id):
    # 1) Try RQ jobs first (used by /analyze)
    try:
        from rq.job import Job
        from rq.exceptions import NoSuchJobError

        redis_conn = None
        try:
            from backend.queue_config import redis_conn as _redis_conn
            redis_conn = _redis_conn
        except Exception:
            try:
                from queue_config import redis_conn as _redis_conn
                redis_conn = _redis_conn
            except Exception:
                redis_conn = None

        if redis_conn:
            try:
                job = Job.fetch(job_id, connection=redis_conn)
                rq_status = (job.get_status() or '').lower()
                if rq_status == 'finished':
                    return jsonify({'status': 'finished', 'result': job.result})
                if rq_status == 'failed':
                    return jsonify({'status': 'failed', 'error': str(job.exc_info)})
                return jsonify({'status': rq_status or 'queued'})
            except NoSuchJobError:
                pass
            except Exception as e:
                # Some RQ versions raise a generic exception for missing jobs.
                if 'No such job' in str(e):
                    pass
                else:
                    logger.warning(f"RQ job fetch error for {job_id}: {e}")
    except Exception as e:
        # Keep endpoint resilient for environments without RQ wired correctly.
        logger.warning(f"RQ status lookup unavailable: {e}")

    # 2) Fallback to Celery tasks (used by salary/tailor/career)
    try:
        task = celery.AsyncResult(job_id)
        state = (task.state or '').upper()

        if state == 'SUCCESS':
            return jsonify({'status': 'finished', 'result': task.result})
        if state in ('PENDING', 'RECEIVED', 'RETRY'):
            return jsonify({'status': 'queued'})
        if state in ('STARTED',):
            return jsonify({'status': 'started'})
        if state in ('FAILURE', 'REVOKED'):
            return jsonify({'status': 'failed', 'error': str(task.info)})
    except Exception as e:
        logger.warning(f"Celery status lookup unavailable: {e}")

    # 3) Unknown ID in both backends
    return jsonify({
        'status': 'unknown',
        'message': 'Job not found. It may have completed and been cleaned up.'
    }), 404

# =============================
# History / Dashboard Endpoint
# =============================
@app.route("/history", methods=["GET"])
@auth_required
def history(user_info):
    user_id = user_info.get("uid")
    try:
        limit = min(int(request.args.get("limit", "20")), 100)
    except (ValueError, TypeError):
        limit = 20
    records = get_user_history(user_id, limit=limit)
    write_audit(user_id, 'history.view', {'count': len(records)})
    return jsonify({"history": records, "count": len(records)})

# =============================
# PDF Download Endpoints
# =============================
@app.route("/download/analysis-pdf", methods=["POST"])
@app.route("/api/download/analysis-pdf", methods=["POST"])
@auth_required
def download_analysis_pdf(user_info):
    """Generate and download analysis report as PDF."""
    if not generate_job_seeker_pdf:
        return jsonify({"error": "PDF generation not available"}), 503
    
    try:
        data = request.get_json() or {}
        result_data = data.get('result', {})
        mode = data.get('mode', 'jobSeeker')
        candidate_name = data.get('candidateName', 'Candidate')
        
        if mode == 'recruiter':
            pdf_buffer = generate_recruiter_pdf(result_data, candidate_name)
            filename = f"recruiter-analysis-{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        else:
            pdf_buffer = generate_job_seeker_pdf(result_data)
            filename = f"analysis-{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        write_audit(user_info.get('uid'), 'download.analysis_pdf', {'mode': mode})
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return jsonify({"error": f"Failed to generate PDF: {str(e)}"}), 500


@app.route("/download/cover-letter-pdf", methods=["POST"])
@app.route("/api/download/cover-letter-pdf", methods=["POST"])
@auth_required
def download_cover_letter_pdf(user_info):
    """Generate and download cover letter as PDF."""
    if not generate_cover_letter_pdf:
        return jsonify({"error": "PDF generation not available"}), 503
    
    try:
        data = request.get_json() or {}
        cover_letter_text = data.get('coverLetter', '')
        candidate_name = data.get('candidateName', '')
        
        if not cover_letter_text:
            return jsonify({"error": "Cover letter text is required"}), 400
        
        pdf_buffer = generate_cover_letter_pdf(cover_letter_text, candidate_name)
        filename = f"cover-letter-{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        write_audit(user_info.get('uid'), 'download.cover_letter_pdf', {})
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return jsonify({"error": f"Failed to generate PDF: {str(e)}"}), 500


@app.route("/download/coaching-pdf", methods=["POST"])
@app.route("/api/download/coaching-pdf", methods=["POST"])
@auth_required
def download_coaching_pdf(user_info):
    """Generate and download coaching report as PDF."""
    if not generate_coaching_report_pdf:
        return jsonify({"error": "PDF generation not available"}), 503
    
    try:
        data = request.get_json() or {}
        coaching_data = data.get('data', {})
        report_type = data.get('type', 'progress')  # progress, study_pack, interview
        
        pdf_buffer = generate_coaching_report_pdf(coaching_data, report_type)
        filename = f"coaching-{report_type}-{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        write_audit(user_info.get('uid'), 'download.coaching_pdf', {'type': report_type})
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return jsonify({"error": f"Failed to generate PDF: {str(e)}"}), 500



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
    questions = _generate_interview_questions_for_role(
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
@cross_origin()
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
@cross_origin()
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
@cross_origin()
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
@cross_origin()
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
@cross_origin()
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
@cross_origin()
@auth_required
@rate_limit(max_requests=10, per_seconds=60)
def generate_linkedin_profile(user_info):
    if 'resume' not in request.files:
        return jsonify({'error': 'No resume file provided'}), 400
    
    try:
        resume_file = request.files['resume']
        resume_text = extract_text_from_pdf(resume_file)
        
        if not resume_text:
             return jsonify({'error': 'Could not extract text from resume'}), 400

        prompt = f'''
        You are an expert career consultant. Create a professional LinkedIn profile based on the resume below.
        
        RESUME:
        {resume_text[:3000]}
        
        You MUST return the output as a valid and strict JSON object using the exact schema below. Do not include any markdown formatting, preamble, or conversational text.

        {{
            "headline": "string (A catchy professional headline)",
            "about": "string (A compelling About summary)",
            "experience_highlights": ["string"]
        }}
        '''
        
        response = call_llm(prompt, temperature=0.7)
        if not response:
            return jsonify({'error': 'Failed to generate profile'}), 500
            
        parsed = extract_json_from_text(response)
        if parsed is None:
            # Fallback for responses that are plain JSON without wrappers.
            try:
                clean_response = re.sub(r"```(?:json)?", "", response, flags=re.IGNORECASE).replace("```", "").strip()
                parsed = json.loads(clean_response)
            except Exception:
                parsed = {}

        result = normalize_linkedin_profile(parsed, fallback_text=response)
            
        return jsonify(result)
    except Exception as e:
        logger.error(f"Error in generate_linkedin_profile: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/analyze-mock-interview', methods=['POST'])
@cross_origin()
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
    
    You MUST return the output as a valid and strict JSON object using the exact schema below. Do not include any markdown formatting, preamble, or conversational text.

    {{
        "score": number (0-100),
        "feedback": "string",
        "strengths": ["string"],
        "improvements": ["string"]
    }}
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
@cross_origin()
@auth_required
@rate_limit(max_requests=10, per_seconds=60)
def estimate_salary(user_info):
    """Queue salary estimation as an async task to avoid Gunicorn timeouts."""
    if 'resume' not in request.files:
        return jsonify({'error': 'No resume file provided'}), 400
    
    resume_file = request.files['resume']
    job_description = request.form.get('jobDescription', '')
    resume_text = extract_text_from_pdf(resume_file)
    
    if ASYNC_TASKS_ENABLED:
        try:
            task = estimate_salary_task.apply_async(
                args=[resume_text, job_description, user_info.get("uid", "anonymous")],
                timeout=300  # 5 minutes - extended for Cohere API calls
            )
            return jsonify({
                "status": "queued",
                "job_id": task.id,
                "mode": "salary_estimation"
            }), 202
        except Exception as e:
            logger.warning(f"Celery task queue failed: {e}, falling back to sync")

    result = estimate_salary_task.run(
        resume_text,
        job_description,
        user_info.get("uid", "anonymous")
    )
    return jsonify(result)

@app.route('/tailor-resume', methods=['POST'])
@cross_origin()
@auth_required
@rate_limit(max_requests=10, per_seconds=60)
def tailor_resume(user_info):
    """Queue resume tailoring as async task to avoid Gunicorn timeouts."""
    if 'resume' not in request.files:
        return jsonify({'error': 'No resume file provided'}), 400
    
    resume_file = request.files['resume']
    job_description = request.form.get('jobDescription', '')
    resume_text = extract_text_from_pdf(resume_file)
    
    if not resume_text:
        return jsonify({'error': 'Failed to extract resume text'}), 400
    
    if ASYNC_TASKS_ENABLED:
        try:
            task = tailor_resume_task.apply_async(
                args=[resume_text, job_description, user_info.get("uid", "anonymous")],
                timeout=300  # 5 minutes - extended for Cohere API calls
            )
            return jsonify({
                "status": "queued",
                "job_id": task.id,
                "mode": "tailor_resume"
            }), 202
        except Exception as e:
            logger.warning(f"Celery task queue failed: {e}, falling back to sync")

    result = tailor_resume_task.run(
        resume_text,
        job_description,
        user_info.get("uid", "anonymous")
    )
    return jsonify(result)

@app.route('/generate-career-path', methods=['POST'])
@cross_origin()
@auth_required
@rate_limit(max_requests=10, per_seconds=60)
def generate_career_path(user_info):
    """Queue career path generation as async task to avoid Gunicorn timeouts."""
    if 'resume' not in request.files:
        return jsonify({'error': 'No resume file provided'}), 400
    
    resume_file = request.files['resume']
    resume_text = extract_text_from_pdf(resume_file)
    
    if not resume_text:
        return jsonify({'error': 'Failed to extract resume text'}), 400
    
    if ASYNC_TASKS_ENABLED:
        try:
            task = generate_career_path_task.apply_async(
                args=[resume_text, user_info.get("uid", "anonymous")],
                timeout=300  # 5 minutes - extended for Cohere API calls
            )
            return jsonify({
                "status": "queued",
                "job_id": task.id,
                "mode": "career_path"
            }), 202
        except Exception as e:
            logger.warning(f"Celery task queue failed: {e}, falling back to sync")

    result = generate_career_path_task.run(
        resume_text,
        user_info.get("uid", "anonymous")
    )
    return jsonify(result)

@app.route('/generate-job-description', methods=['POST'])
@cross_origin()
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
    
    Return a JSON object with a "job_description" key containing exactly this structure:
    {{
      "title": "String",
      "overview": "String",
      "responsibilities": ["List of strings"],
      "skills_and_experience": {{
        "required": ["List of required skills and experience"],
        "preferred": ["List of preferred skills"]
      }},
      "benefits": ["List of benefits"]
    }}
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

@app.route('/recruiter/templates', methods=['GET'])
@cross_origin()
@auth_required
def list_recruiter_templates(user_info):
    user_id = user_info.get("uid")
    kind = request.args.get("kind")
    if kind and kind not in ["email", "job_description"]:
        return jsonify({"error": "Invalid kind"}), 400

    templates = _list_recruiter_templates(user_id, kind=kind)
    summaries = []
    for item in templates:
        versions = item.get("versions", [])
        latest = versions[-1] if versions else {}
        content = latest.get("content")
        preview = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
        summaries.append({
            "id": item.get("id"),
            "kind": item.get("kind"),
            "title": item.get("title"),
            "createdAt": item.get("createdAt"),
            "updatedAt": item.get("updatedAt"),
            "latestVersion": len(versions),
            "preview": (preview or "")[:220],
        })

    write_audit(user_id, 'recruiter.templates.list', {'count': len(summaries), 'kind': kind or 'all'})
    return jsonify({"templates": summaries})

@app.route('/recruiter/templates/<template_id>', methods=['GET'])
@cross_origin()
@auth_required
def get_recruiter_template(user_info, template_id):
    user_id = user_info.get("uid")
    template = _get_recruiter_template(user_id, template_id)
    if not template:
        return jsonify({"error": "Template not found"}), 404
    write_audit(user_id, 'recruiter.templates.get', {'templateId': template_id})
    return jsonify({"template": template})

@app.route('/recruiter/templates', methods=['POST'])
@cross_origin()
@auth_required
@rate_limit(max_requests=20, per_seconds=60)
def save_recruiter_template(user_info):
    user_id = user_info.get("uid")
    data = request.get_json(silent=True) or {}
    kind = (data.get("kind") or "").strip()
    title = (data.get("title") or "").strip()
    content = data.get("content")
    metadata = data.get("metadata") or {}
    template_id = data.get("templateId")

    if kind not in ["email", "job_description"]:
        return jsonify({"error": "kind must be email or job_description"}), 400
    if content is None or (isinstance(content, str) and not content.strip()):
        return jsonify({"error": "content is required"}), 400
    if metadata and not isinstance(metadata, dict):
        return jsonify({"error": "metadata must be an object"}), 400

    saved = _save_recruiter_template(
        user_id=user_id,
        kind=kind,
        title=title,
        content=content,
        metadata=metadata,
        template_id=template_id,
    )
    write_audit(user_id, 'recruiter.templates.save', {'templateId': saved.get('id'), 'kind': kind, 'version': len(saved.get('versions', []))})
    return jsonify({"template": saved})

@app.route('/resume-health-check', methods=['POST'])
@cross_origin()
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
    
    You MUST return the output as a valid and strict JSON object using the exact schema below. Do not include any markdown formatting, preamble, or conversational text.

    {{
        "score": number (0-100),
        "summary": "string",
        "checks": [
            {{
                "category": "string (e.g., Impact, Formatting, Action Verbs)",
                "status": "string (pass, warning, or fail)",
                "feedback": "string"
            }}
        ],
        "improvements": ["string"]
    }}
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
@cross_origin()
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
    
    You MUST return the output as a valid and strict JSON object using the exact schema below. Do not include any markdown formatting, preamble, or conversational text.

    {{
        "boolean_string": "string (e.g., (Java OR Kotlin) AND (Android) AND (Senior OR Lead))",
        "explanation": "string (Why these keywords and operators were chosen)"
    }}
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
@cross_origin()
@auth_required
@rate_limit(max_requests=10, per_seconds=60)
def generate_networking_message(user_info):
    try:
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
        
        You MUST return the output as a valid and strict JSON object using the exact schema below. Do not include any markdown formatting, preamble, or conversational text.

        {{
            "subject": "string (If applicable, otherwise empty)",
            "message": "string (The message body)",
            "tips": ["string"]
        }}
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
    except Exception as e:
        logger.error(f"Error in generate_networking_message: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)

