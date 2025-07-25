import os
import json
import re
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
import firebase_admin
from firebase_admin import auth as firebase_auth, credentials
import cohere
import pdfplumber
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Initialize Firebase Admin SDK
firebase_cred_path = os.getenv("FIREBASE_CREDENTIAL_PATH", "firebase-service-account.json")
cred = credentials.Certificate(firebase_cred_path)
firebase_admin.initialize_app(cred)

# Initialize Cohere client
COHERE_API_KEY = os.getenv("COHERE_API_KEY")
cohere_client = cohere.Client(COHERE_API_KEY)

def verify_firebase_token(id_token):
    try:
        decoded_token = firebase_auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        print(f"Token verification failed: {e}")
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
    try:
        response = cohere_client.chat(
            model="command-light-nightly",
            message=prompt,
            temperature=0.6
        )
        return response.text.strip()
    except Exception as e:
        print(f"Cohere API call failed: {e}")
        return None

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

@app.route("/", methods=["GET"])
def index():
    return "AI Job Screening Resume Analyzer Backend Running."

@app.route("/analyze", methods=["POST"])
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
        final_result["generalFeedback"] = f"Match Percentage: {match_percentage}%\n\n{final_result['generalFeedback']}"
        final_result["formattedReport"] = format_report(final_result)
        return jsonify(final_result)

    else:
        return jsonify({"error": "Unhandled mode"}), 400


if __name__ == "__main__":
    app.run(debug=True)
