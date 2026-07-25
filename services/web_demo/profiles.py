from __future__ import annotations

import json
from pathlib import Path
from secrets import token_urlsafe
from typing import Any
from uuid import uuid4

from meantbyme.adapters.profile import (
    ProfileBundle,
    ProfileBundleError,
    load_profile_bundle,
    parse_profile_markdown,
)
from services.web_demo.profile_storage import ProfileSource, ProfileStore


class DemoProfileRegistry:
    """Resolves built-ins and server-persisted user profiles."""

    def __init__(
        self,
        profile_root: Path,
        *,
        max_profile_bytes: int,
        max_uploaded_profiles: int,
        cloud_mode: bool,
        store: ProfileStore,
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
        self._store = store

    def close(self) -> None:
        self._store.close()

    def list_profiles(self) -> list[dict[str, Any]]:
        order = {
            "no_profile": 0,
            "lin_yue_demo": 1,
            "david_demo": 2,
        }
        builtins = sorted(
            self._builtins.values(),
            key=lambda profile: (
                order.get(profile.profile_id, 100),
                profile.label.casefold(),
            ),
        )
        result = [
            self._summary(
                profile.profile_id,
                profile,
                source="built_in",
            )
            for profile in builtins
        ]
        rows = self._store.list_profiles()
        for row in rows:
            profile = parse_profile_markdown(
                row.markdown, max_bytes=self._max_profile_bytes
            )
            result.append(
                self._summary(
                    row.profile_ref,
                    profile,
                    source=row.source,
                )
            )
        return result

    def register_upload(self, markdown: str) -> dict[str, Any]:
        profile = parse_profile_markdown(
            markdown, max_bytes=self._max_profile_bytes
        )
        if not profile.simulated:
            profile, markdown = self._demote_unverified_upload(profile)
        self._require_cloud_consent(profile)
        reference = f"uploaded-{token_urlsafe(24)}"
        self._persist(reference, profile, markdown, source="uploaded")
        return self._summary(reference, profile, source="uploaded")

    def create_from_questionnaire(
        self,
        *,
        display_name: str,
        language: str,
        answers: dict[str, str],
    ) -> dict[str, Any]:
        patient_id = f"user-{uuid4().hex}"
        memories = []
        field_metadata = {
            "background": ("personal_background", "身份与背景"),
            "relationships": ("relationships", "家人与重要关系"),
            "routines": ("routine", "日常习惯与安排"),
            "interests": ("interests", "兴趣爱好"),
            "communication_preferences": (
                "communication_preference",
                "沟通偏好与需要的帮助",
            ),
            "additional_notes": ("additional_context", "其他补充"),
        }
        for field_name, (kind, title) in field_metadata.items():
            text = answers.get(field_name, "").strip()
            if not text:
                continue
            memories.append(
                {
                    "simulated": False,
                    "id": f"ctx-{uuid4().hex}",
                    "memory_type": "context",
                    "verification_level": "silver",
                    "source": "caregiver",
                    "text": f"{title}：{text}",
                    "language": language,
                    "context": {
                        "kind": kind,
                        "entry_method": "caregiver_questionnaire",
                    },
                    "usage_count": 0,
                    "confirmation_session_id": None,
                    "sensitivity": "ordinary",
                    "prompt_eligible": True,
                }
            )
        if not memories:
            raise ProfileBundleError(
                "at least one profile question must be answered"
            )
        payload = {
            "schema_version": 1,
            "simulated": False,
            "profile_id": patient_id,
            "label": display_name,
            "patient": {
                "patient_id": patient_id,
                "display_name": display_name,
                "languages": [language],
                "default_language": language,
            },
            "consent": {
                "scope": "app_personalization",
                "cloud_processing_allowed": True,
            },
            "memories": memories,
        }
        markdown = (
            f"# {display_name} 的人物档案\n\n"
            "档案由陪护者在 MeantByMe App 中填写；所有内容均按 "
            "Silver 辅助上下文处理，不代表患者本人确认的意愿。\n\n"
            "```meantbyme-profile\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
            "```\n"
        )
        profile = parse_profile_markdown(
            markdown, max_bytes=self._max_profile_bytes
        )
        reference = patient_id
        self._persist(
            reference,
            profile,
            markdown,
            source="questionnaire",
        )
        return self._summary(
            reference, profile, source="questionnaire"
        )

    def detail(self, profile_ref: str) -> dict[str, Any]:
        profile, source = self._resolve_with_source(profile_ref)
        return {
            **self._summary(profile_ref, profile, source=source),
            "profile_id": profile.profile_id,
            "display_name": profile.patient.display_name,
            "simulated": profile.simulated,
            "memories": [
                {
                    "id": memory.id,
                    "text": memory.text,
                    "kind": str(memory.context.get("kind", "其他")),
                    "verification_level": memory.verification_level.value,
                    "source": memory.source,
                    "sensitivity": memory.sensitivity.value,
                    "prompt_eligible": memory.prompt_eligible,
                }
                for memory in profile.memories
            ],
        }

    def resolve(self, profile_ref: str) -> ProfileBundle:
        profile, _ = self._resolve_with_source(profile_ref)
        self._require_cloud_consent(profile)
        return profile

    def _resolve_with_source(
        self, profile_ref: str
    ) -> tuple[ProfileBundle, str]:
        profile = self._builtins.get(profile_ref)
        if profile is not None:
            return profile, "built_in"
        row = self._store.get_profile(profile_ref)
        if row is None:
            raise ProfileBundleError("profile not found")
        return (
            parse_profile_markdown(
                row.markdown, max_bytes=self._max_profile_bytes
            ),
            row.source,
        )

    def _persist(
        self,
        reference: str,
        profile: ProfileBundle,
        markdown: str,
        *,
        source: ProfileSource,
    ) -> None:
        if self._store.count_profiles() >= self._max_uploaded_profiles:
            raise ProfileBundleError("profile capacity reached")
        self._store.insert_profile(
            profile_ref=reference,
            profile_id=profile.profile_id,
            markdown=markdown,
            source=source,
        )

    def _require_cloud_consent(self, profile: ProfileBundle) -> None:
        if self._cloud_mode and not profile.consent.cloud_processing_allowed:
            raise ProfileBundleError(
                "profile does not permit cloud processing"
            )

    def _demote_unverified_upload(
        self, profile: ProfileBundle
    ) -> tuple[ProfileBundle, str]:
        """An uploaded file cannot self-assert patient confirmation."""
        payload = profile.model_dump(mode="json")
        payload["voice_consent"] = None
        for memory in payload["memories"]:
            memory["verification_level"] = "silver"
            memory["source"] = "caregiver"
            memory["confirmation_session_id"] = None
            memory["context"] = {
                **memory.get("context", {}),
                "entry_method": "markdown_import",
            }
        normalized = (
            f"# {profile.patient.display_name} 的人物档案\n\n"
            "该文件通过 App 导入；其中内容作为 Silver 辅助上下文，"
            "不代表患者本人已确认的意愿。\n\n"
            "```meantbyme-profile\n"
            f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
            "```\n"
        )
        return (
            parse_profile_markdown(
                normalized, max_bytes=self._max_profile_bytes
            ),
            normalized,
        )

    @staticmethod
    def _summary(
        profile_ref: str,
        profile: ProfileBundle,
        *,
        source: str,
    ) -> dict[str, Any]:
        return {
            "profile_ref": profile_ref,
            "label": profile.label,
            "default_language": profile.patient.default_language,
            "languages": profile.patient.languages,
            "source": source,
            "simulated": profile.simulated,
            "memory_count": len(profile.memories),
        }
