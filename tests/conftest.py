from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

from app.api.dependencies import get_chat_service
from app.application.chat.dto import ChatMessage
from app.application.chat.errors import ChatError
from app.application.chat.service import ChatService
from app.application.knowledge.dto import KnowledgeChunk
from app.application.knowledge.errors import KnowledgeError
from app.main import app


class FakeRepository:
    def __init__(self) -> None:
        self.conversations: dict[int, list[ChatMessage]] = {}

    async def create_conversation(self) -> int:
        conversation_id = len(self.conversations) + 1
        self.conversations[conversation_id] = []
        return conversation_id

    async def get_messages(self, conversation_id: int) -> list[ChatMessage] | None:
        if conversation_id not in self.conversations:
            return None
        return list(self.conversations[conversation_id])

    async def add_message(self, conversation_id: int, message: ChatMessage) -> None:
        self.conversations[conversation_id].append(message)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class FakeLLM:
    def __init__(
        self,
        deltas: tuple[str, ...] = ('При', 'вет', '!'),
        error: ChatError | None = None,
    ) -> None:
        self.deltas = deltas
        self.error = error
        self.last_messages: list[ChatMessage] | None = None
        self.last_conversation_id: int | None = None

    async def complete(
        self, messages, *, conversation_id: int | None = None
    ) -> str:
        self.last_messages = list(messages)
        self.last_conversation_id = conversation_id
        if self.error is not None:
            raise self.error
        return ''.join(self.deltas)

    async def stream(
        self, messages, *, conversation_id: int | None = None
    ) -> AsyncIterator[str]:
        self.last_messages = list(messages)
        self.last_conversation_id = conversation_id
        for delta in self.deltas:
            yield delta
        if self.error is not None:
            raise self.error


class FakeKnowledge:
    def __init__(
        self,
        chunks: list[KnowledgeChunk] | None = None,
        error: KnowledgeError | None = None,
    ) -> None:
        self.chunks = chunks or []
        self.error = error
        self.last_query: str | None = None
        self.last_limit: int | None = None

    async def search(self, query: str, *, limit: int = 5) -> list[KnowledgeChunk]:
        self.last_query = query
        self.last_limit = limit
        if self.error is not None:
            raise self.error
        return self.chunks[:limit]


@pytest.fixture
def repo() -> FakeRepository:
    return FakeRepository()


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def llm() -> FakeLLM:
    return FakeLLM()


@pytest.fixture
def knowledge() -> FakeKnowledge:
    return FakeKnowledge()


@pytest.fixture
def service(
    llm: FakeLLM,
    repo: FakeRepository,
    uow: FakeUnitOfWork,
    knowledge: FakeKnowledge,
) -> ChatService:
    return ChatService(llm, repo, uow, knowledge)


@pytest_asyncio.fixture
async def client(service: ChatService) -> AsyncIterator[httpx.AsyncClient]:
    app.dependency_overrides[get_chat_service] = lambda: service
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url='http://test'
    ) as client:
        yield client
    app.dependency_overrides.clear()