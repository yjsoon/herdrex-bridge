# herdrex-bridge details

The full reference. [README.md](README.md) has the short version; coding agents should follow
[AGENTS.md](AGENTS.md).

## How it works

```
hc terminals                      Rex session "herdr"
  t12  myproject / 1      ──►      ┌ myproject / 1 ┬ myproject / 2 ┬ other / 1 ┐
  t1c  myproject / 2      ──►      │ hc attach t12 │ hc attach t1c │ …         │
  t1b  other / 1          ──►      └───────────────┴───────────────┴───────────┘
```

- Puts every live hc terminal in one Rex session (default `herdr`), one window each, running
  `hc attach <address>`.
- Titles each window with the terminal's hc `name`, otherwise Herdr's `where` label
  (`directory / tab number`, for example `myproject / 1`; it renumbers as tabs open and close),
  otherwise the directory name.
- Follows renames, keeps windows sorted by title (numbers sort numerically), and closes a window
  when its terminal ends.

It only calls the `hc` and `rex` command-line tools (no sockets, no other program's files) and
needs only the Python 3 standard library.

## Requirements

- Python 3.8+, with `hc` and `rex` on your `PATH`
- [herdr-core](https://herdr.dev/core/) (`hc`): `curl -fsSL https://releases.herdr.dev/core/install.sh | sh`
  on macOS or Linux ([docs](https://herdr.dev/guide/), [source](https://github.com/herdrdev/herdr-core))
- [Rex](https://superlogical.com): **in a staged beta at the time of writing (November 2026).** Access is by
  [waitlist](https://superlogical.com/updates/public-testing-beginning), and only the macOS app is in
  testing, though Rex servers also run on Linux. There is no public install guide yet, so follow what
  you are sent.
- Tested with hc 0.1.14 and Rex 0.1.0-preview.12 on Linux

Both programs are young and the bridge reads their JSON output, so a new release may break it.
Issues and pull requests are welcome.

## Running by hand

```sh
./herdrex_bridge.py --dry-run   # print what it would do, then exit
./herdrex_bridge.py             # sync, then keep syncing until Ctrl-C (use --once to sync and exit)
```

Then open the `herdr` session in Rex (`rex ls` lists sessions). With no live hc terminal the bridge
does nothing and the session does not exist yet; it appears with the first terminal. When the last
terminal ends, the session stays, empty. Without systemd (for example on macOS), this by-hand run is
the way to use it: it logs to the terminal and stops with Ctrl-C. No launchd file is provided and it
is untested there.

## Run it as a service (systemd)

```sh
install -Dm755 herdrex_bridge.py ~/.local/bin/herdrex-bridge
install -Dm644 herdrex-bridge.service ~/.config/systemd/user/herdrex-bridge.service
systemctl --user daemon-reload
systemctl --user enable --now herdrex-bridge
```

Logs: `journalctl --user -u herdrex-bridge -f`. Stop: `systemctl --user disable --now herdrex-bridge`.
After a `git pull`, re-run the `install` lines, then `systemctl --user restart herdrex-bridge`.

The unit adds `~/.local/bin` to `PATH`; if `hc` or `rex` live elsewhere, edit its `Environment=PATH=`
line. If they are missing from `PATH` the service stops with an error instead of restarting forever.
On a remote or headless machine, everything stops at your last logout unless your user lingers. That
covers the bridge, the hc core, and a Rex server run as a user service. Check with
`loginctl show-user $USER -p Linger`; if it says `no`, run `sudo loginctl enable-linger $USER`.

### Switching from the old name (hc-rex-bridge)

This program used to be called `hc-rex-bridge`. An install under the old name keeps working until you
switch, and the new version moves the old state file for you on its first start, so no windows are
duplicated. To switch (Linux, systemd):

```sh
systemctl --user disable --now hc-rex-bridge
# Only if you made a drop-in (systemctl --user edit):
mv ~/.config/systemd/user/hc-rex-bridge.service.d ~/.config/systemd/user/herdrex-bridge.service.d
rm ~/.config/systemd/user/hc-rex-bridge.service ~/.local/bin/hc-rex-bridge
install -Dm755 herdrex_bridge.py ~/.local/bin/herdrex-bridge
install -Dm644 herdrex-bridge.service ~/.config/systemd/user/herdrex-bridge.service
systemctl --user daemon-reload
systemctl --user enable --now herdrex-bridge
```

If the drop-in has an `ExecStart=` line, change `hc-rex-bridge` to `herdrex-bridge` in it. Do not delete
`~/.local/state/hc-rex-bridge/windows.json`; the bridge moves it to `~/.local/state/herdrex-bridge/`.
Check with `systemctl --user status herdrex-bridge` and compare `rex window ls -s herdr --json` with
`hc ls --json`: one window per live terminal. If you run it by hand, just run the new script.

## Using it from another machine

The point is to reach your hc terminals from a Rex client elsewhere. Run the bridge on the **host**,
the machine where the hc terminals live. That host also needs `hc` and a Rex server, because the
bridge talks to both locally. Your laptop only needs a Rex client.

1. **On the host:** install `hc` and Rex (see [Requirements](#requirements)), start the bridge, and
   make the Rex server reachable, for example `rex server tailscale on`, or start it with
   `--extra-listen tailnet://:7297` as the author does. See `rex server start --help`.
2. **On your laptop:** `rex hosts add box box.your-tailnet.ts.net`, then `rex -S box ls` should list
   the `herdr` session. The Rex app lists the same hosts.

Keep the whole stack running on the host (see [Run it as a service](#run-it-as-a-service-systemd)),
not just the bridge. After a reboot the unit starts the hc core (`hc server start`), Rex needs its own
service (for example a user unit that runs `rex server run`), and the bridge then rebuilds the windows.
Terminals that were running come back as fresh shells; hc does not resume interrupted agent runs.

hc can also reach other machines over ssh (`hc machine add`); the bridge has not been tried with
that, so run one bridge per host.

## Options

| Option | Effect |
| --- | --- |
| `--session NAME` | Rex session that holds the windows. Default `herdr`, or `$HERDREX_SESSION` if set. |
| `--observe` | Read-only mirrors: you can watch, but keystrokes and resizes are not sent. The default lets you type. |
| `--once` | Sync one time and exit. |
| `--dry-run` | Print what would change without touching Rex, then exit. |

For the service, set options in a drop-in so reinstalling the unit does not erase them. Run
`systemctl --user edit herdrex-bridge` and enter, for example:

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/env python3 -I %h/.local/bin/herdrex-bridge --observe --session work
```

Saving it restarts nothing, so then run `systemctl --user restart herdrex-bridge`. To change only the
session name, `Environment=HERDREX_SESSION=work` in the drop-in is enough.

After changing `--observe` or `--session`, stop the bridge, close the Rex session
(`rex kill herdr`, using your session's name), then start the bridge again. It rebuilds the windows
with the new settings. Existing windows keep the settings they were created with. A new `--session`
leaves the old session behind; close that yourself.

## Good to know

- **Interactive mode shares window size.** If another hc client such as the Herdr app is attached
  too, the clients can fight over the terminal's size. `--observe` avoids that.
- **Closing a mirror only detaches.** The program keeps running in hc; end it with `hc kill <address>`.
- **A window you close by hand stays closed** until the bridge restarts. Close the whole Rex session
  instead and the bridge rebuilds it, with every live terminal, the next time hc reports a terminal
  starting, ending or being renamed (or when the bridge restarts).
- **State** lives in `$XDG_STATE_HOME/herdrex-bridge/windows.json` (default `~/.local/state/...`) and
  maps terminals to windows. If you delete it, close the Rex session first or you will get duplicate windows.

## Development

```sh
python3 -m unittest discover -s tests -v
```

The tests use stand-ins for `hc` and `rex`, so they need neither installed.
