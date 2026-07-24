from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any, Callable
from uuid import uuid4

from meantbyme.core.domain import (
    AuthorizedExpression,
    CommandActor,
    ConfirmationMethod,
    ConfirmedContext,
    ExpressionCandidate,
    ExpressionReceipt,
    ExpressionSession,
    MemoryItem,
    MemoryType,
    PatientCommand,
    PatientCommandType,
    RiskLevel,
    RuntimeEvent,
    RuntimeEventType,
    SessionStage,
    SessionViewModel,
    UncertaintyBand,
    VerificationLevel,
)
from meantbyme.core.personalization import (
    compose_situation,
    expression_hash,
    has_strong_verified_match,
    idempotency_key,
    rank_candidates,
)
from meantbyme.core.policies import (
    assess_uncertainty,
    can_use_personal_voice,
    classify_risk,
)
from meantbyme.core.ports import ASRPort, IntentPort, RepositoryPort, TTSPort
from meantbyme.core.runtime.evidence import build_transcript_evidence
from meantbyme.core.runtime.state_machine import transition


class CommandRejected(ValueError):
    pass


class ProviderContractError(RuntimeError):
    pass


class MeantByMeRuntime:
    def __init__(
        self,
        *,
        asr: ASRPort,
        intent: IntentPort,
        tts: TTSPort,
        repository: RepositoryPort,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._asr = asr
        self._intent = intent
        self._tts = tts
        self._repository = repository
        self._now = clock
        self._session: ExpressionSession | None = None
        self._events: list[RuntimeEvent] = []

    @property
    def session(self) -> ExpressionSession:
        if self._session is None:
            raise RuntimeError("No active session")
        return self._session.model_copy(deep=True)

    @property
    def events(self) -> tuple[RuntimeEvent, ...]:
        return tuple(event.model_copy(deep=True) for event in self._events)

    def create_session(
        self,
        *,
        session_id: str,
        patient_id: str,
        language: str,
        voice_profile_id: str,
        situation: str | None = None,
    ) -> ExpressionSession:
        if self._session is not None:
            raise RuntimeError("Runtime already has an active session")
        self._session = ExpressionSession(
            session_id=session_id,
            patient_id=patient_id,
            language=language,
            voice_profile_id=voice_profile_id,
            situation=situation,
        )
        self._repository.create_session(patient_id, self._session)
        self._emit(RuntimeEventType.SESSION_STARTED, {"mode": "mock"})
        return self.session

    def handle(self, command: PatientCommand) -> ExpressionSession:
        if command.session_id != self.session.session_id:
            raise CommandRejected("Command session does not match active session")

        try:
            if command.command is PatientCommandType.STOP:
                self._handle_stop()
            elif command.command is PatientCommandType.SWITCH_INPUT_METHOD:
                self._emit(
                    RuntimeEventType.INPUT_METHOD_SWITCH_REQUESTED,
                    {"actor": command.actor.value},
                )
            elif command.command is PatientCommandType.REQUEST_HELP:
                self._emit(
                    RuntimeEventType.HELP_REQUESTED,
                    {"actor": command.actor.value},
                )
            elif command.command is PatientCommandType.START_CAPTURE:
                self._handle_start_capture(command)
            elif command.command is PatientCommandType.STOP_CAPTURE:
                self._handle_stop_capture(command)
            elif command.command is PatientCommandType.CONFIRM_HEARD_CONTENT:
                self._handle_confirm_heard_content(command)
            elif command.command is PatientCommandType.REJECT_HEARD_CONTENT:
                self._handle_reject_heard_content(command)
            elif command.command is PatientCommandType.SELECT_CATEGORY:
                self._handle_select_category(command)
            elif command.command is PatientCommandType.SELECT_CANDIDATE:
                self._handle_select_candidate(command)
            elif command.command is PatientCommandType.NONE_OF_THESE:
                self._handle_none_of_these(command)
            elif command.command is PatientCommandType.FINAL_CONFIRM:
                self._handle_final_confirm(command)
            elif command.command is PatientCommandType.PLAYBACK_COMPLETED:
                self._handle_playback_completed(command)
            elif command.command is PatientCommandType.PLAYBACK_FAILED:
                self._handle_playback_failed(command)
            elif command.command is PatientCommandType.EDIT_COMPLETION:
                self._handle_edit_completion(command)
            elif command.command is PatientCommandType.GO_BACK:
                self._handle_go_back(command)
            else:
                raise CommandRejected(f"Unsupported command: {command.command}")
        except CommandRejected as error:
            self._emit(
                RuntimeEventType.COMMAND_REJECTED,
                {
                    "command": command.command.value,
                    "reason": str(error),
                    "actor": command.actor.value,
                },
            )
            raise
        return self.session

    def view_model(self) -> SessionViewModel:
        allowed = self._allowed_actions()
        if self.session.stage is SessionStage.SPOKEN:
            personal_voice_status = "used"
        elif self.session.stage is SessionStage.VOICE_AUTHORIZED:
            personal_voice_status = "authorized"
        elif self.session.patient_confirmed:
            personal_voice_status = "blocked"
        else:
            personal_voice_status = "awaiting_confirmation"

        evidence = self.session.evidence
        return SessionViewModel(
            session_id=self.session.session_id,
            stage=self.session.stage,
            headline=self.session.stage.value.replace("_", " ").title(),
            heard_stable=evidence.stable_fragments if evidence else [],
            heard_uncertain=evidence.uncertain_fragments if evidence else [],
            clarification_question=(
                "Is this about a plan, treatment, meeting someone, or something else?"
                if self.session.stage is SessionStage.CATEGORY_CLARIFICATION
                else None
            ),
            clarification_options=(
                ["plan", "treatment", "meeting someone", "something else"]
                if self.session.stage is SessionStage.CATEGORY_CLARIFICATION
                else []
            ),
            candidates=self.session.candidates,
            allowed_actions=allowed,
            trace_items=[
                event.model_dump(mode="json") for event in self._events
            ],
            personal_voice_status=personal_voice_status,
        )

    def _handle_start_capture(self, command: PatientCommand) -> None:
        self._require_patient(command)
        self._require_stage(SessionStage.READY)
        self._move(SessionStage.CAPTURING)

    def _handle_stop_capture(self, command: PatientCommand) -> None:
        self._require_patient(command)
        self._require_stage(SessionStage.CAPTURING)
        audio_id = command.payload.get("audio_id")
        if not isinstance(audio_id, str) or not audio_id:
            raise CommandRejected("stop_capture requires a fixture audio_id")

        audio_hash = hashlib.sha256(audio_id.encode("utf-8")).hexdigest()
        self._move(
            SessionStage.AUDIO_CAPTURED,
            audio_id=audio_id,
            audio_input_hash=audio_hash,
        )
        self._emit(
            RuntimeEventType.AUDIO_CAPTURED,
            {"audio_input_hash": audio_hash, "fixture": True},
        )

        self._move(SessionStage.TRANSCRIBING)
        results = self._asr.transcribe(audio_id)
        for result in results:
            self._emit(
                RuntimeEventType.ASR_RESULT_RECEIVED,
                {
                    "provider": result.provider,
                    "status": result.status,
                    "language": result.language,
                },
            )

        evidence = build_transcript_evidence(results)
        self._move(SessionStage.EVIDENCE_EXTRACTED, evidence=evidence)
        self._emit(
            RuntimeEventType.EVIDENCE_EXTRACTED,
            {
                "stable_fragments": evidence.stable_fragments,
                "uncertain_fragments": evidence.uncertain_fragments,
                "conflict_count": len(evidence.conflicts),
                "missing_slots": evidence.missing_slots,
            },
        )

        self._move(SessionStage.MEMORY_RETRIEVING)
        try:
            memories = self._repository.search_verified_memories(
                self.session.patient_id, evidence.stable_fragments
            )
            self._replace(retrieved_memories=memories)
            self._emit(
                RuntimeEventType.MEMORY_RETRIEVED,
                {
                    "memory_ids": [memory.id for memory in memories],
                    "verified_count": len(memories),
                },
            )
        except Exception as error:
            self._replace(retrieved_memories=[])
            self._emit(
                RuntimeEventType.MEMORY_RETRIEVAL_FAILED,
                {"fallback": "generic_mode", "error_type": type(error).__name__},
            )

        try:
            context_memories = self._repository.search_context_memories(
                self.session.patient_id,
                evidence.stable_fragments + evidence.uncertain_fragments,
                limit=5,
            )
        except Exception as error:
            context_memories = []
            self._emit(
                RuntimeEventType.MEMORY_RETRIEVAL_FAILED,
                {
                    "fallback": "no_context",
                    "error_type": type(error).__name__,
                },
            )
        situation = compose_situation(
            context_memories,
            now=self._now(),
            override=self.session.situation,
        )
        self._replace(situation=situation)
        self._emit(
            RuntimeEventType.CONTEXT_RETRIEVED,
            {
                "count": len(context_memories),
                "memory_ids": [
                    memory.id for memory in context_memories
                ],
                "sources": [
                    memory.context.get(
                        "source", memory.verification_level.value
                    )
                    for memory in context_memories
                ],
            },
        )
        self._move(SessionStage.HEARD_CONTENT_REVIEW)

    def _handle_confirm_heard_content(
        self, command: PatientCommand
    ) -> None:
        self._require_patient(command)
        self._require_stage(SessionStage.HEARD_CONTENT_REVIEW)
        evidence = self._require_evidence()
        context = self.session.confirmed_context.model_copy(
            update={
                "locked_tokens": list(
                    dict.fromkeys(
                        self.session.confirmed_context.locked_tokens
                        + evidence.stable_fragments
                    )
                )
            }
        )
        base_band = assess_uncertainty(evidence)
        self._move(
            SessionStage.UNCERTAINTY_ASSESSED,
            confirmed_context=context,
        )

        strong_memory = has_strong_verified_match(
            self.session.retrieved_memories
        )
        if base_band is UncertaintyBand.HIGH and strong_memory:
            effective_route = UncertaintyBand.MEDIUM
        elif base_band is UncertaintyBand.MEDIUM and strong_memory:
            effective_route = UncertaintyBand.LOW
        else:
            effective_route = base_band
        self._emit(
            RuntimeEventType.UNCERTAINTY_ASSESSED,
            {
                "evidence_band": base_band.value,
                "effective_route": effective_route.value,
                "memory_downgraded": effective_route is not base_band,
            },
        )

        if effective_route is UncertaintyBand.HIGH:
            self._move(
                SessionStage.CATEGORY_CLARIFICATION,
                previous_stage=SessionStage.HEARD_CONTENT_REVIEW,
            )
            self._emit(
                RuntimeEventType.CLARIFICATION_REQUESTED,
                {"dimension": "category"},
            )
            return

        self._generate_candidates()
        if effective_route is UncertaintyBand.LOW:
            self._move(
                SessionStage.FINAL_REVIEW,
                previous_stage=SessionStage.HEARD_CONTENT_REVIEW,
            )
        else:
            self._move(
                SessionStage.CANDIDATE_SELECTION,
                previous_stage=SessionStage.HEARD_CONTENT_REVIEW,
            )

    def _handle_reject_heard_content(
        self, command: PatientCommand
    ) -> None:
        self._require_patient(command)
        self._require_stage(SessionStage.HEARD_CONTENT_REVIEW)
        self._replace(
            evidence=None,
            retrieved_memories=[],
            failure_status="heard_content_rejected",
        )

    def _handle_select_category(self, command: PatientCommand) -> None:
        self._require_patient(command)
        self._require_stage(SessionStage.CATEGORY_CLARIFICATION)
        category = command.payload.get("category")
        if not isinstance(category, str) or not category:
            raise CommandRejected("select_category requires category")
        slots = dict(self.session.confirmed_context.locked_slots)
        slots["category"] = category
        self._replace(
            confirmed_context=self.session.confirmed_context.model_copy(
                update={"locked_slots": slots}
            )
        )
        self._generate_candidates()
        self._move(
            SessionStage.CANDIDATE_SELECTION,
            previous_stage=SessionStage.CATEGORY_CLARIFICATION,
        )

    def _handle_select_candidate(self, command: PatientCommand) -> None:
        self._require_patient(command)
        if self.session.stage not in {
            SessionStage.CANDIDATE_SELECTION,
            SessionStage.FINAL_REVIEW,
        }:
            raise CommandRejected(
                "select_candidate requires candidate selection or final review"
            )
        if (
            self.session.stage is SessionStage.FINAL_REVIEW
            and self.session.selected_candidate_id is not None
        ):
            raise CommandRejected("A candidate is already selected")

        # D14: this assertion keeps model/ranker code out of the selection path.
        assert command.command is PatientCommandType.SELECT_CANDIDATE
        assert command.actor is CommandActor.PATIENT
        candidate_id = command.payload.get("candidate_id")
        candidate = self._candidate_by_id(candidate_id)
        risk = classify_risk(candidate.text, candidate.risk_level)
        self._replace(
            selected_candidate_id=candidate.id,
            risk_level=risk,
            strict=risk is RiskLevel.HIGH_RISK,
            patient_confirmed=False,
            confirmation_method=None,
            neutral_readback_path=None,
        )
        self._emit(
            RuntimeEventType.PATIENT_SELECTION_RECEIVED,
            {"candidate_id": candidate.id, "actor": command.actor.value},
        )
        if self.session.stage is SessionStage.CANDIDATE_SELECTION:
            self._move(SessionStage.FINAL_REVIEW)

        readback = self._tts.synthesize_neutral(candidate)
        if readback.status == "success":
            self._replace(
                neutral_readback_path=readback.audio_path,
                failure_status=None,
            )
            self._emit(
                RuntimeEventType.PRIVATE_READBACK_READY,
                {"voice": "neutral", "candidate_id": candidate.id},
            )
        else:
            self._replace(failure_status="neutral_tts_failed")
            self._emit(
                RuntimeEventType.TTS_FAILED,
                {"voice": "neutral", "error": readback.error},
            )

    def _handle_none_of_these(self, command: PatientCommand) -> None:
        self._require_patient(command)
        if self.session.stage not in {
            SessionStage.CANDIDATE_SELECTION,
            SessionStage.FINAL_REVIEW,
        }:
            raise CommandRejected(
                "none_of_these requires candidate selection or final review"
            )
        rejected_texts = list(self.session.confirmed_context.rejected_texts)
        for candidate in self.session.candidates:
            self._repository.record_rejected_candidate(
                self.session.patient_id,
                candidate.id,
                candidate.text,
                self.session.session_id,
            )
            if candidate.text not in rejected_texts:
                rejected_texts.append(candidate.text)

        context = self.session.confirmed_context.model_copy(
            update={"rejected_texts": rejected_texts}
        )
        if self.session.stage is SessionStage.FINAL_REVIEW:
            self._move(SessionStage.CANDIDATE_SELECTION)
        self._replace(
            confirmed_context=context,
            candidates=[],
            selected_candidate_id=None,
            patient_confirmed=False,
            confirmation_method=None,
            strict=False,
            risk_level=RiskLevel.ORDINARY,
            neutral_readback_path=None,
        )
        self._generate_candidates()

    def _handle_final_confirm(self, command: PatientCommand) -> None:
        self._require_patient(command)
        self._require_stage(SessionStage.FINAL_REVIEW)
        candidate = self.session.selected_candidate()
        if candidate is None:
            raise CommandRejected(
                "Patient must explicitly select a candidate before confirmation"
            )
        if command.confirmation_method is None:
            raise CommandRejected(
                "Silence, timeout, or absent method cannot confirm"
            )
        if command.payload.get("private_readback_completed") is not True:
            raise CommandRejected(
                "Full private readback must complete before confirmation"
            )

        risk = classify_risk(candidate.text, candidate.risk_level)
        strict = risk is RiskLevel.HIGH_RISK
        if strict and command.payload.get("strict_confirmation") is not True:
            raise CommandRejected(
                "High-risk expression requires strict confirmation"
            )
        if (
            candidate.source_level == "L3"
            and command.payload.get("l3_confirmation") is not True
        ):
            raise CommandRejected(
                "L3 suggestion requires an additional explicit confirmation"
            )
        if (
            command.confirmation_method
            is ConfirmationMethod.VOICE_SEMANTIC
            and (strict or candidate.source_level == "L3")
        ):
            self._require_distinct_voice_confirmation_evidence(command)

        self._move(
            SessionStage.PATIENT_CONFIRMED,
            patient_confirmed=True,
            confirmation_method=command.confirmation_method,
            risk_level=risk,
            strict=strict,
        )
        self._emit(
            RuntimeEventType.FINAL_CONFIRMATION_RECEIVED,
            {
                "method": command.confirmation_method.value,
                "strict": strict,
                "actor": command.actor.value,
            },
        )

        active_consent = self._repository.has_active_voice_consent(
            self.session.patient_id, self.session.voice_profile_id
        )
        if not active_consent:
            self._replace(failure_status="long_term_voice_consent_missing")
            self._emit(
                RuntimeEventType.VOICE_AUTHORIZATION_BLOCKED,
                {"reason": "long_term_voice_consent_missing_or_revoked"},
            )
            return

        authorized = AuthorizedExpression(
            session_id=self.session.session_id,
            patient_id=self.session.patient_id,
            final_text=candidate.text,
            language=candidate.language,
            voice_profile_id=self.session.voice_profile_id,
            authorization_scope="this_expression",
            confirmation_method=command.confirmation_method,
            authorized_at=datetime.now(UTC),
        )
        self._move(
            SessionStage.VOICE_AUTHORIZED,
            voice_authorized=True,
            authorization_scope="this_expression",
            authorized_expression=authorized,
            failure_status=None,
        )
        self._emit(
            RuntimeEventType.VOICE_AUTHORIZATION_GRANTED,
            {"scope": "this_expression"},
        )

        consent_still_active = self._repository.has_active_voice_consent(
            self.session.patient_id, self.session.voice_profile_id
        )
        if not can_use_personal_voice(self.session, consent_still_active):
            self._replace(failure_status="voice_policy_blocked")
            self._emit(
                RuntimeEventType.VOICE_AUTHORIZATION_BLOCKED,
                {"reason": "authorization_policy_failed"},
            )
            return

        tts_result = self._tts.synthesize_personal(authorized)
        if tts_result.status != "success":
            self._replace(failure_status="personal_tts_failed")
            self._emit(
                RuntimeEventType.TTS_FAILED,
                {"voice": "personal", "error": tts_result.error},
            )
            return

        # Synthesis only makes authorized audio available. The expression is
        # not spoken until the output device reports successful completion.
        self._replace(failure_status=None)

    def _handle_playback_completed(self, command: PatientCommand) -> None:
        self._require_system(command)
        playback_id = self._playback_id(command)
        if self.session.stage in {
            SessionStage.SPOKEN,
            SessionStage.MEMORY_UPDATED,
            SessionStage.COMPLETED,
        }:
            if self.session.playback_id == playback_id:
                return
            raise CommandRejected(
                "A different playback already completed this expression"
            )
        self._require_stage(SessionStage.VOICE_AUTHORIZED)
        if self.session.failure_status == "personal_tts_failed":
            raise CommandRejected("Personal TTS did not produce playable audio")
        if (
            not self.session.voice_authorized
            or self.session.authorized_expression is None
        ):
            raise CommandRejected("Expression is not authorized for playback")
        output_channel = command.payload.get("output_channel")
        if output_channel not in {"iphone_speaker", "browser_speaker"}:
            raise CommandRejected(
                "Playback completion requires a supported public output"
            )
        candidate = self.session.selected_candidate()
        if candidate is None:
            raise CommandRejected("Playback has no selected candidate")
        completed_at = self._now()
        self._move(
            SessionStage.SPOKEN,
            playback_id=playback_id,
            playback_completed_at=completed_at,
            playback_output_channel=output_channel,
            failure_status=None,
        )
        self._emit(
            RuntimeEventType.PLAYBACK_COMPLETED,
            {
                "playback_id": playback_id,
                "output_channel": output_channel,
            },
        )
        self._emit(
            RuntimeEventType.EXPRESSION_SPOKEN,
            {
                "playback_id": playback_id,
                "output_channel": output_channel,
            },
        )
        self._create_receipt_then_write_memory(candidate)

    def _handle_playback_failed(self, command: PatientCommand) -> None:
        self._require_system(command)
        self._require_stage(SessionStage.VOICE_AUTHORIZED)
        playback_id = self._playback_id(command)
        output_channel = command.payload.get("output_channel")
        if output_channel not in {"iphone_speaker", "browser_speaker"}:
            raise CommandRejected(
                "Playback failure requires a supported public output"
            )
        self._replace(
            playback_id=playback_id,
            playback_output_channel=output_channel,
            failure_status="playback_failed",
        )
        self._emit(
            RuntimeEventType.PLAYBACK_FAILED,
            {
                "playback_id": playback_id,
                "output_channel": output_channel,
            },
        )

    def _handle_edit_completion(self, command: PatientCommand) -> None:
        self._require_patient(command)
        self._require_stage(SessionStage.FINAL_REVIEW)
        text = command.payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise CommandRejected("edit_completion requires text")
        edited = ExpressionCandidate(
            id=f"patient-edit-{uuid4().hex}",
            text=text.strip(),
            language=self.session.language or "en",
            patient_supported_spans=[text.strip()],
            ai_added_spans=[],
            memory_support_ids=[],
            ranking_reasons=["patient-authored edit"],
            risk_level=classify_risk(text),
            source_level="L1",
        )
        self._replace(
            candidates=[edited],
            selected_candidate_id=None,
            neutral_readback_path=None,
        )

    def _handle_go_back(self, command: PatientCommand) -> None:
        self._require_patient(command)
        if self.session.stage in {
            SessionStage.VOICE_AUTHORIZED,
            SessionStage.SPOKEN,
            SessionStage.MEMORY_UPDATED,
            SessionStage.COMPLETED,
        }:
            raise CommandRejected("Nothing is reversible after voice authorization")

        if self.session.stage is SessionStage.FINAL_REVIEW:
            self._move(
                SessionStage.CANDIDATE_SELECTION,
                selected_candidate_id=None,
                patient_confirmed=False,
                confirmation_method=None,
                strict=False,
                neutral_readback_path=None,
            )
        elif self.session.stage is SessionStage.CANDIDATE_SELECTION:
            target = (
                SessionStage.CATEGORY_CLARIFICATION
                if self.session.previous_stage
                is SessionStage.CATEGORY_CLARIFICATION
                else SessionStage.HEARD_CONTENT_REVIEW
            )
            self._move(
                target,
                candidates=[],
                selected_candidate_id=None,
            )
        elif self.session.stage is SessionStage.CATEGORY_CLARIFICATION:
            slots = dict(self.session.confirmed_context.locked_slots)
            slots.pop("category", None)
            self._move(
                SessionStage.HEARD_CONTENT_REVIEW,
                confirmed_context=self.session.confirmed_context.model_copy(
                    update={"locked_slots": slots}
                ),
            )
        else:
            raise CommandRejected(
                f"go_back is not defined from {self.session.stage.value}"
            )

    def _handle_stop(self) -> None:
        if self.session.stage in {SessionStage.COMPLETED, SessionStage.STOPPED}:
            raise CommandRejected("Session is already terminal")
        self._move(
            SessionStage.STOPPED,
            voice_authorized=False,
            authorized_expression=None,
            authorization_scope=None,
        )
        self._emit(RuntimeEventType.SESSION_STOPPED, {})

    def _generate_candidates(self) -> None:
        evidence = self._require_evidence()
        assert self.session.selected_candidate_id is None
        proposal = self._intent.propose(
            evidence,
            self.session.retrieved_memories,
            self.session.confirmed_context,
            self.session.situation,
        )
        if not proposal.requires_confirmation:
            raise ProviderContractError(
                "Intent provider attempted to skip final confirmation"
            )
        if not 2 <= len(proposal.candidates) <= 3:
            raise ProviderContractError(
                "Intent provider must return two or three candidates"
            )
        if len({candidate.text for candidate in proposal.candidates}) != len(
            proposal.candidates
        ):
            raise ProviderContractError("Intent candidates must be distinct")

        self._replace(candidates=proposal.candidates)
        self._emit(
            RuntimeEventType.CANDIDATES_GENERATED,
            {"candidate_ids": [item.id for item in proposal.candidates]},
        )
        ranked = rank_candidates(
            proposal.candidates, self.session.retrieved_memories
        )
        assert self.session.selected_candidate_id is None
        self._replace(candidates=ranked)
        assert self.session.selected_candidate_id is None
        self._emit(
            RuntimeEventType.CANDIDATES_RERANKED,
            {"candidate_ids": [item.id for item in ranked]},
        )

    def _create_receipt_then_write_memory(
        self, candidate: ExpressionCandidate
    ) -> None:
        method = self.session.confirmation_method
        if (
            method is None
            or self.session.audio_input_hash is None
            or self.session.playback_id is None
            or self.session.playback_completed_at is None
            or self.session.playback_output_channel is None
        ):
            raise RuntimeError("Confirmed expression lacks receipt evidence")
        receipt = ExpressionReceipt(
            receipt_id=f"receipt-{self.session.session_id}",
            session_id=self.session.session_id,
            patient_id=self.session.patient_id,
            patient_supported_content=candidate.patient_supported_spans,
            ai_added_content=candidate.ai_added_spans,
            memory_ids_used=candidate.memory_support_ids,
            expression_level=candidate.source_level,
            selected_candidate_id=candidate.id,
            patient_confirmed=True,
            confirmation_method=method,
            voice_profile_id=self.session.voice_profile_id,
            authorization_scope="this_expression",
            output_channel=self.session.playback_output_channel,
            playback_id=self.session.playback_id,
            playback_completed_at=self.session.playback_completed_at,
            audio_input_hash=self.session.audio_input_hash,
            final_text_hash=expression_hash(candidate.text),
            created_at=datetime.now(UTC),
            signature=None,
        )
        try:
            self._repository.store_receipt(self.session.patient_id, receipt)
        except Exception as error:
            self._replace(failure_status="receipt_write_failed")
            self._emit(
                RuntimeEventType.EXPRESSION_RECEIPT_FAILED,
                {"error_type": type(error).__name__},
            )
            return
        self._replace(receipt_id=receipt.receipt_id)
        self._emit(
            RuntimeEventType.EXPRESSION_RECEIPT_CREATED,
            {"receipt_id": receipt.receipt_id, "signature": None},
        )

        update_type = "verified_semantic_expression"
        key = idempotency_key(
            self.session.session_id, candidate.text, update_type
        )
        memory = MemoryItem(
            id=(
                "mem-"
                + hashlib.sha256(
                    (
                        self.session.patient_id
                        + ":"
                        + expression_hash(candidate.text)
                    ).encode("utf-8")
                ).hexdigest()[:24]
            ),
            patient_id=self.session.patient_id,
            memory_type=MemoryType.SEMANTIC,
            verification_level=VerificationLevel.GOLD,
            text=candidate.text,
            language=candidate.language,
            context={"source": "confirmed_expression"},
            usage_count=0,
            confirmation_session_id=self.session.session_id,
        )
        try:
            write_result = self._repository.write_verified_memory(
                self.session.patient_id, memory, key
            )
        except Exception as error:
            self._replace(failure_status="memory_write_failed")
            self._emit(
                RuntimeEventType.MEMORY_WRITE_FAILED,
                {"error_type": type(error).__name__},
            )
            return

        self._move(SessionStage.MEMORY_UPDATED)
        self._emit(
            RuntimeEventType.VERIFIED_MEMORY_WRITTEN,
            {
                "memory_id": write_result.memory.id,
                "usage_count": write_result.memory.usage_count,
                "new_write": write_result.written,
                "idempotency_key": write_result.idempotency_key,
            },
        )
        self._move(SessionStage.COMPLETED)
        self._emit(RuntimeEventType.SESSION_COMPLETED, {})

    def _candidate_by_id(self, candidate_id: Any) -> ExpressionCandidate:
        if not isinstance(candidate_id, str):
            raise CommandRejected("select_candidate requires candidate_id")
        candidate = next(
            (
                item
                for item in self.session.candidates
                if item.id == candidate_id
            ),
            None,
        )
        if candidate is None:
            raise CommandRejected("Candidate does not belong to this session")
        return candidate

    def _require_stage(self, expected: SessionStage) -> None:
        if self.session.stage is not expected:
            raise CommandRejected(
                f"Command requires {expected.value}; current stage is "
                f"{self.session.stage.value}"
            )

    @staticmethod
    def _require_patient(command: PatientCommand) -> None:
        if command.actor is not CommandActor.PATIENT:
            raise CommandRejected(
                "Only an explicit patient command may make this decision"
            )

    @staticmethod
    def _require_system(command: PatientCommand) -> None:
        if command.actor is not CommandActor.SYSTEM:
            raise CommandRejected(
                "Only an authenticated playback callback may report output"
            )

    @staticmethod
    def _playback_id(command: PatientCommand) -> str:
        playback_id = command.payload.get("playback_id")
        if not isinstance(playback_id, str) or not playback_id.strip():
            raise CommandRejected("Playback callback requires playback_id")
        if len(playback_id) > 128:
            raise CommandRejected("playback_id is too long")
        return playback_id

    @staticmethod
    def _require_distinct_voice_confirmation_evidence(
        command: PatientCommand,
    ) -> None:
        evidence = command.payload.get("voice_confirmation_evidence")
        if not isinstance(evidence, dict):
            raise CommandRejected(
                "High-risk voice confirmation requires two evidence records"
            )
        fields = (
            "first_prompt_id",
            "second_prompt_id",
            "first_audio_hash",
            "second_audio_hash",
        )
        if any(
            not isinstance(evidence.get(field), str)
            or not evidence[field].strip()
            for field in fields
        ):
            raise CommandRejected(
                "Voice confirmation evidence is incomplete"
            )
        if evidence["first_prompt_id"] == evidence["second_prompt_id"]:
            raise CommandRejected(
                "Voice confirmations require distinct prompts"
            )
        if evidence["first_audio_hash"] == evidence["second_audio_hash"]:
            raise CommandRejected(
                "Voice confirmations require distinct audio evidence"
            )

    def _require_evidence(self):
        if self.session.evidence is None:
            raise RuntimeError("Session has no transcript evidence")
        return self.session.evidence

    def _replace(self, **updates: Any) -> None:
        self._session = self.session.model_copy(update=updates)
        self._repository.update_session(self.session.patient_id, self.session)

    def _move(self, target: SessionStage, **updates: Any) -> None:
        moved = transition(self.session, target)
        self._session = moved.model_copy(update=updates)
        self._repository.update_session(self.session.patient_id, self.session)

    def _emit(
        self, event_type: RuntimeEventType, payload: dict[str, Any]
    ) -> None:
        event = RuntimeEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            session_id=self.session.session_id,
            patient_id=self.session.patient_id,
            timestamp=datetime.now(UTC),
            payload=payload,
        )
        self._events.append(event)
        self._repository.append_event(self.session.patient_id, event)

    def _allowed_actions(self) -> list[PatientCommandType]:
        stage_actions = {
            SessionStage.READY: [PatientCommandType.START_CAPTURE],
            SessionStage.CAPTURING: [PatientCommandType.STOP_CAPTURE],
            SessionStage.HEARD_CONTENT_REVIEW: [
                PatientCommandType.CONFIRM_HEARD_CONTENT,
                PatientCommandType.REJECT_HEARD_CONTENT,
            ],
            SessionStage.CATEGORY_CLARIFICATION: [
                PatientCommandType.SELECT_CATEGORY,
                PatientCommandType.GO_BACK,
            ],
            SessionStage.CANDIDATE_SELECTION: [
                PatientCommandType.SELECT_CANDIDATE,
                PatientCommandType.NONE_OF_THESE,
                PatientCommandType.GO_BACK,
            ],
            SessionStage.FINAL_REVIEW: [
                PatientCommandType.SELECT_CANDIDATE,
                PatientCommandType.FINAL_CONFIRM,
                PatientCommandType.EDIT_COMPLETION,
                PatientCommandType.NONE_OF_THESE,
                PatientCommandType.GO_BACK,
            ],
            SessionStage.VOICE_AUTHORIZED: [
                PatientCommandType.PLAYBACK_COMPLETED,
                PatientCommandType.PLAYBACK_FAILED,
            ],
        }
        actions = list(stage_actions.get(self.session.stage, []))
        if self.session.stage not in {
            SessionStage.COMPLETED,
            SessionStage.STOPPED,
        }:
            actions.extend(
                [
                    PatientCommandType.STOP,
                    PatientCommandType.SWITCH_INPUT_METHOD,
                    PatientCommandType.REQUEST_HELP,
                ]
            )
        return list(dict.fromkeys(actions))
