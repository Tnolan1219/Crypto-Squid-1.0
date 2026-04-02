# Oracle Cloud Free Paper Runtime Skill

## Purpose
Deploy Crypto Squid paper runtime to Oracle Cloud Free Tier as always-on services, without modifying strategy code.

## Use When
- User asks to keep bot running while local computer is off
- User asks for low-cost or free 24/7 runtime
- User asks for Oracle Cloud deployment steps

## Do Not
- Do not change trading logic in `src/`
- Do not switch to live execution flags automatically
- Do not expose dashboard publicly without security warning

## Inputs Required
- Oracle VM public IP
- SSH key path
- Repo URL or local archive source
- Desired run mode (paper only for this workflow)

## Workflow
1. Provision Always Free Ubuntu VM.
2. Install runtime dependencies (`python3`, `python3-venv`, `git`).
3. Deploy repo to `/opt/cryptosquid`.
4. Create `.env` from current known-good paper config.
5. Install systemd units:
   - `cryptosquid-bot.service`
   - `cryptosquid-dashboard.service`
6. Enable/start services and verify health.
7. Validate dashboard endpoint and runtime state updates.

## Verification Commands
- `sudo systemctl status cryptosquid-bot`
- `sudo systemctl status cryptosquid-dashboard`
- `journalctl -u cryptosquid-bot -f`
- `journalctl -u cryptosquid-dashboard -f`

## Success Criteria
- Both services are active and enabled
- Bot restarts automatically on failure/reboot
- Dashboard reachable and showing fresh state
- No source code changes required

## Rollback
1. `sudo systemctl stop cryptosquid-bot cryptosquid-dashboard`
2. `sudo systemctl disable cryptosquid-bot cryptosquid-dashboard`
3. Remove unit files from `/etc/systemd/system/`
4. `sudo systemctl daemon-reload`
