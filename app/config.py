"""
app/config.py -- Settings for CONSILIUM AI v3.0.
Reads variables from .env via python-dotenv.
"""

import os
from dotenv import load_dotenv
from loguru import logger

load_dotenv()


class Settings:
    APP_NAME: str = "Consilium AI"
    APP_VERSION: str = "3.0.0"
    DESCRIPTION: str = "Multi-agent AI Deliberation System"

    # --- Database ---
    DB_PATH: str = "consilium.db"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./consilium.db")

    # --- AI providers ---
    OPENROUTER_API_KEY: str = os.getenv("OPENROUTER_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # --- Ollama (optional, local only) ---
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")

    # --- SMTP mail ---
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASS: str = os.getenv("SMTP_PASS", "")

    # --- Security ---
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")

    # --- JWT ---
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

    # --- CORS ---
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "*").split(",")

    # --- Stripe (credit top-up billing) ---
    # All three are blank by default -- billing endpoints check for this and
    # return 503 "Billing not configured" rather than crashing on import, so
    # the rest of the app keeps working even before Stripe is wired up.
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    # Base URL used to build Stripe Checkout success_url/cancel_url redirects.
    # Must match wherever the frontend is actually served from.
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")


# -- Singleton instance ──────────────────────────────────────────────────────
settings = Settings()

# -- Startup checks (warnings, NOT crashes) ──────────────────────────────────
if not settings.OPENROUTER_API_KEY:
    logger.warning(
        "⚠️  OPENROUTER_API_KEY not found. "
        "Council mode unavailable. Add key to .env"
    )

if not settings.SECRET_KEY:
    raise ValueError("❌ SECRET_KEY not set in .env!")

if not settings.STRIPE_SECRET_KEY:
    logger.warning(
        "⚠️  STRIPE_SECRET_KEY not found. "
        "Credit top-up (billing) unavailable until configured in .env"
    )

# -- Log active providers ────────────────────────────────────────────────────
_providers = []
if settings.OPENROUTER_API_KEY: _providers.append("OpenRouter")
if settings.ANTHROPIC_API_KEY:  _providers.append("Claude")
if settings.GEMINI_API_KEY:     _providers.append("Gemini")
if settings.GROQ_API_KEY:       _providers.append("Groq")
logger.info(f"🔑 Active providers: {', '.join(_providers) or 'none'}")
logger.info(f"🔐 JWT: algorithm={settings.JWT_ALGORITHM} | expire={settings.JWT_EXPIRE_HOURS}h")
logger.info(f"💳 Stripe billing: {'configured' if settings.STRIPE_SECRET_KEY else 'NOT configured'}")
