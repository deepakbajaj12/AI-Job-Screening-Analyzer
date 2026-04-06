import requests
import time
from io import BytesIO

BASE_URL = 'http://localhost:5000'

# Test data
resume_text = '''John Doe
Software Engineer
john.doe@example.com

EXPERIENCE
Senior Software Engineer at TechCorp (2020-2024)
- Led development of microservices architecture
- Improved API performance by 40%
- Mentored junior developers

Mid-level Developer at WebApp Inc (2018-2020)
- Developed full-stack applications
- Implemented CI/CD pipelines

SKILLS
Python, JavaScript, React, Node.js, AWS, Docker, SQL

EDUCATION
Bachelor of Science in Computer Science
University of Technology, 2018
'''

job_desc = '''Senior Software Engineer
Requirements:
- 5+ years experience with Python
- AWS expertise
- Leadership experience
- Full-stack development
'''

print('=== TESTING EXTENDED FEATURES ===\n')

try:
    # Test 1: Estimate Salary
    print('1. Estimate Salary Endpoint')
    files = {'resume': ('resume.txt', BytesIO(resume_text.encode()))}
    data = {'jobDescription': job_desc}
    r = requests.post(f'{BASE_URL}/estimate-salary', files=files, data=data, timeout=30)
    print(f'   Status: {r.status_code}')
    resp = r.json()
    print(f'   Response Keys: {list(resp.keys())}')
    if 'error' in resp:
        print(f'   Error: {resp["error"]}')
    if 'status' in resp:
        print(f'   Status: {resp.get("status")} (Async Job)\n')
    else:
        print(f'   Result: {resp.get("salaryEstimate", "No salary estimate")}\n')

    # Test 2: Tailor Resume
    print('2. Tailor Resume Endpoint')
    files = {'resume': ('resume.txt', BytesIO(resume_text.encode()))}
    data = {'jobDescription': job_desc}
    r = requests.post(f'{BASE_URL}/tailor-resume', files=files, data=data, timeout=30)
    print(f'   Status: {r.status_code}')
    resp = r.json()
    print(f'   Response Keys: {list(resp.keys())}')
    if 'error' in resp:
        print(f'   Error: {resp["error"]}')
    if 'status' in resp:
        print(f'   Status: {resp.get("status")} (Async Job)\n')
    else:
        print(f'   Result Has Tailored Resume: {bool(resp.get("tailoredResume", ""))}\n')

    # Test 3: Generate Career Path
    print('3. Generate Career Path Endpoint')
    files = {'resume': ('resume.txt', BytesIO(resume_text.encode()))}
    r = requests.post(f'{BASE_URL}/generate-career-path', files=files, timeout=30)
    print(f'   Status: {r.status_code}')
    resp = r.json()
    print(f'   Response Keys: {list(resp.keys())}')
    if 'error' in resp:
        print(f'   Error: {resp["error"]}')
    if 'status' in resp:
        print(f'   Status: {resp.get("status")} (Async Job)')
        job_id = resp.get('job_id')
        print(f'   Job ID: {job_id}')
        print(f'\n   These endpoints return async jobs.')
        print(f'   To get results, poll: GET /status/{job_id}\n')
    else:
        print(f'   Result: {resp.get("careerPath", "No career path")}\n')

except requests.exceptions.ConnectionError:
    print('ERROR: Backend not running at', BASE_URL)
    print('Start backend with: python backend/app.py')
except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
