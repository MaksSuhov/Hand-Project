from collections.abc import AsyncIterator, Sequence
from typing import Protocol

from app.application.chat.dto import ChatMessage


class LLMProvider(Protocol):
    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        conversation_id: int | None = None,
    ) -> str: ...

    def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        conversation_id: int | None = None,
    ) -> AsyncIterator[str]: ...


class ConversationRepository(Protocol):
    async def create_conversation(self) -> int: ...

    async def get_messages(self, conversation_id: int) -> list[ChatMessage] | None: ...

    async def add_message(self, conversation_id: int, message: ChatMessage) -> None: ...


class UnitOfWork(Protocol):
    async def commit(self) -> None: ...