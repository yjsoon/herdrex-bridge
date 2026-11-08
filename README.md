# herdrex-bridge

Show your [hc](https://herdr.dev/core/) (herdr-core) terminals inside [Rex](https://superlogical.com).
Open Rex and see, and type into, the same agents the Herdr app shows. (Installs as `hc-rex-bridge`.)

```
hc terminals                      Rex session "herdr"
  t12  myproject / 1      ──►      ┌ myproject / 1 ┬ myproject / 2 ┬ other / 1 ┐
  t1c  myproject / 2      ──►      │ hc attach t12 │ hc attach t1c │ …         │
  t1b  other / 1          ──►      └───────────────┴───────────────┴───────────┘
```

## What it does

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
- Tested with hc 0.1.14 and Rex 0.1.0-preview.12 on Linux

Both programs are young and the bridge reads their JSON output, so a new release may break it.
Issues and pull requests are welcome.

## Try it

```sh
git clone https://github.com/yjsoon/herdrex-bridge && cd herdrex-bridge
./hc_rex_bridge.py --dry-run   # print what it would do
./hc_rex_bridge.py             # sync, then keep syncing until Ctrl-C
```

Then open the `herdr` session in Rex (`rex ls` lists sessions). It is created as soon as one hc
terminal is live.

## Run it as a service (systemd)

```sh
install -Dm755 hc_rex_bridge.py ~/.local/bin/hc-rex-bridge
install -Dm644 hc-rex-bridge.service ~/.config/systemd/user/hc-rex-bridge.service
systemctl --user daemon-reload
systemctl --user enable --now hc-rex-bridge
```

Logs: `journalctl --user -u hc-rex-bridge -f`. Stop: `systemctl --user disable --now hc-rex-bridge`.

The unit adds `~/.local/bin` to `PATH`; if `hc` or `rex` live elsewhere, edit its `Environment=PATH=`
line. On macOS, run the script from a terminal or a launchd agent instead.

## Options

| Option | Effect |
| --- | --- |
| `--session NAME` | Rex session that holds the windows. Default `herdr`, or `$HERDREX_SESSION` if set. |
| `--observe` | Read-only mirrors: you can watch, but keystrokes and resizes are not sent. The default lets you type. |
| `--once` | Sync one time and exit. |
| `--dry-run` | Print what would change without touching Rex. |

For the service, set options on the `ExecStart=` line (or add `Environment=HERDREX_SESSION=name`)
in `~/.config/systemd/user/hc-rex-bridge.service`, then run
`systemctl --user daemon-reload && systemctl --user restart hc-rex-bridge`.

After changing `--observe` or `--session`, stop the bridge, close the Rex session, then start the
bridge again. It rebuilds the windows with the new settings. (A new `--session` leaves the old
session behind; close that yourself.)

## Good to know

- **Interactive mode shares window size.** If another hc client such as the Herdr app is attached
  too, the clients can fight over the terminal's size. `--observe` avoids that.
- **Closing a mirror only detaches.** The program keeps running in hc; end it with `hc kill <address>`.
- **A window you close by hand stays closed** until the bridge restarts. Close the whole Rex session
  instead and the bridge rebuilds it, with every live terminal, the next time hc reports a terminal
  starting, ending or being renamed (or when the bridge restarts).
- **State** lives in `$XDG_STATE_HOME/hc-rex-bridge/windows.json` (default `~/.local/state/...`) and
  maps terminals to windows. If you delete it, close the Rex session first or you will get duplicate windows.

## Development

```sh
python3 -m unittest -v
```

The tests cover the title, sorting and ordering logic. Everything that calls `hc` and `rex` is
checked by running the bridge against real servers; `--dry-run` is a safe first step.

## License

MIT. See [LICENSE](LICENSE).
