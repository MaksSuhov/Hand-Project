from app.application.chat.dto import Role
from app.application.knowledge.dto import KnowledgeChunk
from app.application.knowledge.errors import KnowledgeUnavailableError
from tests.conftest import FakeKnowledge, FakeLLM

_CHUNK = KnowledgeChunk(
    source='knowledge_base/01_hr_vacation.md',
    title='Отпуска и дни отдыха',
    heading='Основной отпуск',
    content='Каждому сотруднику положен отпуск — 28 календарных дней.',
    score=0.78,
)


async def test_rag_injects_context_before_history(
    client, llm: FakeLLM, knowledge: FakeKnowledge
) -> None:
    knowledge.chunks = [_CHUNK]

    response = await client.post('/chat', json={'content': 'Сколько дней отпуска?'})

    assert response.status_code == 200
    assert knowledge.last_query == 'Сколько дней отпуска?'
    system = llm.last_messages[0]
    assert system.role is Role.SYSTEM
    assert '28 календарных дней' in system.content
    assert 'knowledge_base/01_hr_vacation.md' in system.content
    assert llm.last_messages[-1].role is Role.USER


async def test_rag_unavailable_degrades_to_empty_context(
    client, llm: FakeLLM, knowledge: FakeKnowledge
) -> None:
    knowledge.error = KnowledgeUnavailableError('embedding provider is down')

    response = await client.post('/chat', json={'content': 'Сколько дней отпуска?'})

    assert response.status_code == 200
    assert llm.last_messages[0].role is Role.SYSTEM
    assert 'Фрагменты не найдены' in llm.last_messages[0].content