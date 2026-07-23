import sqlite3

import pytest

from meantbyme.adapters.storage.sqlite import SCHEMA
from meantbyme.core.domain import MemoryType


EXPECTED_TABLES = {
    "patients",
    "memories",
    "rejected_candidates",
    "memory_writes",
    "authorizations",
    "sessions",
    "events",
    "receipts",
}


def test_sqlite_schema_has_patient_scope_and_gold_check() -> None:
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA)
    tables = {
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert EXPECTED_TABLES.issubset(tables)
    for table in EXPECTED_TABLES:
        columns = {
            row[1]
            for row in connection.execute(f"PRAGMA table_info({table})")
        }
        assert "patient_id" in columns

    connection.execute(
        "INSERT INTO patients(patient_id, display_name) VALUES ('p1', 'P1')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            """
            INSERT INTO memories(
                id, patient_id, memory_type, verification_level, text,
                confirmation_session_id
            ) VALUES ('m1', 'p1', 'semantic', 'gold', 'guess', NULL)
            """
        )


def test_authorization_is_not_a_memory_type() -> None:
    assert {item.value for item in MemoryType} == {
        "semantic",
        "acoustic",
        "context",
        "language",
        "interaction",
    }
