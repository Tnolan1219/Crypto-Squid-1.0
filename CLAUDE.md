# Crypto Squid — CLAUDE.md
> Project type: Python trading bot (workflow)
> Stack: Python 3.11+, Hyperliquid WebSocket + optional SDK execution, SQLite
> Phase: Hyperliquid MVP Validation

## Mission
Automated downside-overreaction reversal bot for Hyperliquid perpetual markets.
Exploits sharp panic flushes and short-horizon mean reversion bounces.
Rule-based. No ML. No prediction. React to forced mechanics.

## Skill Discovery
Obsidian quick-lookup: `C:/Users/tnola/OneDrive/Documents/Obsidian Vault/03_Skills/INDEX.md`
Workspace catalog: `C:/Users/tnola/Downloads/CLAUDE_Foundation2/.claude/skills/SKILLS-INDEX.md`

## PSB Workflow
Plan → Setup → Build.
All docs live in `docs/`. Check `STATE.md` before starting any work.

## Layer Boundaries (CRITICAL — never violate)

### Layer 1 — Immutable Core (Claude may NOT change without explicit approval)
- Risk per trade: 0.50% of capital (stop-aware sizing)
- Max trades per day: 3
- Max consecutive losses before stop: 2
- No market orders — limit orders only
- No shorting in MVP
- Kill switch: `TRADING_ENABLED=false` in `.env` halts all new entries

### Layer 2 — Tunable Parameters (Claude may propose changes via hypotheses.md, test only)
- 3-minute drop threshold by symbol
- Volume spike multiplier vs rolling baseline
- Price z-score threshold
- Stabilization timing and confirmation style
- TP/SL by symbol and hold-time stop

### Layer 3 — Research Memory (Claude may update freely)
- `journal/` trade reviews
- `reports/` summaries
- `strategy/hypotheses.md` experiment proposals
- `docs/regime-definitions.md`

## Self-Improvement Protocol
After every weekly review:
1. Claude classifies each trade: valid-winner / valid-loser / invalid-winner / invalid-loser
2. Claude proposes max 3 parameter experiments — written to `strategy/hypotheses.md` only
3. No live config changes without user approval
4. Append lessons to `C:/Users/tnola/OneDrive/Documents/Obsidian Vault/02_System/lessons.md`
5. Run session-close skill → sync to mem0 (User ID: `Tnolan1219-default-org`)

## State Management
- Always check `STATE.md` before working
- Update `STATE.md` + `changelog.md` after phase gates
- All trade output writes to `data/trades/` and `journal/`

## What Claude Must NOT Do
- Rewrite `strategy/core-rules.md` autonomously
- Change `.env` thresholds without user approval
- Optimize to recent winners (overfitting)
- Change multiple parameters simultaneously
- Run `git push` or deploy to VPS without explicit instruction

## Custom Commands
- `/review-trade <symbol-date>` — generate post-trade review
- `/weekly-review <YYYY-WNN>` — weekly performance analysis
- `/propose-experiments` — generate parameter experiment candidates
