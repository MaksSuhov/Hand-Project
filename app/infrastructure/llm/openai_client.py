import logging
from collections.abc import Sequence

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    OpenAIError,
    PermissionDeniedError,
    RateLimitError,
    UnprocessableEntityError,
)

from app.application.chat.dto import ChatMessage
from app.application.chat.errors import (
    LLMConfigurationError,
    LLMError,
    LLMRateLimitedError,
    LLMRequestRejectedError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.core.config import settings

logger = logging.getLogger(__name__)


def _to_llm_error(exc: OpenAIError) -> LLMError:
    if isinstance(exc, APITimeoutError):
        return LLMTimeoutError('LLM provider timed out')
    if isinstance(exc, APIConnectionError):
        return LLMUnavailableError('LLM provider is unavailable')
    if isinstance(exc, RateLimitError):
        return LLMRateLimitedError('LLM provider rate limit exceeded')
    if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
        return LLMConfigurationError('LLM provider rejected credentials')
    if isinstance(exc, (BadRequestError, UnprocessableEntityError, NotFoundError)):
        return LLMRequestRejectedError('LLM provider rejected the request')
    if isinstance(exc, APIStatusError):
        return LLMUnavailableError('LLM provider returned an error')
    return LLMUnavailableError('LLM request failed')


class OpenAIChatClient:
    """Адаптер RouterAI (OpenAI-совместимый API) под порт LLMProvider."""

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
        self._model = model or settings.OPENAI_CHAT_MODEL

    async def complete(self, messages: Sequence[ChatMessage]) -> str:
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {'role': message.role, 'content': message.content}
                    for message in messages
                ],
            )
        except OpenAIError as exc:
            logger.warning('LLM provider request failed: %s', exc)
            raise _to_llm_error(exc) from exc

        content = response.choices[0].message.content
        return content or ""