from sqlalchemy import literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.knowledge.dto import KnowledgeChunk
from app.infrastructure.db.models import KnowledgeChunk as KnowledgeChunkRow
from app.infrastructure.knowledge.embeddings import OpenAIEmbeddings


class PgVectorKnowledgeBase:
    """Поиск по базе знаний: косинусное расстояние в pgvector."""

    def __init__(
        self,
        session: AsyncSession,
        embeddings: OpenAIEmbeddings,
        *,
        min_score: float = 0.0,
    ) -> None:
        self._session = session
        self._embeddings = embeddings
        self._min_score = min_score

    async def search(self, query: str, *, limit: int = 5) -> list[KnowledgeChunk]:
        vector = await self._embeddings.embed_query(query)
        distance = KnowledgeChunkRow.embedding.cosine_distance(vector)
        statement = (
            select(KnowledgeChunkRow, (literal(1.0) - distance).label('score'))
            .order_by(distance)
            .limit(limit)
        )
        rows = (await self._session.execute(statement)).all()
        return [
            KnowledgeChunk(
                source=chunk.source,
                title=chunk.title,
                heading=chunk.heading,
                content=chunk.content,
                score=float(score),
            )
            for chunk, score in rows
            if score >= self._min_score
        ]