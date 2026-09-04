import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    mongodb_uri: str = os.getenv(
        "MONGODB_URI",
        "mongodb+srv://lenhan16587_db_user:g3ib5kVSL42WNfON@quanlycamera.uh2fyhm.mongodb.net/?retryWrites=true&w=majority&appName=quanlycamera"
    )
    database_name: str = os.getenv("DATABASE_NAME", "quanlycamera")
    scan_interval_seconds: int = int(os.getenv("SCAN_INTERVAL_SECONDS", "60"))
    min_incident_seconds: int = int(os.getenv("MIN_INCIDENT_SECONDS", "1800")) # Mặc định 30 phút (1800 giây)
    admin_default_username: str = os.getenv("ADMIN_DEFAULT_USERNAME", "admin")
    admin_default_password: str = os.getenv("ADMIN_DEFAULT_PASSWORD", "admin123")
    secret_key: str = os.getenv("SECRET_KEY", "quanlycamera-secure-secret-key-2025-token-sign")
    token_expire_days: int = int(os.getenv("TOKEN_EXPIRE_DAYS", "7"))
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

settings = Settings()
