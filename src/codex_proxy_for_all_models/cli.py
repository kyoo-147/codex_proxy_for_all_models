from __future__ import annotations

from .config import load_config
from .server import create_server


def main() -> int:
    config = load_config(__import__("os").environ)
    print(f"Codex Proxy for All Models")
    print(f"  Listen: http://{config.listen_host}:{config.listen_port}")
    print(f"  Upstream: {config.upstream_base_url}")
    print(f"  Model: {config.upstream_model}")
    print(f"  Provider: {config.provider_label}")
    server = create_server(config)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0
