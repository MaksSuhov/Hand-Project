from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, Relationship, mapped_column

from app.infrastructure.db import Base


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