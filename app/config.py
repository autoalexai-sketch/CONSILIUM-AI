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
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")

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
    STRIPE_SECRET_KEY: str = os.getenv("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET: str = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PUBLISHABLE_KEY: str = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    PUBLIC_BASE_URL: str = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

    # --- hCaptcha (bot protection on /register) ---
    # Get keys at: https://dashboard.hcaptcha.com
    # If HCAPTCHA_SECRET is empty, captcha verification is skipped (dev mode).
    # Site key is public -- safe to expose in frontend JS.
    HCAPTCHA_SECRET: str = os.getenv("HCAPTCHA_SECRET", "")
    HCAPTCHA_SITE_KEY: str = os.getenv("HCAPTCHA_SITE_KEY", "")


# -- Singleton instance -------------------------------------------------------
settings = Settings()

# -- Startup checks (warnings, NOT crashes) -----------------------------------
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

if not settings.HCAPTCHA_SECRET:
    logger.warning(
        "⚠️  HCAPTCHA_SECRET not set. "
        "Bot protection on /register is DISABLED. "
        "Set HCAPTCHA_SECRET + HCAPTCHA_SITE_KEY in .env to enable."
    )

# -- Log active providers -----------------------------------------------------
_providers = []
if settings.OPENROUTER_API_KEY: _providers.append("OpenRouter")
if settings.ANTHROPIC_API_KEY:  _providers.append("Claude")
if settings.GEMINI_API_KEY:     _providers.append("Gemini")
if settings.GROQ_API_KEY:       _providers.append("Groq")
if settings.DEEPSEEK_API_KEY:   _providers.append("DeepSeek")
logger.info(f"🔑 Active providers: {', '.join(_providers) or 'none'}")
logger.info(f"🔐 JWT: algorithm={settings.JWT_ALGORITHM} | expire={settings.JWT_EXPIRE_HOURS}h")
logger.info(f"💳 Stripe billing: {'configured' if settings.STRIPE_SECRET_KEY else 'NOT configured'}")
logger.info(f"🤖 hCaptcha: {'enabled' if settings.HCAPTCHA_SECRET else 'disabled (dev mode)'}")
