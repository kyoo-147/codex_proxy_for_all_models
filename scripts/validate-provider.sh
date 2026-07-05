#!/usr/bin/env bash
# Validate a provider works with the Codex Proxy.
# Usage: ./scripts/validate-provider.sh [base_url]
# Default base_url: http://127.0.0.1:8787

set -euo pipefail

BASE="${1:-http://127.0.0.1:8787}"
PASS=0
FAIL=0

pass() { echo "  ✅ $1"; PASS=$((PASS + 1)); }
fail() { echo "  ❌ $1"; FAIL=$((FAIL + 1)); }

echo "=== Provider validation: $BASE ==="
echo ""

# 1. Health check
echo "--- Health check ---"
HEALTH=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/health")
if [ "$HEALTH" = "200" ]; then
    pass "/health returns 200"
else
    fail "/health returned $HEALTH (expected 200)"
fi

# 2. Models endpoint
echo "--- Models ---"
MODELS=$(curl -s "$BASE/v1/models")
if echo "$MODELS" | python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d['models'])>0; print(d['models'][0]['slug'])" 2>/dev/null; then
    pass "/v1/models returns model catalog"
else
    fail "/v1/models failed or returned empty"
fi

# 3. Basic text round-trip
echo "--- Text round-trip ---"
TEXT_RESP=$(curl -s -X POST "$BASE/v1/responses" \
    -H "Content-Type: application/json" \
    -d '{"input": "hello"}')
TEXT_OK=$(echo "$TEXT_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['output'][0]['content'][0]['text'])" 2>/dev/null)
if [ -n "$TEXT_OK" ]; then
    pass "Text response received: $TEXT_OK"
else
    fail "Text response failed"
fi

# 4. Tool-calling round-trip
echo "--- Tool calling ---"
TOOL_RESP=$(curl -s -X POST "$BASE/v1/responses" \
    -H "Content-Type: application/json" \
    -d '{"input": [{"type":"function_call","call_id":"call_1","name":"shell_command","arguments":"{\"cmd\":\"echo hi\"}"},{"type":"function_call_output","call_id":"call_1","output":"hi"}]}')
TOOL_OK=$(echo "$TOOL_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['output'][0]['type'])" 2>/dev/null)
if [ "$TOOL_OK" = "message" ]; then
    pass "Tool loop returns message response"
else
    fail "Tool loop failed (got: $TOOL_OK)"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
exit $FAIL
