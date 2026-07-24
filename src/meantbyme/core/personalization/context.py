from datetime import datetime

from meantbyme.core.domain import MemoryItem, VerificationLevel


def compose_situation(
    context_memories: list[MemoryItem],
    *,
    now: datetime,
    override: str | None,
) -> str | None:
    if override:
        return override

    rendered = []
    for memory in context_memories:
        if not memory.text:
            continue
        item = memory.text.strip()
        if memory.verification_level is VerificationLevel.SILVER:
            item = f"{item} (caregiver-provided)"
        rendered.append(item)
    if not rendered:
        return None

    prefix = f"Today is {now:%A %Y-%m-%d}. Known patient context: "
    return prefix + "; ".join(rendered)
