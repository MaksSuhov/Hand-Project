class ChatError(Exception):
    """Базовая ошибка сценария чата."""


class ConversationNotFoundError(ChatError):
    def __init__(self, conversation_id: int) -> None:
        super().__init__(f'Conversation {conversation_id} not found')
        self.conversation_id = conversation_id


class LLMError(ChatError):
    """Сбой LLM-провайдера; исходное исключение — в __cause__."""


class LLMUnavailableError(LLMError):
    pass


class LLMTimeoutError(LLMError):
    pass


class LLMRateLimitedError(LLMError):
    pass


class LLMConfigurationError(LLMError):
    pass


class LLMRequestRejectedError(LLMError):
    pass