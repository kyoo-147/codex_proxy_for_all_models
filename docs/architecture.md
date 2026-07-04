# Architecture

The proxy translates Codex-facing Responses API calls into upstream `chat/completions` calls.

## Flow

1. Codex sends `/responses`
2. Proxy maps inputs, tools, and reasoning flags
3. Upstream receives `chat/completions`
4. Proxy maps upstream output back to Codex-friendly response items

## Modules

- `config.py`
  - environment loading
  - runtime config object
- `protocol.py`
  - request and response mapping
  - model catalog payload generation
- `server.py`
  - HTTP server
  - upstream I/O
- `cli.py`
  - local process entrypoint

## Why stdlib only

- smaller attack surface
- easier portability
- no dependency drift
- lower friction for Windows/macOS/Linux users
