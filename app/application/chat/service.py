from app.application.chat.dto import ChatMessage
from app.application.chat.errors import ConversationNotFoundError
from app.application.chat.ports import ConversationRepository, LLMProvider
from app.schemas.chat_schema import ChatRequest, ChatResponse


class ChatService:
    def __init__(self, llm: LLMProvider, repository: ConversationRepository) -> None:
        self._llm = llm
        self._repository = repository

    async def handle(self, request: ChatRequest) -> ChatResponse:
        history: list[ChatMessage] = []
        if request.conversation_id is None:
            conversation_id = await self._repository.create_conversation()
        else:
            conversation_id = request.conversation_id
            stored = await self._repository.get_messages(conversation_id)
            if stored is None:
                raise ConversationNotFoundError(conversation_id)
            history = stored

        user_message = ChatMessage(role='user', content=request.content)
        await self._repository.add_message(
            conversation_id, user_message.role, user_message.content
        )

        answer = await self._llm.complete([*history, user_message])

        await self._repository.add_message(conversation_id, 'assistant', answer)
        await self._repository.commit()

        return ChatResponse(conversation_id=conversation_id, content=answer)