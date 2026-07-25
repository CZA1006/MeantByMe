from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol


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


class SQLiteProfileStore:
    """Deterministic local/mock profile store."""

    def __init__(self, database_path: Path) -> None:
        database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            str(database_path), check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
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
        return [
            StoredProfile(
                profile_ref=row["profile_ref"],
                markdown=row["markdown"],
                source=row["source"],
            )
            for row in rows
        ]

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
        if row is None:
            return None
        return StoredProfile(
            profile_ref=row["profile_ref"],
            markdown=row["markdown"],
            source=row["source"],
        )

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
                else:
                    cursor.execute("SELECT 1 FROM user_profiles LIMIT 1")

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
        return [
            StoredProfile(
                profile_ref=row["profile_ref"],
                markdown=row["markdown"],
                source=row["source"],
            )
            for row in rows
        ]

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
        if row is None:
            return None
        return StoredProfile(
            profile_ref=row["profile_ref"],
            markdown=row["markdown"],
            source=row["source"],
        )

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

    def close(self) -> None:
        # Connections are intentionally short-lived and closed per operation.
        return
