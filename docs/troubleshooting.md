# Troubleshooting

## Codex says key is missing

If your Codex config uses:

```toml
env_key = "DUMMY_API_KEY"
```

set that variable for Codex:

```bash
export DUMMY_API_KEY=dummy
```

or on PowerShell:

```powershell
$env:DUMMY_API_KEY = "dummy"
```

## Upstream returns 404 on `/responses`

That is normal for many non-OpenAI providers. Point Codex at this proxy, not directly at the provider.

## Upstream returns 429

The proxy cannot solve provider-side rate limiting. Reduce load, wait, or switch upstream/provider.

## Codex app shows `Custom`

That usually means Codex recognized a custom provider session. It may not show the exact upstream model name in the app UI.

## Windows app still uses old config

Close the Codex app fully and reopen it. Existing processes may not reload environment variables or config immediately.
