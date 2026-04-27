"""
Smoke tests для CONSILIUM AI v3.0
Покрывают: /health, /version, register → verify → login → ws_reject_bad_token
Env и init_database() — в conftest.py (autouse fixture).
"""
import uuid
import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from main import app  # noqa: E402


# ── /health ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_health_get():
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as ac:
        r = await ac.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "service" in data


@pytest.mark.asyncio
async def test_health_head():
    """Render использует HEAD для healthcheck."""
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as ac:
        r = await ac.head("/health")
    assert r.status_code == 200


# ── /version ───────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_version():
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as ac:
        r = await ac.get("/version")
    assert r.status_code == 200
    data = r.json()
    assert "version" in data


# ── / (frontend) ───────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_root_returns_html():
    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as ac:
        r = await ac.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")


# ── Auth flow: register → verify → login ───────────────────────────────────
@pytest.mark.asyncio
async def test_register_verify_login_flow():
    email    = f"smoke_{uuid.uuid4().hex[:8]}@test.com"
    password = "StrongPass123!"

    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as ac:

        # 1. Регистрация
        r = await ac.post("/register",
                          json={"email": email, "password": password})
        assert r.status_code == 200, f"register failed: {r.text}"
        reg = r.json()
        assert reg.get("status") == "success"
        assert "token" in reg

        token = reg["token"]

        # 2. Verify
        r = await ac.get("/verify",
                         headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, f"verify failed: {r.text}"
        v = r.json()
        assert v.get("status") == "valid"
        assert v.get("email") == email

        # 3. Логин
        r = await ac.post("/login",
                          json={"email": email, "password": password})
        assert r.status_code == 200, f"login failed: {r.text}"
        login = r.json()
        assert login.get("status") == "success"
        assert "token" in login

        # 4. Verify с новым токеном
        r = await ac.get("/verify",
                         headers={"Authorization": f"Bearer {login['token']}"})
        assert r.status_code == 200
        assert r.json().get("email") == email


# ── WebSocket: плохой токен должен вернуть error ───────────────────────────
def test_ws_rejects_invalid_token():
    client = TestClient(app)
    with client.websocket_connect("/ws/council") as ws:
        ws.send_json({
            "token":   "this-is-not-a-valid-token",
            "message": "smoke test",
            "chat_id": "smoke-001",
        })
        payload = ws.receive_json()
    assert payload.get("type") == "error", \
        f"Expected error, got: {payload}"


# ── ExperienceRanker unit test ─────────────────────────────────────────────
# TODO: включить в Этапе 4 когда core/experience/ будет создан
# def test_experience_ranker_weights(): ...


# ── ai_fallback: DeepSeek провайдер инициализируется ──────────────────────
def test_deepseek_provider_init():
    """Проверяем только что атрибуты есть — без реального сетевого вызова."""
    from core.ai_fallback import AIFallbackManager
    mgr = AIFallbackManager()
    assert hasattr(mgr, "deepseek_available")
    assert hasattr(mgr, "_call_deepseek")
