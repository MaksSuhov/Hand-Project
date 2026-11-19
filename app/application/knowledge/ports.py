from typing import Protocol

from app.application.knowledge.dto import KnowledgeChunk


class KnowledgeBase(Protocol):
    async def search(self, query: str, *, limit: int = 5) -> list[KnowledgeChunk]: ...