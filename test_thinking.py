import urllib.request, json, ssl, os
ssl._create_default_https_context = ssl._create_unverified_context

# Test enable_thinking parameter
path = os.path.expanduser("~/.codex/glm_proxy.py")
with open(path) as f:
    for line in f:
        if "ZHIPU_KEY" in line and "os.environ" in line:
            import re
            m = re.search(r'"([^"]+)"', line.split("os.environ")[1])
            key = m.group(1) if m else "MISSING"
            break

# Test: enable_thinking=False
d = json.dumps({"model": "glm-5.2", "messages": [{"role": "user", "content": "Say OK"}], "max_tokens": 50, "enable_thinking": False}).encode()
r = urllib.request.Request("https://open.bigmodel.cn/api/paas/v4/chat/completions", data=d, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
try:
    resp = urllib.request.urlopen(r, timeout=60)
    result = json.loads(resp.read())
    c = result.get("choices", [{}])[0].get("message", {})
    print("=== enable_thinking=False ===")
    print("Content:", (c.get("content") or "")[:200])
    print("Has reasoning:", bool(c.get("reasoning_content")))
except Exception as e:
    print("Error:", e)
