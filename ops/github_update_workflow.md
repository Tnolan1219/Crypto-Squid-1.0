# GitHub Update Workflow (Runner)

This workflow keeps the runner in sync with GitHub and verifies the update landed cleanly.

## Assumptions
- Default branch is `main`.
- Runner branch is `runner/Thomas`.
- Secrets are in `.env` and are not committed.

## Receive Updates (pull from GitHub)
1. Run: `powershell -ExecutionPolicy Bypass -File ops\runner_pull.ps1`
2. Verify: `git status` shows clean on `main`.

## Verify Update Applied
1. Check latest commit: `git log -1 --oneline`
2. Compare to GitHub: confirm the same commit is shown on the repo page.
3. Run a quick smoke check:
   - `C:\Users\tnola\Downloads\Live Trading Bots\Crypto Squid 1.0 Live\.venv\Scripts\python.exe test_coinbase.py`
   - or `C:\Users\tnola\Downloads\Live Trading Bots\Crypto Squid 1.0 Live\.venv\Scripts\python.exe src\bot_v2.py`

## Publish Suggestions (runner branch)
1. Switch: `git switch runner/Thomas`
2. Make changes and commit.
3. Run: `powershell -ExecutionPolicy Bypass -File ops\runner_publish.ps1`
4. Open a PR from `runner/Thomas` → `main`.

## Failure Handling
- If pull fails or branches diverge, stop and open a PR from another machine.
- Never force-push `main` from the runner.
