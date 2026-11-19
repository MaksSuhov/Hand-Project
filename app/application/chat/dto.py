from dataclasses import dataclass
from enum import StrEnum

MAX_CONTENT_LENGTH = 800


class Role(StrEnum):
    SYSTEM = 'system'
    USER = 'user'
    ASSISTANT = 'assistant'


@dataclass(frozen=True)
class ChatMessage:
    role: Role
    content: str


@dataclass(frozen=True)
class ChatCommand:
    content: str
    conversation_id: int | None = None


@dataclass(frozen=True)
class ChatAnswer:
    conversation_id: int
    content: str