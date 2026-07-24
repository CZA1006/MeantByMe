from __future__ import annotations

import threading
from pathlib import Path
from secrets import token_urlsafe
from typing import Any

from meantbyme.adapters.profile import (
    ProfileBundle,
    ProfileBundleError,
    load_profile_bundle,
    parse_profile_markdown,
)


class DemoProfileRegistry:
    """Holds built-in and process-local simulated profile bundles."""

    def __init__(
        self,
        profile_root: Path,
        *,
        max_profile_bytes: int,
        max_uploaded_profiles: int,
        cloud_mode: bool,
    ) -> None:
        self._max_profile_bytes = max_profile_bytes
        self._max_uploaded_profiles = max_uploaded_profiles
        self._cloud_mode = cloud_mode
        self._builtins = {
            profile.profile_id: profile
            for profile in (
                load_profile_bundle(
                    path, max_bytes=self._max_profile_bytes
                )
                for path in sorted(profile_root.glob("*.md"))
            )
        }
        self._uploaded: dict[str, ProfileBundle] = {}
        self._lock = threading.RLock()

    def list_profiles(self) -> list[dict[str, Any]]:
        order = {
            "no_profile": 0,
            "lin_yue_demo": 1,
            "david_demo": 2,
        }
        profiles = sorted(
            self._builtins.values(),
            key=lambda profile: (
                order.get(profile.profile_id, 100),
                profile.label.casefold(),
            ),
        )
        return [
            {
                "profile_ref": profile.profile_id,
                "label": profile.label,
                "default_language": profile.patient.default_language,
                "languages": profile.patient.languages,
                "source": "built_in",
            }
            for profile in profiles
        ]

    def register_upload(self, markdown: str) -> dict[str, Any]:
        profile = parse_profile_markdown(
            markdown, max_bytes=self._max_profile_bytes
        )
        if self._cloud_mode and not profile.consent.cloud_processing_allowed:
            raise ProfileBundleError(
                "profile does not permit cloud processing for demo testing"
            )
        with self._lock:
            if len(self._uploaded) >= self._max_uploaded_profiles:
                raise ProfileBundleError("uploaded profile capacity reached")
            reference = f"uploaded-{token_urlsafe(24)}"
            self._uploaded[reference] = profile
        return {
            "profile_ref": reference,
            "label": profile.label,
            "default_language": profile.patient.default_language,
            "languages": profile.patient.languages,
            "source": "uploaded",
        }

    def resolve(self, profile_ref: str) -> ProfileBundle:
        with self._lock:
            profile = self._builtins.get(profile_ref) or self._uploaded.get(
                profile_ref
            )
        if profile is None:
            raise ProfileBundleError("simulated profile not found")
        if self._cloud_mode and not profile.consent.cloud_processing_allowed:
            raise ProfileBundleError(
                "profile does not permit cloud processing for demo testing"
            )
        return profile
