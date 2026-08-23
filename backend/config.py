import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = os.environ.get("KALIBA_DB_PATH", str(ROOT / "gastos_kaliba.db"))
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-in-production")
JWT_EXP_DAYS = int(os.environ.get("JWT_EXP_DAYS", "14"))
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    if origin.strip()
]
COOKIE_NAME = "kaliba_session"
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"
APP_ENV = os.environ.get("APP_ENV", "development")
RENDER_PING_URL = os.environ.get(
    "RENDER_PING_URL", "https://meu-bot-financeiro-vcou.onrender.com/ping"
)
