def parse_sse(text: str) -> list[tuple[str, str]]:
    """Разбирает тело ответа text/event-stream в список (event, data)."""
    events: list[tuple[str, str]] = []
    for frame in text.split('\n\n'):
        if not frame.strip():
            continue
        event = 'message'
        data_lines: list[str] = []
        for line in frame.split('\n'):
            if line.startswith(':'):
                continue
            if line.startswith('event:'):
                event = line[len('event:'):].strip()
            elif line.startswith('data:'):
                data_lines.append(line[len('data:'):].lstrip())
        events.append((event, '\n'.join(data_lines)))
    return events