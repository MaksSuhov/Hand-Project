from sqlalchemy.ext.asyncio import AsyncSession

from app.application.chat.dto import ChatMessage
from app.infrastructure.db.models import Conversation, Message


class SQLAlchemyConversationRepository:
    """Репозиторий истории диалога под порт ConversationRepository."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_conversation(self) -> int:
        conversation = Conversation()
        self._session.add(conversation)
        await self._session.flush()
        return conversation.conversation_id

    async def get_messages(self, conversation_id: int) -> list[ChatMessage] | None:
        conversation = await self._session.get(Conversation, conversation_id)
        if conversation is None:
            return None
        return [
            ChatMessage(role=message.role, content=message.content)
            for message in conversation.messages
        ]

    async def add_message(self, conversation_id: int, role: str, content: str) -> None:
        self._session.add(
            Message(conversation_id=conversation_id, role=role, content=content)
        )

    async def commit(self) -> None:
        await self._session.commit()