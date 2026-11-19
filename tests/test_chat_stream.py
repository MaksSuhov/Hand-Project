import json

import pytest

from app.application.chat.dto import ChatMessage, Role
from app.application.chat.errors import (
    LLMConfigurationError,
    LLMRateLimitedError,
    LLMRequestRejectedError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from tests.conftest import FakeLLM, FakeRepository, FakeUnitOfWork
from tests.sse import parse_sse


async def test_stream_new_conversation(
    client, repo: FakeRepository, uow: FakeUnitOfWork
) -> None:
    response = await client.post('/chat/stream', json={'content': 'привет'})

    assert response.status_code == 200
    assert response.headers['content-type'].startswith('text/event-stream')

    events = parse_sse(response.text)
    assert [name for name, _ in events] == [
        'meta',
        'delta',
        'delta',
        'delta',
        'done',
    ]
    assert json.loads(events[0][1]) == {'conversation_id': 1}
    assert ''.join(data for name, data in events if name == 'delta') == 'Привет!'
    assert json.loads(events[-1][1]) == {'conversation_id': 1}

    assert repo.conversations[1] == [
        ChatMessage(role=Role.USER, content='привет'),
        ChatMessage(role=Role.ASSISTANT, content='Привет!'),
    ]
    assert uow.commits == 1


async def test_stream_continues_history(
    client, llm: FakeLLM, repo: FakeRepository
) -> None:
    repo.conversations[1] = [
        ChatMessage(role=Role.USER, content='старое'),
        ChatMessage(role=Role.ASSISTANT, content='ответ'),
    ]

    response = await client.post(
        '/chat/stream', json={'conversation_id': 1, 'content': 'новое'}
    )

    assert response.status_code == 200
    assert [message.role for message in llm.last_messages] == [
        Role.SYSTEM,
        Role.USER,
        Role.ASSISTANT,
        Role.USER,
    ]
    assert llm.last_conversation_id == 1
    assert repo.conversations[1][-1] == ChatMessage(
        role=Role.ASSISTANT, content='Привет!'
    )


async def test_stream_unknown_conversation_returns_http_404(client) -> None:
    response = await client.post(
        '/chat/stream', json={'conversation_id': 99, 'content': 'x'}
    )

    assert response.status_code == 404
    assert response.json()['detail'] == {
        'code': 'conversation_not_found',
        'message': 'Conversation 99 not found',
    }
    assert 'text/event-stream' not in response.headers['content-type']


@pytest.mark.parametrize(
    ('error', 'code'),
    [
        (LLMUnavailableError('LLM provider is unavailable'), 'provider_unavailable'),
        (LLMTimeoutError('LLM provider timed out'), 'provider_timeout'),
        (LLMRateLimitedError('LLM provider rate limit exceeded'), 'rate_limited'),
        (LLMRequestRejectedError('LLM provider rejected the request'), 'request_rejected'),
        (LLMConfigurationError('LLM provider rejected credentials'), 'provider_misconfigured'),
    ],
)
async def test_stream_provider_error_becomes_error_event(
    client,
    llm: FakeLLM,
    uow: FakeUnitOfWork,
    error,
    code: str,
) -> None:
    llm.error = error

    response = await client.post('/chat/stream', json={'content': 'x'})

    assert response.status_code == 200
    events = parse_sse(response.text)
    assert [name for name, _ in events] == [
        'meta',
        'delta',
        'delta',
        'delta',
        'error',
    ]
    assert json.loads(events[-1][1]) == {'code': code, 'message': str(error)}
    assert 'done' not in [name for name, _ in events]
    assert uow.commits == 0


async def test_stream_empty_content_returns_422(client) -> None:
    response = await client.post('/chat/stream', json={'content': ''})

    assert response.status_code == 422