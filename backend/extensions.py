from groq import Groq
from config import Config

# Initialize Groq client once
groq_client = Groq(api_key=Config.GROQ_API_KEY)