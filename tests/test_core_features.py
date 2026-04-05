"""
Comprehensive tests for the AI Job Screening Resume Analyzer.
Covers: health endpoints, auth, resume parsing, analysis, coaching,
cover letter, skill gap, rate limiting, MongoDB integration, and more.
"""
import os
import sys
import json
import io
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime

# Ensure environment is set for testing
os.environ.setdefault("DEV_BYPASS_AUTH", "1")
os.environ.setdefault("APP_VERSION", "1.0.0-test")
os.environ.setdefault("FIREBASE_CREDENTIAL_PATH", "backend/firebase-service-account.json")


@pytest.fixture(scope="module")
def app_module():
    """Import the app module once for all tests in this file."""
    from backend.app import app
    return app


@pytest.fixture()
def client(app_module):
    """Create a Flask test client."""
    app_module.config["TESTING"] = True
    with app_module.test_client() as c:
        yield c


# =============================
# 1. Health & System Endpoints
# =============================
class TestHealthEndpoints:
    def test_health_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.get_json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "time" in data

    def test_version_endpoint(self, client):
        r = client.get("/version")
        assert r.status_code == 200
        data = r.get_json()
        assert "version" in data

    def test_metrics_endpoint(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200
        data = r.get_json()
        assert "uptimeSeconds" in data

    def test_sys_info(self, client):
        r = client.get("/internal/sys-info")
        assert r.status_code == 200
        data = r.get_json()
        assert "platform" in data
        assert "python_version" in data
        assert "cpu_count" in data

    def test_process_info(self, client):
        r = client.get("/internal/process-info")
        assert r.status_code == 200
        data = r.get_json()
        assert "pid" in data
        assert "thread_count" in data

    def test_network_info(self, client):
        r = client.get("/internal/network-info")
        assert r.status_code == 200
        data = r.get_json()
        assert "hostname" in data

    def test_thread_info(self, client):
        r = client.get("/internal/thread-info")
        assert r.status_code == 200
        data = r.get_json()
        assert "total_threads" in data

    def test_gc_info(self, client):
        r = client.get("/internal/gc-info")
        assert r.status_code == 200
        data = r.get_json()
        assert "gc_enabled" in data

    def test_time_info(self, client):
        r = client.get("/internal/time-info")
        assert r.status_code == 200
        data = r.get_json()
        assert "current_time" in data

    def test_root_index(self, client):
        r = client.get("/")
        assert r.status_code == 200


# =============================
# 2. Authentication Tests
# =============================
class TestAuthentication:
    def test_analyze_without_auth_in_dev_mode(self, client):
        """With DEV_BYPASS_AUTH=1, requests should succeed with dev user."""
        r = client.post("/analyze", json={
            "mode": "jobSeeker",
            "resume": "Experienced Python developer with 5 years of experience in Flask and Django."
        })
        # Should not return 401
        assert r.status_code != 401

    def test_coaching_progress_dev_mode(self, client):
        """Auth-protected endpoints should work in dev mode."""
        r = client.get("/coaching/progress")
        assert r.status_code == 200

    def test_security_headers_present(self, client):
        """Verify security headers are set on responses."""
        r = client.get("/health")
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert "strict-origin" in r.headers.get("Referrer-Policy", "")
        assert "X-Request-ID" in r.headers

    def test_request_id_propagation(self, client):
        """Custom X-Request-ID should be echoed back."""
        r = client.get("/health", headers={"X-Request-ID": "test-req-123"})
        assert r.headers.get("X-Request-ID") == "test-req-123"


# =============================
# 3. Resume Parsing Tests
# =============================
class TestResumeParsing:
    def test_parse_resume_sections(self):
        from backend.app import parse_resume_sections
        text = """Summary
Experienced developer with 5 years
Skills
Python, Java, Docker, Kubernetes
Experience
Senior Dev at TechCo - 3 years
Education
B.Tech Computer Science"""
        sections = parse_resume_sections(text)
        assert "summary" in sections
        assert "skills" in sections
        assert "experience" in sections
        assert "education" in sections

    def test_detect_skills(self):
        from backend.app import detect_skills
        text = "I am proficient in Python, React, Docker, and AWS with experience in machine learning"
        skills = detect_skills(text)
        assert "python" in skills
        assert "react" in skills
        assert "docker" in skills
        assert "aws" in skills
        assert "machine learning" in skills

    def test_detect_skill_gaps(self):
        from backend.app import detect_skill_gaps
        resume_skills = ["python", "react"]
        job_text = "Looking for Python, React, Docker, Kubernetes, and AWS experience"
        gaps = detect_skill_gaps(resume_skills, job_text)
        assert "docker" in gaps
        assert "kubernetes" in gaps
        assert "aws" in gaps
        assert "python" not in gaps  # already have it

    def test_extract_bullets(self):
        from backend.app import extract_bullets
        text = """- Built scalable microservices
- Reduced latency by 40%
• Led a team of 5 engineers
Short line"""
        bullets = extract_bullets(text)
        assert len(bullets) >= 3

    def test_compute_basic_metrics(self):
        from backend.app import compute_basic_metrics
        text = "Python developer with experience in building scalable applications and machine learning models"
        bullets = ["Built ML pipeline", "Reduced errors by 50%"]
        skills = ["python", "machine learning"]
        gaps = ["docker"]
        metrics = compute_basic_metrics(text, bullets, skills, gaps)
        assert "wordCount" in metrics
        assert "bulletCount" in metrics
        assert metrics["bulletCount"] == 2
        assert "skillCoverageRatio" in metrics
        assert 0 <= metrics["skillCoverageRatio"] <= 1


# =============================
# 4. Semantic Matching Tests
# =============================
class TestSemanticMatching:
    def test_compute_semantic_match(self):
        from backend.app import compute_semantic_match
        resume = "Python developer experienced in Flask web APIs and machine learning with TensorFlow"
        jd = "Looking for Python developer with Flask and machine learning experience"
        score = compute_semantic_match(resume, jd)
        assert score is not None
        assert 0 <= score <= 100
        # These texts are very similar, score should be high
        assert score > 30

    def test_semantic_match_empty_inputs(self):
        from backend.app import compute_semantic_match
        assert compute_semantic_match("", "some text") is None
        assert compute_semantic_match("some text", "") is None

    def test_semantic_match_dissimilar_texts(self):
        from backend.app import compute_semantic_match
        resume = "Chef with 10 years experience in French cuisine and pastry"
        jd = "Looking for quantum physicist with PhD in particle physics"
        score = compute_semantic_match(resume, jd)
        assert score is not None
        # Very different texts should have a lower score
        assert score < 50


# =============================
# 5. Analysis Endpoint Tests
# =============================
class TestAnalyzeEndpoint:
    def test_analyze_invalid_mode(self, client):
        r = client.post("/analyze", json={
            "mode": "invalid",
            "resume": "Test resume"
        })
        assert r.status_code == 400
        assert "Invalid mode" in r.get_json()["error"]

    def test_analyze_missing_resume(self, client):
        r = client.post("/analyze", json={
            "mode": "jobSeeker"
        })
        # Either 400 for missing resume or empty resume
        assert r.status_code == 400

    @patch("backend.app.call_llm")
    def test_analyze_jobseeker_json(self, mock_llm, client):
        """Test job seeker analysis with mocked LLM."""
        mock_llm.return_value = json.dumps({
            "strengths": ["Python expert", "Fast learner"],
            "improvementAreas": ["System design", "Public speaking"],
            "recommendedRoles": ["Backend Developer", "ML Engineer"],
            "generalFeedback": "Strong candidate with good technical skills."
        })
        r = client.post("/analyze", json={
            "mode": "jobSeeker",
            "resume": "Experienced Python developer with 5 years at Google. Built scalable ML pipelines.",
            "job_description": "Looking for Senior Python Developer"
        })
        assert r.status_code in (200, 202)
        data = r.get_json()
        # 200 = sync result, 202 = queued
        if r.status_code == 200:
            assert "strengths" in data
            assert "formattedReport" in data
        else:
            assert "job_id" in data

    @patch("backend.app.call_llm")
    def test_analyze_recruiter_json(self, mock_llm, client):
        """Test recruiter analysis with mocked LLM."""
        mock_llm.return_value = json.dumps({
            "strengths": ["Relevant experience"],
            "improvementAreas": ["More leadership"],
            "recommendedRoles": ["Senior Developer"],
            "generalFeedback": "Good fit for the role."
        })
        r = client.post("/analyze", json={
            "mode": "recruiter",
            "resume": "Python developer with Flask and Docker experience",
            "job_description": "Senior Python developer position requiring Flask",
            "recruiterEmail": "recruiter@test.com"
        })
        assert r.status_code in (200, 202)
        data = r.get_json()
        if r.status_code == 200:
            assert "lexicalMatchPercentage" in data or "strengths" in data
        else:
            assert "job_id" in data

    @patch("backend.app.call_llm")
    def test_recruiter_shortlist_dashboard_schema(self, mock_llm):
        """Recruiter analysis should include structured shortlist evidence and risks."""
        from backend.app import run_analysis_task

        mock_llm.return_value = json.dumps({
            "strengths": ["Strong backend delivery", "Good collaboration"],
            "improvementAreas": ["System design depth", "Stakeholder communication"],
            "recommendedRoles": ["Senior Python Developer"],
            "generalFeedback": "Strong candidate with relevant platform experience."
        })

        result = run_analysis_task(
            "recruiter",
            "Python engineer delivered 30% latency reduction with Flask and Docker.",
            "Need Python Flask Docker AWS leadership communication",
            "recruiter@test.com",
            {"uid": "test-user"}
        )

        assert "shortlistDashboard" in result
        dashboard = result["shortlistDashboard"]
        assert dashboard["decision"] in {"shortlisted", "review", "hold"}
        assert isinstance(dashboard.get("evidence", []), list)
        assert isinstance(dashboard.get("riskFlags", []), list)
        assert "confidenceScore" in dashboard


# =============================
# 6. Cover Letter Generation Tests
# =============================
class TestCoverLetter:
    @patch("backend.app.call_llm")
    def test_generate_cover_letter_no_file(self, mock_llm, client):
        """Should return 400 when no resume file is provided."""
        r = client.post("/generate-cover-letter", data={
            "jobDescription": "Python Developer"
        })
        assert r.status_code == 400

    @patch("backend.app.call_llm")
    @patch("backend.app.extract_text_from_pdf")
    def test_generate_cover_letter_success(self, mock_pdf, mock_llm, client):
        """Test successful cover letter generation with mocked PDF and LLM."""
        mock_pdf.return_value = "Python developer with 5 years experience"
        mock_llm.return_value = "Dear Hiring Manager, I am excited to apply..."
        data = {
            "jobDescription": "Looking for Python Developer"
        }
        data["resume"] = (io.BytesIO(b"%PDF-fake"), "resume.pdf")
        r = client.post("/generate-cover-letter", data=data, content_type="multipart/form-data")
        assert r.status_code == 200
        assert "coverLetter" in r.get_json()


# =============================
# 7. Mock Interview Tests
# =============================
class TestMockInterview:
    @patch("backend.app.call_llm")
    def test_mock_interview_response(self, mock_llm, client):
        """Test mock interview returns AI response."""
        mock_llm.return_value = "Tell me about a challenging project you worked on."
        r = client.post("/mock-interview", json={
            "message": "Hello, I'm ready for my interview.",
            "history": [],
            "jobContext": "Software Engineer"
        })
        assert r.status_code == 200
        assert "response" in r.get_json()

    @patch("backend.app.call_llm")
    def test_analyze_mock_interview(self, mock_llm, client):
        """Test mock interview analysis/scoring."""
        mock_llm.return_value = json.dumps({
            "score": 75,
            "feedback": "Good communication, needs more technical depth",
            "strengths": ["Clear communication"],
            "improvements": ["Add more technical details"]
        })
        r = client.post("/analyze-mock-interview", json={
            "history": [
                {"sender": "ai", "text": "Tell me about yourself"},
                {"sender": "user", "text": "I am a software engineer with 5 years of experience"}
            ],
            "jobContext": "Software Engineer"
        })
        assert r.status_code == 200

    def test_analyze_empty_history(self, client):
        """Should return 400 for empty interview history."""
        r = client.post("/analyze-mock-interview", json={
            "history": [],
            "jobContext": "Developer"
        })
        assert r.status_code == 400


# =============================
# 8. Coaching Endpoints Tests
# =============================
class TestCoaching:
    def test_coaching_progress(self, client):
        r = client.get("/coaching/progress")
        assert r.status_code == 200
        data = r.get_json()
        assert "versions" in data

    def test_coaching_study_pack(self, client):
        r = client.get("/coaching/study-pack")
        assert r.status_code == 200

    @patch("backend.app.call_llm")
    def test_coaching_interview_questions(self, mock_llm, client):
        mock_llm.return_value = json.dumps({"questions": ["Tell me about yourself"]})
        r = client.get("/coaching/interview-questions?targetRole=Software+Engineer")
        assert r.status_code == 200
        data = r.get_json()
        assert "questions" in data

    def test_coaching_diff_insufficient_versions(self, client):
        """Should return 400 if less than 2 versions exist."""
        # This test checks edge case handling
        r = client.get("/coaching/diff?prev=1&curr=2")
        # Either 400 (not enough versions) or 200 (if user has data)
        assert r.status_code in [200, 400]


# =============================
# 9. Utility Function Tests
# =============================
class TestUtilityFunctions:
    def test_extract_json_from_text(self):
        from backend.app import extract_json_from_text
        text = 'Here is some text before {"key": "value", "num": 42} and after'
        result = extract_json_from_text(text)
        assert result is not None
        assert result["key"] == "value"
        assert result["num"] == 42

    def test_extract_json_invalid(self):
        from backend.app import extract_json_from_text
        result = extract_json_from_text("No JSON here at all")
        assert result is None

    def test_ensure_non_empty_fields(self):
        from backend.app import ensure_non_empty_fields
        data = {"strengths": [], "improvementAreas": None}
        result = ensure_non_empty_fields(data)
        assert len(result["strengths"]) > 0
        assert len(result["improvementAreas"]) > 0
        assert len(result["recommendedRoles"]) > 0

    def test_format_report(self):
        from backend.app import format_report
        data = {
            "strengths": ["Good at Python"],
            "improvementAreas": ["Learn Docker"],
            "recommendedRoles": ["Backend Developer"],
            "generalFeedback": "Strong candidate overall."
        }
        report = format_report(data)
        assert "Strengths" in report
        assert "Good at Python" in report
        assert "Backend Developer" in report

    def test_build_study_pack(self):
        from backend.app import build_study_pack
        gaps = ["python", "docker"]
        pack = build_study_pack(gaps)
        assert len(pack) == 2
        assert pack[0]["skill"] == "python"
        assert len(pack[0]["resources"]) > 0

    def test_format_general_feedback_empty(self):
        from backend.app import format_general_feedback
        assert format_general_feedback(None) == "- No feedback provided."
        assert format_general_feedback("") == "- No feedback provided."


# =============================
# 10. Email & Recruiter Endpoints
# =============================
class TestRecruiterFeatures:
    @patch("backend.app.call_llm")
    def test_generate_email(self, mock_llm, client):
        mock_llm.return_value = "Subject: Interview Invitation\n\nDear Candidate..."
        r = client.post("/generate-email", json={
            "type": "interview_invite",
            "candidateName": "John Doe",
            "jobTitle": "Software Engineer"
        })
        assert r.status_code == 200
        assert "email" in r.get_json()

    @patch("backend.app.call_llm")
    def test_generate_job_description(self, mock_llm, client):
        mock_llm.return_value = json.dumps({
            "job_description": "We are looking for a talented engineer..."
        })
        r = client.post("/generate-job-description", json={
            "title": "Software Engineer",
            "skills": "Python, Flask, Docker",
            "experience": "3-5 years"
        })
        assert r.status_code == 200


# =============================
# 11. History Endpoint Tests
# =============================
class TestHistory:
    def test_history_endpoint(self, client):
        r = client.get("/history")
        assert r.status_code == 200
        data = r.get_json()
        assert "history" in data
        assert "count" in data

    def test_history_with_limit(self, client):
        r = client.get("/history?limit=5")
        assert r.status_code == 200


# =============================
# 12. MongoDB Integration Tests
# =============================
class TestMongoIntegration:
    def test_mongo_module_imports(self):
        """Verify mongo_db module can be imported without errors."""
        from backend.mongo_db import save_analysis, get_user_history, get_db
        assert callable(save_analysis)
        assert callable(get_user_history)
        assert callable(get_db)

    def test_save_analysis_without_uri(self):
        """Without MONGO_URI, save should gracefully return None."""
        from backend.mongo_db import save_analysis
        result = save_analysis("test-user", "jobSeeker", {"test": True})
        # Without MONGO_URI configured, this should return None gracefully
        assert result is None

    def test_get_history_without_uri(self):
        """Without MONGO_URI, history should return empty list."""
        from backend.mongo_db import get_user_history
        result = get_user_history("test-user")
        assert result == []


# =============================
# 13. Worker Tasks Tests
# =============================
class TestWorkerTasks:
    def test_process_resume_analysis_accepts_user_id(self):
        """Verify process_resume_analysis accepts user_id parameter."""
        from backend.worker_tasks import process_resume_analysis
        import inspect
        
        # Check function signature includes user_id parameter
        sig = inspect.signature(process_resume_analysis)
        params = list(sig.parameters.keys())
        assert "user_id" in params, "process_resume_analysis missing user_id parameter"
        
        # Check user_id has default value
        assert sig.parameters["user_id"].default == "anonymous", "user_id should default to 'anonymous'"

    @patch('backend.app.run_analysis_task')
    def test_process_resume_analysis_calls_save_with_user_id(self, mock_run):
        """Verify process_resume_analysis calls save_analysis with user_id."""
        from backend.worker_tasks import process_resume_analysis
        from unittest.mock import patch as mock_patch
        
        mock_run.return_value = {"combinedMatchPercentage": 75}
        
        # Patch save_analysis where it's imported (inside mongo_db)
        with mock_patch('backend.mongo_db.save_analysis') as mock_save:
            # Call with explicit user_id
            result = process_resume_analysis(
                "sample resume text",
                "sample jd",
                "jobSeeker",
                "user-123"
            )
            
            # Verify save_analysis was called with user_id
            mock_save.assert_called_once()
            call_kwargs = mock_save.call_args[1]
            assert call_kwargs.get("user_id") == "user-123", "user_id not passed to save_analysis"
            assert call_kwargs.get("mode") == "jobSeeker"
            assert "result" in call_kwargs
