"""
conftest.py — общие фикстуры для всех тестов CONSILIUM AI.
Вызывает init_database() до любого теста, чтобы таблицы существовали.
"""
import os
import pytest

# Env до импорта app
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")
os.environ.setdefault("DEEPSEEK_API_KEY",   "test-deepseek-key")
os.environ.setdefault("GROQ_API_KEY",       "test-groq-key")
os.environ.setdefault("ANTHROPIC_API_KEY",  "test-anthropic-key")
os.environ.setdefault("GEMINI_API_KEY",     "test-gemini-key")
os.environ.setdefault("SECRET_KEY",         "test-secret-key-for-ci-only")
os.environ.setdefault("DATABASE_URL",       "sqlite:///./ci_test.db")
os.environ.setdefault("CORS_ORIGINS",       "*")
os.environ.setdefault("SMTP_USER",          "")
os.environ.setdefault("SMTP_PASS",          "")
os.environ.setdefault("APP_ENV",            "test")

# --- Stripe billing ---------------------------------------------------------
# Left BLANK on purpose (matches production default-safe behavior): the
# billing endpoints must degrade gracefully to 503 "not configured" rather
# than crash when these are unset. tests/test_billing.py asserts exactly
# that contract. Tests that need to exercise webhook signature verification
# set these via pytest's monkeypatch fixture scoped to just that test --
# never via process-wide env vars, so the "unconfigured by default" contract
# stays the one every other test runs against.
os.environ.setdefault("STRIPE_SECRET_KEY",      "")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET",  "")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "")
os.environ.setdefault("PUBLIC_BASE_URL",        "http://localhost:8000")


@pytest.fixture(scope="session", autouse=True)
def initialize_db():
    """Создаёт таблицы в тестовой БД один раз перед всей сессией."""
    from app.database import init_database
    init_database()
    yield
    # Best-effort cleanup of the throwaway test DB file. On Windows, SQLAlchemy's
    # connection pool can still hold the file handle open at this point (POSIX
    # allows deleting an open file, Windows does not), which would otherwise
    # surface as a hard pytest ERROR on an unrelated test's teardown. Failing
    # to delete a temp file is not a test failure -- it's just cosmetic.
    import os as _os
    db_path = "ci_test.db"
    if _os.path.exists(db_path):
        try:
            _os.remove(db_path)
        except PermissionError:
            pass


@pytest.fixture
async def auth_token():
    """
    Registers a fresh throwaway user and returns a valid JWT bearer token.
    Shared by any test that needs an authenticated request (billing,
    knowledge, experience, etc.) instead of each test file re-implementing
    its own register/login boilerplate.
    """
    import uuid
    from httpx import ASGITransport, AsyncClient
    from main import app

    email = f"fixture_{uuid.uuid4().hex[:8]}@test.com"
    password = "StrongPass123!"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r = await ac.post("/register", json={"email": email, "password": password})
        assert r.status_code == 200, f"fixture register failed: {r.text}"
        token = r.json()["token"]

    return token
