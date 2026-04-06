import time
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from app import run_analysis_task

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

print('=== DIRECT ANALYSIS PERFORMANCE TEST ===\n')
print('(No network overhead - pure function performance)\n')

try:
    # Test 1: JobSeeker mode - First request
    print('1. JobSeeker Analysis - First Request')
    start = time.time()
    result = run_analysis_task('jobSeeker', resume_text, job_desc, '', {'uid': 'test-user'})
    elapsed = time.time() - start
    print(f'   Execution Time: {elapsed*1000:.2f}ms')
    print(f'   Has Results: {bool(result.get("strengths"))}')
    print(f'   Match Score: {result.get("semanticMatchPercentage", "N/A")}%\n')

    # Test 2: JobSeeker mode - Second request (should be cached)
    print('2. JobSeeker Analysis - Second Request (Cached)')
    start = time.time()
    result = run_analysis_task('jobSeeker', resume_text, job_desc, '', {'uid': 'test-user'})
    elapsed = time.time() - start
    print(f'   Execution Time: {elapsed*1000:.2f}ms')
    print(f'   Expected: Much faster than first request (cache hit)\n')

    # Test 3: Recruiter mode - First request
    print('3. Recruiter Analysis - First Request')
    start = time.time()
    result = run_analysis_task('recruiter', resume_text, job_desc, 'recruiter@example.com', {'uid': 'test-user'})
    elapsed = time.time() - start
    print(f'   Execution Time: {elapsed*1000:.2f}ms')
    print(f'   Has Dashboard: {bool(result.get("shortlistDashboard"))}')
    print(f'   Combined Score: {result.get("combinedMatchPercentage", "N/A")}%\n')

    # Test 4: Recruiter mode - Second request (should be cached)
    print('4. Recruiter Analysis - Second Request (Cached)')
    start = time.time()
    result = run_analysis_task('recruiter', resume_text, job_desc, 'recruiter@example.com', {'uid': 'test-user'})
    elapsed = time.time() - start
    print(f'   Execution Time: {elapsed*1000:.2f}ms')
    print(f'   Expected: Much faster than first request (cache hit)\n')

    print('=== PERFORMANCE SUMMARY ===')
    print('✓ First requests should take 3-8 seconds (AI API call)')
    print('✓ Cached requests should take <10ms (direct file read)')
    print('✓ This demonstrates the cache effectiveness')

except Exception as e:
    print(f'ERROR: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
