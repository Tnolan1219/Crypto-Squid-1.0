# VPS Access and Deploy Contract

## Default deploy path

- Agent deploys by pushing `main`.
- VPS applies updates using `cryptosquid-sync.timer`.
- Agent validates via `/health` and `/snapshot`.

## SSH break-glass requirement

- SSH must remain non-interactive for agent use.
- Required: at least one valid private key in operator environment with root or deploy-user access.
- If key rotation occurs, update authorized key immediately and verify:
  - `ssh -o BatchMode=yes <user>@<vps> "echo ok"`

## Mandatory post-deploy checks

1. `/health` returns `engine_running=true`
2. `/snapshot` returns expected strategy `version` and `strategy_name`
3. `paper_mode=true` and `enable_live_trading=false` unless explicitly changed
