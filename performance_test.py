import requests
import time
import json
import sys

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

print('=== TESTING BACKEND ENDPOINTS ===\n')

try:
    # Test 1: Health endpoint
    print('1. Health Check')
    start = time.time()
    r = requests.get(f'{BASE_URL}/health', timeout=10)
    elapsed = time.time() - start
    print(f'   Status: {r.status_code}')
    print(f'   Response Time: {elapsed*1000:.2f}ms\n')

    # Test 2: Version endpoint
    print('2. Version Endpoint')
    start = time.time()
    r = requests.get(f'{BASE_URL}/version', timeout=10)
    elapsed = time.time() - start
    print(f'   Status: {r.status_code}')
    print(f'   Response Time: {elapsed*1000:.2f}ms\n')

    # Test 3: Analyze (jobSeeker mode)
    print('3. Analyze - JobSeeker Mode')
    start = time.time()
    r = requests.post(f'{BASE_URL}/analyze', 
        json={'resume': resume_text, 'job_description': job_desc, 'mode': 'jobSeeker', 'user_id': 'test-user'},
        timeout=30)
    elapsed = time.time() - start
    print(f'   Status: {r.status_code}')
    print(f'   Response Time: {elapsed*1000:.2f}ms')
    if r.status_code == 200:
        data = r.json()
        has_strengths = bool(data.get('strengths'))
        print(f'   Has Results: {has_strengths}\n')
    else:
        print(f'   Error: {r.text}\n')

    # Test 4: Analyze (recruiter mode)
    print('4. Analyze - Recruiter Mode')
    start = time.time()
    r = requests.post(f'{BASE_URL}/analyze',
        json={'resume': resume_text, 'job_description': job_desc, 'mode': 'recruiter', 'user_id': 'test-user'},
        timeout=30)
    elapsed = time.time() - start
    print(f'   Status: {r.status_code}')
    print(f'   Response Time: {elapsed*1000:.2f}ms')
    if r.status_code == 200:
        data = r.json()
        has_dashboard = bool(data.get('shortlistDashboard'))
        print(f'   Has Dashboard: {has_dashboard}\n')

    # Test 5: Same analysis again (should hit cache)
    print('5. Analyze - JobSeeker Mode (Cached - 2nd request)')
    start = time.time()
    r = requests.post(f'{BASE_URL}/analyze',
        json={'resume': resume_text, 'job_description': job_desc, 'mode': 'jobSeeker', 'user_id': 'test-user'},
        timeout=30)
    elapsed = time.time() - start
    print(f'   Status: {r.status_code}')
    print(f'   Response Time: {elapsed*1000:.2f}ms (should be much faster - cache!)\n')

    # Test 6: History endpoint
    print('6. History Endpoint')
    start = time.time()
    r = requests.get(f'{BASE_URL}/history/test-user', timeout=10)
    elapsed = time.time() - start
    print(f'   Status: {r.status_code}')
    print(f'   Response Time: {elapsed*1000:.2f}ms\n')

    print('=== TESTING COMPLETE ===')
    
except requests.exceptions.ConnectionError:
    print('ERROR: Could not connect to backend at', BASE_URL)
    print('Make sure the backend is running on port 5000')
    sys.exit(1)
except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')
    sys.exit(1)
