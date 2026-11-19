from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, Relationship, mapped_column

from app.infrastructure.db import Base

EMBEDDING_DIM = 1024


class Conversation(Base):
    __tablename__ = 'conversations'

    conversation_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    messages: Mapped[list['Message']] = Relationship(
        back_populates='conversation',
        cascade='all, delete-orphan',
        lazy='selectin',
        order_by='Message.message_id',
    )

class Message(Base):
    __tablename__ = 'messages'

    message_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey('conversations.conversation_id', ondelete='CASCADE'), nullable=False)
    role: Mapped[str] = mapped_column(String(), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    conversation: Mapped["Conversation"] = Relationship(back_populates="messages")


class KnowledgeChunk(Base):
    __tablename__ = 'knowledge_chunks'
    __table_args__ = (
        UniqueConstraint('source', 'chunk_index', name='uq_knowledge_chunks_source_chunk_index'),
        Index(
            'ix_knowledge_chunks_embedding_hnsw',
            'embedding',
            postgresql_using='hnsw',
            postgresql_ops={'embedding': 'vector_cosine_ops'},
        ),
    )

    chunk_id: Mapped[int] = mapped_column(primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    heading: Mapped[str | None] = mapped_column(String(255))
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())