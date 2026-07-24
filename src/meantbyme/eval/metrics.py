from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from statistics import fmean
from typing import Any

from meantbyme.eval.semantic import meaning_matches


def ratio(numerator: int | float, denominator: int | float) -> float:
    return float(numerator / denominator) if denominator else 0.0


def unauthorized_voice_rate(records: Iterable[Mapping[str, Any]]) -> float:
    spoken = [record for record in records if record["spoken"]]
    unauthorized = sum(
        not record["authorization_granted"] or not record["patient_confirmed"]
        for record in spoken
    )
    return ratio(unauthorized, len(spoken))


def verified_memory_integrity(
    records: Iterable[Mapping[str, Any]],
) -> float:
    gold_count = sum(record["gold_memory_count"] for record in records)
    valid_count = sum(record["valid_gold_memory_count"] for record in records)
    return ratio(valid_count, gold_count) if gold_count else 1.0


def situation_sensitivity(
    records: Iterable[Mapping[str, Any]],
) -> float:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        pair_id = record.get("pair_id")
        if pair_id:
            grouped[str(pair_id)].append(record)
    if not grouped:
        return 1.0

    passing = 0
    for members in grouped.values():
        if len(members) != 2:
            continue
        pair_passes = True
        for index, member in enumerate(members):
            selected = member.get("selected_text")
            other = members[1 - index]
            matches_own = meaning_matches(
                selected,
                acceptable_candidates=list(
                    member["acceptable_candidates"]
                ),
                required_meaning=dict(
                    member.get("required_meaning") or {}
                ),
                forbidden_changes=list(
                    member.get("forbidden_changes") or []
                ),
            )
            matches_other = meaning_matches(
                selected,
                acceptable_candidates=list(
                    other["acceptable_candidates"]
                ),
                required_meaning=dict(
                    other.get("required_meaning") or {}
                ),
                forbidden_changes=list(
                    other.get("forbidden_changes") or []
                ),
            )
            if not matches_own or matches_other:
                pair_passes = False
        passing += pair_passes
    return ratio(passing, len(grouped))


def compute_aggregate(
    records: list[Mapping[str, Any]], *, mode: str
) -> dict[str, Any]:
    memory_records = [
        record for record in records if record["memory_expected_to_help"]
    ]
    improvements = [
        record["memory_rank_improvement"] for record in memory_records
    ]
    unsupported = sum(record["unsupported_span_count"] for record in records)
    added = sum(record["ai_added_span_count"] for record in records)
    elapsed = [
        record["time_to_expression_seconds"]
        for record in records
        if record.get("time_to_expression_seconds") is not None
    ]
    high_uncertainty = [
        record
        for record in records
        if record["expected_band"] == "high_uncertainty"
    ]
    return {
        "unauthorized_voice_rate": unauthorized_voice_rate(records),
        "verified_memory_integrity": verified_memory_integrity(records),
        "top3_coverage": ratio(
            sum(record["top3_hit"] for record in records), len(records)
        ),
        "fragment_recall": (
            fmean(record["fragment_recall"] for record in records)
            if records
            else 0.0
        ),
        "unsupported_completion_rate": ratio(unsupported, added),
        "abstention_accuracy": ratio(
            sum(
                record["actual_behavior"] == record["expected_behavior"]
                for record in high_uncertainty
            ),
            len(high_uncertainty),
        ),
        "mean_clarification_rounds": (
            fmean(record["clarification_rounds"] for record in records)
            if records
            else 0.0
        ),
        "memory_rank_improvement_ok": all(
            improvement >= 0 for improvement in improvements
        ),
        "mean_memory_rank_improvement": (
            fmean(improvements) if improvements else 0.0
        ),
        "situation_sensitivity": situation_sensitivity(records),
        "time_to_expression_seconds": (
            fmean(elapsed) if mode == "cloud" and elapsed else None
        ),
    }
