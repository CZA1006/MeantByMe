"""Deterministic semantic-slot matching for the eval harness.

Product principle: "不需要 100% 的字字对应，但意思不能错" — a completion is
correct when it carries the intended *meaning*, not when it reproduces an exact
string. This module scores that meaning deterministically:

  - ``required_meaning`` — the meaning slots that MUST be present (entity /
    action / object / negation …). Each slot lists human-maintained paraphrases;
    the slot is satisfied when any paraphrase's content words appear, in order,
    in the candidate. Negation is a first-class slot so "want to go" can never
    silently pass as "don't want to go".
  - ``forbidden_changes`` — surface content that only appears when the meaning
    has been changed wrongly (wrong object, antonym, wrong date). If any
    forbidden phrase matches, the candidate fails regardless of the slots.

This is an evaluation aid ONLY. It never runs inside the patient-facing runtime
and never gates patient confirmation, voice authorization, or a Gold-memory
write — those remain the patient's explicit act. An LLM judge, if ever added,
may only annotate eval output; it must never replace this deterministic check.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from meantbyme.eval.text import eval_tokens, text_matches

# Grammatical words may be omitted when comparing a human-maintained paraphrase.
# Pronouns, possessives, negation, and temporal terms deliberately remain because
# changing any of them can change who means what, whose object is referenced, or
# whether/when an action should happen.
_PHRASE_STOPWORDS = frozenset(
    {
        "to", "the", "a", "an", "is", "are", "am", "be", "of", "and", "or",
        "please", "do", "did", "does", "that", "this", "will",
    }
)
_CONTRACTIONS = {
    "i'm": ("i", "am"),
    "we're": ("we", "are"),
    "you're": ("you", "are"),
    "they're": ("they", "are"),
    "isn't": ("is", "not"),
    "aren't": ("are", "not"),
    "don't": ("do", "not"),
    "doesn't": ("does", "not"),
    "didn't": ("did", "not"),
    "can't": ("can", "not"),
    "cannot": ("can", "not"),
    "won't": ("will", "not"),
}


@dataclass(frozen=True)
class MeaningMatch:
    matched: bool
    basis: Literal["exact", "meaning_slots", "none"]
    matched_slots: tuple[str, ...] = ()
    missing_slots: tuple[str, ...] = ()
    forbidden_matches: tuple[str, ...] = ()


def _content_tokens(text: str) -> list[str]:
    expanded: list[str] = []
    for token in eval_tokens(text):
        expanded.extend(_CONTRACTIONS.get(token, (token,)))
    return [
        token for token in expanded if token not in _PHRASE_STOPWORDS
    ]


def _contains_sequence(needle: list[str], haystack: list[str]) -> bool:
    """Return whether a normalized token sequence appears contiguously."""
    if not needle:
        return False
    width = len(needle)
    return any(
        haystack[start : start + width] == needle
        for start in range(len(haystack) - width + 1)
    )


def phrase_present(phrase: str, candidate_tokens: list[str]) -> bool:
    return _contains_sequence(_content_tokens(phrase), candidate_tokens)


def evaluate_meaning(
    text: str | None,
    *,
    acceptable_candidates: list[str],
    required_meaning: dict[str, list[str]] | None = None,
    forbidden_changes: list[str] | None = None,
) -> MeaningMatch:
    """Evaluate an annotated expression without making a runtime decision.

    When a sample supplies ``required_meaning``, every slot is authoritative and
    must match one human-maintained alternative. Exact-string matching remains a
    backward-compatible fallback only for samples without semantic slots.
    """
    if text is None:
        return MeaningMatch(matched=False, basis="none")

    candidate_tokens = _content_tokens(text)
    forbidden = tuple(
        phrase
        for phrase in forbidden_changes or []
        if phrase_present(phrase, candidate_tokens)
    )

    required = required_meaning or {}
    if not required:
        exact = not forbidden and text_matches(text, acceptable_candidates)
        return MeaningMatch(
            matched=exact,
            basis="exact" if exact else "none",
            forbidden_matches=forbidden,
        )

    matched_slots: list[str] = []
    missing_slots: list[str] = []
    for slot, alternatives in required.items():
        if any(
            phrase_present(alternative, candidate_tokens)
            for alternative in alternatives
        ):
            matched_slots.append(slot)
        else:
            missing_slots.append(slot)
    matched = not missing_slots and not forbidden
    return MeaningMatch(
        matched=matched,
        basis="meaning_slots" if matched else "none",
        matched_slots=tuple(matched_slots),
        missing_slots=tuple(missing_slots),
        forbidden_matches=forbidden,
    )


def meaning_matches(
    text: str | None,
    *,
    acceptable_candidates: list[str],
    required_meaning: dict[str, list[str]] | None = None,
    forbidden_changes: list[str] | None = None,
) -> bool:
    return evaluate_meaning(
        text,
        acceptable_candidates=acceptable_candidates,
        required_meaning=required_meaning,
        forbidden_changes=forbidden_changes,
    ).matched
