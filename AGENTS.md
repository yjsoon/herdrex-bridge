# Notes for coding agents

Use these steps when a user asks you to set up this repo. README.md has the details.

1. Check prerequisites: `python3 --version` (3.8+), `command -v hc rex`, `hc ls --json` and `rex ls --json` both succeed.
2. Ask the user before you install anything:
   - Should it run as a systemd user service (Linux only) or by hand in a terminal?
   - Interactive (the default, typing reaches the agents) or `--observe` (watch only)?
   - Session name: keep `herdr` or use another?
3. Run `./hc_rex_bridge.py --dry-run` and show the user the output. It changes nothing.
4. To install, follow "Run it as a service" in README.md. Put any options on the `ExecStart=` line of the installed unit before running `enable --now`.
5. Verify with `systemctl --user status hc-rex-bridge` and `rex window ls -s herdr --json`, which should list one window per live hc terminal.
6. Never run `hc kill`, and don't close the user's Rex sessions or windows, without asking.
7. The service runs the copy in `~/.local/bin`. After a `git pull`, re-run the `install` lines, then `systemctl --user restart hc-rex-bridge`.
