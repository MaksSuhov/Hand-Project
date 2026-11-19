from sqlalchemy.ext.asyncio import AsyncSession

from app.application.chat.dto import ChatMessage, Role
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
            ChatMessage(role=Role(message.role), content=message.content)
            for message in conversation.messages
        ]

    async def add_message(self, conversation_id: int, message: ChatMessage) -> None:
        self._session.add(
            Message(
                conversation_id=conversation_id,
                role=message.role.value,
                content=message.content,
            )
        )