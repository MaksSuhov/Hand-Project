# Состояние проекта

Обновлено: 2026-11-10

## Сделано

- Создана структура документации (`docs/`) и правила проекта (`AGENTS.md`).
- Выбрана IDE: VS Code (ADR-0001), PyCharm не используется.
- Создано окружение проекта: `.venv` от python.org 3.14.7 (ADR-0002); Anaconda не задействована.
- Создан каркас приложения по слоям (`api` / `application` / `core` / `infrasructure` / `schemas`), ADR-0003; модули пока пустые.
- `app/main.py` — работающий `GET /health`.
- Установлены зависимости: FastAPI, uvicorn, Pydantic 2 (+ `pydantic-settings` 2.16.2), SQLAlchemy 2.1, LangChain/LangGraph, OpenAI SDK.
- Инициализирован git-репозиторий: ветка `main`, коммитов ещё нет, remote не настроен.

## В работе

- Ничего.

## Следующие шаги

- Переименовать `app/infrasructure` → `app/infrastructure` (пока нет импортов).
- `.gitignore` (`.venv/`, `__pycache__/`, `*.pyc`, `.env`, `*.db`), первый коммит, remote и push — до появления реального кода.
- Зафиксировать зависимости (`requirements.txt` / `pyproject.toml`).
- Выбрать первый вертикальный срез (один сценарий сквозь все слои) и зафиксировать в PRD.
- Решить два дорогих к переделке вопроса: JSON или streaming (SSE) и sync или async БД.
- Решить, где хранится история диалога: checkpointer LangGraph или свои таблицы.
- Только после этого — `schemas` → `application` → `api`, затем `models`/`repositories`/`unit_of_work`.

## Известные проблемы / открытые вопросы

- Идея проекта ещё не сформулирована; по зависимостям направление — LLM-чат/агент.
- Опечатка в имени пакета `infrasructure`.
- Нет `__init__.py` в `app/` и подпакетах (работает за счёт namespace-пакетов, но тулинг может спотыкаться).
- Нет `.gitignore` и первого коммита; remote не настроен; `user.name`/`user.email` в git не заданы; `gh` и SSH-ключей на машине нет (push — только HTTPS + token или после `ssh-keygen`).
- `pytest` не установлен; тестов нет.
- Code Runner в VS Code запускает Anaconda-питон вместо `.venv` — источник ложных `ModuleNotFoundError`.
