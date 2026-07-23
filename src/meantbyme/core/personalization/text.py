import hashlib
import re
import unicodedata


def normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = normalized.replace("\u2019", "'")
    normalized = re.sub(r"[^\w\s']", " ", normalized)
    return " ".join(normalized.split())


def tokenize(text: str) -> list[str]:
    return re.findall(r"\b[\w']+\b", normalize(text))


def expression_hash(final_text: str) -> str:
    return hashlib.sha256(normalize(final_text).encode("utf-8")).hexdigest()


def idempotency_key(
    session_id: str, final_text: str, update_type: str
) -> str:
    return f"{session_id}:{expression_hash(final_text)}:{update_type}"
