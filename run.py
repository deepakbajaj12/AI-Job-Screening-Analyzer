import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Ensure the root directory is in the path so we can import Backend_old
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Backend_old.app import app

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
