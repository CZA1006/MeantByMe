import json
from pathlib import Path

from meantbyme.adapters.http import GatewayHttpClient
from meantbyme.eval.__main__ import main
from meantbyme.eval.models import RiskLevel, load_dataset
from meantbyme.eval.runner import DISCLAIMER, run_evaluation


DATASET = Path("demo/eval/dataset.jsonl")


def test_full_dataset_mock_harness_passes_hard_gates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    report_path = tmp_path / "eval_report.json"

    def fail_network(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise AssertionError("mock evaluation attempted network access")

    monkeypatch.setattr(
        GatewayHttpClient,
        "request",
        fail_network,
    )

    result = run_evaluation(
        dataset=DATASET,
        mode="mock",
        report=report_path,
    )

    assert result["hard_gates_passed"] is True
    assert result["aggregate"]["unauthorized_voice_rate"] == 0.0
    assert result["aggregate"]["verified_memory_integrity"] == 1.0
    assert result["aggregate"]["situation_sensitivity"] == 1.0
    assert result["n_samples"] == len(load_dataset(DATASET))
    assert all(
        row["expected_band"] == row["actual_band"]
        for row in result["per_sample"]
    )
    assert all(
        row["expected_behavior"] == row["actual_behavior"]
        for row in result["per_sample"]
    )

    raw_report = report_path.read_text(encoding="utf-8")
    parsed = json.loads(raw_report)
    assert next(iter(parsed)) == "disclaimer"
    assert parsed["disclaimer"] == DISCLAIMER

    high_risk_texts = {
        sample.intended_expression
        for sample in load_dataset(DATASET)
        if sample.risk_level is RiskLevel.HIGH_RISK
        or "treatment" in sample.intended_expression.casefold()
    }
    assert all(text not in raw_report for text in high_risk_texts)
    high_risk_rows = [
        row
        for row in parsed["per_sample"]
        if row["high_risk_plaintext_redacted"]
    ]
    assert high_risk_rows
    treatment_row = next(
        row
        for row in high_risk_rows
        if row["sample_id"] == "en_tomorrow_treatment"
    )
    assert treatment_row["strict_confirmation"] is True
    assert all(
        candidate["text"] == "[REDACTED]"
        for row in high_risk_rows
        for candidate in row["candidates"]
    )


def test_cli_returns_zero_for_mock_dataset(tmp_path: Path) -> None:
    exit_code = main(
        [
            "--dataset",
            str(DATASET),
            "--mode",
            "mock",
            "--report",
            str(tmp_path / "cli_report.json"),
        ]
    )

    assert exit_code == 0
