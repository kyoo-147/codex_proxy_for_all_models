from __future__ import annotations

import json
import ssl
import traceback
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

from .config import ProxyConfig
from .protocol import (
    model_catalog_payload,
    responses_to_chat_request,
    upstream_to_responses_payload,
)


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def create_server(config: ProxyConfig) -> ThreadingHTTPServer:
    ssl._create_default_https_context = ssl._create_unverified_context

    class ProxyHandler(BaseHTTPRequestHandler):
        def handle_one_request(self):
            try:
                super().handle_one_request()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                pass
            except Exception:
                traceback.print_exc()

        def log_message(self, format, *args):
            return

        def do_OPTIONS(self):
            self.send_response(200)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "*")
            self.end_headers()

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/health":
                self._json(200, {"status": "ok", "provider": config.provider_label.lower()})
                return
            if path in {"/models", "/v1/models"}:
                self._json(
                    200,
                    model_catalog_payload(
                        model_slug=config.upstream_model,
                        display_name=config.upstream_model,
                        provider_label=config.provider_label,
                        context_window=config.context_window,
                        max_output_tokens=config.max_output_tokens,
                    ),
                )
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self):
            path = self.path.split("?")[0]
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)

            if path in {"/responses", "/v1/responses"}:
                request = json.loads(raw.decode("utf-8"))
                upstream_request = responses_to_chat_request(request, config.bridge_upstream_model)
                upstream_response = _call_upstream(config, upstream_request)
                payload = upstream_to_responses_payload(upstream_response, config.upstream_model)
                self._json(200, payload)
                return

            if path in {"/chat/completions", "/v1/chat/completions"}:
                request = json.loads(raw.decode("utf-8"))
                request["model"] = config.bridge_upstream_model
                upstream_response = _call_upstream(config, request)
                self._json(200, upstream_response)
                return

            self.send_response(404)
            self.end_headers()

        def _json(self, status_code: int, payload: dict):
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return ThreadingHTTPServer((config.listen_host, config.listen_port), ProxyHandler)


def _call_upstream(config: ProxyConfig, payload: dict) -> dict:
    headers = {
        "Authorization": f"Bearer {config.bridge_upstream_api_key}",
        "Content-Type": "application/json",
        "User-Agent": "codex-proxy-for-all-models/0.1",
    }
    headers.update(config.extra_headers or {})
    request = urllib.request.Request(
        f"{config.bridge_upstream_base_url}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"Upstream {exc.code}: {body}") from exc
