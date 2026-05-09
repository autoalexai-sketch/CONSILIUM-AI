# CLAUDE.md — CONSILIUM AI v3.0
# Этот файл читается в начале каждой сессии Claude Code.
# Obsidian vault: C:\Users\HP\OneDrive\Документы\my-ai-wiki\Consilium AI\

---

## 1. Think Before Coding
**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what is confusing. Ask.
- Check [[02_ARCHITECTURE]] and [[03_DECISIONS]] from Obsidian vault.

## 2. Simplicity First
**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" that wasn't requested.
- If you write 200 lines and it could be 50, rewrite it.

For CONSILIUM-AI specifically:
- Don't add provider adapters unless explicitly requested.
- Don't change consensus logic without comparing alternatives.
- Don't add cost/telemetry tracking without clear business case.

## 3. Surgical Changes
**Touch only what you must. Clean up only your own mess.**

- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- CLI command contracts are sacred. Don't break them.
- Provider routing must preserve fallback behavior.
- Don't touch index.html without explicit request.

## 4. Goal-Driven Execution
**Define success criteria. Loop until verified.**

- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Refactor X" → "Ensure tests pass before and after"

## 5. CONSILIUM-AI Specific Rules
- profile.dimensions — Set[CognitiveDimension], NOT a field. Use: next(iter(profile.dimensions), None)
- conftest.py — edit only as whole file via write_file
- Unicode files (Russian text) — use PowerShell with UTF8 encoding, not str_replace
- Provider chain order: Groq(1) → DeepSeek(2) → OpenRouter(3) → Gemini(4) → Ollama(5) — never change order
- WebSocket: token in message body, not URL. while True loop — never break it.

## 6. Obsidian Memory Rules
- Vault path: C:\Users\HP\OneDrive\Документы\my-ai-wiki\Consilium AI\
- Before session: read 00_START.md, 03_DECISIONS.md, 04_TODO.md
- After non-trivial work: update 03_DECISIONS.md with what changed and why
- End of session: append summary to 05_LOG.md
- Keep notes structured and non-duplicative
- Never store secrets (API keys, passwords) in vault

## 7. Запуск

```bash
cd "C:\Users\HP\OneDrive\Рабочий стол\Consilium AI v30"
uvicorn main:app --reload --port 8000
# Открывать: http://localhost:8000 (НЕ file://)
```

## 8. Частые ошибки — не повторять
- profile.primary_dimension — не существует → AttributeError → вечный спиннер
- git rebase вместо git pull --no-rebase -X ours при конфликтах
- Copilot ломает conftest.py — только write_file целиком
- updateCoherence(87, false) — хардкод убран, не возвращать
- S.currentBlock без S.sid — карточки попадают в первый блок