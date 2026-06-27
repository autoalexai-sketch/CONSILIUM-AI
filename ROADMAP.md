# CONSILIUM AI — Roadmap

> Source of truth for project status. README.md links here instead of
> keeping a second, easily-stale copy of this list.

## Stage 0 — Public Alpha (DONE)
- [x] FastAPI backend running
- [x] WebSocket /ws/council streaming
- [x] Auth: /login /register /verify
- [x] Multi-provider LLM fallback chain: Groq → DeepSeek V4 → OpenRouter → Gemini → Ollama
- [x] Frontend with demo mode
- [x] README, Dockerfile, .env.example, docker-compose
- [x] Public GitHub + Landing page

## Stage 1 — Public Demo (DONE)
- [x] Frontend served correctly at http://localhost:8000 (single-file SPA in `frontend/index.html`)
- [x] Replace Ollama-only with Groq/DeepSeek for cloud deploy (Ollama kept as local-only final fallback)
- [x] Hosting: Render.com
- [x] Domain + HTTPS: ai-consilium.com
- [ ] Live demo link prominently in README (currently buried in Founder section — fix during README cleanup)

## Stage 2 — AWS Activate & Accelerators
- [x] AWS Activate Founders credits approved ($1,160 grant)
- [x] Founder block on landing page
- [ ] PFR AI Startups Hunt 2026 — application submitted 2026-06-22, outcome pending
- [ ] Semantic search / RAG for Personal Vault (OpenSearch or pgvector — currently plain LIKE-based text search on `wiki_pages`, not vector search; pitch deck's "Personal Vault (RAG)" claim is roadmap, not shipped)

## Stage 3 — Experience Layer (DONE)
- [x] `experience_sessions` + `experience_signals` tables
- [x] ExperienceService (create_session / finalize_session / add_signal / get_session_count / get_session_detail / delete_session)
- [x] Hooks in `ws_council.py` + `council.py` (session_id links decision_journal → experience_sessions)
- [x] helpfulness_score, outcome_label, task_type, protocol_used all logged
- [ ] Prompt/version registry (track which prompt version produced which verdict — not built yet)

## Stage 4 — Observability
- [x] Health endpoint /health (+ HEAD for Render cold-start) and /version
- [x] Prometheus + Grafana (`docker-compose --profile monitoring up`, `monitoring/prometheus.yml`)
- [ ] Cost-per-decision Grafana panel (raw `total_cost_usd` data exists per deliberation; no dashboard panel built yet)

## Stage 5 — Scale & Knowledge
- [x] PostgreSQL on AWS RDS (eu-north-1) — production database
- [x] **Knowledge Vault + LLM Wiki** — `wiki_pages` table, full CRUD API (`/api/knowledge/wiki/*`), frontend search/add/pin/delete UI
- [x] **Session History API** — `/api/experience/sessions/*`, click-to-view saved Chairman verdict instead of re-running the query
- [x] **Protocol Manager** — `PROTOCOL_CONFIG` in `council.py`; Standard/Strategy/Crisis/Reflection/Planning/Deep actually change council composition + Chairman framing (previously cosmetic-only in the UI)
- [x] **Stripe credit top-up** — `/api/billing/*`, server-side pricing, signature-verified webhook, idempotent via `UNIQUE(stripe_session_id)`. Replaced and removed the old unauthenticated `/buy_credits` endpoint (was a live free-credits exploit).
- [x] GitHub Actions CI hardened — billing security tests (forged/missing/valid webhook signatures), protocol config sanity check, `/buy_credits` regression guard, repo-wide `py_compile` pre-check
- [ ] Redis — present in `docker-compose.yml` as a service, not yet integrated into any app code (no caching layer wired up)
- [ ] ECS Fargate / k8s deployment (still single Render.com instance)

## Open questions / things to verify before relying on them externally
- A third-party "technical & investment audit" surfaced GitHub repos
  (`yushakhov/consilium`, `pontus-espe/ai-consilium`, `imprecise-nest694/consilium-ai`)
  as evidence of "code fragmentation." These are unrelated projects that
  happen to share the word "consilium" in their name — the real repo is the
  single monorepo `autoalexai-sketch/CONSILIUM-AI`. Do not cite that
  fragmentation finding without correcting it first.
- Pitch deck claims "Tier 2: AWS Bedrock" in the fallback chain and a
  "local-first / BYOB data sovereignty" architecture. Neither exists in the
  current codebase (the real chain is Groq→DeepSeek→OpenRouter→Gemini→Ollama,
  and the backend is a normal FastAPI+PostgreSQL cloud service, not
  client-side/local-first). Treat these as roadmap items, not shipped
  features, if asked about them in due diligence.
