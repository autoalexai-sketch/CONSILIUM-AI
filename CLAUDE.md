# CLAUDE.md — CONSILIUM AI v3.0
# Этот файл читается в начале каждой сессии. Обновляй после значимых изменений.

## Что это за проект
CONSILIUM AI v3.0 — мультиагентная система делиберации ("Совет директоров") на FastAPI.
9 ролей: Scout, Analyst, Architect, Devil's Advocate, Synthesizer, Verifier, Chairman + др.
Цель: IWE (Intellectual Work Environment) для стратегических решений, CEE-рынок (PL/UA/EN).
Автор: Oleksandr Latyntsev, Łódź PL. GitHub: autoalexai-sketch/CONSILIUM-AI

---

## Запуск (ВАЖНО — только так)
```bash
cd "C:\Users\HP\OneDrive\Рабочий стол\Consilium AI v30"
uvicorn main:app --reload --port 8000
# Открывать: http://localhost:8000 (НЕ file://)
```

## Деплой
- Render.com: https://consilium-ai-paen.onrender.com
- Автодеплой при git push в main
- Render использует HEAD /health для cold-start healthcheck

---

## Стек
- **Backend:** Python 3.11, FastAPI, SQLAlchemy (SQLite), uvicorn
- **AI провайдеры (цепочка fallback):** Groq → DeepSeek V4 → OpenRouter → Gemini → Ollama
- **Frontend:** Чистый HTML/JS (frontend/index.html), WebSocket стриминг
- **Мониторинг:** Prometheus (опционально, docker compose --profile monitoring up)
- **CI/CD:** GitHub Actions (.github/workflows/ci.yml) — smoke tests

## Структура проекта
```
main.py                    # Точка входа FastAPI
app/
  api/
    auth.py                # JWT auth: /register /login /verify
    chat.py                # POST /chat
    council.py             # run_council_deliberation() — главная логика
    ws_council.py          # WebSocket /ws/council — while True loop
    experience.py          # GET /api/experience/sessions, POST /feedback
  database.py              # SQLAlchemy таблицы + init_database()
  config.py                # Settings из .env
  dependencies.py          # verify_jwt_token, get_current_user
  middleware/
    security.py            # Security headers
    rate_limiter.py        # Rate limiting
core/
  ai_fallback.py           # AIFallbackManager — цепочка провайдеров
  cognitive_classifier.py  # CognitiveClassifier → TaskProfile
  council_selector.py      # Выбор директоров по профилю задачи
  deliberation.py          # Движок делиберации фаз
  synthesizer_integration.py
  experience/
    experience_service.py  # create_session / finalize / add_signal
    experience_ranker.py   # semantic*weight + experience*weight
frontend/
  index.html               # Весь UI (64KB SPA)
```

---

## Ключевые архитектурные факты

### WebSocket протокол (/ws/council)
- Клиент шлёт: `{"token": "...", "message": "...", "chat_id": "..."}`
- Сервер стримит: `phase_start` → `phase_done` → `final`
- Соединение НЕ закрывается — while True loop, несколько вопросов подряд
- При cold-start Render: фронтенд показывает "сервер просыпается" (15с таймаут)

### Цепочка провайдеров (core/ai_fallback.py)
```
Уровень 1: Groq         (llama-3.3-70b-versatile) — бесплатный, быстрый
Уровень 2: DeepSeek V4  (deepseek-v4-pro) — $0.28/1M tokens
Уровень 3: OpenRouter   — платный
Уровень 4: Gemini       (gemini-2.0-flash) — бесплатный лимит
Уровень 5: Ollama       — локальный
```

### TaskProfile (cognitive_classifier.py)
- `dimensions: Set[CognitiveDimension]` — НЕТ поля primary_dimension
- Правильно: `_dim = next(iter(profile.dimensions), None)`

### Experience Layer (Этап 4)
- Таблицы: experience_sessions, experience_signals
- Автоматически логирует каждый WS запрос
- API: GET /api/experience/sessions, POST /api/experience/feedback

---

## Переменные окружения (.env)
```
SECRET_KEY=           # JWT подпись — ОБЯЗАТЕЛЬНО
GROQ_API_KEY=         # Приоритет 1 — получить на console.groq.com
OPENROUTER_API_KEY=   # Приоритет 3
ANTHROPIC_API_KEY=    # Claude Synthesizer
GEMINI_API_KEY=       # Приоритет 4
DEEPSEEK_API_KEY=     # Приоритет 2 — platform.deepseek.com
DATABASE_URL=sqlite:///./consilium.db
CORS_ORIGINS=*
```

---

## История багов и фиксов (Decision Log)

| Дата | Баг | Фикс | Файл |
|------|-----|------|------|
| апр 2026 | finalized флаг — Chairman двойной запуск | finalized=True после первой финализации | council.py |
| апр 2026 | HEAD /health — Render cold-start зависал | Добавлен HEAD endpoint + Response import | main.py |
| апр 2026 | "Входим..." — бесконечно на Render | AbortController 15с таймаут | frontend/index.html |
| апр 2026 | DeepSeek V4 — не было провайдера | Добавлен как уровень 2 в цепочку | core/ai_fallback.py |
| апр 2026 | CI красный — no such table: users | conftest.py autouse фикстура init_database() | tests/conftest.py |
| апр 2026 | Copilot сломал conftest.py | Перезаписан правильный файл | tests/conftest.py |
| апр 2026 | Chairman ответ обрезан | onFinalResponse обновляет st-chairman полным текстом | frontend/index.html |
| апр 2026 | Спиннер не исчезал | removeThinkRow → querySelectorAll(".think-row") | frontend/index.html |
| апр 2026 | Чат не открывался после регистрации | hideAuth: style.display='none' + classList.add | frontend/index.html |
| апр 2026 | Один вопрос на сессию | ws_council: while True loop | app/api/ws_council.py |
| апр 2026 | Docker build 15GB | .dockerignore исключает venv/ | .dockerignore |
| май 2026 | "classifier думает..." — вечный спиннер | AttributeError на primary_dimension → next(iter()) | app/api/council.py |
| май 2026 | Пустые карточки на 2-й вопрос | phase_error обработчик в frontend | frontend/index.html |

---

## Дорожная карта (статус)

| Этап | Описание | Статус |
|------|----------|--------|
| 0 | Backend перенос в v30, main.py без hardcoded путей | ✅ |
| 1 | Render deploy, Groq fallback | ✅ |
| 2 | CI/CD GitHub Actions, smoke tests | ✅ зелёный |
| 3 | AWS Activate подача | ✅ подан |
| 4 | Experience Layer MVP | ✅ |
| 5 | Prometheus + Grafana (docker profile) | ✅ |
| 6 | Knowledge Vault + ChromaDB RAG | ⬜ |
| 7 | Telegram bot | ⬜ |
| 8 | Freemium + Stripe | ⬜ |

---

## Правила работы с кодом
1. **Не трогай соседний код** — только то, что просили
2. **Unicode файлы** (русский текст) — редактировать через Python heredoc, не str_replace
3. **Проверяй синтаксис** — py_compile перед записью важных файлов
4. **Тесты** — pytest tests/ -q после изменений бэкенда
5. **Всегда спрашивай** если данных недостаточно — не додумывай

## Частые ошибки (не повторять)
- `profile.primary_dimension` — не существует, использовать `next(iter(profile.dimensions), None)`
- `from prometheus_fastapi_instrumentator import Instrumentator` — оборачивать в try/except
- Редактировать `conftest.py` — только через Filesystem:write_file целиком
- `git rebase` при конфликтах с Copilot — использовать `git pull --no-rebase -X ours`
