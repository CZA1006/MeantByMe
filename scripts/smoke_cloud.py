from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from meantbyme.adapters.asr import GatewayASRAdapter
from meantbyme.adapters.audio import AudioStore
from meantbyme.adapters.http import GatewayHttpClient
from meantbyme.adapters.intent import GatewayIntentAdapter
from meantbyme.adapters.tts import GatewayTTSAdapter
from meantbyme.core.domain import ConfirmedContext
from meantbyme.core.runtime.evidence import build_transcript_evidence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manually verify cloud providers through the local gateway"
    )
    parser.add_argument("wav", type=Path, help="Local WAV input")
    parser.add_argument(
        "--gateway-url",
        default="http://127.0.0.1:8000",
        help="Running local gateway",
    )
    parser.add_argument("--patient-id", default="manual-smoke-patient")
    parser.add_argument("--session-id", default="manual-smoke-session")
    parser.add_argument(
        "--situation",
        default=(
            "A friend asked if he wants to go out tomorrow. "
            "Tomorrow is Sunday."
        ),
    )
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    client = GatewayHttpClient(
        args.gateway_url,
        timeout_seconds=args.timeout,
        max_attempts=2,
    )
    health_response = client.request("GET", "/v1/health")
    health = json.loads(health_response.body)

    with tempfile.TemporaryDirectory(prefix="meantbyme-smoke-") as directory:
        store = AudioStore(directory)
        audio_id = "manual-smoke-audio"
        store.import_wav(args.wav, audio_id=audio_id)
        asr_results = GatewayASRAdapter(
            client=client,
            audio_store=store,
            patient_id=args.patient_id,
            session_id=args.session_id,
            secondary_endpoint=None,
        ).transcribe(audio_id)
        if not asr_results or asr_results[0].status != "success":
            print(
                json.dumps(
                    {
                        "health": health,
                        "asr_status": (
                            asr_results[0].status
                            if asr_results
                            else "missing"
                        ),
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 1

        evidence = build_transcript_evidence(asr_results)
        proposal = GatewayIntentAdapter(
            client=client,
            patient_id=args.patient_id,
            session_id=args.session_id,
            situation=args.situation,
        ).propose(evidence, [], ConfirmedContext())
        neutral = GatewayTTSAdapter(client=client).synthesize_neutral(
            proposal.candidates[0]
        )

    result = {
        "health": health,
        "asr_provider": asr_results[0].provider,
        "asr_status": asr_results[0].status,
        "transcript": asr_results[0].transcript,
        "language": asr_results[0].language,
        "candidate_count": len(proposal.candidates),
        "candidate_ids": [
            candidate.id for candidate in proposal.candidates
        ],
        "situation_supplied": bool(args.situation),
        "requires_confirmation": proposal.requires_confirmation,
        "neutral_tts_status": neutral.status,
        "neutral_tts_media_type": neutral.media_type,
        "neutral_tts_bytes": len(neutral.audio_bytes or b""),
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if neutral.status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
