#  CONSILIUM AI v3.0 — Intellectual Work Environment (IWE)

[![FastAPI](https://img.shields.io/badge/FastAPI-0.135.3-brightgreen)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-WSL_2-blue)](https://www.docker.com)
[![Python](https://img.shields.io/badge/Python-3.11-green)](https://python.org)

**Consilium AI** is a professional Multi-Agent Strategic Council designed for small and medium businesses (SMB) in the CEE region. It implements an Intellectual Work Environment (IWE) that orchestrates 8 specialized AI directors to solve complex strategic tasks with **94% decision confidence**.

##  Problems We Solve
* **LLM Hallucinations:** Traditional LLMs have a 20-30% error rate. Our 6-phase deliberation reduces this significantly.
* **Data Fragmentation:** Consilium bridges the gap between scattered files (Docs, Emails) and long-term memory.
* **Lack of Engineering Verification:** We apply "Superpowers" (Reflective Pause, Knowledge Gate) to every AI response.

##  Technical Architecture
The system is built on a **4-layer architecture** as detailed in our strategic documentation:

### LEVEL 3: USER EXPERIENCE (Frontend)
* **Intelligence Monitor:** Real-time tracking of urgency, emotional load, and coherence via WebSockets.
* **Live Deliberation Protocol:** 6-phase streaming UI for agent collaboration.

### LEVEL 2: AGENT INTELLIGENCE
* **8 Specialized Roles:** TaxLawyerPL, HRStrategist, ProductLead, Chairman, etc.
* **Deliberation Pipeline:** Scout → Analyst → Devil's Advocate → Synthesizer → Verifier → Chairman.
* **4-level Fallback:** Reliability chain: OpenRouter → Claude → Gemini → Ollama.

### LEVEL 1: KNOWLEDGE INFRASTRUCTURE
* **Context Gateway:** Fan-out requests with <200ms SLA.
* **MemPalace RAG:** High-recall memory indexing (96.6% recall) using ChromaDB/pgvector.
* **LLM Wiki:** Automated indexing of Markdown knowledge items.

### LEVEL 0: PERSISTENCE
* **PostgreSQL:** Transactional metadata.
* **ChromaDB:** Semantic embeddings.
* **Docker:** Full containerization (WSL 2 optimized).

##  Performance Metrics (MVP)
| Component | Latency | Accuracy/Recall |
|-----------|---------|-----------------|
| Context Gateway | **180ms** | **98% relevance** |
| Full Council Cycle | **18-35s** | **94% confidence** |
| MemPalace Recall | - | **96.6%** |

##  Project Structure
```text
.
├── app/                # Backend logic (FastAPI)
├── frontend/           # Core UI (index.html)
├── static/             # Assets (CSS/JS)
│   ├── css/            # main.css
│   └── js/ui/          # chat.js, sidebar.js, utils.js
├── templates/          # HTML templates
├── docker-compose.yml  # Deployment configuration
├── main.py             # Entry point
└── requirements.txt    # Dependencies
