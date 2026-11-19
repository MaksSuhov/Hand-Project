# Журнал решений (ADR)

Ключевые технические решения и их причины. Цель — не пересматривать заново то, что уже решено, и помнить «почему» через месяцы.

## Формат записи

Одно решение = один блок:

```
## NNNN. Название решения — YYYY-MM-DD

Контекст:  почему вообще возник вопрос
Варианты:  A / B / C — коротко каждый
Выбор:     какой вариант и ПОЧЕМУ
Последствия: что это упрощает/усложняет, чем платим
```

## Решения

## 0001. IDE — VS Code — 2026-11-10

Контекст:  проект пустой, на машине стоят и PyCharm, и VS Code; нужно выбрать одну среду, чтобы не распылять настройки и документацию.
Варианты:  PyCharm (мощный Python-IDE «из коробки») / VS Code (лёгкий редактор + расширения).
Выбор:     VS Code — пользователь работает только в нём; PyCharm не используется.
Последствия: настройка идёт через Python-расширение (`.venv`, Pylance, debugpy); PyCharm-специфичные шаги в документацию не попадают; часть удобств PyCharm (рефакторинги, инспекции) недоступна без плагинов.

## 0002. Окружение проекта — локальный venv от python.org — 2026-11-10

Контекст:  на машине несколько Пайтонов, Anaconda первая в `PATH` и автоактивирует `base`; нужно изолированное окружение проекта, не смешанное с Anaconda.
Варианты:  A — conda-окружение (`conda create -n ...`); B — локальный `venv` в корне проекта.
Выбор:     B — `.venv` создан командой `/usr/local/bin/python3 -m venv .venv` (python.org 3.14.7).
Последствия: окружение живёт рядом с кодом и видно IDE автоматически; не зависим от Anaconda. Минус: venv умеет только уже установленные версии Пайтона — если библиотеке понадобится другая версия, придётся ставить её отдельно (или переходить на conda).

## 0003. Каркас приложения — слоистая структура — 2026-11-10

Контекст:  идея продукта ещё не определена, но нужен каркас, чтобы начать писать код; зависимости (FastAPI, SQLAlchemy, LangGraph, OpenAI) уже установлены.
Варианты:  A — минимализм (`main.py` + `routers/`, всё в одном слое); B — готовый boilerplate из сети; C — свои слои `api` / `application` / `core` / `infrastructure` / `schemas`.
Выбор:     C (создан пользователем). Даёт односторонние зависимости и место для каждой будущей сущности; на старте часть каталогов пустая.
Последствия: масштабируется до среднего проекта, легко тестировать сервисы без HTTP/БД. Цена — риск преждевременных абстракций (`unit_of_work.py` до появления второго репозитория) и лишние переходы между файлами на мелких фичах. Пересмотреть, если после 3–5 фич правка одной фичи требует касания всех папок: тогда перейти на вертикальные срезы (`app/chat/…`) по фичам.

## 0004. БД — async SQLAlchemy, Postgres + asyncpg — 2026-11-11

Контекст:  LLM-клиент `AsyncOpenAI` и эндпоинты async; синхронный `Session` внутри async-эндпоинта блокирует event loop. Нужен способ ходить в БД, не смешивая sync и async.
Варианты:  A — sync SQLAlchemy, вызовы в threadpool; B — async SQLAlchemy (`create_async_engine` / `async_sessionmaker`) + Postgres/`asyncpg`; C — SQLite + `aiosqlite` для разработки, Postgres позже.
Выбор:     B — зафиксировано в коде 2026-11-11 (`DATABASE_URL=postgresql+asyncpg://…`, async engine/sessionmaker).
Последствия: в окружении нужны `sqlalchemy[asyncio]` (тянет `greenlet`) и `asyncpg`; локально требуется запущенный Postgres (Docker); `alembic` пока не подключён. `asyncpg` + `greenlet` пока не записаны в `requirements.txt`. SQLite можно добавить позже для быстрых тестов, но диалект и поведение отличаются от Postgres.

## 0005. Реальные пакеты: `__init__.py` во всех каталогах `app/` — 2026-11-11

Контекст:  проект стартовал без `__init__.py` (PEP 420 namespace-пакеты). Из-за этого `from app.infrastructure.db import AsyncSessionLocal` был невозможен, `app/infrastructure/repositories/` не попадал в git, а тулинг (mypy, pytest, `find_packages`) вёл себя непредсказуемо.
Варианты:  A — оставить namespace-пакеты; B — добавить `__init__.py` во все пакеты (по умолчанию пустые; в `db/` — реэкспорт); C — только в `db/` как точечный фикс.
Выбор:     B — единообразно и предсказуемо; `db/__init__.py` реэкспортирует `Base`, `engine`, `AsyncSessionLocal`. Модели там не импортируются: `import app.infrastructure.db.models` делается явно там, где нужен `Base.metadata` (как ожидает Alembic `env.py`).
Последствия: импорт пакетов не зависит от `sys.path` и чужих `app/`; пустые каталоги хранятся в git. Пустой `__init__.py` — дефолт, а не требование: если пакет должен предоставлять публичный API (как `db/`), реэкспорт в `__init__.py` уместен. Бизнес-логику и `create_engine` туда не кладём; подмодули по умолчанию импортируются напрямую (`from .db import Base`), чтобы не ловить циклы.

## 0006. Первый срез чата: порт LLMProvider + адаптер RouterAI — 2026-11-11

Контекст:  echo-ручка работала, но не использовала LLM; нужно провести реальный сценарий, не нарушив правило слоёв (`application` не знает про FastAPI/SQLAlchemy/`openai`) и не блокируя работу на неготовой БД.
Варианты:  A — вызвать `openai` прямо в роутере (быстро, но слой `application` остаётся пустым); B — `ChatService` импортирует `AsyncOpenAI` (слои перепутаны, сервис не тестируется без сети); C — порт `LLMProvider` (`Protocol`) в `application`, адаптер `OpenAIChatClient` в `infrastructure`, связывание в `api/dependencies.py`.
Выбор:     C — сервис зависит от абстракции, адаптер подменяется в тестах; RouterAI подключается через уже готовый `AsyncOpenAI`.
Последствия: срез проверен живым запросом (`POST /chat` → ответ модели). История пока не сохраняется: `conversation_id` — echo, `0` означает «новый диалог»; следующий шаг — репозиторий + `ChatService(llm, repo)`. Ошибки провайдера не маппятся (сейчас выходят как 500), это записано в `PROGRESS.md`. Контракт: `conversation_id` необязателен, `path=''` (`POST /chat`; `/chat/` → 307).

## 0007. История диалога: порт репозитория + сессия на запрос — 2026-11-11

Контекст:  `POST /chat` вызывает LLM, но не сохраняет сообщения; `conversation_id` был echo. Нужно: создавать диалог, загружать историю, передавать её в модель, сохранять оба сообщения и не нарушить правило слоёв (`application` без FastAPI/SQLAlchemy).
Варианты:  A — SQL/ORM прямо в `ChatService` (быстро, но слой `application` начинает зависеть от SQLAlchemy); B — репозиторий возвращает ORM-объекты `Conversation`/`Message` (сервис всё равно знает ORM); C — порт `ConversationRepository` (`Protocol`) + простой DTO `ChatMessage` в `application`, SQLAlchemy-репозиторий в `infrastructure/repositories/`.
Выбор:     C. `ChatService` зависит от двух портов (`LLMProvider`, `ConversationRepository`); `LLMProvider.complete` принимает `Sequence[ChatMessage]`, поэтому в модель уходит история, а не одно сообщение. Репозиторий отдаёт `None` для несуществующего диалога; сервис поднимает `ConversationNotFoundError`, роутер переводит его в 404. Commit — один, в конце успешного сценария; при исключении сессия закрывается без commit. Так как сессия нужна на запрос, `get_chat_service` больше не под `lru_cache`; кешируется только `get_llm()`.
Последствия: сценарий тестируется с фейковыми LLM и репозиторием; DI явный, транзакция видна в сервисе. Цена: DTO и порты — лишний слой для одного сценария; история уходит в LLM целиком (нужна обрезка); `create_all` создаёт таблицы, но не мигрирует схему — Alembic откладывается до стабилизации модели. Проверено fake LLM через ASGI и реальным RouterAI (модель воспроизвела число из предыдущей реплики).

## 0008. Пакет `application/chat`: порты, DTO и ошибки отдельно — 2026-11-12

Контекст:  после первой версии `chat_service.py` смешивал сценарий, порты, DTO и исключения; дальше добавляются streaming, новые ошибки и, возможно, второй провайдер — файл стал бы свалкой. Нужно место, куда складывать прикладной контракт, не заводя пустой `domain`.
Варианты:  A — держать всё в `application/chat_service.py`; B — завести `app/domain/`; C — пакет `app/application/chat/` с `service.py`, `ports.py`, `dto.py`, `errors.py`.
Выбор:     C. Порты — прикладной контракт, а не бизнес-правила; доменных инвариантов пока нет, поэтому `domain/` был бы пустым слоем (риск, о котором предупреждает ADR-0003). `domain/` появится по триггеру: правила ролей/лимитов/состояний, не зависящие от HTTP/БД, или второй bounded context.
Последствия: договорённость — новые порты, DTO и ошибки чата пишутся только в `application/chat/` (`ports.py`, `dto.py`, `errors.py`), а не в `service.py` и не рядом с адаптерами. Импорты обновлены; `application/chat_service.py` удалён. `application` по-прежнему не импортирует FastAPI/SQLAlchemy/`openai`. Streaming-типы (чанк, событие ошибки) добавятся в этот же пакет.

## 0009. Маппинг ошибок LLM-провайдера — 2026-11-12

Контекст:  исключения `openai`/RouterAI выходили из `ChatService` наружу и FastAPI отдавал общий 500; клиент не отличал сбой провайдера от бага приложения, а тело ответа не давало понять причину.
Варианты:  A — ловить `openai`-исключения прямо в `ChatService`; B — ловить их в роутере; C — адаптер переводит `OpenAIError` в прикладные `LLM*`, роутер маппит `ChatError` в HTTP.
Выбор:     C. `_to_llm_error` в `openai_client.py`: `APITimeoutError` → `LLMTimeoutError`; `APIConnectionError` → `LLMUnavailableError`; `RateLimitError` → `LLMRateLimitedError`; `AuthenticationError`/`PermissionDeniedError` → `LLMConfigurationError`; `BadRequestError`/`UnprocessableEntityError`/`NotFoundError` → `LLMRequestRejectedError`; прочие `APIStatusError`/`OpenAIError` → `LLMUnavailableError`. Роутер: 504/502/429/503/422 соответственно, `ConversationNotFoundError` → 404. Исходное исключение сохраняется в `__cause__`, в тело уходит безопасное сообщение.
Последствия: `application` не знает про `openai`; клиент получает осмысленный код, 502 не маскируется под баг. Цена: таблицу маппинга нужно поддерживать при смене провайдера; при streaming после отправки заголовков код поменять нельзя — ошибку придётся отдавать событием в потоке.

## 0010. Alembic вместо ручного `create_all` — 2026-11-12

Контекст:  таблицы создавались одноразовым `init_db.py` через `Base.metadata.create_all`; схема уже менялась (FK, timestamptz), и `create_all` не умеет мигрировать существующие таблицы.
Варианты:  A — оставить `create_all` до стабилизации схемы; B — подключить Alembic сейчас; C — отложить Alembic до продакшена.
Выбор:     B. `alembic==1.20.1`, async-шаблон; `env.py` берёт URL из `settings.DATABASE_URL` и `target_metadata = Base.metadata` (модели импортируются явно). Начальная ревизия `fa04bfd1fe77` создаёт `conversations`/`messages` с FK `ON DELETE CASCADE`, timestamptz и индексами. `init_db.py` удалён, чтобы не было второго источника схемы.
Последствия: схема меняется только ревизиями: `alembic revision --autogenerate -m "…"` + `alembic upgrade head`; миграции хранятся в git. Startup не применяет миграции (нужен явный шаг деплоя). Autogenerate требует запущенной БД и корректного `Base.metadata`; ручные правки миграции иногда неизбежны (renames, data migrations).

## 0011. Langfuse: drop-in обёртка OpenAI в адаптере, Cloud — 2026-11-12

Контекст:  нужна наблюдаемость LLM-вызовов (prompt/completion, латентность, токены, стоимость, ошибки), впереди streaming; при этом `application` не должен зависеть от SDK, а интеграция не должна требовать переписывания при переходе на SSE.
Варианты:  хостинг — Cloud (Hobby) / self-host (Postgres + Redis + ClickHouse + S3 + web/worker); инструментация — `@observe` на сценарии или роутере / ручные `start_as_current_observation` / drop-in `langfuse.openai.AsyncOpenAI`; место — `ChatService` / роутер / адаптер `infrastructure/llm/`.
Выбор:     Cloud + drop-in обёртка в адаптере. Порт `LLMProvider.complete` получает нейтральный `conversation_id`; клиент Langfuse создаётся явно из `settings` в `infrastructure/observability/tracing.py`, `init_tracing()`/`shutdown_tracing()` вызываются в lifespan. Обёртка сама снимает input/output/model/usage/latency/ошибки и поддерживает async-streaming (`LangfuseResponseGeneratorAsync`). Сессия задаётся `with propagate_attributes(session_id=str(conversation_id))` вокруг вызова: в 5.2.0 kwargs `session_id`/`user_id`/`tags` не вырезаются из аргументов и приводят к `TypeError` от OpenAI SDK.
Последствия: одна правка в `application` (параметр порта), ноль langfuse-импортов вне `infrastructure`; при SSE Langfuse-код почти не меняется (добавляются `stream=True` и `stream_options={"include_usage": True}`). RouterAI возвращает `usage.cost`, поэтому стоимость попадает в трейс автоматически; отдельный прайс нужен только провайдерам без `cost`. Цена: `langfuse` записан в `requirements.txt`; ключи — в `.env`; `auth_check()` синхронный и блокирует event loop на старте; неизвестно, поддерживает ли RouterAI `include_usage` в стриме. Не использовать `@observe` на `ChatService.handle`/роутере: при превращении в async generator декоратор перестанет видеть output и время стрима. Проверено 2026-11-12 end-to-end: `POST /chat` → 200, Langfuse Observations API v2 отдал generation с `sessionId`, токенами и `totalCost`, input/output заполнены; ошибочный вызов даёт observation уровня ERROR.

## 0013. Стриминг ответа — SSE на встроенном `EventSourceResponse` — 2026-11-12

Контекст:  ответ модели ждать целиком долго; нужен потоковый вывод. Из ADR-0009 уже известно: после отправки заголовков код ошибки не поменять. При этом установленный FastAPI 0.162.3 содержит встроенный SSE (`fastapi.sse`), а `sse-starlette` не установлен.
Варианты:  A — SSE через `sse-starlette`; B — JSONL-поток (async-генератор без `response_class`); C — встроенный `fastapi.sse.EventSourceResponse`; D — оставить один JSON-ответ и не стримить.
Выбор:     C — отдельная ручка `POST /chat/stream` с `response_class=EventSourceResponse`; endpoint сам является async-генератором. События: `meta {conversation_id}` → `delta` (`raw_data`, сырой текст) → `done {conversation_id}`; ошибки после старта — терминальное `error {code, message}`. Валидация и 404 — в зависимости `get_prepared_chat` (генератор начинает выполняться только после отправки заголовков). Порт `LLMProvider` получил `stream()`, `ChatService` разделён на `prepare()`/`stream()`, `handle()` переиспользует `prepare()`. Адаптер: `stream=True`, `stream_options={'include_usage': True}`, `try/except OpenAIError` вокруг всей итерации, `await stream.close()` в `finally`.
Последствия:  ноль новых зависимостей; FastAPI сам делает фрейминг, keep-alive `: ping` каждые 15 с, `Cache-Control: no-cache`, `X-Accel-Buffering: no` и OpenAPI. Клиент — `fetch` + `ReadableStream`: нативный `EventSource` не умеет `POST`. Сессия БД живёт весь стрим (проверено), `commit` — после `done`; обрыв клиента отменяет генератор и ничего не сохраняет. Цена: два контракта (`/chat` и `/chat/stream`), `PreparedChat` и двухфазный сервис, ошибки после старта видны только событием. Langfuse: `include_usage` проверен — usage/cost попадают в стриминговую generation. JSONL (вариант B) остаётся запасным, если понадобится простая построчная передача без SSE-семантики и keep-alive.

## 0012. Сборка роутеров через `api/router.py` — 2026-11-12

Контекст:  `main.py` подключает каждый фичевый роутер сам; с ростом числа ручек точка входа разрастается, а `app/api/router.py` был задуман как агрегатор.
Варианты:  A — `main.py` импортирует и подключает каждый роутер; B — `api/router.py` создаёт `api_router = APIRouter()`, включает фичевые роутеры, а `main.py` подключает один `api_router`; C — складывать все ручки в один файл без агрегатора.
Выбор:     B. FastAPI-приложение создаётся только в `main.py` (composition root); агрегатор не импортирует `app`, поэтому цикла нет. Фичевые роутеры импортируются по модулю (`from app.api.routes.chat_router import router as chat_router`); `routes/__init__.py` может оставаться пустым, но реэкспорт роутера как публичного API пакета тоже допустим — это не нарушение ADR-0005.
Последствия: добавление ручки — одна строка в агрегаторе, `main.py` стабилен. `api/router.py` реализован и подключён (проверено 2026-11-12). Тестовая подмена зависимостей и порядок include остаются в одном месте.

## 0014. Развязка `application` от схем, `UnitOfWork` и `ChatExchange` — 2026-11-12

Контекст:  ревью слоёв показало три дрейфа после внедрения SSE: `application` импортировал Pydantic-схемы (`ChatRequest`/`ChatResponse`), транзакция жила в порту репозитория (`ConversationRepository.commit`) при пустом `unit_of_work.py`, а `PreparedChat` + `ChatService.stream` создавали неявный инвариант «user-сообщение добавлено, но не закоммичено»; роутер получал `service` и `prepared` двумя зависимостями. Частично заменяет ADR-0007 (commit в сервисе/репозитории) и ADR-0013 (`PreparedChat`, двухфазный сервис).
Варианты:  A — оставить до следующей фичи; B — только переименовать; C — ввести `ChatCommand`/`ChatAnswer`, порт `UnitOfWork` и объект `ChatExchange`.
Выбор:     C.
  1. `schemas` (Pydantic) остаются в API; роутер маппит `ChatRequest → ChatCommand`, `ChatAnswer → ChatResponse`. `MAX_CONTENT_LENGTH` — в `application/chat/dto.py`, схема импортирует константу.
  2. `Role` — `StrEnum` (`user`/`assistant`); `add_message(conversation_id, ChatMessage)` вместо разрозненных `str`.
  3. `ChatExchange` (`application/chat/exchange.py`) — объект-возможность: `complete()`/`stream()`; `_finish()` сохраняет assistant и вызывает `UnitOfWork.commit()`. `ChatService.prepare()` возвращает его; `ChatService.chat()` переиспользует `prepare()`.
  4. `SQLAlchemyUnitOfWork` реализует порт `UnitOfWork` поверх `AsyncSession`; `commit` убран из `ConversationRepository`.
  5. `api/error_mapping.py` — одна таблица `type → (status, code)`, поиск по `isinstance`; HTTP и SSE отдают `{code, message}`.
Последствия: `application` не импортирует Pydantic-схемы и пригоден вне HTTP; транзакция отделена от репозитория; инвариант обмена выражен типом; добавление ошибки — одна строка в таблице. Цена: `ChatExchange` держит порты (это прикладной объект с поведением, не DTO); HTTP-тело ошибки изменилось на `{code, message}`; `role` в БД остаётся строкой без check-констрейнта — неизвестное значение падает при чтении в `Role(...)`. Проверено 2026-11-12 фейковым LLM/репозиторием/UoW: `/chat` 200, `/chat/stream` meta/delta/done, неизвестный диалог → 404 `conversation_not_found`, таймаут провайдера → 504 `provider_timeout` и SSE `error`, пустой/длинный `content` → 422.

## 0015. Автотесты: pytest + pytest-asyncio + ASGITransport — 2026-11-12

Контекст:  проверки были ручными (ASGI-скрипты с фейками), регрессии после рефакторингов ловились глазами; `pytest` не был установлен, тестовых зависимостей в `requirements.txt` не было.
Варианты:  A — `pytest` + `pytest-asyncio` + `httpx.ASGITransport` (тесты через HTTP-слой); B — pytest с прямыми вызовами `ChatService`/`ChatExchange` без HTTP; C — `unittest` + `TestClient`.
Выбор:     A. `pytest 9.2.0`, `pytest-asyncio 1.5.0`, `asyncio_mode = auto` в `pytest.ini`. Фейковые `FakeLLM`, `FakeRepository`, `FakeUnitOfWork` — в `tests/conftest.py`, подмена через `app.dependency_overrides[get_chat_service]`; реальные Postgres и RouterAI не задействованы. Вспомогательный парсер SSE — `tests/sse.py`.
Последствия: 14 тестов покрывают `/chat` (200, история, 404, 504, 422) и `/chat/stream` (`meta/delta/done`, история, 404 до заголовков, пять кодов `error`, 422). Прогон — 0,04 с без сети и БД; запуск `.venv/bin/python -m pytest -q`. Цена: тесты идут через HTTP-слой, `ChatService`/`ChatExchange` и `_to_llm_error` отдельно не юнит-тестируются; `ASGITransport` буферизует SSE, поэтому инкрементальность проверяется вручную (uvicorn + curl); при изменении сигнатур портов фейки нужно править.

## 0016. RAG: pgvector в текущем Postgres, свой порт и промпт с источниками — 2026-11-16

Контекст:  ассистент должен отвечать сотрудникам по внутренней базе знаний, а не из общих знаний модели; впереди eval-прогоны, для которых нужен контролируемый корпус и прозрачный retrieval. В стеке уже есть Postgres/`asyncpg`/Alembic, и добавлять отдельную векторную БД ради десятков тысяч чанков — лишняя инфраструктура и вторая согласованность.
Варианты:  хранилище — A отдельная векторная БД (Qdrant/Chroma) / B pgvector в текущем Postgres; эмбеддинги — A OpenAI `text-embedding-3-small` / B `baai/bge-m3` через RouterAI / C локальная модель; интеграция — A LangChain vectorstore / B свой порт + SQL-адаптер.
Выбор:  B + B + B.
  1. Образ БД — `pgvector/pgvector:pg17` (`compose.yaml`), том `handproject_pgdata` переиспользован; расширение `vector` ставит миграция `8d4b2f1c9a71` (`CREATE EXTENSION`), таблица `knowledge_chunks` с `embedding vector(1024)`, `unique(source, chunk_index)` и HNSW `vector_cosine_ops`. Схемой по-прежнему владеет Alembic.
  2. Эмбеддинги — `baai/bge-m3` через RouterAI (`OpenAIEmbeddings`, батчи): мультиязычная, 1024 измерения, не требует префиксов «query:/passage:», не добавляет второго провайдера/ключа.
  3. Порт `KnowledgeBase.search(query, limit) → list[KnowledgeChunk]` в `application/knowledge/`; адаптер `PgVectorKnowledgeBase` — `ORDER BY embedding <=> $vec LIMIT k`, score = `1 - distance`, фильтр `RAG_MIN_SCORE`. `ChatService` получает порт, ищет по текущему сообщению и вставляет `Role.SYSTEM` с инструкцией и нумерованными фрагментами перед историей (`application/chat/prompt.py`).
  4. Деградация: `KnowledgeError` ловится в сервисе, чат продолжает работать с промптом «Фрагменты не найдены» — база знаний не должна ронять диалог.
  5. Корпус — синтетический (`knowledge_base/`, 16 документов, 75 чанков), сид — `scripts/seed_knowledge.py` (идемпотентно по `source`, `--reset` для полной очистки). Порог `RAG_MIN_SCORE=0.45` откалиброван на корпусе: релевантные чанки 0.49–0.74, оффтоп ≤0.37.
Последствия: одна БД и одна транзакционная модель, никакого второго сервиса; retrieval виден в SQL и тестируется на фейках порта. Цена: размерность зашита в модель/миграцию — смена embedding-модели требует новой миграции и полной переиндексации; порог и качество зависят от корпуса и модели; поиск идёт без переформулировки вопроса (follow-up хуже); цитаты формирует модель, программной проверки `source` нет; сид статичный, удалённые файлы остаются в таблице до `--reset`. Эмбеддинги идут обычным `openai.AsyncOpenAI`, а не через Langfuse: обёртка создавала отдельные трейсы без сессии и шум в логах сида. Проверено 2026-11-16 живым RouterAI: 28 дней отпуска (архивные 24 не использованы), 3 500 ₽ суточных, отказ на вопрос вне базы, правильная пометка архива; `/chat/stream` работает с тем же контекстом; 16 тестов проходят.

## 0017. LangChain: только text splitters в индексации — 2026-11-16

Контекст:  при внедрении RAG нужно было решить, тянуть ли LangChain в runtime и насколько глубоко; пользователь хочет увидеть, как LangChain работает базово, но без оверинжиниринга.
Варианты:  A — полный стек LCEL: chains, `langchain-openai` (chat + embeddings), `langchain-postgres.PGVector`; B — только утилиты чанкинга (`langchain-text-splitters`) в скрипте сида; C — не использовать LangChain вовсе.
Выбор:  B. `MarkdownHeaderTextSplitter` режет документ по H1/H2/H3 и переносит заголовки в metadata (используется как `heading` чанка), `RecursiveCharacterTextSplitter` ограничивает размер 1200/150 символов. Оба — в `scripts/seed_knowledge.py`, то есть только во время индексации.
Последствия: LangChain виден в реальной задаче (чанкинг), но не появляется в runtime-пути. `langchain-postgres.PGVector` не берём: он владеет таблицей/схемой, тянет собственное подключение и конфликтует с Alembic, `AsyncSession` и `UnitOfWork`; нам нужен один SQL-запрос. `langchain-openai` не берём: дублирует уже настроенный клиент, ретраи и маппинг ошибок. Chains не дают ничего для одного шага retrieve → prompt → LLM, который уже выражен в `ChatService`. Триггеры для расширения LangChain: rerank/hybrid search, multi-query, tools/structured output, второй провайдер — тогда через порт, не в обход слоёв. `langchain-text-splitters 1.1.3` записан в `requirements.txt`.
