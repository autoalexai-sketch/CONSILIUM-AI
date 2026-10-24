"""Regression: startup must not write the DB password to the log.
Production logs on Render showed the full RDS DATABASE_URL in plain text."""
from loguru import logger

import main


async def test_startup_log_hides_db_password(monkeypatch):
    monkeypatch.setattr(main.settings, "DATABASE_URL",
                        "postgresql://admin:S3cretPassw0rd@db.example.com:5432/app")
    monkeypatch.setattr(main, "init_database", lambda: None)
    lines = []
    sink = logger.add(lines.append, format="{message}")
    try:
        await main.startup_event()
    finally:
        logger.remove(sink)
    text = "".join(lines)
    assert "Database initialized" in text
    assert "db.example.com" in text
    assert "S3cretPassw0rd" not in text
