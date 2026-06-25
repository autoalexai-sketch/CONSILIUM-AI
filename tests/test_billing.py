"""
tests/test_billing.py — Stripe credit top-up: contract + security tests.

Covers:
  1. Public packages list
  2. Auth is required on checkout-session / history
  3. Billing endpoints fail CLOSED (503) when Stripe is not configured --
     this is the explicit design contract from app/api/billing.py, not an
     incidental behavior, so it gets its own test rather than being implied.
  4. Webhook signature verification: forged/invalid signatures are rejected
     with 400, valid signatures are accepted -- this is the single most
     security-critical code path in the whole billing feature (a bypass
     here means free credits for anyone who can guess a session id).
  5. Regression guard: the old unauthenticated POST /buy_credits exploit
     (app/api/chat.py, removed in this same change) must stay gone.
  6. Protocol Manager debug endpoint sanity check.

Env defaults come from conftest.py: STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET
are blank by default (matching production's safe-by-default behavior).
Tests 4's signature checks monkeypatch those two settings locally, scoped to
just that test, rather than changing the process-wide env.
"""

import hashlib
import hmac
import json
import time

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from app.config import settings


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _fake_stripe_event(event_type: str, data_object: dict, object_kind: str = "event") -> bytes:
    """
    Builds a structurally-complete Stripe Event JSON payload. stripe-python's
    Webhook.construct_event() inspects the top-level "object" field (and the
    nested data.object's own "object" field) to resolve which StripeObject
    subclass to instantiate -- a minimal {"type": ..., "data": {"object": {}}}
    dict is NOT enough and raises an internal error unrelated to signature
    verification. This mirrors the real shape Stripe actually sends.
    """
    return json.dumps({
        "id": "evt_test_00000000000000",
        "object": object_kind,
        "api_version": "2024-06-20",
        "created": int(time.time()),
        "type": event_type,
        "data": {"object": data_object},
    }).encode()


def _sign_stripe_payload(payload_bytes: bytes, secret: str, timestamp: int = None) -> str:
    """Replicates Stripe's documented webhook signing scheme so we can test
    stripe.Webhook.construct_event's verification path with zero network
    calls and zero dependency on real Stripe credentials."""
    ts = timestamp if timestamp is not None else int(time.time())
    signed_payload = f"{ts}.{payload_bytes.decode()}"
    signature = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    return f"t={ts},v1={signature}"


# ── 1. Public packages list ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_packages_list_is_public_and_well_formed():
    async with await _client() as ac:
        r = await ac.get("/api/billing/packages")
    assert r.status_code == 200
    packages = r.json()["packages"]
    ids = {p["id"] for p in packages}
    assert {"starter", "growth", "scale"} <= ids
    for p in packages:
        assert p["price_usd"] > 0
        assert p["credits"] > 0


# ── 2. Auth required ─────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_checkout_session_requires_auth():
    async with await _client() as ac:
        r = await ac.post("/api/billing/checkout-session", json={"package_id": "starter"})
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_billing_history_requires_auth():
    async with await _client() as ac:
        r = await ac.get("/api/billing/history")
    assert r.status_code in (401, 403)


# ── 3. Fails closed when Stripe is not configured ───────────────────────────
@pytest.mark.asyncio
async def test_checkout_session_503_when_stripe_unconfigured(auth_token):
    """conftest.py leaves STRIPE_SECRET_KEY blank by default -- this proves
    the app degrades gracefully instead of crashing or (worse) silently
    granting credits when billing isn't wired up yet."""
    assert not settings.STRIPE_SECRET_KEY, "this test assumes Stripe is unconfigured by default"
    async with await _client() as ac:
        r = await ac.post(
            "/api/billing/checkout-session",
            json={"package_id": "starter"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_checkout_session_invalid_package_still_fails_closed(auth_token):
    """Stripe-not-configured is checked before package validation, so even a
    bogus package_id should still 503 rather than leak a 400 that implies
    'billing is live, you just picked wrong' when it isn't live at all."""
    async with await _client() as ac:
        r = await ac.post(
            "/api/billing/checkout-session",
            json={"package_id": "does-not-exist"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    assert r.status_code == 503


# ── 4. Webhook signature verification (security-critical) ──────────────────
@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature(monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_dummy_for_ci")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_dummy_for_ci")

    body = _fake_stripe_event(
        "checkout.session.completed",
        {"id": "cs_test_forged", "object": "checkout.session"},
    )
    async with await _client() as ac:
        r = await ac.post(
            "/api/billing/webhook",
            content=body,
            headers={"stripe-signature": "t=1,v1=0000deadbeef0000"},
        )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_webhook_rejects_missing_signature_header(monkeypatch):
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_dummy_for_ci")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", "whsec_dummy_for_ci")

    body = _fake_stripe_event(
        "checkout.session.completed",
        {"id": "cs_test_nosig", "object": "checkout.session"},
    )
    async with await _client() as ac:
        r = await ac.post("/api/billing/webhook", content=body)
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_webhook_accepts_valid_signature_for_unknown_session(monkeypatch):
    """Proves the verification path itself works (a correctly signed event
    is NOT rejected) while also proving an event for a session we never
    created a pending credit_purchases row for cannot grant credits --
    it's acknowledged with 200 so Stripe stops retrying, but no money moves."""
    secret = "whsec_dummy_for_ci"
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_dummy_for_ci")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", secret)

    body = _fake_stripe_event(
        "checkout.session.completed",
        {"id": "cs_test_never_created", "payment_intent": "pi_test_x", "object": "checkout.session"},
    )
    sig_header = _sign_stripe_payload(body, secret)

    async with await _client() as ac:
        r = await ac.post(
            "/api/billing/webhook",
            content=body,
            headers={"stripe-signature": sig_header},
        )
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "no_matching_purchase"


@pytest.mark.asyncio
async def test_webhook_ignores_unrelated_event_types(monkeypatch):
    secret = "whsec_dummy_for_ci"
    monkeypatch.setattr(settings, "STRIPE_SECRET_KEY", "sk_test_dummy_for_ci")
    monkeypatch.setattr(settings, "STRIPE_WEBHOOK_SECRET", secret)

    body = _fake_stripe_event(
        "customer.created",
        {"id": "cus_test_x", "object": "customer"},
    )
    sig_header = _sign_stripe_payload(body, secret)

    async with await _client() as ac:
        r = await ac.post(
            "/api/billing/webhook",
            content=body,
            headers={"stripe-signature": sig_header},
        )
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "ignored"


# ── 5. Regression guard: the old free-credits exploit must stay removed ────
@pytest.mark.asyncio
async def test_legacy_buy_credits_endpoint_is_gone(auth_token):
    """app/api/chat.py used to expose POST /buy_credits?amount=X&price=Y that
    credited the caller with ZERO payment verification. If this test ever
    starts failing, someone re-added an unauthenticated/unverified credit
    grant -- do not relax this assertion, fix the reintroduction instead."""
    async with await _client() as ac:
        r = await ac.post(
            "/buy_credits?amount=1000&price=35",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
    assert r.status_code == 404


# ── 6. Protocol Manager sanity check ────────────────────────────────────────
@pytest.mark.asyncio
async def test_protocol_config_exposes_all_six_protocols():
    async with await _client() as ac:
        r = await ac.get("/debug/protocols")
    assert r.status_code == 200
    protocols = r.json()["protocols"]
    assert set(protocols.keys()) == {
        "standard", "strategy", "crisis", "reflection", "planning", "deep"
    }
    # Crisis must hard-limit to scout+chairman -- that's the whole point of it.
    assert protocols["crisis"]["limit_directors"] == ["scout", "chairman"]
