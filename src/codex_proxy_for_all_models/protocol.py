from __future__ import annotations

import time
import uuid


def _append_input_item(messages: list, item: dict) -> None:
    """Append a single Responses API input item to the chat messages list."""
    item_type = item.get("type", "")

    if item_type == "input_text":
        text = (item.get("text") or "").strip()
        if text:
            messages.append({"role": "user", "content": text})
        return

    if item_type == "message":
        role = item.get("role", "assistant")
        content_blocks = item.get("content", [])
        if isinstance(content_blocks, list):
            texts = [b.get("text", "") for b in content_blocks if b.get("type") == "output_text"]
            content = " ".join(t for t in texts if t)
        else:
            content = str(content_blocks) if content_blocks else ""
        if content:
            messages.append({"role": role, "content": content})
        return

    if item_type == "function_call":
        messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [{
                "id": item.get("call_id", item.get("id", "")),
                "type": "function",
                "function": {
                    "name": item.get("name", ""),
                    "arguments": item.get("arguments", "{}"),
                },
            }],
        })
        return

    if item_type == "function_call_output":
        call_id = item.get("call_id", "")
        output = item.get("output", "")
        messages.append({
            "role": "tool",
            "tool_call_id": call_id,
            "content": output,
        })
        return

    # Legacy Messages API items (role + content, no type field)
    role = item.get("role", "user")
    content = item.get("content", "")
    if isinstance(content, list):
        text_parts = []
        for part in content:
            if part.get("type") in {"input_text", "output_text", "text"} and part.get("text"):
                text_parts.append(part["text"])
        content = " ".join(text_parts)
    if content:
        messages.append({"role": role, "content": content})


def responses_to_chat_request(request: dict, upstream_model: str) -> dict:
    messages = []
    instructions = request.get("instructions", "")
    if instructions:
        messages.append({"role": "system", "content": instructions})

    raw_input = request.get("input", request.get("messages", []))
    if isinstance(raw_input, str):
        messages.append({"role": "user", "content": raw_input})
    elif isinstance(raw_input, list):
        for item in raw_input:
            _append_input_item(messages, item)

    chat_request = {
        "model": upstream_model,
        "messages": messages,
        "temperature": request.get("temperature", 1),
        "top_p": request.get("top_p", 1),
        "max_tokens": request.get("max_output_tokens", 16384),
    }

    tools = []
    for tool in request.get("tools", []):
        if tool.get("type") != "function":
            continue
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("parameters", {}),
                },
            }
        )
    if tools:
        chat_request["tools"] = tools
        chat_request["tool_choice"] = request.get("tool_choice", "auto")

    reasoning = request.get("reasoning", {}) or {}
    effort = reasoning.get("effort")
    if effort and effort != "none":
        chat_request["enable_thinking"] = True
    else:
        chat_request["enable_thinking"] = False

    return chat_request


def upstream_to_responses_payload(upstream: dict, upstream_model: str) -> dict:
    choice = (upstream.get("choices") or [{}])[0]
    message = choice.get("message", {})
    usage = upstream.get("usage", {})
    output = []
    for tool_call in message.get("tool_calls") or []:
        function = tool_call.get("function", {})
        output.append(
            {
                "type": "function_call",
                "id": tool_call.get("id", f"fc_{uuid.uuid4().hex[:8]}"),
                "call_id": tool_call.get("id", f"fc_{uuid.uuid4().hex[:8]}"),
                "name": function.get("name", ""),
                "arguments": function.get("arguments", ""),
                "status": "completed",
            }
        )

    content = (message.get("content") or "").strip()
    if content or not output:
        output.append(
            {
                "type": "message",
                "id": f"msg_{uuid.uuid4().hex[:12]}",
                "status": "completed",
                "role": "assistant",
                "content": [{"type": "output_text", "text": content}],
            }
        )

    return {
        "id": f"resp_{uuid.uuid4().hex[:12]}",
        "object": "response",
        "created_at": int(time.time()),
        "status": "in_progress" if message.get("tool_calls") else "completed",
        "model": upstream_model,
        "output": output,
        "usage": {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },
    }


def extract_reasoning_effort(request: dict) -> str:
    reasoning = request.get("reasoning", {}) or {}
    effort = str(reasoning.get("effort", "medium")).strip().lower()
    if effort not in {"low", "medium", "high"}:
        return "medium"
    return effort


def model_catalog_payload(
    model_slug: str,
    display_name: str,
    provider_label: str,
    context_window: int,
    max_output_tokens: int,
) -> dict:
    return {
        "object": "list",
        "models": [
            {
                "slug": model_slug,
                "id": model_slug,
                "display_name": display_name,
                "description": f"{display_name} via {provider_label}",
                "default_reasoning_level": "medium",
                "supported_reasoning_levels": [
                    {"effort": "low", "description": "Fast responses with lighter reasoning"},
                    {"effort": "medium", "description": "Balanced speed and reasoning depth"},
                    {"effort": "high", "description": "Greater reasoning depth for harder tasks"},
                ],
                "shell_type": "shell_command",
                "visibility": "list",
                "supported_in_api": True,
                "priority": 1,
                "additional_speed_tiers": [],
                "service_tiers": [],
                "availability_nux": None,
                "upgrade": None,
                "base_instructions": "You are Codex, a coding agent based on GPT-5.",
                "supports_reasoning_summaries": False,
                "default_reasoning_summary": "none",
                "support_verbosity": False,
                "default_verbosity": None,
                "apply_patch_tool_type": "freeform",
                "web_search_tool_type": "text_and_image",
                "truncation_policy": {"mode": "tokens", "limit": 10000},
                "supports_parallel_tool_calls": True,
                "supports_image_detail_original": False,
                "context_window": context_window,
                "max_context_window": context_window,
                "effective_context_window_percent": 95,
                "experimental_supported_tools": [],
                "input_modalities": ["text"],
                "supports_search_tool": False,
                "use_responses_lite": False,
                "max_output_tokens": max_output_tokens,
            }
        ],
    }
