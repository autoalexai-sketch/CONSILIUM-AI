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


@pytest.fixture(scope="session", autouse=True)
def initialize_db():
    """Создаёт таблицы в тестовой БД один раз перед всей сессией."""
    from app.database import init_database
    init_database()
    yield
    # После сессии — удаляем тестовую БД
    import os as _os
    db_path = "ci_test.db"
    if _os.path.exists(db_path):
        _os.remove(db_path)
