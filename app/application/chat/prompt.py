from collections.abc import Sequence

from app.application.knowledge.dto import KnowledgeChunk

_INSTRUCTIONS = """Ты — ассистент по внутренней базе знаний компании «Северный Ветер».
Отвечай сотруднику, опираясь только на фрагменты базы знаний ниже.
Правила:
- Если во фрагментах нет ответа, скажи, что в базе знаний такой информации нет; не выдумывай.
- Фрагменты с пометкой «архив» или «не действует» не используй как действующие правила.
- В конце ответа перечисли источники, на которые опирался, в формате (источник: путь).
- Отвечай по-русски, кратко и по делу.

Фрагменты базы знаний:"""


def build_grounding_prompt(chunks: Sequence[KnowledgeChunk]) -> str:
    if not chunks:
        return f'{_INSTRUCTIONS}\n\nФрагменты не найдены: в базе знаний нет информации по этому вопросу.'
    blocks = []
    for number, chunk in enumerate(chunks, start=1):
        heading = f' — {chunk.heading}' if chunk.heading else ''
        blocks.append(
            f'[{number}] {chunk.title}{heading} (источник: {chunk.source})\n'
            f'{chunk.content}'
        )
    return f'{_INSTRUCTIONS}\n\n' + '\n\n'.join(blocks)