"""Загрузка корпоративной базы знаний в pgvector.

Запуск из корня проекта:
    .venv/bin/python -m scripts.seed_knowledge
    .venv/bin/python -m scripts.seed_knowledge --reset
"""
import argparse
import asyncio
from pathlib import Path

from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)
from sqlalchemy import delete, func, select

from app.infrastructure.db.db import AsyncSessionLocal
from app.infrastructure.db.models import KnowledgeChunk
from app.infrastructure.knowledge.embeddings import OpenAIEmbeddings

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / 'knowledge_base'
DOCUMENT_GLOB = '[0-9][0-9]_*.md'
CHUNK_SIZE = 1200
CHUNK_OVERLAP = 150
EMBED_BATCH = 32

_HEADERS = [('#', 'title'), ('##', 'section'), ('###', 'subsection')]


def _read_document(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding='utf-8')
    title = path.stem
    for line in text.splitlines():
        if line.startswith('# '):
            title = line[2:].strip()
            break
    return title, text


def _split(text: str) -> list[tuple[str | None, str]]:
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=_HEADERS)
    size_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=['\n\n', '\n', '. ', ' ', ''],
    )
    chunks: list[tuple[str | None, str]] = []
    for section in markdown_splitter.split_text(text):
        heading = ' / '.join(
            part
            for part in (
                section.metadata.get('section'),
                section.metadata.get('subsection'),
            )
            if part
        ) or None
        for piece in size_splitter.split_documents([section]):
            content = piece.page_content.strip()
            if content:
                chunks.append((heading, content))
    return chunks


async def seed(reset: bool) -> None:
    paths = sorted(KNOWLEDGE_DIR.glob(DOCUMENT_GLOB))
    if not paths:
        raise SystemExit(f'Не найдено документов в {KNOWLEDGE_DIR}')

    documents = []
    for path in paths:
        title, text = _read_document(path)
        source = str(path.relative_to(KNOWLEDGE_DIR.parent))
        documents.append((source, title, _split(text)))

    embeddings = OpenAIEmbeddings()
    async with AsyncSessionLocal() as session:
        if reset:
            await session.execute(delete(KnowledgeChunk))
            print('Таблица knowledge_chunks очищена')

        total = 0
        for source, title, chunks in documents:
            vectors: list[list[float]] = []
            for start in range(0, len(chunks), EMBED_BATCH):
                batch = [content for _, content in chunks[start:start + EMBED_BATCH]]
                vectors.extend(await embeddings.embed(batch))

            await session.execute(
                delete(KnowledgeChunk).where(KnowledgeChunk.source == source)
            )
            session.add_all(
                [
                    KnowledgeChunk(
                        source=source,
                        title=title,
                        heading=heading,
                        chunk_index=index,
                        content=content,
                        embedding=vector,
                    )
                    for index, ((heading, content), vector) in enumerate(
                        zip(chunks, vectors)
                    )
                ]
            )
            await session.flush()
            total += len(chunks)
            print(f'{source}: {len(chunks)} чанков')

        await session.commit()
        stored = await session.scalar(select(func.count()).select_from(KnowledgeChunk))
        print(f'Готово: загружено {total} чанков, в таблице {stored}')


def main() -> None:
    parser = argparse.ArgumentParser(description='Загрузка базы знаний в pgvector')
    parser.add_argument(
        '--reset',
        action='store_true',
        help='очистить таблицу перед загрузкой',
    )
    args = parser.parse_args()
    asyncio.run(seed(args.reset))


if __name__ == '__main__':
    main()