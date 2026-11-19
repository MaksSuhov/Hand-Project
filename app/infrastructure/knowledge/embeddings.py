import logging
from collections.abc import Sequence

from openai import AsyncOpenAI, OpenAIError

from app.application.knowledge.errors import KnowledgeUnavailableError
from app.core.config import settings

logger = logging.getLogger(__name__)


class OpenAIEmbeddings:
    """Эмбеддинги через OpenAI-совместимый RouterAI."""

    def __init__(
        self,
        client: AsyncOpenAI | None = None,
        model: str | None = None,
    ) -> None:
        self._client = client or AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            timeout=30.0,
            max_retries=2,
        )
        self._model = model or settings.OPENAI_EMBEDDING_MODEL

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        try:
            response = await self._client.embeddings.create(
                model=self._model,
                input=list(texts),
            )
        except OpenAIError as exc:
            logger.warning('Embedding request failed: %s', exc)
            raise KnowledgeUnavailableError('Embedding provider is unavailable') from exc
        return [item.embedding for item in response.data]

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed([text]))[0]