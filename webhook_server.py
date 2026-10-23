"""Minimal HTTP endpoint for signed PayPal invoice webhooks."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable

from modules.trustloop.service import build_runtime_service
from modules.trustloop.webhook_events import process_verified_paypal_event
from modules.webhook_handler import WebhookHandler


MAX_BODY_BYTES = 1_000_000


class TrustLoopWebhookServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address,
        *,
        verifier,
        service_factory: Callable,
    ) -> None:
        super().__init__(server_address, WebhookRequestHandler)
        self.verifier = verifier
        self.service_factory = service_factory


class WebhookRequestHandler(BaseHTTPRequestHandler):
    server: TrustLoopWebhookServer
    protocol_version = "HTTP/1.1"

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path == "/health":
            self._send_json(
                200,
                {
                    "status": "ok",
                    "service": "tradepilot-trustloop-webhook",
                    "store_configured": bool(
                        os.getenv("TRUSTLOOP_STORE_PATH", "").strip()
                    ),
                },
            )
            return
        self._send_json(404, {"error": "not_found"})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
        if self.path != "/paypal/webhook":
            self._send_json(404, {"error": "not_found"})
            return
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "invalid_content_length"})
            return
        if content_length <= 0 or content_length > MAX_BODY_BYTES:
            self._send_json(413, {"error": "invalid_body_size"})
            return

        raw_body = self.rfile.read(content_length)
        try:
            body = raw_body.decode("utf-8")
            event = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"error": "invalid_json"})
            return

        if not self.server.verifier.verify_signature(dict(self.headers.items()), body):
            self._send_json(401, {"error": "signature_verification_failed"})
            return

        service = self.server.service_factory()
        if service.store is None:
            self._send_json(503, {"error": "persistent_store_required"})
            return
        try:
            result = process_verified_paypal_event(event, service)
        except Exception as exc:
            self._send_json(
                500,
                {
                    "error": "processing_failed",
                    "error_type": type(exc).__name__,
                },
            )
            return
        self._send_json(
            200 if result.status != "run_not_found" else 404,
            {
                "status": result.status,
                "processed": result.processed,
                "message": result.message,
                "run_id": result.run_id,
                "state": result.state,
            },
        )

    def log_message(self, format: str, *args) -> None:
        return


def build_server(
    *,
    host: str = "0.0.0.0",
    port: int = 8787,
    verifier=None,
    service_factory: Callable | None = None,
) -> TrustLoopWebhookServer:
    webhook_id = os.getenv("PAYPAL_WEBHOOK_ID", "").strip()
    selected_verifier = verifier or WebhookHandler(
        webhook_id=webhook_id,
        demo_mode=False,
    )
    selected_factory = service_factory or (
        lambda: build_runtime_service(paypal_backend="rest", use_llm=False)
    )
    return TrustLoopWebhookServer(
        (host, port),
        verifier=selected_verifier,
        service_factory=selected_factory,
    )


def main() -> int:
    host = os.getenv("WEBHOOK_HOST", "0.0.0.0")
    port = int(os.getenv("WEBHOOK_PORT", "8787"))
    if not os.getenv("PAYPAL_WEBHOOK_ID", "").strip():
        raise SystemExit("PAYPAL_WEBHOOK_ID is required")
    if not os.getenv("TRUSTLOOP_STORE_PATH", "").strip():
        raise SystemExit("TRUSTLOOP_STORE_PATH is required")
    server = build_server(host=host, port=port)
    print(f"TrustLoop webhook server listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
