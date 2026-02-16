import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Centralized configuration for the Resume Analyzer backend.

    All environment variables are loaded via python-dotenv (if a .env file exists)
    to simplify local development while remaining 12-factor friendly in production.
    """

    APP_VERSION: str = os.getenv("APP_VERSION", "0.4.1-fix")
    DEV_BYPASS_AUTH: bool = os.getenv("DEV_BYPASS_AUTH", "1") == "1"
    ALLOWED_ORIGINS: str = os.getenv("ALLOWED_ORIGINS", "*")

    FIREBASE_CREDENTIAL_PATH: str = os.getenv(
        "FIREBASE_CREDENTIAL_PATH", "Backend_old/firebase-service-account.json"
    )

    COHERE_API_KEY: str | None = os.getenv("COHERE_API_KEY")
    OPENAI_API_KEY: str | None = os.getenv("OPENAI_API_KEY")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "cohere:command-r-08-2024")

    DATA_DIR: str = os.getenv("DATA_DIR", "data")

    SMTP_HOST: str | None = os.getenv("SMTP_HOST")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str | None = os.getenv("SMTP_USER")
    SMTP_PASS: str | None = os.getenv("SMTP_PASS")

    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

    SMTP_PASS: str | None = os.getenv("SMTP_PASS")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "no-reply@example.com")
    WEBHOOK_URL: str | None = os.getenv("WEBHOOK_URL")


def init_directories(config: Config) -> None:
    """Ensure required persistence directories exist."""
    data_dir = config.DATA_DIR
    coaching_dir = os.path.join(data_dir, "coaching")
    audit_dir = os.path.join(data_dir, "audit")
    os.makedirs(coaching_dir, exist_ok=True)
    os.makedirs(audit_dir, exist_ok=True)


def configure_logging() -> None:
    """Set up basic structured logging.

    Uses a single stdout handler to remain container-friendly.
    """
    import logging, sys, json, time

    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            payload = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            # Inject Correlation ID if available in Flask context
            try:
                from flask import has_request_context, g
                if has_request_context() and hasattr(g, "request_id"):
                     payload["requestId"] = g.request_id
            except ImportError:
                pass

            if record.exc_info:
                payload["exception"] = self.formatException(record.exc_info)
            return json.dumps(payload, ensure_ascii=False)

    root = logging.getLogger("resume_analyzer")
    if root.handlers:
        return  # already configured
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)


__all__ = ["Config", "init_directories", "configure_logging"]
