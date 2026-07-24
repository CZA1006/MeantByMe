import hashlib
import re
import unicodedata


_CJK_RANGES = (
    (ord("\u3400"), ord("\u4dbf")),
    (ord("\u4e00"), ord("\u9fff")),
    (ord("\uf900"), ord("\ufaff")),
)


def _is_cjk(char: str) -> bool:
    codepoint = ord(char)
    return any(start <= codepoint <= end for start, end in _CJK_RANGES)


def normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    normalized = normalized.replace("\u2019", "'")
    normalized = re.sub(r"[^\w\s']", " ", normalized)
    return " ".join(normalized.split())


def tokenize(text: str) -> list[str]:
    tokens: list[str] = []
    for word_run in re.findall(r"\b[\w']+\b", normalize(text)):
        latin_run: list[str] = []
        for char in word_run:
            if _is_cjk(char):
                if latin_run:
                    tokens.append("".join(latin_run))
                    latin_run = []
                tokens.append(char)
            else:
                latin_run.append(char)
        if latin_run:
            tokens.append("".join(latin_run))
    return tokens


def expression_hash(final_text: str) -> str:
    return hashlib.sha256(normalize(final_text).encode("utf-8")).hexdigest()


def idempotency_key(
    session_id: str, final_text: str, update_type: str
) -> str:
    return f"{session_id}:{expression_hash(final_text)}:{update_type}"
