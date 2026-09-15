import os
from dotenv import load_dotenv
load_dotenv()
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    MODEL_NAME = "openai/gpt-oss-120b"
    DEBUG = True
    ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")
    DOCTORS_DATA_FILE = os.path.join(BASE_DIR, "data", "doctors_data.json")
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024