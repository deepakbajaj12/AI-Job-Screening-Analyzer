import sys
import os

# Add the project root to sys.path so that Backend_old and tests can be imported
# conftest.py is in the tests directory, so go up one level to get the project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
