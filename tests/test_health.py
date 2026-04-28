"""
tests/test_health.py — тесты /health и /version.
Env и init_database() — в conftest.py (autouse fixture).
"""
import pytest
from httpx import ASGITransport, AsyncClient

from main import app


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as ac:
        r = await ac.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "ok"
    assert "service" in body


@pytest.mark.asyncio
async def test_health_head():
    """HEAD /health — Render/ALB используют для healthcheck."""
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as ac:
        r = await ac.head("/health")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_version_check():
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as ac:
        r = await ac.get("/version")
    assert r.status_code == 200
    assert "version" in r.json()
