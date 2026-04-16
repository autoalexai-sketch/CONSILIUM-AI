# CONSILIUM AI v3.0 — Intellectual Work Environment (IWE)

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-brightgreen)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11%2B-blue)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-yellow)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Public%20Alpha-orange)](https://consilium-ai-v3.carrd.co)

**Consilium AI** is a multi-agent Intellectual Work Environment for strategic decision-making. Not just another chat — a structured **Board of Directors** of specialized AI agents that deliberate on your questions from every angle.

> _"From raw data to verified strategy."_

---

## What It Does

Instead of one AI giving you one answer, Consilium runs a **6-phase deliberation pipeline**:

```
Scout → Analyst → Architect → Devil's Advocate → Synthesizer → Verifier → Chairman
```

Each director analyzes your question from a different perspective. The Chairman delivers the final, cross-verified verdict.

---

## Status

**Public Alpha.** The server runs locally, all providers initialize, WebSocket deliberation streams in real time. Some v3.0 features from the strategic docs are still in development.

---

## Screenshots

![Auth](screenshots/consilium-auth.png)
![Dashboard](screenshots/consilium-dashboard.png)
![Deliberation](screenshots/consilium-deliberation.png)

---

## Quick Start

### Requirements
- Python 3.11+
- At least one LLM provider key (OpenRouter recommended)

### 1. Clone and install
```bash
git clone https://github.com/autoalexai-sketch/CONSILIUM-AI.git
cd CONSILIUM-AI
pip install -r requirements.txt
cp .env.example .env
# Edit .env — add your OPENROUTER_API_KEY and SECRET_KEY
```

### 2. Run
```bash
uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000** — not `file://`, the WebSocket requires a real server.

### 3. Docker
```bash
docker compose up --build
```

---

## Environment Variables

See `.env.example`. Required:

```env
OPENROUTER_API_KEY=sk-or-v1-...
SECRET_KEY=your-random-secret-32-chars-min

# Optional — enable more providers
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/login` | Login, returns JWT |
| POST | `/register` | Create account |
| GET | `/verify` | Verify token, get credits |
| WS | `/ws/council` | WebSocket deliberation stream |
| POST | `/chat` | Single-shot council request |

### WebSocket Protocol (`/ws/council`)

Client sends first message:
```json
{"token": "eyJ...", "message": "your question", "chat_id": "chat_123"}
```

Server streams:
```json
{"type": "council_ready", "selected": ["scout", "analyst", "chairman"]}
{"type": "phase_start",   "phase": "scout", "text": "Scanning sources..."}
{"type": "phase_done",    "phase": "scout", "tokens": 198, "provider": "openrouter"}
{"type": "final",         "response": "...", "council_used": [...], "credits_left": 9}
```

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              FRONTEND (HTML/JS)              │
│   Auth → Chat → Live Deliberation Stream     │
└──────────────────┬──────────────────────────┘
                   │ WebSocket + REST
┌──────────────────▼──────────────────────────┐
│              FASTAPI BACKEND                 │
│                                              │
│  CognitiveClassifier → ProtocolSelector      │
│  ContextGateway (Vault + Wiki + History)     │
│  CouncilDeliberation (7 directors)           │
│  Synthesizer + Verifier + Chairman           │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────▼──────────────────────────┐
│              LLM PROVIDERS                   │
│  OpenRouter → Claude → Gemini → Ollama       │
│  (4-level fallback, auto-routing)            │
└─────────────────────────────────────────────┘
```

---

## Features

- **Multi-agent deliberation** — 7+ specialized AI directors
- **Real-time streaming** — WebSocket phase-by-phase updates
- **Provider fallback** — OpenRouter → Claude → Gemini → Ollama
- **Local-first / BYOB** — bring your own API keys
- **4 UI themes** — dark, light, sepia, midnight
- **CEE-ready** — Polish, Ukrainian, English, Russian
- **Decision Journal** — every session logged with coherence score
- **Demo mode** — works offline without a server

---

## Roadmap

- [x] Core deliberation pipeline (Scout→Chairman)
- [x] WebSocket streaming
- [x] Auth + JWT
- [x] Multi-provider LLM routing
- [x] Public alpha
- [ ] Public deployment (Render/Hetzner)
- [ ] Experience Layer (helpfulness_score, outcome_label)
- [ ] Prometheus + Grafana observability
- [ ] AWS Activate deployment
- [ ] Knowledge Vault + LLM Wiki (v3.1)

---

## Founder

**Alex** / autoalex.ai  
Location: Łódź, Poland (CEE)  
Email: autoalexai@gmail.com  
Landing: [consilium-ai-v3.carrd.co](https://consilium-ai-v3.carrd.co)

---

## License

MIT
