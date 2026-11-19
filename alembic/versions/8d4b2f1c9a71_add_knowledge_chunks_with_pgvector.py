"""add knowledge chunks with pgvector

Revision ID: 8d4b2f1c9a71
Revises: fa04bfd1fe77
Create Date: 2026-11-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import pgvector.sqlalchemy
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8d4b2f1c9a71'
down_revision: Union[str, Sequence[str], None] = 'fa04bfd1fe77'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1024


def upgrade() -> None:
    """Upgrade schema."""
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    op.create_table(
        'knowledge_chunks',
        sa.Column('chunk_id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('heading', sa.String(length=255), nullable=True),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', pgvector.sqlalchemy.Vector(dim=EMBEDDING_DIM), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('chunk_id'),
        sa.UniqueConstraint('source', 'chunk_index', name='uq_knowledge_chunks_source_chunk_index'),
    )
    op.create_index(op.f('ix_knowledge_chunks_chunk_id'), 'knowledge_chunks', ['chunk_id'], unique=False)
    op.create_index(op.f('ix_knowledge_chunks_source'), 'knowledge_chunks', ['source'], unique=False)
    op.create_index(
        'ix_knowledge_chunks_embedding_hnsw',
        'knowledge_chunks',
        ['embedding'],
        unique=False,
        postgresql_using='hnsw',
        postgresql_ops={'embedding': 'vector_cosine_ops'},
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_knowledge_chunks_embedding_hnsw', table_name='knowledge_chunks')
    op.drop_index(op.f('ix_knowledge_chunks_source'), table_name='knowledge_chunks')
    op.drop_index(op.f('ix_knowledge_chunks_chunk_id'), table_name='knowledge_chunks')
    op.drop_table('knowledge_chunks')
    op.execute('DROP EXTENSION IF EXISTS vector')