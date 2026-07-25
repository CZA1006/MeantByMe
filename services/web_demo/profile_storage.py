from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from meantbyme.core.domain import ExpressionMapping
from meantbyme.core.personalization import (
    embed_expression,
    normalize,
    update_mapping_confidence,
)


ProfileSource = Literal["questionnaire", "uploaded"]


@dataclass(frozen=True)
class StoredProfile:
    profile_ref: str
    markdown: str
    source: ProfileSource


class ProfileStore(Protocol):
    def list_profiles(self) -> list[StoredProfile]: ...

    def get_profile(self, profile_ref: str) -> StoredProfile | None: ...

    def count_profiles(self) -> int: ...

    def insert_profile(
        self,
        *,
        profile_ref: str,
        profile_id: str,
        markdown: str,
        source: ProfileSource,
    ) -> None: ...

    def record_expression_feedback(
        self,
        *,
        profile_ref: str,
        profile_id: str,
        session_id: str,
        input_text: str,
        intent_text: str,
        language: str,
        confirmed: bool,
    ) -> ExpressionMapping: ...

    def list_expression_mappings(
        self,
        *,
        profile_ref: str,
        profile_id: str,
        min_confidence: float = 0.0,
    ) -> list[ExpressionMapping]: ...

    def close(self) -> None: ...


class ProfileStorageError(RuntimeError):
    """A sanitized profile database failure safe to map to HTTP 503."""


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_profiles (
    profile_ref TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL,
    markdown TEXT NOT NULL,
    source TEXT NOT NULL
        CHECK (source IN ('questionnaire', 'uploaded')),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_user_profiles_created
ON user_profiles(created_at);

CREATE TABLE IF NOT EXISTS expression_mappings (
    mapping_id TEXT PRIMARY KEY,
    profile_ref TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    input_text TEXT NOT NULL,
    intent_text TEXT NOT NULL,
    language TEXT NOT NULL,
    embedding TEXT NOT NULL,
    confidence REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    positive_count INTEGER NOT NULL DEFAULT 0,
    negative_count INTEGER NOT NULL DEFAULT 0,
    last_session_id TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_expression_mapping_scope
ON expression_mappings(profile_ref, profile_id, confidence, updated_at);

CREATE TABLE IF NOT EXISTS expression_feedback_events (
    feedback_key TEXT PRIMARY KEY,
    mapping_id TEXT NOT NULL REFERENCES expression_mappings(mapping_id),
    profile_ref TEXT NOT NULL,
    profile_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    confirmed INTEGER NOT NULL CHECK (confirmed IN (0, 1)),
    created_at TEXT NOT NULL
);
"""


MYSQL_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_profiles (
    profile_ref VARCHAR(160) NOT NULL PRIMARY KEY,
    profile_id VARCHAR(80) NOT NULL,
    markdown MEDIUMTEXT NOT NULL,
    source ENUM('questionnaire', 'uploaded') NOT NULL,
    created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    INDEX idx_user_profiles_created (created_at)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci
"""

MYSQL_EXPRESSION_MAPPING_SCHEMA = """
CREATE TABLE IF NOT EXISTS expression_mappings (
    mapping_id VARCHAR(160) NOT NULL PRIMARY KEY,
    profile_ref VARCHAR(160) NOT NULL,
    profile_id VARCHAR(80) NOT NULL,
    input_text TEXT NOT NULL,
    intent_text TEXT NOT NULL,
    language VARCHAR(12) NOT NULL,
    embedding TEXT NOT NULL,
    confidence DOUBLE NOT NULL,
    positive_count INT NOT NULL DEFAULT 0,
    negative_count INT NOT NULL DEFAULT 0,
    last_session_id VARCHAR(160) NOT NULL,
    updated_at DATETIME(6) NOT NULL,
    INDEX idx_expression_mapping_scope(
        profile_ref, profile_id, confidence, updated_at
    )
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci
"""

MYSQL_FEEDBACK_EVENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS expression_feedback_events (
    feedback_key VARCHAR(160) NOT NULL PRIMARY KEY,
    mapping_id VARCHAR(160) NOT NULL,
    profile_ref VARCHAR(160) NOT NULL,
    profile_id VARCHAR(80) NOT NULL,
    session_id VARCHAR(160) NOT NULL,
    confirmed TINYINT(1) NOT NULL,
    created_at DATETIME(6) NOT NULL,
    INDEX idx_expression_feedback_scope(profile_ref, profile_id, created_at)
) ENGINE=InnoDB
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci
"""


class SQLiteProfileStore:
    """Deterministic local/mock profile store."""

    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            str(database_path), check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.executescript(SQLITE_SCHEMA)
        self._lock = threading.RLock()

    def list_profiles(self) -> list[StoredProfile]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT profile_ref, markdown, source
                FROM user_profiles
                ORDER BY created_at, profile_ref
                """
            ).fetchall()
        return [_row_to_profile(row) for row in rows]

    def get_profile(self, profile_ref: str) -> StoredProfile | None:
        with self._lock:
            row = self._connection.execute(
                """
                SELECT profile_ref, markdown, source
                FROM user_profiles
                WHERE profile_ref=?
                """,
                (profile_ref,),
            ).fetchone()
        return _row_to_profile(row) if row is not None else None

    def count_profiles(self) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT COUNT(*) AS count FROM user_profiles"
            ).fetchone()
        return int(row["count"])

    def insert_profile(
        self,
        *,
        profile_ref: str,
        profile_id: str,
        markdown: str,
        source: ProfileSource,
    ) -> None:
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO user_profiles(
                    profile_ref, profile_id, markdown, source, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    profile_ref,
                    profile_id,
                    markdown,
                    source,
                    datetime.now(UTC).isoformat(),
                ),
            )
            self._connection.commit()

    def record_expression_feedback(
        self,
        *,
        profile_ref: str,
        profile_id: str,
        session_id: str,
        input_text: str,
        intent_text: str,
        language: str,
        confirmed: bool,
    ) -> ExpressionMapping:
        mapping_id, feedback_key = _mapping_keys(
            profile_ref=profile_ref,
            profile_id=profile_id,
            session_id=session_id,
            input_text=input_text,
            intent_text=intent_text,
            confirmed=confirmed,
        )
        now = datetime.now(UTC)
        with self._lock:
            existing = self._connection.execute(
                """
                SELECT * FROM expression_mappings
                WHERE mapping_id=? AND profile_ref=? AND profile_id=?
                """,
                (mapping_id, profile_ref, profile_id),
            ).fetchone()
            already_recorded = self._connection.execute(
                """
                SELECT 1 FROM expression_feedback_events
                WHERE feedback_key=? AND profile_ref=? AND profile_id=?
                """,
                (feedback_key, profile_ref, profile_id),
            ).fetchone()
            if already_recorded:
                if existing is None:
                    raise RuntimeError("Feedback exists without its mapping")
                return _row_to_mapping(existing)

            confidence = update_mapping_confidence(
                float(existing["confidence"]) if existing else None,
                confirmed=confirmed,
            )
            positive_count = (
                int(existing["positive_count"]) if existing else 0
            ) + int(confirmed)
            negative_count = (
                int(existing["negative_count"]) if existing else 0
            ) + int(not confirmed)
            embedding = embed_expression(input_text)
            try:
                self._connection.execute("BEGIN")
                self._connection.execute(
                    """
                    INSERT INTO expression_mappings(
                        mapping_id, profile_ref, profile_id, input_text,
                        intent_text, language, embedding, confidence,
                        positive_count, negative_count, last_session_id,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(mapping_id) DO UPDATE SET
                        embedding=excluded.embedding,
                        confidence=excluded.confidence,
                        positive_count=excluded.positive_count,
                        negative_count=excluded.negative_count,
                        last_session_id=excluded.last_session_id,
                        updated_at=excluded.updated_at
                    """,
                    (
                        mapping_id,
                        profile_ref,
                        profile_id,
                        input_text,
                        intent_text,
                        language,
                        json.dumps(embedding),
                        confidence,
                        positive_count,
                        negative_count,
                        session_id,
                        now.isoformat(),
                    ),
                )
                self._connection.execute(
                    """
                    INSERT INTO expression_feedback_events(
                        feedback_key, mapping_id, profile_ref, profile_id,
                        session_id, confirmed, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        feedback_key,
                        mapping_id,
                        profile_ref,
                        profile_id,
                        session_id,
                        int(confirmed),
                        now.isoformat(),
                    ),
                )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
            row = self._connection.execute(
                """
                SELECT * FROM expression_mappings
                WHERE mapping_id=? AND profile_ref=? AND profile_id=?
                """,
                (mapping_id, profile_ref, profile_id),
            ).fetchone()
        if row is None:
            raise RuntimeError("Expression mapping was not persisted")
        return _row_to_mapping(row)

    def list_expression_mappings(
        self,
        *,
        profile_ref: str,
        profile_id: str,
        min_confidence: float = 0.0,
    ) -> list[ExpressionMapping]:
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM expression_mappings
                WHERE profile_ref=? AND profile_id=? AND confidence>=?
                ORDER BY confidence DESC, updated_at DESC
                """,
                (profile_ref, profile_id, min_confidence),
            ).fetchall()
        return [_row_to_mapping(row) for row in rows]

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class MySQLProfileStore:
    """MySQL-backed profile store for the deployed service."""

    def __init__(
        self,
        *,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        connect_timeout_seconds: int = 5,
        ssl_ca: str | None = None,
        auto_create_schema: bool = False,
    ) -> None:
        if not host or not user or not database:
            raise ValueError(
                "MySQL profile storage requires host, user, and database"
            )
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._database = database
        self._connect_timeout_seconds = connect_timeout_seconds
        self._ssl_ca = ssl_ca
        self._auto_create_schema = auto_create_schema
        self._verify_schema()

    def _connect(self):
        try:
            import pymysql
            from pymysql.cursors import DictCursor
        except ImportError as error:
            raise RuntimeError(
                "PyMySQL is required for MySQL profile storage"
            ) from error
        kwargs = {
            "host": self._host,
            "port": self._port,
            "user": self._user,
            "password": self._password,
            "database": self._database,
            "charset": "utf8mb4",
            "cursorclass": DictCursor,
            "autocommit": True,
            "connect_timeout": self._connect_timeout_seconds,
            "read_timeout": 10,
            "write_timeout": 10,
        }
        if self._ssl_ca:
            kwargs["ssl"] = {"ca": self._ssl_ca}
        return pymysql.connect(**kwargs)

    @contextmanager
    def _connection_scope(self):
        connection = None
        try:
            connection = self._connect()
            yield connection
        except ProfileStorageError:
            raise
        except Exception as error:
            raise ProfileStorageError(
                "profile database is unavailable"
            ) from error
        finally:
            if connection is not None:
                connection.close()

    def _verify_schema(self) -> None:
        with self._connection_scope() as connection:
            with connection.cursor() as cursor:
                if self._auto_create_schema:
                    cursor.execute(MYSQL_SCHEMA)
                    cursor.execute(MYSQL_EXPRESSION_MAPPING_SCHEMA)
                    cursor.execute(MYSQL_FEEDBACK_EVENT_SCHEMA)
                else:
                    cursor.execute("SELECT 1 FROM user_profiles LIMIT 1")
                    cursor.execute(
                        "SELECT 1 FROM expression_mappings LIMIT 1"
                    )
                    cursor.execute(
                        "SELECT 1 FROM expression_feedback_events LIMIT 1"
                    )

    def list_profiles(self) -> list[StoredProfile]:
        with self._connection_scope() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT profile_ref, markdown, source
                    FROM user_profiles
                    ORDER BY created_at, profile_ref
                    """
                )
                rows = cursor.fetchall()
        return [_row_to_profile(row) for row in rows]

    def get_profile(self, profile_ref: str) -> StoredProfile | None:
        with self._connection_scope() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT profile_ref, markdown, source
                    FROM user_profiles
                    WHERE profile_ref=%s
                    """,
                    (profile_ref,),
                )
                row = cursor.fetchone()
        return _row_to_profile(row) if row is not None else None

    def count_profiles(self) -> int:
        with self._connection_scope() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) AS count FROM user_profiles"
                )
                row = cursor.fetchone()
        return int(row["count"])

    def insert_profile(
        self,
        *,
        profile_ref: str,
        profile_id: str,
        markdown: str,
        source: ProfileSource,
    ) -> None:
        with self._connection_scope() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO user_profiles(
                        profile_ref, profile_id, markdown, source
                    ) VALUES (%s, %s, %s, %s)
                    """,
                    (profile_ref, profile_id, markdown, source),
                )

    def record_expression_feedback(
        self,
        *,
        profile_ref: str,
        profile_id: str,
        session_id: str,
        input_text: str,
        intent_text: str,
        language: str,
        confirmed: bool,
    ) -> ExpressionMapping:
        mapping_id, feedback_key = _mapping_keys(
            profile_ref=profile_ref,
            profile_id=profile_id,
            session_id=session_id,
            input_text=input_text,
            intent_text=intent_text,
            confirmed=confirmed,
        )
        now = datetime.now(UTC)
        with self._connection_scope() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM expression_mappings
                    WHERE mapping_id=%s AND profile_ref=%s AND profile_id=%s
                    """,
                    (mapping_id, profile_ref, profile_id),
                )
                existing = cursor.fetchone()
                cursor.execute(
                    """
                    SELECT 1 FROM expression_feedback_events
                    WHERE feedback_key=%s AND profile_ref=%s AND profile_id=%s
                    """,
                    (feedback_key, profile_ref, profile_id),
                )
                if cursor.fetchone():
                    if existing is None:
                        raise RuntimeError(
                            "Feedback exists without its mapping"
                        )
                    return _row_to_mapping(existing)

                confidence = update_mapping_confidence(
                    float(existing["confidence"]) if existing else None,
                    confirmed=confirmed,
                )
                positive_count = (
                    int(existing["positive_count"]) if existing else 0
                ) + int(confirmed)
                negative_count = (
                    int(existing["negative_count"]) if existing else 0
                ) + int(not confirmed)
                cursor.execute(
                    """
                    INSERT INTO expression_mappings(
                        mapping_id, profile_ref, profile_id, input_text,
                        intent_text, language, embedding, confidence,
                        positive_count, negative_count, last_session_id,
                        updated_at
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON DUPLICATE KEY UPDATE
                        embedding=VALUES(embedding),
                        confidence=VALUES(confidence),
                        positive_count=VALUES(positive_count),
                        negative_count=VALUES(negative_count),
                        last_session_id=VALUES(last_session_id),
                        updated_at=VALUES(updated_at)
                    """,
                    (
                        mapping_id,
                        profile_ref,
                        profile_id,
                        input_text,
                        intent_text,
                        language,
                        json.dumps(embed_expression(input_text)),
                        confidence,
                        positive_count,
                        negative_count,
                        session_id,
                        now,
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO expression_feedback_events(
                        feedback_key, mapping_id, profile_ref, profile_id,
                        session_id, confirmed, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        feedback_key,
                        mapping_id,
                        profile_ref,
                        profile_id,
                        session_id,
                        int(confirmed),
                        now,
                    ),
                )
                cursor.execute(
                    """
                    SELECT * FROM expression_mappings
                    WHERE mapping_id=%s AND profile_ref=%s AND profile_id=%s
                    """,
                    (mapping_id, profile_ref, profile_id),
                )
                row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Expression mapping was not persisted")
        return _row_to_mapping(row)

    def list_expression_mappings(
        self,
        *,
        profile_ref: str,
        profile_id: str,
        min_confidence: float = 0.0,
    ) -> list[ExpressionMapping]:
        with self._connection_scope() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT * FROM expression_mappings
                    WHERE profile_ref=%s AND profile_id=%s
                      AND confidence>=%s
                    ORDER BY confidence DESC, updated_at DESC
                    """,
                    (profile_ref, profile_id, min_confidence),
                )
                rows = cursor.fetchall()
        return [_row_to_mapping(row) for row in rows]

    def close(self) -> None:
        return


def _mapping_keys(
    *,
    profile_ref: str,
    profile_id: str,
    session_id: str,
    input_text: str,
    intent_text: str,
    confirmed: bool,
) -> tuple[str, str]:
    normalized_pair = (
        f"{profile_ref}:{profile_id}:{normalize(input_text)}:"
        f"{normalize(intent_text)}"
    )
    mapping_id = (
        "mapping-"
        + hashlib.sha256(normalized_pair.encode("utf-8")).hexdigest()[:24]
    )
    feedback_source = (
        f"{session_id}:{mapping_id}:{'positive' if confirmed else 'negative'}"
    )
    feedback_key = hashlib.sha256(
        feedback_source.encode("utf-8")
    ).hexdigest()
    return mapping_id, feedback_key


def _row_to_profile(row) -> StoredProfile:
    return StoredProfile(
        profile_ref=row["profile_ref"],
        markdown=row["markdown"],
        source=row["source"],
    )


def _row_to_mapping(row) -> ExpressionMapping:
    return ExpressionMapping(
        mapping_id=row["mapping_id"],
        patient_id=row["profile_id"],
        profile_ref=row["profile_ref"],
        input_text=row["input_text"],
        intent_text=row["intent_text"],
        language=row["language"],
        embedding=json.loads(row["embedding"]),
        confidence=float(row["confidence"]),
        positive_count=int(row["positive_count"]),
        negative_count=int(row["negative_count"]),
        last_session_id=row["last_session_id"],
        updated_at=_as_datetime(row["updated_at"]),
    )


def _as_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=value.tzinfo or UTC)
    return datetime.fromisoformat(str(value))
