import logging
from collections.abc import AsyncIterator, Sequence

from langfuse import propagate_attributes
from langfuse.openai import AsyncOpenAI
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
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

_GENERATION_NAME = 'chat.completion'


def _to_session_id(conversation_id: int | None) -> str | None:
    return str(conversation_id) if conversation_id is not None else None


def _to_payload(messages: Sequence[ChatMessage]) -> list[dict[str, str]]:
    return [
        {'role': message.role.value, 'content': message.content}
        for message in messages
    ]


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

    async def complete(
        self,
        messages: Sequence[ChatMessage],
        *,
        conversation_id: int | None = None,
    ) -> str:
        try:
            with propagate_attributes(session_id=_to_session_id(conversation_id)):
                response = await self._client.chat.completions.create(
                    model=self._model,
                    messages=_to_payload(messages),
                    name=_GENERATION_NAME,
                )
        except OpenAIError as exc:
            logger.warning('LLM provider request failed: %s', exc)
            raise _to_llm_error(exc) from exc

        content = response.choices[0].message.content
        return content or ''

    async def stream(
        self,
        messages: Sequence[ChatMessage],
        *,
        conversation_id: int | None = None,
    ) -> AsyncIterator[str]:
        try:
            with propagate_attributes(session_id=_to_session_id(conversation_id)):
                stream = await self._client.chat.completions.create(
                    model=self._model,
                    messages=_to_payload(messages),
                    stream=True,
                    stream_options={'include_usage': True},
                    name=_GENERATION_NAME,
                )
                try:
                    async for chunk in stream:
                        if not chunk.choices:
                            continue
                        delta = chunk.choices[0].delta.content
                        if delta:
                            yield delta
                finally:
                    await stream.close()
        except OpenAIError as exc:
            logger.warning('LLM provider stream failed: %s', exc)
            raise _to_llm_error(exc) from exc