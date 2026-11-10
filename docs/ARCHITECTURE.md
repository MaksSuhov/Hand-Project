# Архитектура

> Статус: создан каркас папок и пустых модулей; архитектура пока заявлена структурой, а не кодом.

## Стек и обоснование

Установлено в `.venv` (2026-11-10), но **не зафиксировано** в `requirements.txt`/`pyproject.toml`:

| Роль | Пакет | Версия |
|---|---|---|
| HTTP | `fastapi` / `uvicorn` / `starlette` | 0.162.3 / 0.54.0 / 1.10.0 |
| Валидация | `pydantic` / `pydantic-settings` | 2.14.3 / 2.16.2 |
| БД | `SQLAlchemy` | 2.1.8 (драйвера БД и `alembic` пока нет) |
| LLM/агенты | `langchain` / `langgraph` / `openai` | 1.4.9 / 1.2.20 / 3.49.0 |
| Тесты | — | `pytest` не установлен |

Python 3.14.7 (`.venv`, ADR-0002). По зависимостям проект — чат/агент на LLM с БД.

## Карта проекта

| Путь | Назначение | Состояние |
|---|---|---|
| `app/main.py` | точка входа FastAPI; сейчас только `GET /health` | работает |
| `app/core/config.py` | настройки приложения | пусто |
| `app/api/routes/router.py` | сборка роутеров | пусто |
| `app/api/routes/dependencies.py` | DI-зависимости FastAPI (сессия БД, сервисы) | пусто |
| `app/application/chat_service.py` | сценарий чата (use case) | пусто |
| `app/infrasructure/db.py` | engine/сессии | пусто |
| `app/infrasructure/models.py` | SQLAlchemy-модели (хранение) | пусто |
| `app/infrasructure/unit_of_work.py` | транзакция на сценарий | пусто |
| `app/infrasructure/repositories/` | репозитории (запросы к БД) | пусто |
| `app/schemas/` | Pydantic-схемы — контракт API | пусто |
| `docs/` | документация проекта | — |

Известный дефект: каталог назван `infrasructure` — переименовать в `infrastructure`, пока импортов нет.

## Правило зависимостей

Стрелки импортов — в одну сторону: `api` → `application` ← `infrastructure`; `schemas` — общий контракт.
`application` не импортирует FastAPI/SQLAlchemy; `infrastructure` реализует то, что нужно `application`.
Дорогую перестройку делают не имена папок, а нарушения этого правила: ORM-модели или `Depends` внутри сервиса, SQL в роутере, `create_engine` на импорте модуля.

## Ключевые потоки данных

<!-- появится с первым сценарием -->

## Запуск и окружение

- Запуск: `source .venv/bin/activate && uvicorn app.main:app --reload` (проверка: `GET http://127.0.0.1:8000/health`).
- Зависимости не зафиксированы: `pip freeze > requirements.txt` (или `pyproject.toml`) до появления реального кода.
- `.env`/переменных окружения пока нет; `pydantic-settings` 2.16.2 уже установлен — `BaseSettings` в `core/config.py` можно писать сразу.

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
