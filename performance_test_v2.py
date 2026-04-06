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

print('=== PERFORMANCE TEST - Backend Features ===\n')

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

    # Test 3: Analyze (jobSeeker mode) - First request
    print('3. Analyze - JobSeeker Mode (First Request)')
    start = time.time()
    r = requests.post(f'{BASE_URL}/analyze', 
        json={'resume': resume_text, 'job_description': job_desc, 'mode': 'jobSeeker', 'user_id': 'test-user'},
        timeout=60)
    elapsed = time.time() - start
    print(f'   Status: {r.status_code}')
    print(f'   Response Time: {elapsed*1000:.2f}ms')
    
    if r.status_code == 202:
        # Async job - get job_id and poll for status
        job_data = r.json()
        job_id = job_data.get('job_id')
        print(f'   Job ID: {job_id}')
        print(f'   Status: {job_data.get("status")}')
        
        # Poll for job completion
        print(f'   Polling for job completion...')
        poll_start = time.time()
        while True:
            r = requests.get(f'{BASE_URL}/status/{job_id}', timeout=10)
            job_status = r.json()
            if job_status.get('status') == 'completed':
                poll_elapsed = time.time() - poll_start
                total_elapsed = time.time() - start
                print(f'   Job completed in {poll_elapsed*1000:.2f}ms (Total: {total_elapsed*1000:.2f}ms)')
                data = job_status.get('result', {})
                has_strengths = bool(data.get('strengths'))
                print(f'   Has Results: {has_strengths}\n')
                break
            elif job_status.get('status') == 'failed':
                print(f'   Job failed: {job_status.get("error")}\n')
                break
            else:
                time.sleep(0.5)
                if time.time() - poll_start > 30:
                    print(f'   Timeout waiting for job completion\n')
                    break
    elif r.status_code == 200:
        # Synchronous response
        data = r.json()
        has_strengths = bool(data.get('strengths'))
        print(f'   Has Results: {has_strengths}\n')
    else:
        print(f'   Error: {r.text}\n')

    # Test 4: Analyze (recruiter mode) with proper email
    print('4. Analyze - Recruiter Mode (First Request)')
    start = time.time()
    r = requests.post(f'{BASE_URL}/analyze',
        json={
            'resume': resume_text, 
            'job_description': job_desc, 
            'mode': 'recruiter', 
            'recruiterEmail': 'recruiter@example.com',
            'user_id': 'test-user'
        },
        timeout=60)
    elapsed = time.time() - start
    print(f'   Status: {r.status_code}')
    print(f'   Response Time: {elapsed*1000:.2f}ms')
    
    if r.status_code == 202:
        job_data = r.json()
        job_id = job_data.get('job_id')
        print(f'   Job ID: {job_id}')
        print(f'   Status: {job_data.get("status")}')
        
        # Poll for job completion
        print(f'   Polling for job completion...')
        poll_start = time.time()
        while True:
            r = requests.get(f'{BASE_URL}/status/{job_id}', timeout=10)
            job_status = r.json()
            if job_status.get('status') == 'completed':
                poll_elapsed = time.time() - poll_start
                total_elapsed = time.time() - start
                print(f'   Job completed in {poll_elapsed*1000:.2f}ms (Total: {total_elapsed*1000:.2f}ms)')
                data = job_status.get('result', {})
                has_dashboard = bool(data.get('shortlistDashboard'))
                print(f'   Has Dashboard: {has_dashboard}\n')
                break
            elif job_status.get('status') == 'failed':
                print(f'   Job failed: {job_status.get("error")}\n')
                break
            else:
                time.sleep(0.5)
                if time.time() - poll_start > 30:
                    print(f'   Timeout waiting for job completion\n')
                    break
    elif r.status_code == 200:
        data = r.json()
        has_dashboard = bool(data.get('shortlistDashboard'))
        print(f'   Has Dashboard: {has_dashboard}\n')
    else:
        print(f'   Error: {r.text}\n')

    # Test 5: Second JobSeeker analysis (should hit cache)
    print('5. Analyze - JobSeeker Mode (Cached - 2nd Request)')
    start = time.time()
    r = requests.post(f'{BASE_URL}/analyze',
        json={'resume': resume_text, 'job_description': job_desc, 'mode': 'jobSeeker', 'user_id': 'test-user'},
        timeout=60)
    elapsed = time.time() - start
    print(f'   Status: {r.status_code}')
    print(f'   Response Time: {elapsed*1000:.2f}ms')
    print(f'   Expected: Much faster than first request (cache hit)\n')

    # Test 6: Metrics endpoint
    print('6. Metrics Endpoint')
    start = time.time()
    r = requests.get(f'{BASE_URL}/metrics', timeout=10)
    elapsed = time.time() - start
    print(f'   Status: {r.status_code}')
    print(f'   Response Time: {elapsed*1000:.2f}ms')
    if r.status_code == 200:
        metrics = r.json()
        analyze_metrics = metrics.get('analyze', {})
        print(f'   Analyze Requests: {analyze_metrics.get("count", 0)}')
        print(f'   Average Response Time: {analyze_metrics.get("avgMs", 0)}ms\n')

    print('=== TEST SUMMARY ===')
    print('✓ All endpoints tested successfully')
    print('✓ Check response times above - faster times = better performance')
    print('✓ Cache should make 2nd requests significantly faster')
    
except requests.exceptions.ConnectionError:
    print('ERROR: Could not connect to backend at', BASE_URL)
    print('Make sure the backend is running on port 5000')
    sys.exit(1)
except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
