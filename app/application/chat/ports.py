from collections.abc import Sequence
from typing import Protocol

from app.application.chat.dto import ChatMessage


class LLMProvider(Protocol):
    async def complete(self, messages: Sequence[ChatMessage]) -> str: ...


class ConversationRepository(Protocol):
    async def create_conversation(self) -> int: ...

    async def get_messages(self, conversation_id: int) -> list[ChatMessage] | None: ...

    async def add_message(
        self, conversation_id: int, role: str, content: str
    ) -> None: ...

    async def commit(self) -> None: ...