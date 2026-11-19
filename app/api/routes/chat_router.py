from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends
from fastapi.responses import EventSourceResponse
from fastapi.sse import ServerSentEvent

from app.api.dependencies import get_chat_service
from app.api.error_mapping import to_http_error, to_sse_event
from app.application.chat.dto import ChatAnswer, ChatCommand
from app.application.chat.errors import ChatError
from app.application.chat.exchange import ChatExchange
from app.application.chat.service import ChatService
from app.schemas.chat_schema import ChatRequest, ChatResponse


router = APIRouter(prefix='/chat')


def _to_command(payload: ChatRequest) -> ChatCommand:
    return ChatCommand(
        content=payload.content,
        conversation_id=payload.conversation_id,
    )


def _to_response(answer: ChatAnswer) -> ChatResponse:
    return ChatResponse(
        conversation_id=answer.conversation_id,
        content=answer.content,
    )


@router.post(path='', response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatResponse:
    try:
        answer = await service.chat(_to_command(payload))
    except ChatError as exc:
        raise to_http_error(exc) from exc
    return _to_response(answer)


async def get_chat_exchange(
    payload: ChatRequest,
    service: ChatService = Depends(get_chat_service),
) -> ChatExchange:
    try:
        return await service.prepare(_to_command(payload))
    except ChatError as exc:
        raise to_http_error(exc) from exc


@router.post(path='/stream', response_class=EventSourceResponse)
async def chat_stream(
    exchange: ChatExchange = Depends(get_chat_exchange),
) -> AsyncIterator[ServerSentEvent]:
    yield ServerSentEvent(
        event='meta',
        data={'conversation_id': exchange.conversation_id},
    )
    try:
        async for delta in exchange.stream():
            yield ServerSentEvent(event='delta', raw_data=delta)
    except ChatError as exc:
        yield to_sse_event(exc)
        return
    yield ServerSentEvent(
        event='done',
        data={'conversation_id': exchange.conversation_id},
    )