from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _first_non_empty_env(
    *names: str,
    default: str = "",
    strip_value: bool = True,
) -> str:
    for name in names:
        value = os.getenv(name)
        if value is not None and value.strip():
            return value.strip() if strip_value else value
    return default


@dataclass(frozen=True)
class WebDemoSettings:
    mode: str = "mock"
    demo_token: str = field(default="", repr=False)
    gateway_url: str = "http://127.0.0.1:8000"
    gateway_token: str = field(default="", repr=False)
    gateway_timeout_seconds: float = 35.0
    gateway_max_attempts: int = 2
    voice_profile_id: str = "cixingnansheng"
    audio_store_root: Path = Path(tempfile.gettempdir()) / "meantbyme-web-demo"
    max_audio_bytes: int = 16 * 1024 * 1024
    max_audio_seconds: float = 20.0
    max_sessions: int = 100
    max_profile_bytes: int = 64 * 1024
    max_uploaded_profiles: int = 500
    profile_database_backend: str = "sqlite"
    profile_database_path: Path | None = None
    mysql_host: str = ""
    mysql_port: int = 3306
    mysql_user: str = ""
    mysql_password: str = field(default="", repr=False)
    mysql_database: str = "meantbyme"
    mysql_connect_timeout_seconds: int = 5
    mysql_ssl_ca: str | None = None
    mysql_auto_create_schema: bool = False
    lin_yue_scripted_demo_enabled: bool = True
    lin_yue_scripted_demo_delay_seconds: float = 3.5

    @classmethod
    def from_env(cls) -> "WebDemoSettings":
        load_dotenv(override=False)
        mode = os.getenv("WEB_DEMO_MODE", "mock").strip().lower()
        if mode not in {"mock", "cloud"}:
            raise ValueError("WEB_DEMO_MODE must be mock or cloud")
        audio_store_root = Path(
            os.getenv(
                "WEB_DEMO_AUDIO_DIR",
                str(Path(tempfile.gettempdir()) / "meantbyme-web-demo"),
            )
        )
        database_value = os.getenv("WEB_DEMO_DATABASE_PATH", "").strip()
        mysql_host = _first_non_empty_env(
            "WEB_DEMO_MYSQL_HOST",
            "MYSQL_HOST",
        )
        database_backend = os.getenv(
            "WEB_DEMO_PROFILE_DB_BACKEND",
            "mysql" if mysql_host else "sqlite",
        ).strip().lower()
        if database_backend not in {"sqlite", "mysql"}:
            raise ValueError(
                "WEB_DEMO_PROFILE_DB_BACKEND must be sqlite or mysql"
            )
        return cls(
            mode=mode,
            demo_token=os.getenv("WEB_DEMO_TOKEN", ""),
            gateway_url=os.getenv(
                "GATEWAY_URL", "http://127.0.0.1:8000"
            ).rstrip("/"),
            gateway_token=os.getenv("GATEWAY_TOKEN", ""),
            gateway_timeout_seconds=float(
                os.getenv("GATEWAY_TIMEOUT_SECONDS", "35")
            ),
            gateway_max_attempts=max(
                1, int(os.getenv("GATEWAY_MAX_ATTEMPTS", "2"))
            ),
            voice_profile_id=os.getenv(
                "WEB_DEMO_VOICE_PROFILE_ID", "cixingnansheng"
            ),
            audio_store_root=audio_store_root,
            max_audio_bytes=max(
                1,
                int(
                    os.getenv(
                        "WEB_DEMO_MAX_AUDIO_BYTES",
                        str(16 * 1024 * 1024),
                    )
                ),
            ),
            max_audio_seconds=max(
                0.1,
                float(os.getenv("WEB_DEMO_MAX_AUDIO_SECONDS", "20")),
            ),
            max_sessions=max(
                1, int(os.getenv("WEB_DEMO_MAX_SESSIONS", "100"))
            ),
            max_profile_bytes=max(
                1,
                int(
                    os.getenv(
                        "WEB_DEMO_MAX_PROFILE_BYTES",
                        str(64 * 1024),
                    )
                ),
            ),
            max_uploaded_profiles=max(
                1,
                int(os.getenv("WEB_DEMO_MAX_UPLOADED_PROFILES", "500")),
            ),
            profile_database_backend=database_backend,
            profile_database_path=(
                Path(database_value)
                if database_value
                else audio_store_root / "profiles.sqlite3"
            ),
            mysql_host=mysql_host,
            mysql_port=int(
                _first_non_empty_env(
                    "WEB_DEMO_MYSQL_PORT",
                    "MYSQL_PORT",
                    default="3306",
                )
            ),
            mysql_user=_first_non_empty_env(
                "WEB_DEMO_MYSQL_USER",
                "MYSQL_USERNAME",
                "MYSQL_USER",
            ),
            mysql_password=_first_non_empty_env(
                "WEB_DEMO_MYSQL_PASSWORD",
                "MYSQL_PASSWORD",
                strip_value=False,
            ),
            mysql_database=_first_non_empty_env(
                "WEB_DEMO_MYSQL_DATABASE",
                "MYSQL_DATABASE",
                default="meantbyme",
            ),
            mysql_connect_timeout_seconds=max(
                1,
                int(
                    os.getenv(
                        "WEB_DEMO_MYSQL_CONNECT_TIMEOUT_SECONDS",
                        "5",
                    )
                ),
            ),
            mysql_ssl_ca=(
                os.getenv("WEB_DEMO_MYSQL_SSL_CA", "").strip() or None
            ),
            mysql_auto_create_schema=(
                os.getenv(
                    "WEB_DEMO_MYSQL_AUTO_CREATE_SCHEMA", "false"
                ).strip().lower()
                in {"1", "true", "yes", "on"}
            ),
            lin_yue_scripted_demo_enabled=(
                os.getenv(
                    "WEB_DEMO_LIN_YUE_SCRIPTED", "true"
                ).strip().lower()
                in {"1", "true", "yes", "on"}
            ),
            lin_yue_scripted_demo_delay_seconds=max(
                0.0,
                float(
                    os.getenv(
                        "WEB_DEMO_LIN_YUE_DELAY_SECONDS", "3.5"
                    )
                ),
            ),
        )
