from collections.abc import AsyncGenerator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.chat.ports import LLMProvider
from app.application.chat.service import ChatService
from app.core.config import settings
from app.infrastructure.db.db import AsyncSessionLocal
from app.infrastructure.knowledge.embeddings import OpenAIEmbeddings
from app.infrastructure.knowledge.retriever import PgVectorKnowledgeBase
from app.infrastructure.llm.openai_client import OpenAIChatClient
from app.infrastructure.repositories.conversation_repository import (
    SQLAlchemyConversationRepository,
)
from app.infrastructure.unit_of_work import SQLAlchemyUnitOfWork


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


@lru_cache
def get_llm() -> LLMProvider:
    return OpenAIChatClient()


@lru_cache
def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings()


def get_chat_service(
    session: AsyncSession = Depends(get_session),
) -> ChatService:
    return ChatService(
        get_llm(),
        SQLAlchemyConversationRepository(session),
        SQLAlchemyUnitOfWork(session),
        PgVectorKnowledgeBase(
            session,
            get_embeddings(),
            min_score=settings.RAG_MIN_SCORE,
        ),
        top_k=settings.RAG_TOP_K,
    )