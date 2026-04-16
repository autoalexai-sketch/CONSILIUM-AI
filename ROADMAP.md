# CONSILIUM AI — Roadmap

## Stage 0 — Public Alpha (DONE)
- [x] FastAPI backend running
- [x] WebSocket /ws/council streaming
- [x] Auth: /login /register /verify
- [x] Multi-provider LLM: OpenRouter, Claude, Gemini, Ollama
- [x] Frontend with demo mode
- [x] README, Dockerfile, .env.example, docker-compose
- [x] Public GitHub + Landing page

## Stage 1 — Public Demo (IN PROGRESS)
- [ ] Copy frontend to v30 correctly (`powershell copy_frontend.ps1`)
- [ ] Fix file:// → http://localhost:8000 serving
- [ ] Replace Ollama with Groq API for cloud deploy
- [ ] Choose hosting: Render / Railway / Hetzner VPS
- [ ] Domain + HTTPS (Let's Encrypt)
- [ ] Live demo link in README

## Stage 2 — AWS Activate
- [ ] Apply for Activate Founders ($1,000 credits) — low barrier, apply now
- [ ] Add founder block to landing (name, country, use case)
- [ ] Find Polish accelerator with AWS Provider status for Portfolio tier ($25k+)
- [ ] OpenSearch POC instead of local ChromaDB

## Stage 3 — Experience Layer
- [ ] Migration 009_add_experience_layer.py
- [ ] ExperienceService + ContextGateway extension
- [ ] Hooks in chat.py and council.py
- [ ] Log helpfulness_score, outcome_label, task_type
- [ ] Prompt/version registry

## Stage 4 — Observability
- [ ] Prometheus + Grafana (docker-compose ready)
- [ ] Cost-per-decision dashboard
- [ ] Health endpoint /health + /version

## Stage 5 — Scale
- [ ] PostgreSQL + Redis (production persistence)
- [ ] Knowledge Vault + LLM Wiki
- [ ] ECS Fargate / k8s deployment
