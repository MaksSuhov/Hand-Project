from app.application.chat.dto import ChatMessage, Role
from app.application.chat.errors import LLMTimeoutError
from tests.conftest import FakeLLM, FakeRepository, FakeUnitOfWork


async def test_chat_new_conversation(
    client, llm: FakeLLM, repo: FakeRepository, uow: FakeUnitOfWork
) -> None:
    response = await client.post('/chat', json={'content': 'привет'})

    assert response.status_code == 200
    assert response.json() == {'conversation_id': 1, 'content': 'Привет!'}
    assert llm.last_conversation_id == 1
    assert repo.conversations[1] == [
        ChatMessage(role=Role.USER, content='привет'),
        ChatMessage(role=Role.ASSISTANT, content='Привет!'),
    ]
    assert uow.commits == 1


async def test_chat_continues_history(
    client, llm: FakeLLM, repo: FakeRepository
) -> None:
    repo.conversations[1] = [
        ChatMessage(role=Role.USER, content='старое'),
        ChatMessage(role=Role.ASSISTANT, content='ответ'),
    ]

    response = await client.post(
        '/chat', json={'conversation_id': 1, 'content': 'новое'}
    )

    assert response.status_code == 200
    assert [message.role for message in llm.last_messages] == [
        Role.SYSTEM,
        Role.USER,
        Role.ASSISTANT,
        Role.USER,
    ]
    assert llm.last_conversation_id == 1


async def test_chat_unknown_conversation_returns_404(client) -> None:
    response = await client.post(
        '/chat', json={'conversation_id': 99, 'content': 'x'}
    )

    assert response.status_code == 404
    assert response.json()['detail'] == {
        'code': 'conversation_not_found',
        'message': 'Conversation 99 not found',
    }


async def test_chat_provider_error_mapped_to_504(
    client, llm: FakeLLM
) -> None:
    llm.error = LLMTimeoutError('LLM provider timed out')

    response = await client.post('/chat', json={'content': 'x'})

    assert response.status_code == 504
    assert response.json()['detail'] == {
        'code': 'provider_timeout',
        'message': 'LLM provider timed out',
    }


async def test_chat_empty_content_returns_422(client) -> None:
    response = await client.post('/chat', json={'content': ''})

    assert response.status_code == 422