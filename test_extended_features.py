import requests
import time
import os

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
    # Create temp resume file (Windows compatible)
    temp_file = 'test_resume_temp.txt'
    with open(temp_file, 'w') as f:
        f.write(resume_text)
    
    # Test 1: Estimate Salary
    print('1. Estimate Salary Endpoint')
    with open(temp_file, 'rb') as f:
        files = {'resume': f}
        data = {'jobDescription': job_desc}
        r = requests.post(f'{BASE_URL}/estimate-salary', files=files, data=data, timeout=30)
    print(f'   Status: {r.status_code}')
    print(f'   Response: {r.json()}\n')

    # Test 2: Tailor Resume
    print('2. Tailor Resume Endpoint')
    with open(temp_file, 'rb') as f:
        files = {'resume': f}
        data = {'jobDescription': job_desc}
        r = requests.post(f'{BASE_URL}/tailor-resume', files=files, data=data, timeout=30)
    print(f'   Status: {r.status_code}')
    print(f'   Response: {r.json()}\n')

    # Test 3: Generate Career Path
    print('3. Generate Career Path Endpoint')
    with open(temp_file, 'rb') as f:
        files = {'resume': f}
        r = requests.post(f'{BASE_URL}/generate-career-path', files=files, timeout=30)
    print(f'   Status: {r.status_code}')
    print(f'   Response: {r.json()}\n')

except requests.exceptions.ConnectionError:
    print('ERROR: Backend not running at', BASE_URL)
except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
finally:
    # Cleanup
    if os.path.exists(temp_file):
        os.remove(temp_file)
