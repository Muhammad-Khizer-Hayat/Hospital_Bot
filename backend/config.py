import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    MODEL_NAME = "openai/gpt-oss-120b"
    DEBUG = True

    # Protects admin-only routes (viewing booked appointments, uploading
    # a new doctors PDF) — set this as an environment variable, never
    # commit it. Without it set, those routes refuse all requests rather
    # than silently staying open.
    ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")

    # Where the doctors list parsed out of an uploaded PDF is stored.
    # hospital_data.py reads from here first and falls back to its
    # built-in defaults if this file doesn't exist yet.
    DOCTORS_DATA_FILE = os.path.join(BASE_DIR, "data", "doctors_data.json")

    # Reject absurdly large uploads (5 MB is plenty for a doctors list PDF)
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024