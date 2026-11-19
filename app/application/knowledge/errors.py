class KnowledgeError(Exception):
    """Сбой поиска по базе знаний; сценарий чата продолжает работу без контекста."""


class KnowledgeUnavailableError(KnowledgeError):
    pass