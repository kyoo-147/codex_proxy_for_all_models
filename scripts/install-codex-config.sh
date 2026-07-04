#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$HOME/.codex"
cp "$(dirname "$0")/../config-examples/codex.config.toml" "$HOME/.codex/config.toml.proxy-example"
echo "Wrote config example to $HOME/.codex/config.toml.proxy-example"
