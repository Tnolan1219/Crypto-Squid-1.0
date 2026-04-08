# Deployment Prompt Plan (Reusable)

Use this prompt when you want an agent to deploy a trading bot to Vultr with Vercel control safely:

```text
You are deploying this trading bot to a Vultr VPS with production-safe defaults.

Goals:
1) Keep strategy logic unchanged.
2) Enforce immutable risk defaults: 0.50% risk/trade, 3 max trades/day, 2 max consecutive losses.
3) Set up systemd services, nginx reverse proxy, TLS, and firewall hardening.
4) Expose secure endpoints: /health, /snapshot, /control/status, /control/start, /control/stop with bearer token auth.
5) Integrate a Vercel proxy dashboard where token stays server-side.
6) Provide explicit copy/paste commands and final verification checks.

Constraints:
- Never commit secrets.
- Keep dashboard service bound to localhost and exposed only through nginx.
- Validate kill-switch behavior before marking complete.
- Stop immediately and report if any risk guardrails conflict with immutable rules.

Deliverables:
- Vultr runbook with exact commands.
- systemd files.
- nginx site config.
- Vercel proxy handlers and required environment variable list.
- Risk mitigation checklist and go-live validation checklist.
```
