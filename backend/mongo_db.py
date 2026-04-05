# DATABASE LAYER: MongoDB integration for persisting user analysis history and coaching version data with graceful fallback
import certifi
import logging
import os

logger = logging.getLogger("resume_analyzer")

# Load Mongo URI from environment variable
MONGO_URI = os.getenv("MONGO_URI")

# Lazy connection — only connect when actually needed
_client = None
_db = None
analysis_collection = None
users_collection = None

MONGO_AVAILABLE = False


def get_db():
    """Lazily connect to MongoDB. Returns (db, True) or (None, False)."""
    global _client, _db, analysis_collection, users_collection, MONGO_AVAILABLE
    if _db is not None:
        return _db, MONGO_AVAILABLE
    if not MONGO_URI:
        logger.warning("MONGO_URI not set — database features disabled")
        return None, False
    try:
        from pymongo import MongoClient
        _client = MongoClient(MONGO_URI, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)
        _client.admin.command("ping")  # verify connection
        _db = _client["resumeAnalyzer"]
        analysis_collection = _db["analysis_results"]
        users_collection = _db["users"]
        MONGO_AVAILABLE = True
        logger.info("Connected to MongoDB Atlas successfully")
    except Exception as e:
        logger.warning(f"MongoDB connection failed: {e} — database features disabled")
        MONGO_AVAILABLE = False
    return _db, MONGO_AVAILABLE


def save_analysis(user_id, mode, result, resume_excerpt="", job_desc_excerpt=""):
    """Save an analysis result to MongoDB."""
    from datetime import datetime
    db, available = get_db()
    if not available or analysis_collection is None:
        return None
    try:
        doc = {
            "userId": user_id,
            "mode": mode,
            "result": result,
            "resumeExcerpt": resume_excerpt[:500],
            "jobDescExcerpt": job_desc_excerpt[:500],
            "createdAt": datetime.utcnow(),
        }
        inserted = analysis_collection.insert_one(doc)
        return str(inserted.inserted_id)
    except Exception as e:
        logger.error(f"mongo.save_analysis_error: {e}")
        return None


def get_user_history(user_id, limit=20):
    """Retrieve past analyses for a user."""
    db, available = get_db()
    if not available or analysis_collection is None:
        return []
    try:
        cursor = (
            analysis_collection.find({"userId": user_id}, {"resumeExcerpt": 0})
            .sort("createdAt", -1)
            .limit(limit)
        )
        results = []
        for doc in cursor:
            doc["_id"] = str(doc["_id"])
            if "createdAt" in doc:
                doc["createdAt"] = doc["createdAt"].isoformat() + "Z"
            results.append(doc)
        return results
    except Exception as e:
        logger.error(f"mongo.get_history_error: {e}")
        return []
