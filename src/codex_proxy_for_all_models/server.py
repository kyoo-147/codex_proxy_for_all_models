from __future__ import annotations

import json
import os
import ssl
import traceback
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

from .config import ProxyConfig
from .protocol import extract_reasoning_effort, responses_to_chat_request, upstream_to_responses_payload


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def create_server(config: ProxyConfig) -> ThreadingHTTPServer:
    if os.environ.get("CODEX_PROXY_INSECURE_SSL", "").strip().lower() in ("1", "true", "yes"):
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
                from .catalog import build_model_catalog

                self._json(200, build_model_catalog(config))
                return
            self.send_response(404)
            self.end_headers()

        def do_POST(self):
            path = self.path.split("?")[0]
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)

            try:
                if path in {"/responses", "/v1/responses"}:
                    request = json.loads(raw.decode("utf-8"))
                    reasoning_effort = extract_reasoning_effort(request)
                    requested_model = request.get("model")
                    upstream_request = responses_to_chat_request(request, config.bridge_upstream_model)
                    from .providers import call_upstream

                    upstream_response = call_upstream(config, upstream_request, requested_model, reasoning_effort)
                    payload = upstream_to_responses_payload(upstream_response, config.upstream_model)
                    self._json(200, payload)
                    return

                if path in {"/chat/completions", "/v1/chat/completions"}:
                    request = json.loads(raw.decode("utf-8"))
                    reasoning_effort = extract_reasoning_effort(request)
                    requested_model = request.get("model")
                    request["model"] = config.bridge_upstream_model
                    from .providers import call_upstream

                    upstream_response = call_upstream(config, request, requested_model, reasoning_effort)
                    self._json(200, upstream_response)
                    return

                self.send_response(404)
                self.end_headers()
            except json.JSONDecodeError:
                self._json(400, {"error": {"message": "Invalid JSON body", "type": "invalid_request_error"}})
            except RuntimeError as exc:
                msg = str(exc)
                if "429" in msg:
                    self._json(429, {"error": {"message": msg, "type": "rate_limit_error"}})
                elif msg.startswith("Upstream 5"):
                    self._json(502, {"error": {"message": msg, "type": "upstream_error"}})
                elif "401" in msg:
                    self._json(401, {"error": {"message": msg, "type": "authentication_error"}})
                elif "403" in msg:
                    self._json(403, {"error": {"message": msg, "type": "authentication_error"}})
                elif "404" in msg:
                    self._json(404, {"error": {"message": msg, "type": "not_found_error"}})
                else:
                    self._json(502, {"error": {"message": msg, "type": "upstream_error"}})
            except Exception:
                traceback.print_exc()
                self._json(500, {"error": {"message": "Internal server error", "type": "server_error"}})

        def _json(self, status_code: int, payload: dict):
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return ThreadingHTTPServer((config.listen_host, config.listen_port), ProxyHandler)
