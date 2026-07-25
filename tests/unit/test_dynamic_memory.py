from meantbyme.adapters.storage import SQLiteRepository
from meantbyme.core.domain import MemoryItem, MemoryType, VerificationLevel
from meantbyme.core.personalization import (
    cosine_similarity,
    embed_expression,
    update_mapping_confidence,
)


def test_feedback_updates_are_bounded_and_penalize_errors_more() -> None:
    confidence = update_mapping_confidence(None, confirmed=True)
    assert confidence == 0.65
    assert update_mapping_confidence(confidence, confirmed=True) == 0.75
    assert update_mapping_confidence(confidence, confirmed=False) == 0.45
    assert update_mapping_confidence(0.95, confirmed=True) == 0.98
    assert update_mapping_confidence(0.10, confirmed=False) == 0.05


def test_expression_embedding_is_deterministic() -> None:
    first = embed_expression("I want the blue cup")
    second = embed_expression("I want the blue cup")
    unrelated = embed_expression("Please close the window")

    assert first == second
    assert cosine_similarity(first, second) > 0.999
    assert cosine_similarity(first, unrelated) < 1.0


def test_vector_mapping_is_retrieved_for_similar_user_expression() -> None:
    repository = SQLiteRepository(":memory:")
    repository.add_patient("patient-1", "Test Patient")
    repository.seed_verified_memory(
        "patient-1",
        MemoryItem(
            id="mapping-1",
            patient_id="patient-1",
            memory_type=MemoryType.SEMANTIC,
            verification_level=VerificationLevel.GOLD,
            text="I would like the blue cup.",
            language="en",
            context={
                "kind": "expression_mapping",
                "input_text": "blue cup please",
                "embedding": embed_expression("blue cup please"),
                "confidence": 0.75,
            },
            confirmation_session_id="session-1",
        ),
    )

    retrieved = repository.search_verified_memories(
        "patient-1", ["blue", "cup"]
    )
    repository.close()

    assert [memory.id for memory in retrieved] == ["mapping-1"]
    assert retrieved[0].similarity_band == "high"


def test_low_confidence_mapping_never_enters_retrieval() -> None:
    repository = SQLiteRepository(":memory:")
    repository.add_patient("patient-1", "Test Patient")
    repository.seed_verified_memory(
        "patient-1",
        MemoryItem(
            id="mapping-low",
            patient_id="patient-1",
            memory_type=MemoryType.SEMANTIC,
            verification_level=VerificationLevel.GOLD,
            text="Wrong interpretation",
            context={
                "kind": "expression_mapping",
                "embedding": embed_expression("blue cup please"),
                "confidence": 0.35,
            },
            confirmation_session_id="session-1",
        ),
    )

    retrieved = repository.search_verified_memories(
        "patient-1", ["blue", "cup"]
    )
    repository.close()

    assert retrieved == []
