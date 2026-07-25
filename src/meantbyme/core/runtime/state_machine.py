from meantbyme.core.domain import ExpressionSession, SessionStage


class InvalidTransition(ValueError):
    pass


ALLOWED_TRANSITIONS: dict[SessionStage, frozenset[SessionStage]] = {
    SessionStage.READY: frozenset(
        {
            SessionStage.CAPTURING,
            SessionStage.EXPRESSION_CANCELLED,
            SessionStage.STOPPED,
        }
    ),
    SessionStage.CAPTURING: frozenset(
        {
            SessionStage.AUDIO_CAPTURED,
            SessionStage.EXPRESSION_CANCELLED,
            SessionStage.STOPPED,
        }
    ),
    SessionStage.AUDIO_CAPTURED: frozenset(
        {
            SessionStage.TRANSCRIBING,
            SessionStage.EXPRESSION_CANCELLED,
            SessionStage.STOPPED,
        }
    ),
    SessionStage.TRANSCRIBING: frozenset(
        {
            SessionStage.EVIDENCE_EXTRACTED,
            SessionStage.EXPRESSION_CANCELLED,
            SessionStage.STOPPED,
        }
    ),
    SessionStage.EVIDENCE_EXTRACTED: frozenset(
        {
            SessionStage.MEMORY_RETRIEVING,
            SessionStage.EXPRESSION_CANCELLED,
            SessionStage.STOPPED,
        }
    ),
    SessionStage.MEMORY_RETRIEVING: frozenset(
        {
            SessionStage.HEARD_CONTENT_REVIEW,
            SessionStage.EXPRESSION_CANCELLED,
            SessionStage.STOPPED,
        }
    ),
    SessionStage.HEARD_CONTENT_REVIEW: frozenset(
        {
            SessionStage.UNCERTAINTY_ASSESSED,
            SessionStage.EXPRESSION_CANCELLED,
            SessionStage.STOPPED,
        }
    ),
    SessionStage.UNCERTAINTY_ASSESSED: frozenset(
        {
            SessionStage.CATEGORY_CLARIFICATION,
            SessionStage.CANDIDATE_SELECTION,
            SessionStage.FINAL_REVIEW,
            SessionStage.EXPRESSION_CANCELLED,
            SessionStage.STOPPED,
        }
    ),
    SessionStage.CATEGORY_CLARIFICATION: frozenset(
        {
            SessionStage.CANDIDATE_SELECTION,
            SessionStage.HEARD_CONTENT_REVIEW,
            SessionStage.EXPRESSION_CANCELLED,
            SessionStage.STOPPED,
        }
    ),
    SessionStage.CANDIDATE_SELECTION: frozenset(
        {
            SessionStage.FINAL_REVIEW,
            SessionStage.CATEGORY_CLARIFICATION,
            SessionStage.HEARD_CONTENT_REVIEW,
            SessionStage.EXPRESSION_CANCELLED,
            SessionStage.STOPPED,
        }
    ),
    SessionStage.FINAL_REVIEW: frozenset(
        {
            SessionStage.CANDIDATE_SELECTION,
            SessionStage.PATIENT_CONFIRMED,
            SessionStage.EXPRESSION_CANCELLED,
            SessionStage.STOPPED,
        }
    ),
    SessionStage.PATIENT_CONFIRMED: frozenset(
        {
            SessionStage.VOICE_AUTHORIZED,
            SessionStage.SPOKEN,
            SessionStage.EXPRESSION_CANCELLED,
            SessionStage.STOPPED,
        }
    ),
    SessionStage.VOICE_AUTHORIZED: frozenset(
        {
            SessionStage.SPOKEN,
            SessionStage.EXPRESSION_CANCELLED,
            SessionStage.STOPPED,
        }
    ),
    SessionStage.SPOKEN: frozenset(
        {SessionStage.MEMORY_UPDATED, SessionStage.STOPPED}
    ),
    SessionStage.MEMORY_UPDATED: frozenset(
        {SessionStage.COMPLETED, SessionStage.STOPPED}
    ),
    SessionStage.COMPLETED: frozenset(),
    SessionStage.EXPRESSION_CANCELLED: frozenset(),
    SessionStage.STOPPED: frozenset(),
}


def transition(
    session: ExpressionSession, target: SessionStage
) -> ExpressionSession:
    if target not in ALLOWED_TRANSITIONS[session.stage]:
        raise InvalidTransition(
            f"Transition {session.stage.value} -> {target.value} is not allowed"
        )
    return session.model_copy(update={"stage": target})
