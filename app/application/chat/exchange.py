from collections.abc import AsyncIterator, Sequence

from app.application.chat.dto import ChatAnswer, ChatMessage, Role
from app.application.chat.ports import ConversationRepository, LLMProvider, UnitOfWork


class ChatExchange:
    """Подготовленный обмен: user-сообщение добавлено, ответ ещё не получен."""

    def __init__(
        self,
        *,
        conversation_id: int,
        messages: Sequence[ChatMessage],
        llm: LLMProvider,
        repository: ConversationRepository,
        uow: UnitOfWork,
    ) -> None:
        self._conversation_id = conversation_id
        self._messages = messages
        self._llm = llm
        self._repository = repository
        self._uow = uow

    @property
    def conversation_id(self) -> int:
        return self._conversation_id

    async def complete(self) -> ChatAnswer:
        content = await self._llm.complete(
            self._messages,
            conversation_id=self._conversation_id,
        )
        await self._finish(content)
        return ChatAnswer(
            conversation_id=self._conversation_id,
            content=content,
        )

    async def stream(self) -> AsyncIterator[str]:
        parts: list[str] = []
        async for delta in self._llm.stream(
            self._messages,
            conversation_id=self._conversation_id,
        ):
            parts.append(delta)
            yield delta
        await self._finish(''.join(parts))

    async def _finish(self, content: str) -> None:
        await self._repository.add_message(
            self._conversation_id,
            ChatMessage(role=Role.ASSISTANT, content=content),
        )
        await self._uow.commit()