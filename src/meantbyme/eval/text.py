from __future__ import annotations

import re
import unicodedata


_EVAL_TOKEN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]|[\w']+")
_PUNCTUATION = re.compile(r"[^\w\u3400-\u4dbf\u4e00-\u9fff']+", re.UNICODE)


def normalize_for_eval(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return _PUNCTUATION.sub("", normalized)


def eval_tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return _EVAL_TOKEN.findall(normalized)


def text_matches(text: str | None, acceptable: list[str]) -> bool:
    if text is None:
        return False
    normalized = normalize_for_eval(text)
    return normalized in {normalize_for_eval(item) for item in acceptable}
