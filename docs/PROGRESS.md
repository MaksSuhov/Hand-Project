# Состояние проекта

Обновлено: 2026-11-19 (окружение восстановлено, рабочая копия разбита на 9 коммитов и отправлена в `origin/main`; предыдущая запись 2026-11-16 — RAG на pgvector: образ БД заменён на `pgvector/pgvector:pg17`, синтетическая корпоративная база знаний — 16 документов / 75 чанков, ответы `/chat` и `/chat/stream` опираются на неё; eval-функции — следующий шаг)

## Сделано

- Создана структура документации (`docs/`) и правила проекта (`AGENTS.md`).
- Выбрана IDE: VS Code (ADR-0001), PyCharm не используется.
- Создано окружение проекта: `.venv` от python.org 3.14.7 (ADR-0002); Anaconda не задействована.
- Создан каркас приложения по слоям (`api` / `application` / `core` / `infrastructure` / `schemas`), ADR-0003.
- `app/main.py` — `GET /health` + подключённый `chat_router`; `title="Hand Project v 0.1.0"`.
- Зависимости зафиксированы в `requirements.txt`; `.gitignore`; коммит `cae8fec`; remote тогда не было (появился позже — см. срез после `5fb8853`).
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
- **Окружение восстановлено 2026-11-19:** `.venv` пересоздан (python.org 3.14.7) + `pip install -r requirements.txt`; Docker Desktop запущен, `handproject-postgres` healthy, том переиспользован (75 чанков на месте), `alembic current` = `8d4b2f1c9a71`; `pytest -q` → 16 passed.
- **Накопленный после `5fb8853` срез разобран на коммиты и запушен 2026-11-19** — 9 коммитов:
  1. `build(deps)` — langfuse, pgvector, `langchain-text-splitters`, pytest;
  2. `chore(infra)` — `compose.yaml` с `pgvector/pgvector:pg17`;
  3. `refactor(api)` — сборка роутеров в `api_router` (ADR-0012);
  4. `feat(observability)` — настройки RAG/Langfuse, `init_tracing()`/`shutdown_tracing()` в lifespan;
  5. `feat(knowledge)` — порт/адаптеры базы знаний, grounding-промпт, модель и миграция `8d4b2f1c9a71`, корпус и сид;
  6. `feat(chat)` — SSE `/chat/stream`, `ChatExchange`, `UnitOfWork`, `ChatCommand`/`ChatAnswer`/`Role`, маппинг ошибок, RAG в `ChatService`;
  7. `test` — чат и SSE на фейках;
  8. `test` — RAG grounding и деградация;
  9. `docs` — ADR-0011…0017 и текущее состояние.
  `origin/main` до пуша содержал только `cae8fec` (начальный каркас).
- **Langfuse подключён в адаптер** (ADR-0011), `langfuse==5.2.0` записан в `requirements.txt`; агрегатор роутеров исправлен по ADR-0012:
  - `app/infrastructure/observability/tracing.py` — `init_tracing()`/`shutdown_tracing()`, клиент создаётся явно из `settings` (`LANGFUSE_PUBLIC_KEY/SECRET_KEY/BASE_URL`), `environment="development"`, при пустом public key — no-op; `shutdown()` флашит батчи.
  - `app/main.py` — `lifespan`: `init_tracing()` на старте, `shutdown_tracing()` на остановке; подключается один `api_router`.
  - `application/chat/ports.py` — `LLMProvider.complete(..., *, conversation_id=None)`; `service.py` передаёт id диалога; `openai_client.py` импортирует `AsyncOpenAI` из `langfuse.openai`.
  - **Дефект 5.2.0 (исправлен):** `session_id` (как и `user_id`/`tags`) не вырезается обёрткой из kwargs и уходит в OpenAI SDK → `TypeError: AsyncCompletions.create() got an unexpected keyword argument 'session_id'` → HTTP 500. В адаптере убран kwarg, вызов обёрнут в `with propagate_attributes(session_id=str(conversation_id))`.
  - **Проверено 2026-11-12 end-to-end:** `POST /chat` → 200 (`{"conversation_id":2,"content":"Привет!"}`); Langfuse Observations API v2: generation `chat.completion`, `sessionId=2`, model `deepseek/deepseek-v4.1-flash-1017`, usage `input 39 / output 3`, `totalCost=0.00686`, latency 2.3 с, input/output заполнены. Тестовый диалог `2` удалён из БД (2 сообщения + 1 диалог).
  - Попутно: Postgres был недоступен (`Docker daemon` не запущен) — это давало второй, независимый 500; после запуска Docker Desktop контейнер `handproject-postgres` поднялся сам.
  - Вывод по streaming: обёртка поддерживает async-streaming и сама финализирует generation, поэтому при SSE Langfuse-код почти не меняется.
- **SSE-стриминг реализован** (ADR-0013), проверено 2026-11-12 фейковым LLM и живым RouterAI:
  - `POST /chat/stream` — `response_class=EventSourceResponse`, endpoint сам является async-генератором. FastAPI 0.162.3 ставит `text/event-stream; charset=utf-8`, `Cache-Control: no-cache`, `X-Accel-Buffering: no` и keep-alive `: ping` каждые 15 с; `sse-starlette` не понадобился.
  - Контракт событий: `meta {conversation_id}` → `delta` (`raw_data`, сырой текст) → `done {conversation_id}`. Ошибки после отправки заголовков — `error {code, message}` с закрытием потока; ошибки до стрима остаются HTTP: `get_prepared_chat` ловит `ChatError` и отдаёт 404/422/… (позже переименован в `get_chat_exchange`, ADR-0014).
  - `application`: `LLMProvider.stream(...) -> AsyncIterator[str]` (в `Protocol` объявлен через `def`, не `async def`), `PreparedChat` в `dto.py`, `ChatService.prepare()` + `ChatService.stream()`; `handle()` переиспользует `prepare()` (позже `PreparedChat` заменён на `ChatExchange`, ADR-0014).
  - `OpenAIChatClient.stream()`: `stream=True`, `stream_options={'include_usage': True}`, `try/except OpenAIError` вокруг всей итерации (обрыв соединения приходит во время `async for`), `await stream.close()` в `finally`, `propagate_attributes` оборачивает всю итерацию.
  - Проверено фейковым LLM: `meta/delta/done`, история в LLM (`user/assistant/user`), неизвестный диалог → 404, сбой провайдера → `delta`… + `error` (HTTP 200), `/chat` продолжает работать. Живой RouterAI (`deepseek/deepseek-v4.1-flash-1017`): 11 кадров, текст собран из `delta`, в БД user+assistant.
  - Langfuse v2 (`fields=core,basic,usage,io,model`): стриминговая generation `chat.completion` с `sessionId`, моделью, input/output, usage `input 47 / output 25 / reasoning 212`, `totalCost=0.01764`. RouterAI подтверждённо поддерживает `include_usage` (финальный чанк: `choices=[]`, `usage.cost`).
  - Тестовые строки удалены (диалог `4`).
- **Рефакторинг слоёв (ADR-0014), проверено 2026-11-12 фейками:**
  - `ChatCommand`/`ChatAnswer` развязали `application` от Pydantic-схем; `MAX_CONTENT_LENGTH` переехал в `application/chat/dto.py`, схема импортирует константу; маппинг — в роутере.
  - `Role` — `StrEnum` (`user`/`assistant`); `add_message(conversation_id, ChatMessage)` вместо `str`-частей; репозиторий маппит `Role` на чтении/записи.
  - `PreparedChat` заменён на `ChatExchange` (`application/chat/exchange.py`): `complete()`/`stream()` + `_finish()`; инвариант «user добавлен, ответ не сохранён» выражен типом.
  - Commit переехал в `UnitOfWork` (`SQLAlchemyUnitOfWork`), у `ConversationRepository` убран; `ChatService` получает третий порт.
  - Ошибки: одна таблица в `api/error_mapping.py` (`isinstance`), HTTP и SSE отдают `{code, message}`; в адаптере убрано дублирование payload/`session_id`.
  - Проверка: `compileall` + фейковый LLM/repo/UoW — `/chat` 200, `/chat/stream` meta/delta/done, неизвестный диалог → 404 `conversation_not_found`, таймаут → 504 `provider_timeout` и SSE `error`, пустой/801 символ → 422. Живой RouterAI после рефакторинга не перепроверялся.
- **Автотесты** (ADR-0015): `pytest 9.2.0` + `pytest-asyncio 1.5.0` в `requirements.txt`; `pytest.ini` (`asyncio_mode=auto`); `tests/conftest.py` — `FakeLLM`/`FakeRepository`/`FakeUnitOfWork` и подмена `get_chat_service` через `dependency_overrides`; `tests/test_chat.py` и `tests/test_chat_stream.py` — 14 тестов (200, история, 404, 504, 422, `meta/delta/done`, пять кодов SSE `error`). `pytest -q` → 14 passed за 0,04 с, без БД и сети.
- **RAG на pgvector** (ADR-0016), проверено 2026-11-16 живым RouterAI:
  - БД: `compose.yaml` с `pgvector/pgvector:pg17` (контейнер `handproject-postgres`, том `handproject_pgdata` переиспользован, данные сохранены). Расширение `vector 0.8.7`; collation после смены образа поправлена (`ALTER DATABASE ... REFRESH COLLATION VERSION` + `REINDEX DATABASE`).
  - Миграция `8d4b2f1c9a71`: `CREATE EXTENSION vector`; таблица `knowledge_chunks` (`source`, `title`, `heading`, `chunk_index`, `content`, `embedding vector(1024)`, `created_at`), unique `(source, chunk_index)`, HNSW-индекс `vector_cosine_ops`. Проверены `downgrade -1` → `upgrade head`.
  - Прикладной слой: `application/knowledge/` (`KnowledgeChunk`, порт `KnowledgeBase`, `KnowledgeError`); в `application/chat/` — `prompt.py` (grounding-промпт с источниками и запретом выдумывать), `Role.SYSTEM`, `ChatService(..., knowledge, top_k)`. Поиск идёт по текущему сообщению; при ошибке KB чат продолжает работать с пустым контекстом («Фрагменты не найдены»).
  - Инфраструктура: `OpenAIEmbeddings` (`baai/bge-m3`, 1024 измерения, обычный `openai.AsyncOpenAI` — эмбеддинги не пишутся в Langfuse) и `PgVectorKnowledgeBase` (`ORDER BY embedding <=> vec LIMIT k`).
  - Корпус: `knowledge_base/` — 16 документов вымышленной ООО «Северный Ветер» (HR, ИТ, финансы, продукт, поддержка, контакты) + два архивных документа-ловушки. Загрузка — `scripts/seed_knowledge.py` через LangChain-сплиттеры; 75 чанков, повторный запуск идемпотентен.
  - Калибровка: релевантные чанки дают score 0.49–0.74, оффтоп ≤0.37 → `RAG_MIN_SCORE=0.45`, `RAG_TOP_K=5`.
  - Живая проверка `/chat`: отпуск — 28 дней (архивные 24 не использованы), суточные за рубеж — 3 500 ₽, потеря ноутбука — 2 часа + ServiceDesk/ИБ, вопрос про борщ — корректный отказ, вопрос про 2022 год — ответ с пометкой «не действует». `/chat/stream` отдаёт `meta/delta/...` с тем же контекстом. Тестовые диалоги удалены.
  - Тесты: 16 passed (`FakeKnowledge` в `conftest.py`, `tests/test_rag.py` — контекст в system-сообщении и graceful degradation).

## В работе

- Langfuse: интегрирован (Cloud, drop-in обёртка), проверен и для `/chat`, и для `/chat/stream`; в UI не смотрели.
- Автотесты: 16 тестов на `/chat`, `/chat/stream` и RAG (фейки); юнит-тестов адаптеров (`_to_llm_error`, embeddings) и проверки инкрементальности SSE в pytest пока нет.
- RAG: контекст ищется только по текущему сообщению (без переформулировки вопроса) и не обрезается по токенам; корпус статичный — переиндексация только через `scripts.seed_knowledge`.
- В модель уходит вся история без обрезки по токенам/длине.

## Блокеры

- Нет (2026-11-19). Окружение восстановлено: `.venv` пересоздан, зависимости из `requirements.txt`, Postgres с pgvector поднят (`docker compose up -d`, контейнер healthy), БД на ревизии `8d4b2f1c9a71`, `pytest -q` → 16 passed.
- Ранее блокеров не было. (`api/router.py` исправлен по ADR-0012; Langfuse-баг закрыт, HTTP-путь проверен; pgvector-образ и расширение работают.)

## Следующие шаги (в этом порядке)

1. **Eval-прогоны** (следующий шаг по договорённости): набор вопросов/эталонных ответов по `knowledge_base/`, метрики retrieval (hit@k, MRR) и ответа (факт/число/источник), прогон против текущего пайплайна.
2. Ограничение истории: обрезка по числу сообщений/токенам перед вызовом LLM (учесть system-промпт RAG).
3. Query rewriting для follow-up вопросов («а сколько переносится?») — иначе поиск идёт по короткой фразе без контекста диалога.
4. Посмотреть трейсы в UI Langfuse (Traces/Sessions) — данные уже доходят, включая стриминговые.
5. Фронтенд: парсер SSE на `fetch` + `ReadableStream` (нативный `EventSource` не умеет `POST`).
6. По желанию — hybrid search (BM25 + vector), rerank (voyage/rerank доступен в RouterAI), юнит-тесты `ChatExchange`/`ChatService`/адаптеров.

## Известные проблемы / замечания

- ~~`Settings.OPENAI_API_KEY` с класса~~ — закрыто (экземпляр `settings`).
- ~~`@router.post` без `path`~~ — закрыто (`path='/'`, см. блокер 6 про слэш).
- ~~`ChatService(Base)`~~ — закрыто (обычный класс).
- ~~`include_router` получал модуль~~ — закрыто (`from ... import router as chat_router`).
- ~~`ChatResponse.content` max_length~~ — закрыто.
- ~~`Mapped[DateTime]` (`models.py:13,27`)~~ — закрыто: `Mapped[datetime]` + `DateTime(timezone=True)` (timestamptz).
- ~~`get_session` без аннотации возврата~~ — закрыто: `AsyncGenerator[AsyncSession, None]`.
- `Conversation()` создаётся без явных полей; `flush()` даёт `conversation_id`. Commit — в `ChatExchange._finish` через `UnitOfWork`; при ошибке LLM сессия закрывается без commit (rollback).
- История в LLM не ограничена: длинный диалог упрётся в контекст модели/лимит запроса. Нужна стратегия обрезки.
- Alembic не подхватывает изменения моделей сам: после правки `models.py` нужна новая ревизия (`alembic revision --autogenerate`) и `alembic upgrade head`.
- SSE: после первого кадра HTTP-код не поменять — сбои провайдера уходят событием `error`, а не-`ChatError` исключения рвут соединение (намеренно, это баги).
- ~~`openai_client` создаётся на импорте~~ — закрыто: `OpenAIChatClient` создаёт клиент в `__init__`, есть `timeout=30.0` и `max_retries=2`.
- `Settings` молча подставляет `"place your API key"` и дефолтный `DATABASE_URL` с паролем — лучше обязательные поля + `.env.example`.
- `.env.example` предусмотрен в `.gitignore`, но файла нет.
- ~~Нет `__init__.py` в `app/` и подпакетах~~ — закрыто (ADR-0005): все пакеты стали реальными; `repositories/` теперь хранится в git.
- ~~`pytest` не установлен; тестов нет~~ — закрыто (ADR-0015): 14 тестов, `.venv/bin/python -m pytest -q`. Тесты идут через HTTP-слой; отдельных юнит-тестов `ChatService`/`ChatExchange`/адаптера нет.
- Langfuse 5.2.0: kwargs `session_id`/`user_id`/`tags` в `chat.completions.create` не вырезаются и ломают запрос; в адаптере уже используется `propagate_attributes(...)` — при добавлении `user_id`/`tags` делать так же.
- `init_tracing()` вызывает синхронный `auth_check()` в async lifespan: до 5 с блокировки event loop на старте (сейчас проходит быстро).
- `.env.example` нет; теперь ему нужны ещё `LANGFUSE_PUBLIC_KEY/SECRET_KEY/BASE_URL`.
- Стоимость берётся из `usage.cost`, который возвращает RouterAI; для моделей/провайдеров без `cost` понадобится прайс в настройках проекта.
- ~~Для streaming не проверено, поддерживает ли RouterAI `stream_options={"include_usage": True}`~~ — закрыто: поддерживает (финальный чанк с `choices=[]` и `usage.cost`), usage/cost попадают в стриминговый трейс Langfuse.
- SSE держит соединение с БД на всё время стрима (сессия из `get_session` живёт до последнего чанка). Для одного-двух пользователей нормально; при нагрузке пул может кончиться — тогда финальное сохранение вынести в отдельную короткую сессию.
- Обрыв клиента = отмена генератора и отсутствие `commit`: ответ не сохраняется, user-сообщение тоже (всё-или-ничего, как и в `/chat` при ошибке провайдера).
- Code Runner в VS Code запускает Anaconda-питон вместо `.venv`.
- `unit_of_work.py` реализован (`SQLAlchemyUnitOfWork`, ADR-0014); второго репозитория пока нет.
- `messages.role` — строка без check-констрейнта; `Role` проверяется при чтении в `SQLAlchemyConversationRepository` (неизвестное значение → `ValueError`). Если нужен инвариант в БД — миграция с `CHECK (role IN ('user','assistant'))`.
- HTTP-ошибка теперь отдаёт `detail={"code", "message"}` вместо строки (ADR-0014); контракт SSE не менялся.
- RAG: `RAG_MIN_SCORE=0.45` откалиброван на синтетическом корпусе и модели `baai/bge-m3`; при смене модели/корпуса порог надо перепроверить (у bge-m3 сжатая шкала сходства). Порог — единственная защита от оффтопа, без eval-набора.
- RAG: размерность эмбеддинга зашита в модель и миграцию (`vector(1024)`). Смена модели на другую размерность = новая миграция + переиндексация всего корпуса.
- RAG: архивные документы специально попадают в топ выдачи (score до 0.68) — корректность держится на промпте и пометке «Архив» в заголовке. Это осознанная ловушка для eval, а не дефект.
- RAG: цитаты в ответе формирует модель по промпту — ссылки не проверяются программно; при eval стоит проверять `source` отдельно.
- RAG: `scripts/seed_knowledge.py` не инкрементальный (удаляет и перезаливает чанки источника), удалённые из `knowledge_base/` файлы остаются в таблице до `--reset`.
- RAG: эмбеддинги идут обычным `openai.AsyncOpenAI` (не через Langfuse): обёртка на `embeddings.create` создавала отдельные трейсы без сессии и шумела в логах сида.
- `compose.yaml` переиспользует внешний том `handproject_pgdata`; при первом переходе с `postgres:17` на `pgvector/pgvector:pg17` нужен `REFRESH COLLATION VERSION` (сделано).

## Streaming — факты, на которые опирается реализация (2026-11-12)

- FastAPI 0.162.3 содержит встроенный SSE: `from fastapi.responses import EventSourceResponse`, `from fastapi.sse import ServerSentEvent`. Достаточно `response_class=EventSourceResponse` на endpoint-е, который сам является async-генератором; `sse-starlette` не нужен. FastAPI сам ставит заголовки, keep-alive и документирует ответ в OpenAPI.
- `ServerSentEvent`: `event`, `data` (всегда JSON; строки уходят в кавычках с `\uXXXX`), `raw_data` (как есть), `id`, `retry`, `comment`. Если endpoint — async-генератор без `response_class`, FastAPI стримит JSONL (`application/jsonl`) — запасной вариант без event-фрейминга и keep-alive.
- `Depends`-зависимости с `yield` живут до конца стриминга: `request_stack` в `fastapi/routing.py` оборачивает и вызов endpoint-а, и `await response(...)` (проверено в исходнике и в рантайме). Поэтому `get_session` работает внутри генератора, но соединение занято весь стрим.
- HTTP-заголовки (200) отправляются до первого `yield`: ошибка до стрима меняет код только через зависимость; исключение внутри генератора рвёт соединение (`ExceptionGroup`), поэтому ошибки потока — событием `error`.

## Внедрение LangChain / LangGraph / Langfuse — триггеры (обновлено 2026-11-12)

- `langfuse 5.2.0` установлен и интегрирован (ADR-0011); `langchain 1.4.9`, `langgraph 1.2.20` стоят, `langchain-openai` нет.
- **LangChain — включён точечно (ADR-0017)**: `langchain-text-splitters 1.1.3` используется только в `scripts/seed_knowledge.py` (`MarkdownHeaderTextSplitter` + `RecursiveCharacterTextSplitter`). Runtime-путь RAG — чистые SQLAlchemy/`openai`, без chains/vectorstore.
- **Langfuse — сделан первым из троих**, до streaming: Cloud, drop-in `langfuse.openai.AsyncOpenAI` в адаптере, `session_id = conversation_id`; правка `application` — только параметр порта.
- SDK v4+ (OpenTelemetry): актуальный API — `get_client()`, `start_as_current_observation(as_type=...)`, `propagate_attributes(...)`, `@observe`. Примеры v2 (`langfuse.trace()`, `generation()`) и v3 неприменимы; `langfuse` требует Python `>=3.11`.
- **LangChain — по триггеру**: RAG/embeddings (включён частично, ADR-0017), tools/function calling, structured output, второй провайдер. Вставляется адаптером за существующий порт `LLMProvider` или отдельным портом.
- **LangGraph — по триггеру**: ветвление/цикл, агент с инструментами, HITL, resume/checkpoint, streaming шагов. В 1.x агенты LangChain (`create_agent`) сами построены на LangGraph.
- Checkpointer LangGraph — не хранилище истории продукта: история в своих таблицах, checkpointer только для состояния графа.
- Версии 1.x: туториалы 0.x неприменимы (legacy chains вынесены в `langchain-classic`).

## Ревью слоёв/ООП — 2026-11-12 (закрыто рефакторингом, ADR-0014)

- `application` развязан от Pydantic-схем: `ChatCommand`/`ChatAnswer`, маппинг в роутере; `MAX_CONTENT_LENGTH` — в `dto.py`.
- Транзакция вынесена в `UnitOfWork`/`SQLAlchemyUnitOfWork`; у репозитория `commit` убран.
- `PreparedChat` заменён на `ChatExchange` (`complete`/`stream` + `_finish`); инвариант обмена внутри объекта.
- `Role` — `StrEnum`; `add_message` принимает `ChatMessage`.
- Ошибки: одна таблица `api/error_mapping.py`, поиск по `isinstance`, тело HTTP/SSE `{code, message}`.
- Адаптер: `_to_payload`/`_to_session_id`/`_GENERATION_NAME` убрали дублирование.
- Осталось: `role` в БД без check-констрейнта; `ruff` не подключён (косметика выправлена вручную в затронутых файлах).

## Открытые вопросы

- Идея продукта формально не зафиксирована в `PRD.md` (по коду — LLM-чат с историей).
- Streaming: выбран SSE через встроенный `EventSourceResponse` (ADR-0013); JSONL остался запасным вариантом.
- История: свои таблицы (выбранный путь) vs checkpointer LangGraph — зафиксировать, когда появится LangGraph.
- Celery (2026-11-13, требование вакансии; разобрали устройство и порог входа): решение не принято, изучать — в отдельной песочнице, не в этом репозитории. Ключевой конфликт: воркеры Celery синхронные, а весь проект async (`asyncpg`, `AsyncSession`, `AsyncOpenAI`). Если понадобится фоновая обработка под текущий стек — сначала смотреть ARQ/TaskIQ (async-native); Celery — если нужен именно стандарт из вакансии.
- Celery, окружение для песочницы (2026-11-13): десктопное приложение не нужно, всё из терминала. Брокер — `brew install redis` + `redis-server` (или `docker run redis:7-alpine`; Docker Desktop уже стоит, но демон сейчас выключен) либо RabbitMQ (тяжелее: Erlang). Воркер — `celery -A tasks worker`. `celery 5.7.0` объявляет Python 3.14 в классификаторах PyPI, т.е. `3.14.7` подходит. Flower — опциональный веб-UI из pip-пакета, не приложение.