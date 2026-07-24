from __future__ import annotations

import re

from meantbyme.core.domain import CommandIntent, CommandInterpretation


class MockCommandIntentAdapter:
    """Deterministic offline fixture; cloud mode uses the model gateway."""

    _PHRASES = {
        CommandIntent.STOP: (
            "停止",
            "停",
            "停一下",
            "不要说了",
            "先不说了",
            "结束",
            "stop",
            "cancel",
        ),
        CommandIntent.REJECT: (
            "不对",
            "不是",
            "不是这个",
            "不是这个意思",
            "换一个",
            "no",
            "wrong",
        ),
        CommandIntent.REPEAT: (
            "再来",
            "再说一次",
            "再来一遍",
            "没听清",
            "repeat",
            "again",
        ),
        CommandIntent.BACK: ("返回", "回去", "上一步", "back"),
        CommandIntent.AFFIRM: (
            "嗯",
            "是",
            "对",
            "没错",
            "就是这个",
            "可以",
            "yes",
            "correct",
        ),
    }

    def interpret(
        self, transcript: str, *, stage: str, language: str | None
    ) -> CommandInterpretation:
        del stage, language
        normalized = re.sub(r"[\s，。！？、,.!?]+", "", transcript).casefold()
        for intent, phrases in self._PHRASES.items():
            if any(normalized == phrase.casefold() for phrase in phrases):
                return CommandInterpretation(
                    provider="mock_command_intent",
                    transcript=transcript,
                    intent=intent,
                )
        return CommandInterpretation(
            provider="mock_command_intent",
            transcript=transcript,
            intent=CommandIntent.UNKNOWN,
        )
