"""
GLM Proxy — Codex + GLM-5.2 协议转换代理
============================================
将 Codex CLI 的 Responses API 转换为智谱 Chat Completions API，
使 Codex 可以使用 GLM-5.2 模型（已实测可用）。

用法:
  export GLM_API_KEY=***    # bash
  set GLM_API_KEY=***        # Windows cmd
  python glm_proxy.py

架构:
  Codex CLI ──Responses API──▶ glm_proxy.py :8787 ──Chat API──▶ open.bigmodel.cn ──▶ GLM-5.2

关键修复:
  - enable_thinking: False  关闭强制思维链（否则 tool call 被 reasoning 占满）
  - SSE 支持 function_call 事件
  - Responses API → Chat Completions 工具格式转换
"""
import os, json, time, ssl, uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.request
import urllib.error

# ── 配置 ──────────────────────────────────────────────────────
ZHIPU_KEY = os.environ.get("GLM_API_KEY", "")
ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4"
ZHIPU_MODEL = "glm-5.2"
LISTEN_PORT = 8787

ssl._create_default_https_context = ssl._create_unverified_context


class ProxyHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        cl = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(cl)
        try:
            body_text = raw.decode("utf-8")
        except UnicodeDecodeError:
            body_text = raw.decode("latin-1")
        body = body_text.encode("utf-8")
        path = self.path.split("?")[0]
        if path in ("/v1/responses", "/responses"):
            self._proxy_responses(body)
        elif path in ("/v1/chat/completions", "/chat/completions"):
            self._proxy_chat(body)
        elif path in ("/v1/models", "/models"):
            self._list_models()
        else:
            self.send_response(404); self.end_headers()
            self.wfile.write(b'{"error": "not found"}')

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/models", "/v1/models"):
            self._list_models()
        elif path == "/health":
            self._json(200, {"status": "ok", "provider": "zhipu"})
        else:
            self.send_response(404); self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        for h, v in [("Access-Control-Allow-Origin","*"),("Access-Control-Allow-Methods","GET,POST,OPTIONS"),("Access-Control-Allow-Headers","*")]:
            self.send_header(h, v)
        self.end_headers()

    def _call_zhipu(self, req_data):
        url = f"{ZHIPU_BASE}/chat/completions"
        req = urllib.request.Request(url, data=json.dumps(req_data).encode("utf-8"),
            headers={"Authorization": f"Bearer {ZHIPU_KEY}","Content-Type":"application/json","User-Agent":"CodexGLMProxy/5.1"},
            method="POST")
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read())

    def _proxy_chat(self, body):
        try:
            req_data = json.loads(body)
            req_data["model"] = ZHIPU_MODEL
            resp = self._call_zhipu(req_data)
            self._json(200, self._to_oai(resp, req_data))
        except urllib.error.HTTPError as e:
            self._json(502, {"error": {"message": f"Upstream {e.code}", "type": "upstream_error"}})
        except Exception as e:
            self._json(500, {"error": {"message": str(e), "type": "internal_error"}})

    def _to_oai(self, resp, req_data):
        choices = []
        for i, c in enumerate(resp.get("choices", [])):
            msg = c.get("message", {})
            content = msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning") or ""
            choices.append({"index": i, "message": {"role": msg.get("role","assistant"), "content": content},
                "finish_reason": c.get("finish_reason", "stop")})
        return {"id": resp.get("id", ""), "object": "chat.completion", "created": int(time.time()),
            "model": req_data.get("model", ZHIPU_MODEL), "choices": choices, "usage": resp.get("usage", {})}

    def _proxy_responses(self, body):
        try:
            req_data = json.loads(body)
            instructions = req_data.get("instructions", "")
            inp = req_data.get("input", req_data.get("messages", []))
            messages = []
            if instructions:
                messages.append({"role": "system", "content": instructions})
            if isinstance(inp, str):
                messages.append({"role": "user", "content": inp})
            elif isinstance(inp, list):
                for item in inp:
                    role = item.get("role", "user")
                    content = item.get("content", "")
                    if isinstance(content, list):
                        content = " ".join(c.get("text","") for c in content if c.get("type") in ("input_text","output_text"))
                    if content:
                        messages.append({"role": role, "content": content})

            chat_req = {"model": ZHIPU_MODEL, "messages": messages,
                "max_tokens": max(min(req_data.get("max_output_tokens", 16384), 65536), 2048),
                "temperature": req_data.get("temperature", 1.0)}

            # 工具格式转换
            tools = req_data.get("tools")
            if tools:
                chat_tools = []
                for t in tools:
                    if t.get("type") == "function":
                        chat_tools.append({"type": "function", "function": {
                            "name": t.get("name",""), "description": t.get("description",""),
                            "parameters": t.get("parameters",{})}})
                if chat_tools:
                    chat_req["tools"] = chat_tools
                    chat_req["tool_choice"] = req_data.get("tool_choice", "auto")

            # 关键：关闭强制思维链，否则 tool call 被 reasoning 消耗
            reasoning = req_data.get("reasoning", {}) or {}
            effort = reasoning.get("effort", "")
            if effort == "none" or not effort:
                chat_req["enable_thinking"] = False
            else:
                chat_req["thinking"] = {"type": "enabled"}

            resp = self._call_zhipu(chat_req)
            usage = resp.get("usage", {})
            resp_id = f"resp_{uuid.uuid4().hex[:12]}"
            msg_id = f"msg_{uuid.uuid4().hex[:12]}"
            created_at = int(time.time())

            output_items = []
            choice = resp.get("choices", [{}])[0]
            msg = choice.get("message", {})
            finish = choice.get("finish_reason", "stop")

            # 解析 tool_calls
            for tc in msg.get("tool_calls") or []:
                fn = tc.get("function", {})
                output_items.append({"type": "function_call", "id": tc.get("id", f"fc_{uuid.uuid4().hex[:8]}"),
                    "status": "completed", "name": fn.get("name",""), "arguments": fn.get("arguments",""),
                    "call_id": tc.get("id","")})

            text = (msg.get("content") or "").strip()
            reasoning_text = (msg.get("reasoning_content") or msg.get("reasoning") or "").strip()
            output_text = text or (reasoning_text if not output_items else "") or ""

            output_items.append({"type": "message", "id": msg_id, "status": "completed",
                "role": "assistant", "content": [{"type": "output_text", "text": output_text}]})

            response_obj = {"id": resp_id, "object": "response", "created_at": created_at,
                "status": "completed" if finish != "tool_calls" else "in_progress",
                "model": ZHIPU_MODEL, "output": output_items,
                "usage": {"input_tokens": usage.get("prompt_tokens",0),
                    "output_tokens": usage.get("completion_tokens",0),
                    "total_tokens": usage.get("total_tokens",0)}}

            if req_data.get("stream"):
                self._sse_stream(resp_id, msg_id, created_at, response_obj)
            else:
                self._json(200, response_obj)

        except urllib.error.HTTPError as e:
            self._json(502, {"error": {"message": f"Upstream {e.code}", "type": "upstream_error"}})
        except Exception as e:
            self._json(500, {"error": {"message": str(e), "type": "internal_error"}})

    def _sse_stream(self, resp_id, msg_id, created_at, response_obj):
        self.send_response(200)
        for h, v in [("Content-Type","text/event-stream"),("Cache-Control","no-cache"),
                      ("Connection","keep-alive"),("Access-Control-Allow-Origin","*")]:
            self.send_header(h, v)
        self.end_headers()

        def send_event(evt, data):
            self.wfile.write(f"event: {evt}\n".encode("utf-8"))
            self.wfile.write(f"data: {json.dumps(data)}\n\n".encode("utf-8"))
            self.wfile.flush()

        send_event("response.created", {"type": "response.created", "response": response_obj})

        for item in response_obj.get("output", []):
            if item.get("type") == "function_call":
                send_event("response.output_item.added", {"type": "response.output_item.added",
                    "response_id": resp_id, "output_index": 0, "item": item})
                send_event("response.output_item.done", {"type": "response.output_item.done",
                    "response_id": resp_id, "output_index": 0, "item": item})
            else:
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        text = c.get("text", "")
                        if text:
                            send_event("response.output_item.added", {"type": "response.output_item.added",
                                "response_id": resp_id, "output_index": 0,
                                "item": {"type": "message", "id": msg_id, "status": "in_progress",
                                    "role": "assistant", "content": []}})
                            send_event("response.content_part.added", {"type": "response.content_part.added",
                                "response_id": resp_id, "item_id": msg_id,
                                "output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": ""}})
                            for i in range(0, len(text), 30):
                                chunk = text[i:i+30]
                                send_event("response.output_text.delta", {"type": "response.output_text.delta",
                                    "response_id": resp_id, "item_id": msg_id, "output_index": 0,
                                    "content_index": 0, "delta": chunk})
                                time.sleep(0.005)
                            send_event("response.output_text.done", {"type": "response.output_text.done",
                                "response_id": resp_id, "item_id": msg_id, "output_index": 0,
                                "content_index": 0, "text": text})
                            send_event("response.content_part.done", {"type": "response.content_part.done",
                                "response_id": resp_id, "item_id": msg_id, "output_index": 0,
                                "content_index": 0, "part": {"type": "output_text", "text": text}})
                            send_event("response.output_item.done", {"type": "response.output_item.done",
                                "response_id": resp_id, "output_index": 0,
                                "item": {"type": "message", "id": msg_id, "status": "completed",
                                    "role": "assistant", "content": [{"type": "output_text", "text": text}]}})

        send_event("response.completed", {"type": "response.completed", "response": response_obj})

    def _list_models(self):
        self._json(200, {"object": "list", "models": [{
            "id": ZHIPU_MODEL, "object": "model", "created": int(time.time()), "owned_by": "zhipu",
            "slug": ZHIPU_MODEL, "display_name": "GLM-5.2 (Zhipu)",
            "supported_reasoning_levels": [
                {"level": "none", "effort": "none", "name": "None", "description": "No reasoning"},
                {"level": "low", "effort": "low", "name": "Low", "description": "Minimal reasoning"},
                {"level": "medium", "effort": "medium", "name": "Medium", "description": "Balanced reasoning"},
                {"level": "high", "effort": "high", "name": "High", "description": "Extensive reasoning"},
                {"level": "xhigh", "effort": "xhigh", "name": "X-High", "description": "Maximum reasoning"}],
            "context_window": 1048576, "max_output_tokens": 131072,
            "capabilities": {"supports_tool_calls": True, "supports_parallel_tool_calls": False,
                "supports_vision": False, "supports_streaming": True}}]})

    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))


def main():
    if not ZHIPU_KEY:
        print("ERROR: GLM_API_KEY not set!")
        print("  export GLM_API_KEY=***     # bash")
        print("  set GLM_API_KEY=***         # Windows cmd")
        return
    print(f"GLM Proxy v5.1 — http://127.0.0.1:{LISTEN_PORT}")
    print(f"  Upstream: {ZHIPU_BASE}  |  Model: {ZHIPU_MODEL}")
    HTTPServer(("127.0.0.1", LISTEN_PORT), ProxyHandler).serve_forever()

if __name__ == "__main__":
    main()
