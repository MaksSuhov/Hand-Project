from dataclasses import dataclass


@dataclass(frozen=True)
class KnowledgeChunk:
    source: str
    title: str
    heading: str | None
    content: str
    score: float