from pydantic import BaseModel, Field

class ChatRequest(BaseModel):

    conversation_id: int | None = None
    content: str = Field(min_length=1, max_length=800)

class ChatResponse(BaseModel):

    conversation_id: int 
    content: str