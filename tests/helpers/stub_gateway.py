from __future__ import annotations

import io
import json
import threading
import time
import wave
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Iterator


def wav_bytes(*, duration_seconds: float = 0.05) -> bytes:
    output = io.BytesIO()
    frame_count = int(16_000 * duration_seconds)
    with wave.open(output, "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(16_000)
        writer.writeframes(b"\x00\x00" * frame_count)
    return output.getvalue()


@dataclass
class StubGatewayState:
    asr_delay_seconds: float = 0.0
    invalid_intent_json: bool = False
    secondary_available: bool = False
    personal_tts_failure: bool = False
    request_count: int = 0


class QuietThreadingHTTPServer(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address) -> None:
        del request, client_address


class StubGateway:
    def __init__(self, state: StubGatewayState | None = None) -> None:
        self.state = state or StubGatewayState()
        self._server = QuietThreadingHTTPServer(
            ("127.0.0.1", 0), self._handler_type()
        )
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            name="meantbyme-stub-gateway",
            daemon=True,
        )

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)

    def _handler_type(self) -> type[BaseHTTPRequestHandler]:
        state = self.state

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args) -> None:
                del format, args

            def do_GET(self) -> None:
                if self.path == "/v1/health":
                    self._json(
                        {
                            "status": "ok",
                            "intent_provider": "stub",
                            "intent_model": "stub-json",
                        }
                    )
                    return
                self.send_error(404)

            def do_POST(self) -> None:
                state.request_count += 1
                content_length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(content_length)
                if self.path == "/v1/asr/primary":
                    if state.asr_delay_seconds:
                        time.sleep(state.asr_delay_seconds)
                    self._asr("stub_step_asr")
                    return
                if self.path == "/v1/asr/secondary":
                    if not state.secondary_available:
                        self.send_error(404)
                        return
                    self._asr("stub_secondary_asr")
                    return
                if self.path == "/v1/intent/propose":
                    if state.invalid_intent_json:
                        self._write(
                            b"{not-json",
                            content_type="application/json",
                        )
                        return
                    request_payload = json.loads(body or b"{}")
                    self._json(_intent_proposal(request_payload))
                    return
                if self.path == "/v1/tts/synthesize":
                    payload = json.loads(body or b"{}")
                    if (
                        payload.get("mode") == "personal"
                        and state.personal_tts_failure
                    ):
                        self.send_error(503)
                        return
                    self._write(wav_bytes(), content_type="audio/wav")
                    return
                if self.path == "/v1/tts/enroll-voice":
                    self._json({"voice_id": "stub-enrolled-voice"})
                    return
                self.send_error(404)

            def _asr(self, provider: str) -> None:
                self._json(
                    {
                        "provider": provider,
                        "transcript": "I don't want to go tomorrow",
                        "language": "en",
                        "segments": [],
                        "latency_ms": 1,
                        "status": "success",
                        "error": None,
                    }
                )

            def _json(self, payload: dict) -> None:
                self._write(
                    json.dumps(payload).encode("utf-8"),
                    content_type="application/json",
                )

            def _write(self, body: bytes, *, content_type: str) -> None:
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError):
                    pass

        return Handler


def _intent_proposal(request_payload: dict) -> dict:
    context = request_payload.get("confirmed_context") or {}
    supported = context.get("locked_tokens") or ["i", "don't", "tomorrow"]
    memory_ids = [
        memory["id"]
        for memory in request_payload.get("memories", [])
        if memory.get("text") == "I don't want to go tomorrow."
    ]

    def candidate(
        candidate_id: str,
        text: str,
        ai_added_spans: list[str],
    ) -> dict:
        return {
            "id": candidate_id,
            "text": text,
            "language": "en",
            "patient_supported_spans": supported,
            "ai_added_spans": ai_added_spans,
            "memory_support_ids": memory_ids if candidate_id == "stub-c1" else [],
            "ranking_reasons": ["stub transcript evidence"],
            "risk_level": "ordinary",
            "source_level": "L2",
        }

    return {
        "certain_content": supported,
        "uncertain_content": [],
        "candidates": [
            candidate(
                "stub-c1",
                "I don't want to go tomorrow.",
                ["want to go"],
            ),
            candidate(
                "stub-c2",
                "I don't want to go to the clinic tomorrow.",
                ["want to go to the clinic"],
            ),
            candidate(
                "stub-c3",
                "I don't want to go alone tomorrow.",
                ["want to go alone"],
            ),
        ],
        "clarification_question": None,
        "clarification_options": [],
        "requires_confirmation": True,
    }


@contextmanager
def running_stub_gateway(
    state: StubGatewayState | None = None,
) -> Iterator[StubGateway]:
    gateway = StubGateway(state)
    gateway.start()
    try:
        yield gateway
    finally:
        gateway.close()
