from datetime import datetime

from meantbyme.core.domain import MemoryItem


def compose_situation(
    context_memories: list[MemoryItem],
    *,
    now: datetime,
    override: str | None,
) -> str | None:
    rendered = []
    for memory in context_memories:
        if not memory.text:
            continue
        item = memory.text.strip()
        rendered.append(item)
    if not rendered:
        return override

    profile = (
        f"Today is {now:%A %Y-%m-%d}. Current user profile: "
        + "; ".join(rendered)
    )
    if override:
        return f"Current situation: {override} {profile}"
    return profile
