"""
GLM Proxy v5.2 — 智谱 API 直连 (crash-resistant)
Codex Responses API → 智谱 Chat Completions (open.bigmodel.cn)
支持 SSE 流式响应

用法:
  set GLM_API_KEY=your_key    (Windows cmd)
  export GLM_API_KEY=your_key (bash)
  python glm_proxy.py
"""
import os, json, time, ssl, uuid, sys, traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import urllib.request
import urllib.error

# ── 配置 ──────────────────────────────────────────────────────
ZHIPU_KEY = os.environ.get("GLM_API_KEY", "")
ZHIPU_BASE = "https://open.bigmodel.cn/api/paas/v4"
ZHIPU_MODEL = "glm-5.2"
LISTEN_PORT = 8787
DEBUG_LOG = os.environ.get("GLM_PROXY_DEBUG", "")  # set to a file path to enable debug logging

# 模块级 SSL 设置（必须在创建 handler 之前）
ssl._create_default_https_context = ssl._create_unverified_context


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """多线程 HTTP 服务器 — 一个请求崩溃不影响其他请求"""
    daemon_threads = True  # 线程随主进程退出
    allow_reuse_address = True


class ProxyHandler(BaseHTTPRequestHandler):

    def handle_one_request(self):
        """覆盖 — 捕获 socket 错误，避免一个断连杀死整个线程"""
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError) as e:
            # 客户端断开 — 静默忽略，不要崩溃
            pass
        except Exception:
            print(f"\n[Handler Crash] Unhandled exception:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            sys.stderr.flush()

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
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "not found"}')

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/models", "/v1/models"):
            self._list_models()
        elif path == "/health":
            self._json(200, {"status": "ok", "provider": "zhipu"})
        else:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.end_headers()

    # ── 智谱 API 调用 ──────────────────────────────────────────
    def _call_zhipu(self, req_data):
        """调用智谱 chat/completions，返回 JSON"""
        url = f"{ZHIPU_BASE}/chat/completions"
        req = urllib.request.Request(
            url,
            data=json.dumps(req_data).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {ZHIPU_KEY}",
                "Content-Type": "application/json",
                "User-Agent": "CodexGLMProxy/5.2",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read())
        except Exception as e:
            import sys
            print(f"[Zhipu Error] {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            raise

    def _extract_text(self, resp):
        """从智谱响应提取文本。content 优先，reasoning 备用。"""
        if "choices" in resp and resp["choices"]:
            msg = resp["choices"][0].get("message", {})
            content = (msg.get("content") or "").strip()
            if content:
                return content
            reasoning = (msg.get("reasoning_content") or msg.get("reasoning") or "").strip()
            return reasoning
        return ""

    # ── Chat Completions 透传 ──────────────────────────────────
    def _proxy_chat(self, body):
        try:
            req_data = json.loads(body)
            req_data["model"] = ZHIPU_MODEL
            resp = self._call_zhipu(req_data)
            self._json(200, self._to_oai(resp, req_data))
        except urllib.error.HTTPError as e:
            eb = e.read().decode("utf-8", errors="replace")[:500]
            self._json(502, {"error": {"message": f"Upstream {e.code}: {eb}", "type": "upstream_error"}})
        except Exception as e:
            self._json(500, {"error": {"message": str(e), "type": "internal_error"}})

    def _to_oai(self, resp, req_data):
        choices = []
        for i, c in enumerate(resp.get("choices", [])):
            msg = c.get("message", {})
            content = msg.get("content") or msg.get("reasoning_content") or msg.get("reasoning") or ""
            choices.append({
                "index": i,
                "message": {"role": msg.get("role", "assistant"), "content": content},
                "finish_reason": c.get("finish_reason", "stop"),
            })
        return {
            "id": resp.get("id", f"chatcmpl-{int(time.time())}"),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": req_data.get("model", ZHIPU_MODEL),
            "choices": choices,
            "usage": resp.get("usage", {}),
        }

    # ── Responses API → Chat Completions ────────────────────────
    def _proxy_responses(self, body):
        try:
            req_data = json.loads(body)

            # DEBUG: log what Codex sends
            if DEBUG_LOG:
                tools = req_data.get("tools")
                reasoning = req_data.get("reasoning", {})
                with open(DEBUG_LOG, "a") as lf:
                    lf.write(f"\n=== REQUEST {time.time()} ===\n")
                    lf.write(f"reasoning={reasoning}\n")
                    lf.write(f"tools_count={len(tools) if tools else 0}\n")
                    lf.write(f"max_tokens={req_data.get('max_output_tokens','?')}\n")
                    lf.write(f"stream={req_data.get('stream')}\n")
                    if tools:
                        lf.write(f"tool_names={[t.get('name') for t in tools[:5]]}\n")
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
                        content = " ".join(
                            c.get("text", "")
                            for c in content
                            if c.get("type") in ("input_text", "output_text")
                        )
                    if content:
                        messages.append({"role": role, "content": content})

            chat_req = {
                "model": ZHIPU_MODEL,
                "messages": messages,
                "max_tokens": max(min(req_data.get("max_output_tokens", 16384), 65536), 2048),
                "temperature": req_data.get("temperature", 1.0),
            }

            # 转发 tool definitions（Responses 格式 → Chat Completions 格式）
            tools = req_data.get("tools")
            if tools:
                chat_tools = []
                for t in tools:
                    if t.get("type") == "function":
                        chat_tools.append({
                            "type": "function",
                            "function": {
                                "name": t.get("name", ""),
                                "description": t.get("description", ""),
                                "parameters": t.get("parameters", {}),
                            }
                        })
                if chat_tools:
                    chat_req["tools"] = chat_tools
                    chat_req["tool_choice"] = req_data.get("tool_choice", "auto")

            # Thinking/推理参数转换（Codex reasoning.effort → Zhipu thinking/enable_thinking）
            reasoning = req_data.get("reasoning", {}) or {}
            effort = reasoning.get("effort", "")
            if effort == "none" or not effort:
                # Codex 不传 reasoning 或 effort=none 时关闭强制思考
                # Zhipu API 忽略 thinking:{type:"disabled"}，需要用 enable_thinking
                chat_req["enable_thinking"] = False
            else:
                chat_req["thinking"] = {"type": "enabled"}

            resp = self._call_zhipu(chat_req)

            # DEBUG: log response
            if DEBUG_LOG:
                with open(DEBUG_LOG, "a") as lf:
                    c0 = resp.get("choices", [{}])[0]
                    msg = c0.get("message", {})
                    lf.write(f"finish_reason={c0.get('finish_reason')}\n")
                    lf.write(f"content_len={len(msg.get('content') or '')}\n")
                    lf.write(f"tool_calls_count={len(msg.get('tool_calls') or [])}\n")
                    lf.write(f"reasoning_len={len(msg.get('reasoning_content') or '')}\n")
                    lf.write(f"usage={resp.get('usage')}\n")

            usage = resp.get("usage", {})

            resp_id = f"resp_{uuid.uuid4().hex[:12]}"
            msg_id = f"msg_{uuid.uuid4().hex[:12]}"
            created_at = int(time.time())

            # 构建 output
            output_items = []
            choice = resp.get("choices", [{}])[0]
            msg = choice.get("message", {})
            finish = choice.get("finish_reason", "stop")

            # 处理 tool_calls
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    output_items.append({
                        "type": "function_call",
                        "id": tc.get("id", f"fc_{uuid.uuid4().hex[:8]}"),
                        "status": "completed",
                        "name": fn.get("name", ""),
                        "arguments": fn.get("arguments", ""),
                        "call_id": tc.get("id", ""),
                    })

            # 处理文本输出
            text = (msg.get("content") or "").strip()
            reasoning = (msg.get("reasoning_content") or msg.get("reasoning") or "").strip()
            if text:
                output_items.append({
                    "type": "message",
                    "id": msg_id,
                    "status": "completed",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": text}],
                })
            elif reasoning and not tool_calls:
                output_items.append({
                    "type": "message",
                    "id": msg_id,
                    "status": "completed",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": reasoning}],
                })
            elif not output_items:
                output_items.append({
                    "type": "message",
                    "id": msg_id,
                    "status": "completed",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": text or reasoning or ""}],
                })

            response_obj = {
                "id": resp_id,
                "object": "response",
                "created_at": created_at,
                "status": "completed" if finish != "tool_calls" else "in_progress",
                "model": ZHIPU_MODEL,
                "output": output_items,
                "usage": {
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "output_tokens": usage.get("completion_tokens", 0),
                    "total_tokens": usage.get("total_tokens", 0),
                },
            }

            if req_data.get("stream"):
                self._sse_stream(resp_id, msg_id, created_at, response_obj)
            else:
                self._json(200, response_obj)

        except urllib.error.HTTPError as e:
            eb = e.read().decode("utf-8", errors="replace")[:500]
            self._json(502, {"error": {"message": f"Upstream {e.code}: {eb}", "type": "upstream_error"}})
        except Exception as e:
            self._json(500, {"error": {"message": str(e), "type": "internal_error"}})

    # ── SSE 流式 ────────────────────────────────────────────────
    def _sse_stream(self, resp_id, msg_id, created_at, response_obj):
        try:
            self._sse_stream_inner(resp_id, msg_id, created_at, response_obj)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            # 客户端中途断开 — 静默吞掉，不要杀死服务器
            pass

    def _sse_stream_inner(self, resp_id, msg_id, created_at, response_obj):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def send_event(event_type, data):
            self.wfile.write(f"event: {event_type}\n".encode("utf-8"))
            self.wfile.write(f"data: {json.dumps(data)}\n\n".encode("utf-8"))
            self.wfile.flush()

        send_event("response.created", {"type": "response.created", "response": response_obj})

        for item in response_obj.get("output", []):
            if item.get("type") == "function_call":
                # 发射 function_call 事件
                send_event("response.output_item.added", {
                    "type": "response.output_item.added",
                    "response_id": resp_id,
                    "output_index": 0,
                    "item": item,
                })
                send_event("response.output_item.done", {
                    "type": "response.output_item.done",
                    "response_id": resp_id,
                    "output_index": 0,
                    "item": item,
                })
            else:
                text = ""
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        text = c.get("text", "")
                if text:
                    send_event("response.output_item.added", {
                        "type": "response.output_item.added", "response_id": resp_id, "output_index": 0,
                        "item": {"type": "message", "id": msg_id, "status": "in_progress", "role": "assistant", "content": []},
                    })
                    send_event("response.content_part.added", {
                        "type": "response.content_part.added", "response_id": resp_id, "item_id": msg_id,
                        "output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": ""},
                    })
                    for i in range(0, len(text), 30):
                        chunk = text[i:i + 30]
                        send_event("response.output_text.delta", {
                            "type": "response.output_text.delta", "response_id": resp_id, "item_id": msg_id,
                            "output_index": 0, "content_index": 0, "delta": chunk,
                        })
                        time.sleep(0.005)
                    send_event("response.output_text.done", {
                        "type": "response.output_text.done", "response_id": resp_id, "item_id": msg_id,
                        "output_index": 0, "content_index": 0, "text": text,
                    })
                    send_event("response.content_part.done", {
                        "type": "response.content_part.done", "response_id": resp_id, "item_id": msg_id,
                        "output_index": 0, "content_index": 0, "part": {"type": "output_text", "text": text},
                    })
                    send_event("response.output_item.done", {
                        "type": "response.output_item.done", "response_id": resp_id, "output_index": 0,
                        "item": {"type": "message", "id": msg_id, "status": "completed", "role": "assistant",
                                 "content": [{"type": "output_text", "text": text}]},
                    })

        send_event("response.completed", {"type": "response.completed", "response": response_obj})

    # ── /models ────────────────────────────────────────────────
    def _list_models(self):
        self._json(200, {
            "object": "list",
            "models": [{
                "id": ZHIPU_MODEL,
                "object": "model",
                "created": int(time.time()),
                "owned_by": "zhipu",
                "slug": ZHIPU_MODEL,
                "display_name": "GLM-5.2 (Zhipu)",
                "supported_reasoning_levels": [
                    {"level": "none", "effort": "none", "name": "None", "description": "No reasoning"},
                    {"level": "low", "effort": "low", "name": "Low", "description": "Minimal reasoning"},
                    {"level": "medium", "effort": "medium", "name": "Medium", "description": "Balanced reasoning"},
                    {"level": "high", "effort": "high", "name": "High", "description": "Extensive reasoning"},
                    {"level": "xhigh", "effort": "xhigh", "name": "X-High", "description": "Maximum reasoning"},
                ],
                "context_window": 1048576,
                "max_output_tokens": 131072,
                "capabilities": {
                    "supports_tool_calls": True,
                    "supports_parallel_tool_calls": False,
                    "supports_vision": False,
                    "supports_streaming": True,
                },
            }],
        })

    # ── 工具 ────────────────────────────────────────────────────
    def _json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))


def main():
    if not ZHIPU_KEY:
        print("ERROR: GLM_API_KEY not set!")
        print("  Windows: set GLM_API_KEY=your_key")
        print("  bash:    export GLM_API_KEY=your_key")
        return

    ssl._create_default_https_context = ssl._create_unverified_context
    print(f"GLM Proxy v5.2 (Zhipu Direct) — crash-resistant")
    print(f"  Listen: http://127.0.0.1:{LISTEN_PORT}")
    print(f"  Upstream: {ZHIPU_BASE}")
    print(f"  Model: {ZHIPU_MODEL}")
    print(f"  Key: {ZHIPU_KEY[:8]}...{ZHIPU_KEY[-4:]}")
    server = ThreadingHTTPServer(("127.0.0.1", LISTEN_PORT), ProxyHandler)
    print(f"  Threading: enabled (daemon threads, safe crash isolation)")
    server.serve_forever()


if __name__ == "__main__":
    main()
