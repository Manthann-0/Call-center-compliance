"""
Configuration settings loaded from environment variables.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # ── API Authentication ──
    API_KEY: str = os.getenv("API_KEY", "sk_track3_987654321")

    # ── Sarvam AI (Saaras v3 STT + Translation) ──
    SARVAM_API_KEY: str = os.getenv("SARVAM_API_KEY", "")

    # ── LLM — Cerebras (free, OpenAI-compatible API) ──
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.cerebras.ai/v1")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.1-8b")

    # ── Infrastructure ──
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./callcenter.db")
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./uploads")
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() == "true"
    PORT: int = int(os.getenv("PORT", "8000"))


settings = Settings()

# Ensure upload directory exists
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
