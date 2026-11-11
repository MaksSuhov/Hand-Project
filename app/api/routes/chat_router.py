from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_chat_service
from app.application.chat.errors import (
    ChatError,
    ConversationNotFoundError,
    LLMConfigurationError,
    LLMRateLimitedError,
    LLMRequestRejectedError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from app.application.chat.service import ChatService
from app.schemas.chat_schema import ChatRequest, ChatResponse


router = APIRouter(prefix='/chat')

_ERROR_STATUS: dict[type[ChatError], int] = {
    ConversationNotFoundError: status.HTTP_404_NOT_FOUND,
    LLMUnavailableError: status.HTTP_502_BAD_GATEWAY,
    LLMTimeoutError: status.HTTP_504_GATEWAY_TIMEOUT,
    LLMRateLimitedError: status.HTTP_429_TOO_MANY_REQUESTS,
    LLMRequestRejectedError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    LLMConfigurationError: status.HTTP_503_SERVICE_UNAVAILABLE,
}


@router.post(path='', response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    try:
        return await service.handle(payload)
    except ChatError as exc:
        status_code = _ERROR_STATUS.get(
            type(exc), status.HTTP_500_INTERNAL_SERVER_ERROR
        )
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc