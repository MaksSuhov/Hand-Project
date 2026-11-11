from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.chat.service import ChatService
from app.infrastructure.db.db import AsyncSessionLocal
from app.infrastructure.llm.openai_client import OpenAIChatClient
from app.infrastructure.repositories.conversation_repository import (
    SQLAlchemyConversationRepository,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


@lru_cache
def get_llm() -> OpenAIChatClient:
    return OpenAIChatClient()


def get_chat_service(
    session: AsyncSession = Depends(get_session),
) -> ChatService:
    return ChatService(get_llm(), SQLAlchemyConversationRepository(session))