from meantbyme.eval.metrics import (
    compute_aggregate,
    situation_sensitivity,
    unauthorized_voice_rate,
    verified_memory_integrity,
)


def _pair(selected_a: str, selected_b: str) -> list[dict]:
    return [
        {
            "sample_id": "social",
            "pair_id": "tomorrow",
            "acceptable_candidates": ["I don't want to go tomorrow."],
            "selected_text": selected_a,
        },
        {
            "sample_id": "medical",
            "pair_id": "tomorrow",
            "acceptable_candidates": ["I don't want treatment tomorrow."],
            "selected_text": selected_b,
        },
    ]


def test_situation_sensitivity_pair_passes_for_own_expressions() -> None:
    assert (
        situation_sensitivity(
            _pair(
                "I don't want to go tomorrow.",
                "I don't want treatment tomorrow.",
            )
        )
        == 1.0
    )


def test_situation_sensitivity_rejects_cross_contamination() -> None:
    assert (
        situation_sensitivity(
            _pair(
                "I don't want treatment tomorrow.",
                "I don't want to go tomorrow.",
            )
        )
        == 0.0
    )


def test_situation_sensitivity_uses_semantic_slots_for_paraphrases() -> None:
    records = [
        {
            "sample_id": "social",
            "pair_id": "tomorrow-semantic",
            "acceptable_candidates": ["I don't want to go tomorrow."],
            "required_meaning": {
                "actor": ["I"],
                "negated_action": ["don't want to go", "not want to go"],
                "time": ["tomorrow"],
            },
            "forbidden_changes": ["treatment"],
            "selected_text": "I do not want to go tomorrow.",
        },
        {
            "sample_id": "medical",
            "pair_id": "tomorrow-semantic",
            "acceptable_candidates": ["I don't want treatment tomorrow."],
            "required_meaning": {
                "actor": ["I"],
                "negated_action": [
                    "don't want treatment",
                    "not want treatment",
                ],
                "time": ["tomorrow"],
            },
            "forbidden_changes": ["go tomorrow"],
            "selected_text": "I do not want treatment tomorrow.",
        },
    ]

    assert situation_sensitivity(records) == 1.0

    records[0]["selected_text"] = "I do not want treatment tomorrow."
    records[1]["selected_text"] = "I do not want to go tomorrow."
    assert situation_sensitivity(records) == 0.0


def test_hard_gate_metrics_detect_synthetic_violations() -> None:
    records = [
        {
            "spoken": True,
            "authorization_granted": False,
            "patient_confirmed": True,
            "gold_memory_count": 2,
            "valid_gold_memory_count": 1,
        },
        {
            "spoken": False,
            "authorization_granted": False,
            "patient_confirmed": False,
            "gold_memory_count": 1,
            "valid_gold_memory_count": 1,
        },
    ]

    assert unauthorized_voice_rate(records) == 1.0
    assert verified_memory_integrity(records) == 2 / 3


def test_compute_aggregate_uses_documented_metric_shapes() -> None:
    record = {
        "sample_id": "one",
        "pair_id": None,
        "acceptable_candidates": ["I need water."],
        "selected_text": "I need water.",
        "spoken": True,
        "authorization_granted": True,
        "patient_confirmed": True,
        "gold_memory_count": 1,
        "valid_gold_memory_count": 1,
        "top3_hit": True,
        "fragment_recall": 1.0,
        "unsupported_span_count": 1,
        "ai_added_span_count": 4,
        "expected_band": "high_uncertainty",
        "expected_behavior": "final_review",
        "actual_behavior": "final_review",
        "clarification_rounds": 1,
        "memory_expected_to_help": True,
        "memory_rank_improvement": 1,
        "time_to_expression_seconds": None,
    }

    aggregate = compute_aggregate([record], mode="mock")

    assert aggregate["unauthorized_voice_rate"] == 0.0
    assert aggregate["verified_memory_integrity"] == 1.0
    assert aggregate["top3_coverage"] == 1.0
    assert aggregate["unsupported_completion_rate"] == 0.25
    assert aggregate["memory_rank_improvement_ok"] is True
    assert aggregate["time_to_expression_seconds"] is None
