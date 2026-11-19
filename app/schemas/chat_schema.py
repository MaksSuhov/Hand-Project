from pydantic import BaseModel, Field

from app.application.chat.dto import MAX_CONTENT_LENGTH


class ChatRequest(BaseModel):
    conversation_id: int | None = None
    content: str = Field(min_length=1, max_length=MAX_CONTENT_LENGTH)


class ChatResponse(BaseModel):
    conversation_id: int
    content: str