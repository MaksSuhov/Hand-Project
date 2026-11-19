import logging

from langfuse import Langfuse

from app.core.config import settings

logger = logging.getLogger(__name__)

_client: Langfuse | None = None


def init_tracing() -> None:
    global _client
    if _client is not None:
        return
    _client = Langfuse(
        public_key=settings.LANGFUSE_PUBLIC_KEY or None,
        secret_key=settings.LANGFUSE_SECRET_KEY or None,
        base_url=settings.LANGFUSE_BASE_URL,
        environment="development",
        tracing_enabled=bool(settings.LANGFUSE_PUBLIC_KEY),
    )
    if settings.LANGFUSE_PUBLIC_KEY and not _client.auth_check():
        logger.warning("Langfuse auth_check failed — traces will not be sent")


def shutdown_tracing() -> None:
    if _client is not None:
        _client.shutdown()