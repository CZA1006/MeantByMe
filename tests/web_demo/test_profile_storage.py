from __future__ import annotations

import pytest

from services.web_demo import config as config_module
from services.web_demo.config import WebDemoSettings
from services.web_demo.profile_storage import (
    MySQLProfileStore,
    ProfileStorageError,
)


class FakeCursor:
    def __init__(self, queries: list[tuple[str, object]]) -> None:
        self.queries = queries
        self.last_sql = ""

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *_) -> None:
        return None

    def execute(self, sql: str, parameters=None) -> None:
        self.last_sql = " ".join(sql.split())
        self.queries.append((self.last_sql, parameters))

    def fetchone(self):
        if "COUNT(*)" in self.last_sql:
            return {"count": 2}
        if "WHERE profile_ref=%s" in self.last_sql:
            return {
                "profile_ref": "user-1",
                "markdown": "# profile",
                "source": "questionnaire",
            }
        return None

    def fetchall(self):
        return [
            {
                "profile_ref": "user-1",
                "markdown": "# profile",
                "source": "questionnaire",
            }
        ]


class FakeConnection:
    def __init__(self, queries: list[tuple[str, object]]) -> None:
        self.queries = queries
        self.closed = False

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.queries)

    def close(self) -> None:
        self.closed = True


def test_mysql_profile_store_uses_parameterized_queries(
    monkeypatch,
) -> None:
    queries: list[tuple[str, object]] = []

    def fake_connect(_self) -> FakeConnection:
        return FakeConnection(queries)

    monkeypatch.setattr(MySQLProfileStore, "_connect", fake_connect)
    store = MySQLProfileStore(
        host="mysql.internal",
        port=3306,
        user="app",
        password="secret",
        database="meantbyme",
    )

    listed = store.list_profiles()
    fetched = store.get_profile("user-1")
    count = store.count_profiles()
    store.insert_profile(
        profile_ref="user-2",
        profile_id="user-2",
        markdown="# second",
        source="uploaded",
    )

    assert listed[0].profile_ref == "user-1"
    assert fetched is not None and fetched.source == "questionnaire"
    assert count == 2
    get_query = next(
        item for item in queries if "WHERE profile_ref=%s" in item[0]
    )
    insert_query = next(
        item for item in queries if item[0].startswith("INSERT")
    )
    assert get_query[1] == ("user-1",)
    assert insert_query[1] == (
        "user-2",
        "user-2",
        "# second",
        "uploaded",
    )
    assert "secret" not in str(queries)


def test_mysql_startup_migrates_dynamic_memory_tables_idempotently(
    monkeypatch,
) -> None:
    queries: list[tuple[str, object]] = []

    def fake_connect(_self) -> FakeConnection:
        return FakeConnection(queries)

    monkeypatch.setattr(MySQLProfileStore, "_connect", fake_connect)
    MySQLProfileStore(
        host="mysql.internal",
        port=3306,
        user="app",
        password="secret",
        database="meantbyme",
        auto_create_schema=False,
    )

    statements = [sql for sql, _ in queries]
    assert "SELECT 1 FROM user_profiles LIMIT 1" in statements
    assert any(
        sql.startswith("CREATE TABLE IF NOT EXISTS expression_mappings")
        for sql in statements
    )
    assert any(
        sql.startswith(
            "CREATE TABLE IF NOT EXISTS expression_feedback_events"
        )
        for sql in statements
    )
    assert not any(
        sql.startswith("CREATE TABLE IF NOT EXISTS user_profiles")
        for sql in statements
    )


def test_mysql_profile_store_sanitizes_connection_failure(
    monkeypatch,
) -> None:
    def fail_connect(_self):
        raise RuntimeError("driver included sensitive connection detail")

    monkeypatch.setattr(MySQLProfileStore, "_connect", fail_connect)

    with pytest.raises(
        ProfileStorageError,
        match="profile database is unavailable",
    ) as caught:
        MySQLProfileStore(
            host="mysql.internal",
            port=3306,
            user="app",
            password="secret",
            database="meantbyme",
        )

    assert "sensitive connection detail" not in str(caught.value)


def test_settings_accept_zeabur_mysql_service_variables(monkeypatch) -> None:
    monkeypatch.setattr(config_module, "load_dotenv", lambda **_: None)
    for name in (
        "WEB_DEMO_MYSQL_HOST",
        "WEB_DEMO_MYSQL_PORT",
        "WEB_DEMO_MYSQL_USER",
        "WEB_DEMO_MYSQL_PASSWORD",
        "WEB_DEMO_MYSQL_DATABASE",
        "MYSQL_USER",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("WEB_DEMO_PROFILE_DB_BACKEND", "mysql")
    monkeypatch.setenv("MYSQL_HOST", "mysql.zeabur.internal")
    monkeypatch.setenv("MYSQL_PORT", "3306")
    monkeypatch.setenv("MYSQL_USERNAME", "profile-app")
    monkeypatch.setenv("MYSQL_PASSWORD", "test-only-password")
    monkeypatch.setenv("MYSQL_DATABASE", "meantbyme")

    settings = WebDemoSettings.from_env()

    assert settings.profile_database_backend == "mysql"
    assert settings.mysql_host == "mysql.zeabur.internal"
    assert settings.mysql_port == 3306
    assert settings.mysql_user == "profile-app"
    assert settings.mysql_password == "test-only-password"
    assert settings.mysql_database == "meantbyme"


def test_scoped_mysql_variables_override_zeabur_defaults(monkeypatch) -> None:
    monkeypatch.setattr(config_module, "load_dotenv", lambda **_: None)
    monkeypatch.setenv("WEB_DEMO_PROFILE_DB_BACKEND", "mysql")
    monkeypatch.setenv("WEB_DEMO_MYSQL_HOST", "scoped.internal")
    monkeypatch.setenv("WEB_DEMO_MYSQL_USER", "scoped-user")
    monkeypatch.setenv("WEB_DEMO_MYSQL_PASSWORD", "scoped-password")
    monkeypatch.setenv("MYSQL_HOST", "mysql.zeabur.internal")
    monkeypatch.setenv("MYSQL_USERNAME", "zeabur-user")
    monkeypatch.setenv("MYSQL_PASSWORD", "zeabur-password")

    settings = WebDemoSettings.from_env()

    assert settings.mysql_host == "scoped.internal"
    assert settings.mysql_user == "scoped-user"
    assert settings.mysql_password == "scoped-password"
