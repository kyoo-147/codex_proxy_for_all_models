import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


from codex_proxy_for_all_models.protocol import (
    model_catalog_payload,
    responses_to_chat_request,
    upstream_to_responses_payload,
)


class ProtocolTests(unittest.TestCase):
    def test_responses_to_chat_request_maps_tools_and_messages(self):
        request = {
            "instructions": "Be precise",
            "input": [{"role": "user", "content": "Ship it"}],
            "temperature": 0.2,
            "max_output_tokens": 3000,
            "tools": [
                {
                    "type": "function",
                    "name": "shell_command",
                    "description": "Run shell",
                    "parameters": {"type": "object"},
                }
            ],
            "reasoning": {"effort": "medium"},
        }

        mapped = responses_to_chat_request(request, "z-ai/glm-5.2")

        self.assertEqual(mapped["model"], "z-ai/glm-5.2")
        self.assertEqual(mapped["messages"][0], {"role": "system", "content": "Be precise"})
        self.assertEqual(mapped["messages"][1], {"role": "user", "content": "Ship it"})
        self.assertEqual(mapped["temperature"], 0.2)
        self.assertEqual(mapped["max_tokens"], 3000)
        self.assertEqual(mapped["tools"][0]["function"]["name"], "shell_command")
        self.assertEqual(mapped["tool_choice"], "auto")
        self.assertTrue(mapped["enable_thinking"])

    def test_responses_to_chat_request_maps_function_call_and_output(self):
        request = {
            "input": [
                {
                    "type": "function_call",
                    "call_id": "call_1",
                    "name": "shell_command",
                    "arguments": '{"command":"echo hi"}',
                },
                {
                    "type": "function_call_output",
                    "call_id": "call_1",
                    "output": "hi",
                },
            ]
        }

        mapped = responses_to_chat_request(request, "z-ai/glm-5.2")

        self.assertEqual(mapped["messages"][0]["role"], "assistant")
        self.assertEqual(mapped["messages"][0]["tool_calls"][0]["id"], "call_1")
        self.assertEqual(mapped["messages"][0]["tool_calls"][0]["function"]["name"], "shell_command")
        self.assertEqual(mapped["messages"][1], {
            "role": "tool",
            "tool_call_id": "call_1",
            "content": "hi",
        })

    def test_responses_to_chat_request_maps_message_type_with_content_blocks(self):
        request = {
            "input": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "Hello"}],
                }
            ]
        }

        mapped = responses_to_chat_request(request, "z-ai/glm-5.2")

        self.assertEqual(mapped["messages"][0]["role"], "assistant")
        self.assertEqual(mapped["messages"][0]["content"], "Hello")

    def test_responses_to_chat_request_maps_input_text(self):
        request = {
            "input": [
                {"type": "input_text", "text": "write code"}
            ]
        }

        mapped = responses_to_chat_request(request, "z-ai/glm-5.2")

        self.assertEqual(mapped["messages"][0]["role"], "user")
        self.assertEqual(mapped["messages"][0]["content"], "write code")

    def test_upstream_to_responses_payload_maps_function_calls(self):
        upstream = {
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "choices": [
                {
                    "finish_reason": "tool_calls",
                    "message": {
                        "content": "",
                        "tool_calls": [
                            {
                                "id": "call_1",
                                "function": {"name": "shell_command", "arguments": '{"command":"dir"}'},
                            }
                        ],
                    },
                }
            ],
        }

        payload = upstream_to_responses_payload(upstream, "z-ai/glm-5.2")

        self.assertEqual(payload["model"], "z-ai/glm-5.2")
        self.assertEqual(payload["status"], "in_progress")
        self.assertEqual(payload["output"][0]["type"], "function_call")
        self.assertEqual(payload["output"][0]["name"], "shell_command")
        self.assertEqual(payload["usage"]["total_tokens"], 15)

    def test_model_catalog_payload_contains_shell_type(self):
        payload = model_catalog_payload(
            model_slug="qwen/qwen3-8b",
            display_name="Qwen3 8B",
            provider_label="Ollama",
            context_window=262144,
            max_output_tokens=16384,
        )

        model = payload["models"][0]
        self.assertEqual(model["slug"], "qwen/qwen3-8b")
        self.assertEqual(model["display_name"], "Qwen3 8B")
        self.assertEqual(model["shell_type"], "shell_command")
        self.assertEqual(model["context_window"], 262144)


if __name__ == "__main__":
    unittest.main()
