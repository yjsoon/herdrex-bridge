# herdrex-bridge

Show your [hc](https://herdr.dev/core/) (herdr-core) terminals inside [Rex](https://superlogical.com).

hc keeps programs and coding agents alive in terminals that outlive any window. Rex is a
multiplexer for working with sessions of terminals. This small bridge makes the two work
together: every live hc terminal appears as a window in a Rex session, and you can open Rex
to see and drive the same agents the Herdr app shows.

```
hc terminals                      Rex session "hc"
  t12  myproject / 1      ──►      ┌ myproject / 1 ┬ myproject / 2 ┬ other / 1 ┐
  t1c  myproject / 2      ──►      │ hc attach t12 │ hc attach t1c │ …         │
  t1b  other / 1          ──►      └───────────────┴───────────────┴───────────┘
```

## What it does

- Creates one Rex session (default `hc`) with a window per live hc terminal. Each window runs
  `hc attach <address>`.
- Titles each window with the terminal's hc `name`, otherwise the `where` label set by the
  Herdr app (for example `myproject / 1`), otherwise the directory name.
- Follows renames, keeps the windows sorted by title (numbers sort numerically), and closes a
  window when its terminal ends.
- Reacts to `hc events`, so there is no polling.

The script and service are installed as `hc-rex-bridge`. It only runs the `hc` and `rex` command-line tools. It reads no private files and talks to no
sockets, and it needs nothing beyond the Python 3 standard library.

## Requirements

- Python 3.8 or newer
- `hc` and `rex` on your `PATH`
- Tested with hc 0.1.14 and Rex 0.1.0-preview.12 on Linux

Both programs are young, and this bridge depends on their command-line output. If a release
changes the JSON that `hc ls --json`, `hc events --json` or `rex window ls --json` print, the
bridge may need updating. Issues and pull requests are welcome.

## Try it

```sh
./hc_rex_bridge.py --dry-run   # print what it would do
./hc_rex_bridge.py --once      # sync once, then exit
./hc_rex_bridge.py             # keep syncing until Ctrl-C
```

## Install as a service (systemd, Linux)

```sh
install -Dm755 hc_rex_bridge.py ~/.local/bin/hc-rex-bridge
install -Dm644 hc-rex-bridge.service ~/.config/systemd/user/hc-rex-bridge.service
systemctl --user daemon-reload
systemctl --user enable --now hc-rex-bridge
```

Check on it with `systemctl --user status hc-rex-bridge` and `journalctl --user -u hc-rex-bridge -f`.
Stop it with `systemctl --user disable --now hc-rex-bridge`.

The unit adds `~/.local/bin` to `PATH`. If `hc` or `rex` live somewhere else, edit the
`Environment=PATH=` line. On macOS, run the script from a launchd agent or a terminal instead.

## Options

| Option | Effect |
| --- | --- |
| `--observe` | Watch only: no typing, no resizing. Default is interactive. |
| `--session NAME` | Rex session that holds the windows (default `hc`). |
| `--once` | Sync one time and exit. |
| `--dry-run` | Print what would change without touching Rex. |

With the service, add options to `ExecStart` in the unit file.

## Behaviour to know about

- **Interactive mode shares window size.** If another hc client such as the Herdr app is
  attached too, the clients can fight over the terminal's size. Use `--observe` to avoid it.
- **Closing a mirror only detaches.** The program keeps running in hc. Use `hc kill <address>`
  to end it.
- **A window you close by hand stays closed** until the bridge restarts.
- **The window-to-terminal mapping** is stored in `~/.local/state/hc-rex-bridge/windows.json`
  (or under `$XDG_STATE_HOME`). Deleting it is safe, but windows already in the session will
  then be duplicated; kill the Rex session first.
- **Titles are Herdr's labels.** The `where` label looks like `directory / number`. Herdr sets
  it, so the numbers can change when you open or close tabs, and the bridge follows.

## License

MIT. See [LICENSE](LICENSE).

## Development

```sh
python3 -m unittest -v
```

The tests cover the title, sorting and ordering logic. The parts that call `hc` and `rex` are
exercised by running the bridge against real servers (`--dry-run` is a safe first check).
