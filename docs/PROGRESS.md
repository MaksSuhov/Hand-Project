# Состояние проекта

Обновлено: 2026-11-12 (пакет `application/chat`, маппинг ошибок, Alembic)

## Сделано

- Создана структура документации (`docs/`) и правила проекта (`AGENTS.md`).
- Выбрана IDE: VS Code (ADR-0001), PyCharm не используется.
- Создано окружение проекта: `.venv` от python.org 3.14.7 (ADR-0002); Anaconda не задействована.
- Создан каркас приложения по слоям (`api` / `application` / `core` / `infrastructure` / `schemas`), ADR-0003.
- `app/main.py` — `GET /health` + подключённый `chat_router`; `title="Hand Project v 0.1.0"`.
- Зависимости зафиксированы в `requirements.txt`; `.gitignore`; коммит `cae8fec`; remote нет.
- `.env` с RouterAI (ключ, base_url, модель `deepseek/deepseek-v4.1-flash-1017`) и `DATABASE_URL`; в git не попадает.
- Настройки починены: `settings = Settings()` (`app/core/config.py:11`), `openai_client.py` использует экземпляр.
- `app/application/chat_service.py` — обычный класс-заглушка `ChatService` (наследование `Base` убрано).
- `ChatResponse.content` без `max_length`; в `ChatRequest` добавлен `conversation_id`.
- **Echo-срез работает** (проверено httpx/ASGI 2026-11-11): `GET /health` → 200; `POST /chat/` с `{conversation_id, content}` → 200 `{"conversation_id":0,"content":"..."}`.
- Инфраструктура переставлена: `app/api/routes/router.py` → `app/api/router.py`, `dependencies.py` → `app/api/dependencies.py`; роутеры перестали быть местом для DI.
- Начат слой БД (`app/infrastructure/db/`): `db.py` — `Base`, async engine, `AsyncSessionLocal`; `models.py` — `Conversation`, `Message`; `api/dependencies.py` — `get_session`.
- Выбран и начат async-стек БД: Postgres + `asyncpg==0.32.0` (установлен), ADR-0004.
- **Все каталоги `app/` оформлены реальными пакетами** (`__init__.py`): `app/`, `api/`, `api/routes/`, `application/`, `core/`, `infrastructure/`, `infrastructure/llm/`, `infrastructure/repositories/`, `schemas/` — пустые маркеры; `infrastructure/db/__init__.py` реэкспортирует `Base`, `engine`, `AsyncSessionLocal` (ADR-0005). Проверено 2026-11-11: `import` каждого пакета и `from app.infrastructure.db import Base` работают в `.venv`; echo-срез после правки — `GET /health` 200, `POST /chat/` 200.
- **Первый срез чата готов** (ADR-0006): `POST /chat` → `ChatService.handle` → `OpenAIChatClient.complete` → RouterAI. Echo убран, история пока не сохраняется.
  - `infrastructure/llm/openai_client.py` — класс `OpenAIChatClient` (клиент не создаётся на импорте; `timeout=30.0`, `max_retries=2`).
  - `application/chat_service.py` — `ChatService(llm)` + порт `LLMProvider` (`Protocol`), без импорта `openai`/FastAPI.
  - `api/dependencies.py` — `get_chat_service()` под `lru_cache`; `api/routes/chat_router.py` — `Depends`, `path=''`.
  - Контракт: `conversation_id` необязателен (`int | None = None`), ответ содержит `0`, пока нет БД.
  - Проверено 2026-11-11: реальный ответ RouterAI (`POST /chat` → 200 `{"conversation_id":0,"content":"отлично"}`); с фейковым LLM — проброс id 42, `null` → 0, пустой `content` → 422; `POST /chat/` → 307 на `/chat`.
- Зависимости БД установлены и записаны: `sqlalchemy[asyncio]==2.1.8` (+ `greenlet 3.5.6`), `asyncpg==0.32.0`.
- Docker 29.7.2 и Docker Compose v5.5.0 установлены; Postgres-контейнер создан и запущен пользователем, `localhost:5432` отвечает.
- **История диалога работает** (ADR-0007), проверено 2026-11-11:
  - `infrastructure/repositories/conversation_repository.py` — `SQLAlchemyConversationRepository` (создание диалога, загрузка сообщений, добавление, commit).
  - `ChatService(llm, repository)`: `conversation_id=None` → новый диалог; переданный id → загрузка истории, `ConversationNotFoundError` → HTTP 404 в роутере. В LLM уходит вся история + новое сообщение; оба сообщения сохраняются.
  - `api/dependencies.py` — `get_session` + `get_chat_service(session)`: сервис и репозиторий живут один запрос, `OpenAIChatClient` кешируется через `lru_cache`.
  - `infrastructure/db/models.py` — FK исправлен (`conversations.conversation_id`), `Mapped[datetime]`, `DateTime(timezone=True)`, `order_by='Message.message_id'`; `configure_mappers()` проходит.
  - Проверка: fake LLM через ASGI — новый диалог (`id=1`), продолжение (в LLM 3 сообщения: user/assistant/user), неизвестный id → 404; реальный RouterAI — модель запомнила число из первой реплики и ответила «7» на второй; в БД 1 диалог и 4 сообщения. Тестовые строки затем удалены.
- **Пакет `app/application/chat/`** (ADR-0008): `service.py` (`ChatService`), `ports.py` (`LLMProvider`, `ConversationRepository`), `dto.py` (`ChatMessage`), `errors.py` (`ChatError`, `ConversationNotFoundError`, `LLM*`). Старый `application/chat_service.py` удалён; импорты обновлены. Договорённость: новые порты/DTO/ошибки чата пишутся только сюда.
- **Маппинг ошибок провайдера** (ADR-0009): адаптер ловит `openai.OpenAIError` и поднимает прикладные `LLMUnavailableError` (502), `LLMTimeoutError` (504), `LLMRateLimitedError` (429), `LLMConfigurationError` (503), `LLMRequestRejectedError` (422); `ConversationNotFoundError` → 404. Маппинг в `api/routes/chat_router.py`. Проверено fake LLM через HTTP и таблицей соответствий в адаптере.
- **Alembic внедрён** (ADR-0010): `alembic==1.20.1`, async `env.py` берёт URL из `settings.DATABASE_URL`, `target_metadata = Base.metadata`. Начальная миграция `alembic/versions/fa04bfd1fe77_create_chat_tables.py`; `upgrade head` → `downgrade base` → `upgrade head` проверены. `init_db.py` удалён: единственный источник схемы — миграции.
- Проверено 2026-11-12: реальный RouterAI после рефакторинга — второй запрос воспроизвёл число «11» из истории; тестовые строки удалены.
- Накопленный срез закоммичен 2026-11-12: 12 коммитов по слоям (пакеты → settings → зависимости → БД → Alembic → порты/DTO/ошибки → LLM → схемы → история → API → docs → `.zcodeignore`).
- **Дальше по плану — streaming** (SSE/JSON-формат ещё не выбран): порт и контракт ответа будут меняться; учитывать, что после отправки заголовков код ошибки поменять нельзя.

## В работе

- Streaming: ближайший функциональный шаг; формат ответа (SSE или JSON-поток) не выбран.
- Автоматических тестов нет: проверки ручные (ASGI + фейковый LLM), `pytest` не установлен.
- В модель уходит вся история без обрезки по токенам/длине.

## Блокеры

1. `app/api/router.py` пуст, хотя задумывался как сборщик роутеров; `main.py` импортирует `chat_router` напрямую. Решить: заполнить агрегатор или удалить.

## Следующие шаги (в этом порядке)

1. Streaming: выбрать формат (вероятно SSE), расширить `LLMProvider` (стриминговый метод) и контракт ответа; ошибки после начала потока отдавать событием, не HTTP-кодом.
2. Тесты: pytest + httpx, фейковый LLM/репозиторий (паттерн override из `api/dependencies.py`).
3. Ограничение истории: обрезка по числу сообщений/токенам перед вызовом LLM.
4. Заполнить или удалить `app/api/router.py`.
5. По мере изменения моделей — новая ревизия Alembic (`alembic revision --autogenerate`), не `create_all`.

## Известные проблемы / замечания

- ~~`Settings.OPENAI_API_KEY` с класса~~ — закрыто (экземпляр `settings`).
- ~~`@router.post` без `path`~~ — закрыто (`path='/'`, см. блокер 6 про слэш).
- ~~`ChatService(Base)`~~ — закрыто (обычный класс).
- ~~`include_router` получал модуль~~ — закрыто (`from ... import router as chat_router`).
- ~~`ChatResponse.content` max_length~~ — закрыто.
- ~~`Mapped[DateTime]` (`models.py:13,27`)~~ — закрыто: `Mapped[datetime]` + `DateTime(timezone=True)` (timestamptz).
- ~~`get_session` без аннотации возврата~~ — закрыто: `AsyncGenerator[AsyncSession, None]`.
- `Conversation()` создаётся без явных полей; `flush()` даёт `conversation_id`. Commit — в `ChatService` в конце сценария; при ошибке LLM сессия закрывается без commit (rollback).
- История в LLM не ограничена: длинный диалог упрётся в контекст модели/лимит запроса. Нужна стратегия обрезки.
- Alembic не подхватывает изменения моделей сам: после правки `models.py` нужна новая ревизия (`alembic revision --autogenerate`) и `alembic upgrade head`.
- Streaming изменит обработку ошибок: если поток уже начат, HTTP-код ответа не поменять — ошибку придётся отдавать событием в потоке.
- ~~`openai_client` создаётся на импорте~~ — закрыто: `OpenAIChatClient` создаёт клиент в `__init__`, есть `timeout=30.0` и `max_retries=2`.
- `Settings` молча подставляет `"place your API key"` и дефолтный `DATABASE_URL` с паролем — лучше обязательные поля + `.env.example`.
- `.env.example` предусмотрен в `.gitignore`, но файла нет.
- ~~Нет `__init__.py` в `app/` и подпакетах~~ — закрыто (ADR-0005): все пакеты стали реальными; `repositories/` теперь хранится в git.
- `pytest` не установлен; тестов нет.
- Code Runner в VS Code запускает Anaconda-питон вместо `.venv`.
- `unit_of_work.py` пуст — сознательно не трогаем до второго репозитория (ADR-0003).

## Внедрение LangChain / LangGraph / Langfuse — триггеры (рекомендация, не ADR; 2026-11-11)

- В `.venv` стоят `langchain 1.4.9`, `langchain-core 1.7.7`, `langgraph 1.2.20`, `langgraph-checkpoint 4.3.1`; `langchain-openai` и `langfuse` не установлены.
- **Langfuse — первым из троих**, после текущего шага streaming: от LangChain не зависит, правка в 1 файле `infrastructure/llm/`, даёт session/token/latency/cost; `session_id = conversation_id`.
- **LangChain — по триггеру**: RAG/embeddings, tools/function calling, structured output, второй провайдер. Вставляется адаптером за существующий порт `LLMProvider`.
- **LangGraph — по триггеру**: ветвление/цикл, агент с инструментами, HITL, resume/checkpoint, streaming шагов. В 1.x агенты LangChain (`create_agent`) сами построены на LangGraph.
- Checkpointer LangGraph — не хранилище истории продукта: история в своих таблицах, checkpointer только для состояния графа.
- Версии 1.x: туториалы 0.x неприменимы (legacy chains вынесены в `langchain-classic`).

## Открытые вопросы

- Идея продукта формально не зафиксирована в `PRD.md` (по коду — LLM-чат с историей).
- Streaming: SSE или другой формат (JSON-поток)? Решено делать streaming следующим, формат ещё нет.
- История: свои таблицы (выбранный путь) vs checkpointer LangGraph — зафиксировать, когда появится LangGraph.