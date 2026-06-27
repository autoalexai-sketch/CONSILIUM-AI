# CONSILIUM AI v3.0 — Intellectual Work Environment (IWE)

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-brightgreen)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![CI](https://github.com/autoalexai-sketch/CONSILIUM-AI/actions/workflows/ci.yml/badge.svg)](https://github.com/autoalexai-sketch/CONSILIUM-AI/actions/workflows/ci.yml)
[![Status](https://img.shields.io/badge/Status-Public%20Alpha-orange)](https://consilium-ai-v3.carrd.co)

**Consilium AI** is a multi-agent Intellectual Work Environment for strategic decision-making. Not just another chat — a structured **Board of Directors** of specialized AI agents that deliberate on your questions from every angle.

> _"From raw data to verified strategy."_

🔗 **Live app:** [ai-consilium.com](https://ai-consilium.com) · **Landing:** [consilium-ai-v3.carrd.co](https://consilium-ai-v3.carrd.co)

---

## What It Does

Instead of one AI giving you one answer, Consilium runs a **6-phase deliberation pipeline**:

```
Scout → Analyst → Architect → Devil's Advocate → Synthesizer → Verifier → Chairman
```

Each director analyzes your question from a different perspective. A **Protocol Manager** (Standard / Strategy / Crisis / Reflection / Planning / Deep) reshapes which directors run and how the Chairman frames the final verdict, depending on what kind of decision you're making. The Chairman delivers the final, cross-verified answer — auto-saved to your personal Decision Journal.

---

## Status

**Public Alpha.** Server runs in production on Render.com (PostgreSQL on AWS RDS), all providers initialize, WebSocket deliberation streams in real time, Stripe credit top-up is wired up pending live API keys. See [ROADMAP.md](ROADMAP.md) for exact done/open status — this README doesn't keep its own separate copy of that list.

---

## Screenshots

![Auth](screenshots/consilium-auth.png)
![Dashboard](screenshots/consilium-dashboard.png)
![Deliberation](screenshots/consilium-deliberation.png)

---

## Quick Start

### Requirements
- Python 3.11+
- At least one LLM provider key (Groq is free and fastest to start with)

### 1. Clone and install
```bash
git clone https://github.com/autoalexai-sketch/CONSILIUM-AI.git
cd CONSILIUM-AI
pip install -r requirements.txt
cp .env.example .env
# Edit .env — add at least GROQ_API_KEY and SECRET_KEY
```

### 2. Run
```bash
uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000** — not `file://`, the WebSocket requires a real server.

### 3. Docker
```bash
docker compose up --build
# Optional Prometheus + Grafana:
docker compose --profile monitoring up
```

---

## Environment Variables

See `.env.example` for the full annotated list. Minimum to run:

```env
GROQ_API_KEY=gsk_...
SECRET_KEY=your-random-secret-32-chars-min

# Optional — more providers in the fallback chain
DEEPSEEK_API_KEY=
OPENROUTER_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=

# Optional — Stripe credit top-up (billing endpoints 503 gracefully if unset)
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
```

---

## API Endpoints

Core:

| Method | Path | Description |
|--------|------|-------------|
| POST | `/login` | Login, returns JWT |
| POST | `/register` | Create account |
| GET | `/verify` | Verify token, get credits |
| WS | `/ws/council` | WebSocket deliberation stream |
| POST | `/chat` | Single-shot council request |

Feature APIs (auth required unless noted):

| Resource | Path prefix | Notes |
|----------|-------------|-------|
| Decision Journal | `/api/knowledge/journal` | Auto-saved Chairman verdicts; draft/verified/approved workflow |
| Principles | `/api/knowledge/principles` | Injected into every deliberation via Context Gateway |
| LLM Wiki | `/api/knowledge/wiki` | Free-form notes; can snapshot a journal entry via `/wiki/from-journal/{id}` |
| Session History | `/api/experience/sessions` | Click-through to the saved verdict for any past session |
| Feedback | `POST /api/experience/feedback` | Good/Poor rating, feeds closed-loop learning |
| Billing | `/api/billing/*` | `packages` (public), `checkout-session`, `webhook` (Stripe-signed, no auth), `history` |
| Protocol config | `GET /debug/protocols` | Inspect the active Standard/Strategy/Crisis/Reflection/Planning/Deep rules |

### WebSocket Protocol (`/ws/council`)

Client sends first message:
```json
{"token": "eyJ...", "message": "your question", "chat_id": "chat_123", "protocol": "standard"}
```
`protocol` is optional (defaults to `"standard"`) — one of `standard|strategy|crisis|reflection|planning|deep`.

Server streams:
```json
{"type": "council_ready", "selected": ["scout", "analyst", "chairman"], "protocol": "standard"}
{"type": "phase_start",   "phase": "scout", "text": "Scanning sources..."}
{"type": "phase_done",    "phase": "scout", "tokens": 198, "provider": "groq"}
{"type": "final",         "response": "...", "council_used": [...], "credits_left": 9, "journal_id": 42}
```

---

## Architecture

```
┌─────────────────────────────────────────────┐
│        FRONTEND (single-file HTML/JS SPA)    │
│  Auth → Chat → Live Deliberation Stream      │
│  Decisions · Principles · Wiki · History     │
└──────────────────┬──────────────────────────┘
                   │ WebSocket + REST
┌──────────────────▼──────────────────────────┐
│              FASTAPI BACKEND                 │
│                                              │
│  CognitiveClassifier → CouncilSelector       │
│  PROTOCOL_CONFIG override (6 modes)          │
│  ContextGateway (Principles + past decisions)│
│  CouncilDeliberation (7 directors)           │
│  Synthesizer + Verifier + Chairman           │
│  ExperienceService (closed-loop feedback)    │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│              LLM PROVIDERS                   │
│  Groq → DeepSeek V4 → OpenRouter → Gemini    │
│  → Ollama (5-level fallback, auto-routing)   │
└─────────────────────────────────────────────┘
```

PostgreSQL on AWS RDS in production; SQLite for local dev (`DATABASE_URL` switches automatically).

---

## Features

- **Multi-agent deliberation** — 7 specialized AI directors (Scout, Analyst, Architect, Devil's Advocate, Synthesizer, Verifier, Chairman)
- **Real-time streaming** — WebSocket phase-by-phase updates
- **5-level provider fallback** — Groq → DeepSeek V4 → OpenRouter → Gemini → Ollama
- **Protocol Manager** — Standard / Strategy / Crisis / Reflection / Planning / Deep, each actually changing council composition and Chairman framing
- **Decision Journal** — every verdict auto-saved with a draft → verified → approved workflow
- **Personal Vault** — user Principles (injected into every deliberation) + LLM Wiki (free-form reference notes)
- **Session History** — click any past session to see its saved verdict, no need to re-run and spend credits twice
- **Stripe credit top-up** — server-side pricing, signature-verified webhook, idempotent crediting
- **Bring your own API keys** — works with whichever providers you configure
- **2 UI themes** — dark, light
- **CEE-ready** — Polish, Ukrainian, English, Russian, with a strict per-response language lock
- **Demo mode** — works offline without a server

---

## Roadmap

Tracked in [ROADMAP.md](ROADMAP.md) — single source of truth for what's shipped vs. open, kept in sync with the actual codebase rather than duplicated here.

---

## Founder

**Oleksandr Latyntsev** — Kraków, Poland (CEE)
Self-employed AI Integrator, building Consilium AI's Digital Board of Directors.

- Email: hello@ai-consilium.com · founder@ai-consilium.com
- GitHub: [autoalexai-sketch](https://github.com/autoalexai-sketch)
- Landing: [consilium-ai-v3.carrd.co](https://consilium-ai-v3.carrd.co)
- App: [ai-consilium.com](https://ai-consilium.com)

---

## License

MIT
