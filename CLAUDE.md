# CLAUDE.md for CONSILIUM-AI v 3.0

## Команды управления
- **Dev:** `npm run dev` / `pnpm dev`
- **Агенты:** `node scripts/test-agent.js` (если есть скрипты тестирования агентов)
- **Сборка:** `npm run build`

## Правила проектирования (Design Rules)
1. **Agent Isolation:** Логика каждого агента должна быть изолирована. Не допускай перекрестных зависимостей между `AgentA` и `AgentB` без участия посредника (Orchestrator).
2. **Schema First:** Все ответы от LLM должны валидироваться через Zod или интерфейсы TypeScript.
3. **Context Management:** При написании кода для обработки длинных диалогов всегда учитывай лимиты токенов (используй утилиты из `@/utils/tokenizer`).

## Стиль кода
- **Async/Await:** Только асинхронный код для всех запросов к API.
- **Naming:** Агенты и классы стратегий — `PascalCase`, утилиты и методы — `camelCase`.
- **Docs:** Каждая новая функция агента должна сопровождаться кратким описанием её "роли" в комментариях JSDoc.

## Context & Environment
## Context & Environment
- **Environment:** Конфигурация среды находится в папке `.env`.
- **API Keys & Credentials:**
  - `GROQ_API_KEY` — используется для высокоскоростного инференса через Groq.
  - `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` — ключи для доступа к LLM.
  - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` — учетные данные для работы с сервисами AWS.
- **Project Structure:** - Основной репозиторий: [GitHub CONSILIUM-AI](https://github.com/autoalexai-sketch/CONSILIUM-AI)
  - Публичная часть/Лендинг: Интеграция с Carrd.co.

## External Tools & Integrations
- **AWS:** Облачная инфраструктура для [хостинга/хранения/вычислений] проекта.
- **Groq:** Основной провайдер для задач, требующих минимальной задержки (Low-latency AI responses).
- **GitHub:** Контроль версий, совместная разработка и CI/CD процессы.
- **Carrd.co:** Используется для фронтенд-презентации или связки с ресурсами на AWS.