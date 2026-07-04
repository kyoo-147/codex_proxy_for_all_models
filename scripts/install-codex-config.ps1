$ErrorActionPreference = "Stop"
$codexHome = Join-Path $HOME ".codex"
New-Item -ItemType Directory -Force $codexHome | Out-Null
Copy-Item "$PSScriptRoot\..\config-examples\codex.config.toml" (Join-Path $codexHome "config.toml.proxy-example") -Force
Write-Output "Wrote config example to $codexHome\config.toml.proxy-example"
