# Архитектура

> Статус: чат с сохранением истории и RAG по корпоративной базе знаний (pgvector) работают сквозным сценарием с RouterAI; есть SSE-стриминг `/chat/stream`; Langfuse пишет трейсы для обоих режимов; слои развязаны по ADR-0014 (RAG — ADR-0016, LangChain — ADR-0017); автотесты — `pytest`, 16 шт. на фейках (ADR-0015).

## Стек и обоснование

Установлено в `.venv` и зафиксировано в `requirements.txt` (2026-11-10, обновлено 2026-11-16):

| Роль | Пакет | Версия |
|---|---|---|
| HTTP | `fastapi` / `uvicorn` / `starlette` | 0.162.3 / 0.54.0 / 1.10.0 |
| Валидация | `pydantic` / `pydantic-settings` | 2.14.3 / 2.16.2 |
| БД | `SQLAlchemy` / `asyncpg` (+ `greenlet`) / `alembic` / `pgvector` | 2.1.8 / 0.32.0 / 3.5.6 / 1.20.1 / 0.5.1 |
| RAG | `langchain-text-splitters` (только ingestion) | 1.1.3 |
| LLM/агенты | `langchain` / `langgraph` / `openai` | 1.4.9 / 1.2.20 / 3.49.0 |
| Наблюдаемость | `langfuse` | 5.2.0 (в `requirements.txt`) |
| Тесты | `pytest` / `pytest-asyncio` | 9.2.0 / 1.5.0 (в `requirements.txt`) |

Python 3.14.7 (`.venv`, ADR-0002). По зависимостям проект — чат/агент на LLM с БД и векторным поиском.

FastAPI 0.162.3 содержит встроенный SSE (`fastapi.sse.EventSourceResponse`, `ServerSentEvent`): отдельный `sse-starlette` не нужен. Проверенные детали (keep-alive, жизненный цикл `Depends` при стриминге, ошибки после заголовков) — в `PROGRESS.md`, раздел «Streaming».

## Карта проекта

| Путь | Назначение | Состояние |
|---|---|---|
| `app/main.py` | точка входа FastAPI | `GET /health` + `include_router(api_router)`; работает |
| `app/core/config.py` | настройки (`Settings`): ключ, base_url, чат-модель, embedding-модель, `DATABASE_URL`, `RAG_TOP_K`/`RAG_MIN_SCORE` | работает; экземпляр `settings` создан |
| `app/api/router.py` | сборка роутеров | `api_router` включает `chat_router`; `main.py` подключает один `api_router` (ADR-0012) |
| `app/api/dependencies.py` | DI-зависимости FastAPI | `get_session()`; `get_chat_service(session)` на запрос (сервис + репозиторий + UoW + `PgVectorKnowledgeBase`); `get_llm()`/`get_embeddings()` под `lru_cache` |
| `app/api/routes/chat_router.py` | `POST /chat` и `POST /chat/stream` | `ChatRequest` → `ChatCommand`; `/chat` — JSON (`ChatAnswer` → `ChatResponse`); `/chat/stream` — SSE (`EventSourceResponse`, async-генератор); `get_chat_exchange` валидирует и отдаёт HTTP-ошибки до стрима |
| `app/api/error_mapping.py` | `ChatError` → HTTP/SSE | одна таблица `type → (status, code)`, поиск по `isinstance`; тело `{code, message}` |
| `app/application/chat/` | сценарий чата и прикладной контракт | `service.py` — `ChatService.chat/prepare` (+ RAG-контекст); `exchange.py` — `ChatExchange.complete/stream`; `prompt.py` — grounding-промпт с источниками; `ports.py` — `LLMProvider`, `ConversationRepository`, `UnitOfWork`; `dto.py` — `Role` (`system`/`user`/`assistant`), `ChatMessage`, `ChatCommand`, `ChatAnswer`; `errors.py` — `ConversationNotFoundError`, `LLM*` |
| `app/application/knowledge/` | контракт поиска по базе знаний | `dto.py` — `KnowledgeChunk`; `ports.py` — `KnowledgeBase.search`; `errors.py` — `KnowledgeError`/`KnowledgeUnavailableError` |
| `app/infrastructure/db/db.py` | `Base`, async engine, `AsyncSessionLocal` | работает (`expire_on_commit=False`) |
| `app/infrastructure/db/models.py` | `Conversation`, `Message`, `KnowledgeChunk` | `KnowledgeChunk.embedding` — `Vector(1024)`, HNSW-индекс в `__table_args__` |
| `app/infrastructure/observability/tracing.py` | инициализация Langfuse | `init_tracing()`/`shutdown_tracing()`; клиент создаётся из `settings`, `environment="development"`; вызывается в lifespan `main.py` |
| `alembic/` | миграции схемы | `env.py` (async, URL из `settings.DATABASE_URL`), `versions/fa04bfd1fe77_create_chat_tables.py`, `versions/8d4b2f1c9a71_add_knowledge_chunks_with_pgvector.py` (extension + таблица + HNSW); upgrade/downgrade проверены |
| `app/infrastructure/unit_of_work.py` | транзакция на сценарий | `SQLAlchemyUnitOfWork.commit()`; порт `UnitOfWork` — в `application/chat/ports.py` |
| `app/infrastructure/llm/openai_client.py` | `OpenAIChatClient` — адаптер RouterAI (`langfuse.openai.AsyncOpenAI`) | `complete` и `stream` (SSE, `include_usage=True`); сессия — через `propagate_attributes(session_id=...)`; `openai.OpenAIError` → `LLM*` ошибки; timeout 30 s, 2 ретрая |
| `app/infrastructure/knowledge/embeddings.py` | `OpenAIEmbeddings` — эмбеддинги RouterAI | `baai/bge-m3`, батчи; обычный `openai.AsyncOpenAI` (без Langfuse); `OpenAIError` → `KnowledgeUnavailableError` |
| `app/infrastructure/knowledge/retriever.py` | `PgVectorKnowledgeBase` — поиск по корпусу | embed запроса → `ORDER BY embedding <=> vec LIMIT k`, фильтр `min_score`, score = `1 - distance` |
| `app/infrastructure/repositories/conversation_repository.py` | `SQLAlchemyConversationRepository` — история диалога | создание, загрузка, добавление сообщений; commit — в `UnitOfWork` |
| `app/schemas/chat_schema.py` | Pydantic-схемы — контракт API | `conversation_id` необязателен; `max_length` берётся из `MAX_CONTENT_LENGTH` в `application/chat/dto.py` |
| `knowledge_base/` | синтетическая корпоративная база знаний | 16 markdown-документов (14 действующих + 2 архивных ловушки), `README.md` с составом |
| `scripts/seed_knowledge.py` | загрузка корпуса в pgvector | LangChain-сплиттеры → эмбеддинги → upsert по `source`; `--reset` |
| `compose.yaml` | Postgres с pgvector | `pgvector/pgvector:pg17`, том `handproject_pgdata` переиспользуется |
| `tests/` | автотесты API | `conftest.py` — `FakeLLM`/`FakeRepository`/`FakeUnitOfWork`/`FakeKnowledge`; `test_chat.py`, `test_chat_stream.py`, `test_rag.py`; `sse.py` — парсер кадров |
| `docs/` | документация проекта | — |

Каталог переименован: `app/infrasructure` → `app/infrastructure` (дефект закрыт).

## Правило зависимостей

Стрелки импортов — в одну сторону: `api` → `application` ← `infrastructure`; `schemas` — Pydantic-контракт HTTP, импортирует из `application` только константу `MAX_CONTENT_LENGTH` (обратной стрелки нет).
`application` не импортирует FastAPI/SQLAlchemy/`openai`/Pydantic-схемы; `infrastructure` реализует то, что нужно `application`.
Дорогую перестройку делают не имена папок, а нарушения этого правила: ORM-модели или `Depends` внутри сервиса, SQL в роутере, `create_engine` на импорте модуля.

## Ключевые потоки данных

### Срез «чат»: сейчас и цель

```
клиент --POST /chat {conversation_id?, content}> api/routes/chat_router.py
  -> ChatRequest → ChatCommand (маппинг роутера) -> Depends(get_chat_service)
  -> application/chat/service.py ChatService.chat
       -> prepare: infrastructure/repositories/conversation_repository.py
            создать диалог (id = None) / загрузить историю (id передан), добавить user
       -> prepare: application/knowledge → infrastructure/knowledge/retriever.py
            embed(content) → pgvector cosine → top_k, отсечка min_score
            system-сообщение с фрагментами/источниками ставится перед историей
            вернуть ChatExchange
       -> ChatExchange.complete -> infrastructure/llm/openai_client.py OpenAIChatClient.complete
            langfuse.openai.AsyncOpenAI → generation (input/output/model/usage/latency)
            session_id = str(conversation_id); ошибки помечаются ERROR и пробрасываются
            ошибки SDK → LLMUnavailable/LLMTimeout/LLMRateLimited/LLMConfiguration/LLMRequestRejected
       -> repositories: сохранить assistant; UnitOfWork.commit (SQLAlchemyUnitOfWork)
  -> ошибки: ChatError → api/error_mapping.py → HTTP (404/502/504/429/422/503), тело {code, message}
  -> ChatAnswer → schemas/chat_schema.py ChatResponse {conversation_id, content}
```

Фактическое состояние (проверено 2026-11-12): срез сквозной — новый диалог создаётся при `conversation_id=None`, переданный id загружает историю из `messages`, оба сообщения сохраняются, ответ содержит реальный id. Неизвестный id → 404. Ошибки провайдера не выходят как 500: адаптер переводит их в прикладные `LLM*`, `api/error_mapping.py` — в 502/504/429/503/422. В LLM уходит вся история без обрезки; commit один, в конце сценария (через `UnitOfWork`). `application` не импортирует FastAPI/SQLAlchemy/`openai`/Pydantic-схемы: порты, DTO и ошибки — в `application/chat/`, адаптеры/repository/UoW — в `infrastructure`, связывание — в `api/dependencies.py`, HTTP-маппинг — в `api/error_mapping.py`.

### Срез «RAG» (база знаний)

```
ChatService.prepare(content)
  -> KnowledgeBase.search(content, limit=settings.RAG_TOP_K)     [порт application/knowledge]
       -> PgVectorKnowledgeBase (infrastructure/knowledge/retriever.py)
            OpenAIEmbeddings.embed_query → RouterAI baai/bge-m3 (1024 dims)
            SELECT ... ORDER BY embedding <=> $vec LIMIT k
            score = 1 - distance; отбросить score < RAG_MIN_SCORE
  -> build_grounding_prompt(chunks)                               [application/chat/prompt.py]
       инструкция «отвечай только по фрагментам, архив не действует, укажи источники»
       + нумерованные блоки «[n] title — heading (источник: path)» + текст
  -> ChatMessage(Role.SYSTEM, prompt) вставляется в начало messages (перед историей)
  -> ChatExchange.complete()/stream() — без изменений
```

- Порт `KnowledgeBase` возвращает нейтральные `KnowledgeChunk`; `application` не знает ни про pgvector, ни про RouterAI.
- Поиск идёт только по текущему сообщению (без переформулировки с учётом истории) — follow-up вопросы могут искать хуже; query rewriting записан в следующие шаги.
- Если поиск упал (`KnowledgeError`), `ChatService` логирует предупреждение и отправляет system-промпт с «Фрагменты не найдены»: чат остаётся доступным, но отвечать по базе не пытается.
- System-сообщение не сохраняется в БД: в `messages` остаются только `user`/`assistant`.

### Индексация базы знаний

```
knowledge_base/*.md (16 документов)
  -> scripts/seed_knowledge.py
       MarkdownHeaderTextSplitter (H1/H2/H3 → title/section/subsection)
       RecursiveCharacterTextSplitter (1200 символов, overlap 150)
       OpenAIEmbeddings.embed (батчи по 32)
       DELETE chunks WHERE source = ?; INSERT ... (идемпотентно; --reset — вся таблица)
  -> knowledge_chunks (vector(1024), HNSW cosine, unique(source, chunk_index))
```

Корпус синтетический (вымышленная ООО «Северный Ветер»), состав и архивные ловушки — в `knowledge_base/README.md`.

### Срез «стриминг»: `/chat/stream`

```
клиент --POST /chat/stream {conversation_id?, content}> Depends(get_chat_exchange)
  -> ChatService.prepare → ChatExchange: создать/загрузить диалог, добавить user (без commit)
       ошибки (неизвестный диалог и т.п.) -> HTTP до отправки заголовков
  -> EventSourceResponse (endpoint chat_stream — async-генератор)
       yield event: meta {conversation_id}
       -> ChatExchange.stream -> OpenAIChatClient.stream (RouterAI, stream=True)
            yield event: delta (raw_data = кусок текста)
       -> в конце ChatExchange._finish: add_message(assistant) + UnitOfWork.commit
       yield event: done {conversation_id}
       ChatError во время генерации -> to_sse_event → yield event: error {code, message}
```

- `get_chat_exchange` возвращает готовый `ChatExchange`; endpoint больше не принимает `ChatService`, поэтому неявной зависимости «тот же экземпляр сервиса» нет. Сессия живёт до конца стрима (проверено в 0.162.3).
- После первого кадра HTTP-код не меняется: `error` — терминальное событие потока.
- Обрыв клиента отменяет генератор: `commit` не выполняется, ничего не сохраняется (то же «всё-или-ничего», что и в `/chat`).
- Keep-alive `: ping` каждые 15 с и заголовки `no-cache` / `X-Accel-Buffering: no` ставит сам FastAPI.

### Инвариант сценария `prepare → stream`

Инвариант — условие о состоянии, которое обязано быть истинно в конкретной точке программы; при его нарушении результат неверен, даже если исключения нет. Это не валидация входа (Pydantic проверяет данные на границе), а согласованность внутреннего состояния между шагами сценария.

Инвариант закрыт в ADR-0014: `ChatService.prepare()` добавляет user-сообщение без commit и возвращает `ChatExchange` — объект-возможность с методами `complete()`/`stream()`. Он сам владеет финализацией (сохранение assistant-сообщения и `UnitOfWork.commit()`), поэтому условия «prepare вызван», «user лежит в сессии», «ответ финализируется один раз» выражены типом, а не порядком вызовов в роутере.

### Наблюдаемость (Langfuse)

- `langfuse` импортируется только в `infrastructure` (`observability/tracing.py` и `llm/openai_client.py`); `application` получает нейтральный `conversation_id`, а не `session_id`.
- Адаптер использует drop-in обёртку `from langfuse.openai import AsyncOpenAI`: она патчит `chat.completions.create` и на каждый вызов создаёт generation, снимая prompt/completion, модель, usage, latency и ошибки. `name` вырезается обёрткой до отправки в RouterAI. **`session_id`/`user_id`/`tags` передавать kwargs нельзя** (в 5.2.0 не вырезаются → `TypeError` от OpenAI SDK): сессия задаётся `with propagate_attributes(session_id=str(conversation_id))` вокруг вызова.
- `tracing.py` создаёт клиент явно из `settings`: pydantic-settings читает `.env`, но не кладёт значения в `os.environ`, а SDK Langfuse сам читает env. Без ключей клиент работает как no-op.
- Один HTTP-запрос = один trace с одной generation; `session_id` группирует запросы одного диалога в Sessions. RouterAI возвращает `usage.cost`, поэтому стоимость попадает в трейс автоматически; прайс в настройках проекта нужен только для провайдеров без `cost` в usage.

## Пакеты и `__init__.py`

Все каталоги `app/` — реальные пакеты (ADR-0005). `__init__.py` — маркер пакета и, если нужно, его публичный API: пустой файл — обычный дефолт проекта, а не требование. Сейчас пусты все, кроме `infrastructure/db/__init__.py`, который реэкспортирует `Base`, `engine`, `AsyncSessionLocal`; если пакету понадобится публичный API, реэкспорт в `__init__.py` — нормальный вариант. Подмодули импортируют друг друга напрямую (`from .db import Base`). Модели в `__init__` не импортируются: там, где нужен `Base.metadata` (Alembic `env.py`), `import app.infrastructure.db.models` пишется явно. В `api/routes/` принято импортировать модули явно (`from app.api.routes.chat_router import router`), но реэкспорт роутера в `__init__.py` тоже допустим.

Соглашение по чату (ADR-0008): порты, DTO и ошибки чата живут только в `app/application/chat/` (`ports.py`, `dto.py`, `errors.py`); новый код такого рода не кладём в `service.py` или рядом с адаптерами. Объект одного обмена с поведением (`ChatExchange`) — в `exchange.py`, рядом с `service.py`.

Соглашение по базе знаний (ADR-0016): контракт поиска — `app/application/knowledge/` (`KnowledgeChunk`, `KnowledgeBase`, `KnowledgeError`). `application/chat` может импортировать из `application/knowledge` (один слой), обратной зависимости нет. Адаптеры (`OpenAIEmbeddings`, `PgVectorKnowledgeBase`) — только в `app/infrastructure/knowledge/`.

## Запуск и окружение

> 2026-11-19: окружение восстановлено — `.venv` пересоздан из `requirements.txt`, Docker Desktop запущен, `handproject-postgres` healthy, БД на `8d4b2f1c9a71` (75 чанков).

- Запуск: `source .venv/bin/activate && uvicorn app.main:app --reload` (проверка: `GET http://127.0.0.1:8000/health`).
- Тесты: `.venv/bin/python -m pytest -q` — без БД и сети, зависимости подменяются фейками в `tests/conftest.py`.
- Зависимости зафиксированы в `requirements.txt` (ручной список; `pyproject.toml` — позже). Async-стек БД требует `sqlalchemy[asyncio]` (тянет `greenlet`) и `asyncpg`; оба записаны. Для RAG добавлены `pgvector` (тип `Vector` для SQLAlchemy) и `langchain-text-splitters` (только сид).
- `.env` есть (RouterAI: ключ, base_url, чат-модель, embedding-модель; `DATABASE_URL=postgresql+asyncpg://…`; `RAG_TOP_K`/`RAG_MIN_SCORE`; Langfuse), в git не попадает; `.env.example` пока не создан. `Settings` читает `.env` относительно CWD — запускать приложение из корня проекта.
- Postgres: `docker compose up -d` поднимает `pgvector/pgvector:pg17` (`handproject-postgres`, `127.0.0.1:5432`, том `handproject_pgdata`). Образ pgvector нужен для расширения `vector`; при переходе с обычного `postgres:17` выполнены `ALTER DATABASE handproject REFRESH COLLATION VERSION` и `REINDEX DATABASE handproject`.
- Схема — только Alembic: `alembic upgrade head` из корня проекта; после правки моделей — `alembic revision --autogenerate -m "…"` и снова `upgrade head`. URL берётся из `settings.DATABASE_URL` в `alembic/env.py` (в `alembic.ini` не хранится). Миграции в startup не применяются.
- База знаний: после миграции — `.venv/bin/python -m scripts.seed_knowledge` (идемпотентно, `--reset` очищает таблицу). Требует доступного RouterAI и 75 embedding-запросов на полный корпус.

### Инвентарь машины разработки (2026-11-10)

Пайтонов на машине несколько — отсюда путаница с выбором интерпретатора в IDE:

| Путь | Версия | Откуда |
|---|---|---|
| `/opt/anaconda3/bin/python3` | 3.14.6 | Anaconda (первый в `PATH`, `conda env list` → только `base`) |
| `/Library/Frameworks/Python.framework/Versions/3.14/bin/python3` | 3.14.7 | python.org-инсталлятор, он же `/usr/local/bin/python3` |
| `/usr/bin/python3` | 3.9.6 | системный (Apple), не трогать |

- Менеджеры окружений: есть только `conda`; `brew`/`pyenv`/`uv`/`poetry`/`pipx` — нет.
- IDE: **VS Code** — выбранная (см. ADR-0001); PyCharm установлен, но не используется. `code` в `PATH` не установлен.
- Anaconda автоактивирует `base` в каждой новой оболочке (`conda init` в `~/.zshrc`), поэтому в терминале без активации `which python` → `/opt/anaconda3/bin/python`.

### Окружение проекта

Проектное окружение — локальный `venv`; Anaconda в нём не задействована.

- `.venv/` в корне проекта (в git не попадает — venv создаёт свой `.venv/.gitignore`).
- База: `/usr/local/bin/python3` → python.org **3.14.7** (`pyvenv.cfg`: `home = /Library/Frameworks/Python.framework/Versions/3.14/bin`), не Anaconda.
- Активация: `source .venv/bin/activate` → в приглашении `(.venv)`, `which python` → `.venv/bin/python`; выход — `deactivate`.
- VS Code: `⌘⇧P` → `Python: Select Interpreter` → `./.venv/bin/python`. Новые терминалы в VS Code активируют выбранное окружение сами.
- Установка пакетов — только при активированном окружении (`pip install ...`); иначе пакет уедет в Anaconda `base` и IDE его не увидит.
- Ловушка: расширение **Code Runner** берёт `python` из общих настроек (`python3 -u`) → это Anaconda, а не `.venv`. Запускать через Python-расширение (▶/F5) либо заменить маппинг на `${command:python.interpreterPath}`.
