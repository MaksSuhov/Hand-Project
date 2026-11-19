from fastapi import HTTPException, status
from fastapi.sse import ServerSentEvent

from app.application.chat.errors import (
    ChatError,
    ConversationNotFoundError,
    LLMConfigurationError,
    LLMRateLimitedError,
    LLMRequestRejectedError,
    LLMTimeoutError,
    LLMUnavailableError,
)

_ERRORS: tuple[tuple[type[ChatError], int, str], ...] = (
    (ConversationNotFoundError, status.HTTP_404_NOT_FOUND, 'conversation_not_found'),
    (LLMUnavailableError, status.HTTP_502_BAD_GATEWAY, 'provider_unavailable'),
    (LLMTimeoutError, status.HTTP_504_GATEWAY_TIMEOUT, 'provider_timeout'),
    (LLMRateLimitedError, status.HTTP_429_TOO_MANY_REQUESTS, 'rate_limited'),
    (LLMRequestRejectedError, status.HTTP_422_UNPROCESSABLE_CONTENT, 'request_rejected'),
    (LLMConfigurationError, status.HTTP_503_SERVICE_UNAVAILABLE, 'provider_misconfigured'),
)


def _resolve(exc: ChatError) -> tuple[int, str]:
    for error_type, http_status, code in _ERRORS:
        if isinstance(exc, error_type):
            return http_status, code
    return status.HTTP_500_INTERNAL_SERVER_ERROR, 'internal_error'


def to_http_error(exc: ChatError) -> HTTPException:
    http_status, code = _resolve(exc)
    return HTTPException(
        status_code=http_status,
        detail={'code': code, 'message': str(exc)},
    )


def to_sse_event(exc: ChatError) -> ServerSentEvent:
    _, code = _resolve(exc)
    return ServerSentEvent(
        event='error',
        data={'code': code, 'message': str(exc)},
    )