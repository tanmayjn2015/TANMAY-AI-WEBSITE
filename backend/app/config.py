import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chaya.db")
SESSION_SECRET = os.getenv("SESSION_SECRET", "")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "tanmay")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")
FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN", "*")
SESSION_HOURS = max(1, int(os.getenv("SESSION_HOURS", "2")))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

if not SESSION_SECRET:
    SESSION_SECRET = "development-only-secret-change-this"
