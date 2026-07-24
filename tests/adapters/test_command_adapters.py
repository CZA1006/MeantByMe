from meantbyme.adapters.command import (
    GatewayCommandIntentAdapter,
    MockCommandIntentAdapter,
)
from meantbyme.adapters.http import GatewayError
from meantbyme.core.domain import CommandIntent


class FailingGatewayClient:
    def post_json(self, path, payload):
        del path, payload
        raise GatewayError("offline")


def test_mock_command_understands_natural_chinese_equivalents() -> None:
    adapter = MockCommandIntentAdapter()

    assert adapter.interpret(
        "嗯", stage="final_review", language="zh"
    ).intent is CommandIntent.AFFIRM
    assert adapter.interpret(
        "不是这个意思", stage="final_review", language="zh"
    ).intent is CommandIntent.REJECT
    assert adapter.interpret(
        "再说一次", stage="final_review", language="zh"
    ).intent is CommandIntent.REPEAT
    assert adapter.interpret(
        "停一下", stage="final_review", language="zh"
    ).intent is CommandIntent.STOP


def test_cloud_command_failure_fails_closed_instead_of_affirming() -> None:
    result = GatewayCommandIntentAdapter(FailingGatewayClient()).interpret(
        "是",
        stage="final_review",
        language="zh",
    )

    assert result.intent is CommandIntent.UNKNOWN
    assert result.status == "failed"
