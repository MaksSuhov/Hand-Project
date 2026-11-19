import logging
from collections.abc import Sequence

from app.application.chat.dto import ChatAnswer, ChatCommand, ChatMessage, Role
from app.application.chat.errors import ConversationNotFoundError
from app.application.chat.exchange import ChatExchange
from app.application.chat.ports import ConversationRepository, LLMProvider, UnitOfWork
from app.application.chat.prompt import build_grounding_prompt
from app.application.knowledge.dto import KnowledgeChunk
from app.application.knowledge.errors import KnowledgeError
from app.application.knowledge.ports import KnowledgeBase

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        llm: LLMProvider,
        repository: ConversationRepository,
        uow: UnitOfWork,
        knowledge: KnowledgeBase | None = None,
        *,
        top_k: int = 5,
    ) -> None:
        self._llm = llm
        self._repository = repository
        self._uow = uow
        self._knowledge = knowledge
        self._top_k = top_k

    async def chat(self, command: ChatCommand) -> ChatAnswer:
        exchange = await self.prepare(command)
        return await exchange.complete()

    async def prepare(self, command: ChatCommand) -> ChatExchange:
        if command.conversation_id is None:
            conversation_id = await self._repository.create_conversation()
            history: list[ChatMessage] = []
        else:
            conversation_id = command.conversation_id
            stored = await self._repository.get_messages(conversation_id)
            if stored is None:
                raise ConversationNotFoundError(conversation_id)
            history = stored

        user_message = ChatMessage(role=Role.USER, content=command.content)
        await self._repository.add_message(conversation_id, user_message)
        messages = [*history, user_message]
        if self._knowledge is not None:
            chunks = await self._retrieve_context(command.content)
            messages.insert(0, self._to_grounding_message(chunks))

        return ChatExchange(
            conversation_id=conversation_id,
            messages=messages,
            llm=self._llm,
            repository=self._repository,
            uow=self._uow,
        )

    async def _retrieve_context(self, query: str) -> Sequence[KnowledgeChunk]:
        if self._knowledge is None:
            return []
        try:
            return await self._knowledge.search(query, limit=self._top_k)
        except KnowledgeError as exc:
            logger.warning('Knowledge base search failed: %s', exc)
            return []

    @staticmethod
    def _to_grounding_message(chunks: Sequence[KnowledgeChunk]) -> ChatMessage:
        return ChatMessage(role=Role.SYSTEM, content=build_grounding_prompt(chunks))