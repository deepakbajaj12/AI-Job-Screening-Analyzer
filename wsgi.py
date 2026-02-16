import os
import sys

# Add the Backend_old directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "Backend_old"))

from Backend_old.app import app

if __name__ == "__main__":
    app.run()
