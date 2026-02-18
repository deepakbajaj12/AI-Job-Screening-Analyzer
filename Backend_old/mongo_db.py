import certifi
from pymongo import MongoClient
import os

# Load Mongo URI from environment variable
MONGO_URI = os.getenv("MONGO_URI")

client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())

# Database Name
db = client["resumeAnalyzer"]

# Collection Name
analysis_collection = db["analysis_results"]
