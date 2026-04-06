# Runner Machine Policy

This machine is an execution runner. It pulls improvements from GitHub and may publish
suggested changes on a dedicated runner branch. The default branch must remain immutable
on this machine.

## Invariants
- No local edits on the default branch.
- All changes are made on the runner branch only.
- Default branch updates are fast-forward only.
- Secrets live in `.env` and are never committed.

## Branching
- Default branch: `main`
- Runner branch: `runner/Thomas`

## Daily Flow
1. Sync default branch: run `ops/runner_pull.ps1`.
2. Switch to runner branch before any edits.
3. Publish suggestions from runner branch only.

## Publish
- Push the runner branch to GitHub, then open a PR to `main`.
- Use `ops/runner_publish.ps1` for a consistent push.

## GitHub Protections (recommended)
- Protect `main`: no direct pushes, required PRs, required status checks.
- Restrict runner credentials to this repo only.
- Rotate tokens/keys quarterly.
