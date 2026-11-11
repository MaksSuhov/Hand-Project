# Архитектура

> Статус: чат с сохранением истории работает сквозным сценарием (RouterAI + Postgres); автоматических тестов нет.

## Стек и обоснование

Установлено в `.venv` и зафиксировано в `requirements.txt` (2026-11-10):

| Роль | Пакет | Версия |
|---|---|---|
| HTTP | `fastapi` / `uvicorn` / `starlette` | 0.162.3 / 0.54.0 / 1.10.0 |
| Валидация | `pydantic` / `pydantic-settings` | 2.14.3 / 2.16.2 |
| БД | `SQLAlchemy` / `asyncpg` (+ `greenlet`) / `alembic` | 2.1.8 / 0.32.0 / 3.5.6 / 1.20.1 (все в `requirements.txt`) |
| LLM/агенты | `langchain` / `langgraph` / `openai` | 1.4.9 / 1.2.20 / 3.49.0 |
| Тесты | — | `pytest` не установлен |

Python 3.14.7 (`.venv`, ADR-0002). По зависимостям проект — чат/агент на LLM с БД.

## Карта проекта

| Путь | Назначение | Состояние |
|---|---|---|
| `app/main.py` | точка входа FastAPI | `GET /health` + `include_router(chat_router)`; работает |
| `app/core/config.py` | настройки (`Settings`): ключ, base_url, модель, `DATABASE_URL` | работает; экземпляр `settings` создан |
| `app/api/router.py` | сборка роутеров | пусто; `main.py` подключает `chat_router` напрямую |
| `app/api/dependencies.py` | DI-зависимости FastAPI | `get_session()`; `get_chat_service(session)` на запрос; `get_llm()` под `lru_cache` |
| `app/api/routes/chat_router.py` | `POST /chat` | вызывает `ChatService`; `ChatError` → HTTP (404/502/504/429/422/503); `path=''` |
| `app/application/chat/` | сценарий чата и прикладной контракт | `service.py` — `ChatService`; `ports.py` — `LLMProvider`, `ConversationRepository`; `dto.py` — `ChatMessage`; `errors.py` — `ConversationNotFoundError`, `LLM*` |
| `app/infrastructure/db/db.py` | `Base`, async engine, `AsyncSessionLocal` | работает (`expire_on_commit=False`) |
| `app/infrastructure/db/models.py` | `Conversation`, `Message` | маппинг проходит; FK исправлен; сообщения упорядочены по `message_id` |
| `alembic/` | миграции схемы | `env.py` (async, URL из `settings.DATABASE_URL`), `versions/fa04bfd1fe77_create_chat_tables.py`; upgrade/downgrade проверены |
| `app/infrastructure/unit_of_work.py` | транзакция на сценарий | пусто (сознательно, ADR-0003) |
| `app/infrastructure/llm/openai_client.py` | `OpenAIChatClient` — адаптер RouterAI (`AsyncOpenAI`) | принимает историю; `openai.OpenAIError` → `LLM*` ошибки; timeout 30 s, 2 ретрая |
| `app/infrastructure/repositories/conversation_repository.py` | `SQLAlchemyConversationRepository` — история диалога | создание, загрузка, добавление сообщений, commit |
| `app/schemas/chat_schema.py` | Pydantic-схемы — контракт API | `conversation_id` необязателен во входе |
| `docs/` | документация проекта | — |

Каталог переименован: `app/infrasructure` → `app/infrastructure` (дефект закрыт).

## Правило зависимостей

Стрелки импортов — в одну сторону: `api` → `application` ← `infrastructure`; `schemas` — общий контракт.
`application` не импортирует FastAPI/SQLAlchemy; `infrastructure` реализует то, что нужно `application`.
Дорогую перестройку делают не имена папок, а нарушения этого правила: ORM-модели или `Depends` внутри сервиса, SQL в роутере, `create_engine` на импорте модуля.

## Ключевые потоки данных

### Срез «чат»: сейчас и цель

```
клиент --POST /chat {conversation_id?, content}> api/routes/chat_router.py
  -> Depends(get_chat_service) -> application/chat/service.py ChatService.handle
       -> infrastructure/repositories/conversation_repository.py
            создать диалог (id = None) / загрузить историю (id передан)
       -> infrastructure/llm/openai_client.py OpenAIChatClient.complete(history + user)
            ошибки SDK → LLMUnavailable/LLMTimeout/LLMRateLimited/LLMConfiguration/LLMRequestRejected
       -> repositories: сохранить user + assistant, commit
  -> ошибки: ChatError → HTTP в chat_router.py (404/502/504/429/422/503)
  -> schemas/chat_schema.py ChatResponse {conversation_id, content}
```

Фактическое состояние (проверено 2026-11-12): срез сквозной — новый диалог создаётся при `conversation_id=None`, переданный id загружает историю из `messages`, оба сообщения сохраняются, ответ содержит реальный id. Неизвестный id → 404. Ошибки провайдера не выходят как 500: адаптер переводит их в прикладные `LLM*`, роутер — в 502/504/429/503/422. В LLM уходит вся история без обрезки; commit один, в конце сценария. `application` не импортирует FastAPI/SQLAlchemy/`openai`: порты и ошибки — в `application/chat/`, адаптеры/repository — в `infrastructure`, связывание — в `api/dependencies.py`, HTTP-маппинг — в роутере.

## Пакеты и `__init__.py`

Все каталоги `app/` — реальные пакеты (ADR-0005): `__init__.py` в `app/`, `api/`, `api/routes/`, `application/`, `application/chat/`, `core/`, `infrastructure/`, `infrastructure/llm/`, `infrastructure/repositories/`, `schemas/` — пустые маркеры; единственное исключение — `infrastructure/db/__init__.py` реэкспортирует `Base`, `engine`, `AsyncSessionLocal`. Подмодули импортируют друг друга напрямую (`from .db import Base`), не через пакет. Модели в `__init__` не импортируются: там, где нужен `Base.metadata` (Alembic `env.py`), `import app.infrastructure.db.models` пишется явно.

Соглашение по чату (ADR-0008): порты, DTO и ошибки чата живут только в `app/application/chat/` (`ports.py`, `dto.py`, `errors.py`); новый код такого рода не кладём в `service.py` или рядом с адаптерами.

## Запуск и окружение

- Запуск: `source .venv/bin/activate && uvicorn app.main:app --reload` (проверка: `GET http://127.0.0.1:8000/health`).
- Зависимости зафиксированы в `requirements.txt` (ручной список; `pyproject.toml` — позже). Async-стек БД требует `sqlalchemy[asyncio]` (тянет `greenlet`) и `asyncpg`; оба записаны.
- `.env` есть (RouterAI: ключ, base_url, модель; `DATABASE_URL=postgresql+asyncpg://…`), в git не попадает; `.env.example` пока не создан. `Settings` читает `.env` относительно CWD — запускать приложение из корня проекта.
- Postgres: контейнер запущен пользователем, `localhost:5432` отвечает. Схемой управляет Alembic: `alembic upgrade head` из корня проекта; после правки моделей — `alembic revision --autogenerate -m "…"` и снова `upgrade head`. URL берётся из `settings.DATABASE_URL` в `alembic/env.py` (в `alembic.ini` не хранится). Миграции в startup не применяются; engine по-прежнему ленивый, приложение стартует без БД, но `POST /chat` без Postgres упадёт.

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
