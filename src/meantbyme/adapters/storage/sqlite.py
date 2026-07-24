from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from meantbyme.core.domain import (
    ExpressionReceipt,
    ExpressionSession,
    MemoryItem,
    MemoryType,
    MemoryWriteResult,
    RuntimeEvent,
    VerificationLevel,
)
from meantbyme.core.personalization.text import normalize, tokenize


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    memory_type TEXT NOT NULL,
    verification_level TEXT NOT NULL
        CHECK (verification_level IN ('gold','silver','unverified')),
    text TEXT,
    language TEXT,
    context TEXT,
    usage_count INTEGER NOT NULL DEFAULT 0,
    last_used_at TEXT,
    confirmation_session_id TEXT,
    CHECK (verification_level != 'gold' OR confirmation_session_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_mem_patient ON memories(patient_id);

CREATE TABLE IF NOT EXISTS rejected_candidates (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    text TEXT NOT NULL,
    session_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_writes (
    idempotency_key TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    memory_id TEXT NOT NULL REFERENCES memories(id),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS authorizations (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    session_id TEXT NOT NULL,
    voice_profile_id TEXT,
    scope TEXT NOT NULL CHECK (scope = 'this_expression'),
    revoked INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    stage TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    event_type TEXT NOT NULL,
    payload TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS receipts (
    receipt_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    patient_id TEXT NOT NULL REFERENCES patients(patient_id),
    body TEXT NOT NULL,
    signature TEXT,
    created_at TEXT NOT NULL
);
"""


class SQLiteRepository:
    def __init__(self, database: str | Path = ":memory:") -> None:
        self._connection = sqlite3.connect(str(database))
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.executescript(SCHEMA)
        self._migrate_memories_columns()

    def close(self) -> None:
        self._connection.close()

    def add_patient(self, patient_id: str, display_name: str) -> None:
        self._connection.execute(
            """
            INSERT INTO patients(patient_id, display_name) VALUES (?, ?)
            ON CONFLICT(patient_id) DO UPDATE SET display_name=excluded.display_name
            """,
            (patient_id, display_name),
        )
        self._connection.commit()

    def create_session(
        self, patient_id: str, session: ExpressionSession
    ) -> None:
        self._require_patient_match(patient_id, session.patient_id)
        self._connection.execute(
            """
            INSERT INTO sessions(session_id, patient_id, stage, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                session.session_id,
                patient_id,
                session.stage.value,
                datetime.now(UTC).isoformat(),
            ),
        )
        self._connection.commit()

    def update_session(
        self, patient_id: str, session: ExpressionSession
    ) -> None:
        self._require_patient_match(patient_id, session.patient_id)
        cursor = self._connection.execute(
            """
            UPDATE sessions SET stage=?
            WHERE session_id=? AND patient_id=?
            """,
            (session.stage.value, session.session_id, patient_id),
        )
        if cursor.rowcount != 1:
            raise LookupError("Patient-scoped session not found")
        self._connection.commit()

    def append_event(self, patient_id: str, event: RuntimeEvent) -> None:
        self._require_patient_match(patient_id, event.patient_id)
        self._require_scoped_session(patient_id, event.session_id)
        self._connection.execute(
            """
            INSERT INTO events(
                event_id, session_id, patient_id, event_type, payload, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                event.session_id,
                patient_id,
                event.event_type.value,
                json.dumps(event.payload, sort_keys=True),
                event.timestamp.isoformat(),
            ),
        )
        self._connection.commit()

    def seed_verified_memory(
        self, patient_id: str, memory: MemoryItem
    ) -> None:
        if memory.memory_type is MemoryType.CONTEXT:
            self.add_context_memory(patient_id, memory)
            return
        self._require_patient_match(patient_id, memory.patient_id)
        self._validate_gold(memory)
        existing = self._connection.execute(
            "SELECT patient_id FROM memories WHERE id=?",
            (memory.id,),
        ).fetchone()
        if existing:
            self._require_patient_match(patient_id, existing["patient_id"])
        self._connection.execute(
            """
            INSERT INTO memories(
                id, patient_id, memory_type, verification_level, text,
                language, context, usage_count, last_used_at,
                confirmation_session_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                text=excluded.text,
                language=excluded.language,
                context=excluded.context,
                usage_count=excluded.usage_count,
                last_used_at=excluded.last_used_at
            """,
            (
                memory.id,
                patient_id,
                memory.memory_type.value,
                memory.verification_level.value,
                memory.text,
                memory.language,
                json.dumps(memory.context, sort_keys=True),
                memory.usage_count,
                (
                    memory.last_used_at.isoformat()
                    if memory.last_used_at
                    else None
                ),
                memory.confirmation_session_id,
            ),
        )
        self._connection.commit()

    def search_verified_memories(
        self, patient_id: str, fragments: list[str]
    ) -> list[MemoryItem]:
        rows = self._connection.execute(
            """
            SELECT * FROM memories
            WHERE patient_id=?
              AND memory_type='semantic'
              AND verification_level IN ('gold','silver')
            ORDER BY usage_count DESC, last_used_at DESC
            """,
            (patient_id,),
        ).fetchall()
        query_tokens = set(tokenize(" ".join(fragments)))
        memories = []
        for row in rows:
            text_tokens = set(tokenize(row["text"] or ""))
            if query_tokens and query_tokens.issubset(text_tokens):
                similarity = "high"
            elif query_tokens and query_tokens.intersection(text_tokens):
                similarity = "medium"
            else:
                similarity = "low"
            memories.append(self._row_to_memory(row, similarity))
        return memories

    def add_context_memory(
        self, patient_id: str, memory: MemoryItem
    ) -> None:
        self._require_patient_match(patient_id, memory.patient_id)
        if memory.memory_type is not MemoryType.CONTEXT:
            raise ValueError("Context repository requires memory_type=context")
        if memory.verification_level not in {
            VerificationLevel.GOLD,
            VerificationLevel.SILVER,
        }:
            raise ValueError("Context memory must be Gold or Silver")
        if not memory.text or not memory.text.strip():
            raise ValueError("Context memory requires human-readable text")

        source = str(memory.context.get("source", "")).casefold()
        if (
            source == "caregiver"
            and memory.verification_level is not VerificationLevel.SILVER
        ):
            raise ValueError("Caregiver context must remain Silver")
        if (
            memory.verification_level is VerificationLevel.GOLD
            and source not in {"patient", "seed"}
        ):
            raise ValueError(
                "Only patient-confirmed or seed context can enter Gold memory"
            )
        self._validate_gold(memory)

        existing = self._connection.execute(
            """
            SELECT patient_id, memory_type, verification_level FROM memories
            WHERE id=?
            """,
            (memory.id,),
        ).fetchone()
        if existing:
            self._require_patient_match(patient_id, existing["patient_id"])
            if existing["memory_type"] != MemoryType.CONTEXT.value:
                raise ValueError("Context memory id collides with another type")
            if existing["verification_level"] != memory.verification_level.value:
                raise ValueError(
                    "Context verification level cannot change automatically"
                )

        self._connection.execute(
            """
            INSERT INTO memories(
                id, patient_id, memory_type, verification_level, text,
                language, context, usage_count, last_used_at,
                confirmation_session_id
            ) VALUES (?, ?, 'context', ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                text=excluded.text,
                language=excluded.language,
                context=excluded.context,
                usage_count=excluded.usage_count,
                last_used_at=excluded.last_used_at
            """,
            (
                memory.id,
                patient_id,
                memory.verification_level.value,
                memory.text,
                memory.language,
                json.dumps(memory.context, sort_keys=True),
                memory.usage_count,
                (
                    memory.last_used_at.isoformat()
                    if memory.last_used_at
                    else None
                ),
                memory.confirmation_session_id,
            ),
        )
        self._connection.commit()

    def search_context_memories(
        self, patient_id: str
    ) -> list[MemoryItem]:
        rows = self._connection.execute(
            """
            SELECT * FROM memories
            WHERE patient_id=?
              AND memory_type='context'
              AND verification_level IN ('gold','silver')
            ORDER BY
              CASE verification_level WHEN 'gold' THEN 0 ELSE 1 END,
              last_used_at DESC
            """,
            (patient_id,),
        ).fetchall()
        return [self._row_to_memory(row) for row in rows]

    def record_rejected_candidate(
        self, patient_id: str, candidate_id: str, text: str, session_id: str
    ) -> None:
        self._require_scoped_session(patient_id, session_id)
        rejection_id = f"{session_id}:{candidate_id}"
        self._connection.execute(
            """
            INSERT OR IGNORE INTO rejected_candidates(
                id, patient_id, text, session_id
            ) VALUES (?, ?, ?, ?)
            """,
            (rejection_id, patient_id, text, session_id),
        )
        self._connection.commit()

    def write_verified_memory(
        self,
        patient_id: str,
        memory: MemoryItem,
        idempotency_key: str,
    ) -> MemoryWriteResult:
        self._require_patient_match(patient_id, memory.patient_id)
        if memory.memory_type is MemoryType.CONTEXT:
            raise ValueError(
                "Context memory cannot use semantic verified writeback"
            )
        self._validate_gold(memory)
        existing_write = self._connection.execute(
            """
            SELECT m.* FROM memory_writes w
            JOIN memories m ON m.id=w.memory_id
            WHERE w.idempotency_key=? AND w.patient_id=? AND m.patient_id=?
            """,
            (idempotency_key, patient_id, patient_id),
        ).fetchone()
        if existing_write:
            return MemoryWriteResult(
                memory=self._row_to_memory(existing_write),
                written=False,
                idempotency_key=idempotency_key,
            )

        now = datetime.now(UTC).isoformat()
        scoped_rows = self._connection.execute(
            """
            SELECT * FROM memories
            WHERE patient_id=? AND memory_type=? AND verification_level='gold'
            """,
            (patient_id, memory.memory_type.value),
        ).fetchall()
        matching = next(
            (
                row
                for row in scoped_rows
                if normalize(row["text"] or "") == normalize(memory.text or "")
            ),
            None,
        )

        try:
            self._connection.execute("BEGIN")
            if matching:
                memory_id = matching["id"]
                self._connection.execute(
                    """
                    UPDATE memories
                    SET usage_count=usage_count + 1, last_used_at=?
                    WHERE id=? AND patient_id=?
                    """,
                    (now, memory_id, patient_id),
                )
            else:
                memory_id = memory.id
                self._connection.execute(
                    """
                    INSERT INTO memories(
                        id, patient_id, memory_type, verification_level, text,
                        language, context, usage_count, last_used_at,
                        confirmation_session_id
                    ) VALUES (?, ?, ?, 'gold', ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        memory_id,
                        patient_id,
                        memory.memory_type.value,
                        memory.text,
                        memory.language,
                        json.dumps(memory.context, sort_keys=True),
                        max(memory.usage_count, 1),
                        now,
                        memory.confirmation_session_id,
                    ),
                )
            self._connection.execute(
                """
                INSERT INTO memory_writes(
                    idempotency_key, patient_id, memory_id, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (idempotency_key, patient_id, memory_id, now),
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

        written_row = self._connection.execute(
            "SELECT * FROM memories WHERE id=? AND patient_id=?",
            (memory_id, patient_id),
        ).fetchone()
        if written_row is None:
            raise RuntimeError("Verified memory write did not persist")
        return MemoryWriteResult(
            memory=self._row_to_memory(written_row),
            written=True,
            idempotency_key=idempotency_key,
        )

    def store_receipt(
        self, patient_id: str, receipt: ExpressionReceipt
    ) -> None:
        self._require_patient_match(patient_id, receipt.patient_id)
        self._require_scoped_session(patient_id, receipt.session_id)
        self._connection.execute(
            """
            INSERT OR IGNORE INTO receipts(
                receipt_id, session_id, patient_id, body, signature, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                receipt.receipt_id,
                receipt.session_id,
                patient_id,
                receipt.model_dump_json(),
                receipt.signature,
                receipt.created_at.isoformat(),
            ),
        )
        self._connection.commit()

    def grant_voice_consent(
        self,
        patient_id: str,
        authorization_id: str,
        consent_session_id: str,
        voice_profile_id: str,
    ) -> None:
        existing = self._connection.execute(
            "SELECT patient_id FROM authorizations WHERE id=?",
            (authorization_id,),
        ).fetchone()
        if existing:
            self._require_patient_match(patient_id, existing["patient_id"])
        self._connection.execute(
            """
            INSERT INTO authorizations(
                id, patient_id, session_id, voice_profile_id, scope, revoked
            ) VALUES (?, ?, ?, ?, 'this_expression', 0)
            ON CONFLICT(id) DO UPDATE SET revoked=0
            """,
            (
                authorization_id,
                patient_id,
                consent_session_id,
                voice_profile_id,
            ),
        )
        self._connection.commit()

    def revoke_voice_consent(
        self, patient_id: str, voice_profile_id: str
    ) -> None:
        self._connection.execute(
            """
            UPDATE authorizations SET revoked=1
            WHERE patient_id=? AND voice_profile_id=?
            """,
            (patient_id, voice_profile_id),
        )
        self._connection.commit()

    def has_active_voice_consent(
        self, patient_id: str, voice_profile_id: str
    ) -> bool:
        row = self._connection.execute(
            """
            SELECT 1 FROM authorizations
            WHERE patient_id=? AND voice_profile_id=?
              AND scope='this_expression' AND revoked=0
            LIMIT 1
            """,
            (patient_id, voice_profile_id),
        ).fetchone()
        return row is not None

    def list_events(
        self, patient_id: str, session_id: str
    ) -> list[sqlite3.Row]:
        return self._connection.execute(
            """
            SELECT * FROM events
            WHERE patient_id=? AND session_id=?
            ORDER BY created_at, rowid
            """,
            (patient_id, session_id),
        ).fetchall()

    def count_memories(self, patient_id: str) -> int:
        return int(
            self._connection.execute(
                "SELECT COUNT(*) FROM memories WHERE patient_id=?",
                (patient_id,),
            ).fetchone()[0]
        )

    def count_rejections(self, patient_id: str) -> int:
        return int(
            self._connection.execute(
                "SELECT COUNT(*) FROM rejected_candidates WHERE patient_id=?",
                (patient_id,),
            ).fetchone()[0]
        )

    def count_memory_writes(self, patient_id: str) -> int:
        return int(
            self._connection.execute(
                "SELECT COUNT(*) FROM memory_writes WHERE patient_id=?",
                (patient_id,),
            ).fetchone()[0]
        )

    def get_receipt(
        self, patient_id: str, session_id: str
    ) -> ExpressionReceipt | None:
        row = self._connection.execute(
            """
            SELECT body FROM receipts
            WHERE patient_id=? AND session_id=?
            """,
            (patient_id, session_id),
        ).fetchone()
        return ExpressionReceipt.model_validate_json(row["body"]) if row else None

    @staticmethod
    def _require_patient_match(expected: str, actual: str) -> None:
        if expected != actual:
            raise PermissionError("Cross-patient operation blocked")

    def _migrate_memories_columns(self) -> None:
        columns = {
            row["name"]
            for row in self._connection.execute(
                "PRAGMA table_info(memories)"
            ).fetchall()
        }
        if "language" not in columns:
            self._connection.execute(
                "ALTER TABLE memories ADD COLUMN language TEXT"
            )
        if "context" not in columns:
            self._connection.execute(
                "ALTER TABLE memories ADD COLUMN context TEXT"
            )
        self._connection.commit()

    def _require_scoped_session(
        self, patient_id: str, session_id: str
    ) -> None:
        row = self._connection.execute(
            """
            SELECT 1 FROM sessions
            WHERE session_id=? AND patient_id=?
            """,
            (session_id, patient_id),
        ).fetchone()
        if row is None:
            raise PermissionError("Cross-patient session operation blocked")

    @staticmethod
    def _validate_gold(memory: MemoryItem) -> None:
        if (
            memory.verification_level is VerificationLevel.GOLD
            and not memory.confirmation_session_id
        ):
            raise ValueError("Gold memory requires confirmation_session_id")

    @staticmethod
    def _row_to_memory(
        row: sqlite3.Row, similarity: str | None = None
    ) -> MemoryItem:
        return MemoryItem(
            id=row["id"],
            patient_id=row["patient_id"],
            memory_type=MemoryType(row["memory_type"]),
            verification_level=VerificationLevel(row["verification_level"]),
            text=row["text"],
            language=row["language"],
            context=json.loads(row["context"]) if row["context"] else {},
            usage_count=row["usage_count"],
            last_used_at=(
                datetime.fromisoformat(row["last_used_at"])
                if row["last_used_at"]
                else None
            ),
            similarity_band=similarity,
            confirmation_session_id=row["confirmation_session_id"],
        )
