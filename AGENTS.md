# Notes for coding agents

Use these steps when a user asks you to set up or change this repo. README.md has the details.
Do the read-only checks first, then ask, then act.

1. Check (read-only): `python3 --version` (3.8+), `command -v hc rex`, `hc ls --json`, `rex ls --json`.
   Also check for an existing install: `ls ~/.local/bin/hc-rex-bridge ~/.config/systemd/user/hc-rex-bridge.service`.
   If one exists this is an update or reconfigure, so `diff hc_rex_bridge.py ~/.local/bin/hc-rex-bridge` and tell the user.
2. Ask before you change anything:
   - How to run it: systemd user service (Linux), or by hand in a terminal? On macOS or without systemd, only run by hand.
   - Interactive (the default, typing reaches the agents) or `--observe` (watch only)?
   - Session name: keep `herdr` or use another?
   - Overwrite the existing install, if you found one?
3. Preview with `./hc_rex_bridge.py --dry-run` and show the user the output. It changes nothing and exits.
4. Install by following "Run it as a service" in README.md. Set options in a drop-in (see "Options" in README.md), not in the installed unit, so a later reinstall does not erase them.
5. Verify: `systemctl --user status hc-rex-bridge`, then `rex window ls -s <session> --json` should list one window per live hc terminal (`hc ls --json`).
6. Never run the bridge in your own shell without `--once` or `--dry-run`: it runs until killed and will block you.
7. Never run `hc kill`, delete `~/.local/state/hc-rex-bridge/windows.json`, or close the user's Rex sessions or windows without asking.
8. After a `git pull`, re-run the `install` lines, then `systemctl --user restart hc-rex-bridge`.
