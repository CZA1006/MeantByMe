from meantbyme.core.domain import ExpressionSession, SessionStage


def can_use_personal_voice(
    session: ExpressionSession, has_long_term_consent: bool
) -> bool:
    return (
        has_long_term_consent
        and session.patient_confirmed
        and session.stage is SessionStage.VOICE_AUTHORIZED
        and session.voice_authorized
        and session.authorization_scope == "this_expression"
        and session.authorized_expression is not None
        and session.authorized_expression.session_id == session.session_id
        and session.authorized_expression.patient_id == session.patient_id
    )
