#!/usr/bin/env python3
"""Mirror live hc (herdr-core) terminals as windows in a Rex session.

Every live hc terminal gets a window in one Rex session (default "herdr") whose
block runs `hc attach <address>`. Window titles come from the terminal's hc
name, falling back to the "where" label that the Herdr app sets (for example
"myproject / 1") and then to the working directory's name. Titles follow
renames, windows are kept sorted by title, and a window closes when its hc
terminal ends.

The bridge reacts to `hc events`, so it never polls. It only calls the `hc` and
`rex` command-line tools; it does not touch either program's files or sockets.

Usage: hc_rex_bridge.py [--observe] [--once] [--dry-run] [--session NAME]
The session name can also be set with the HERDREX_SESSION environment variable.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

# hc event types that can change which terminals exist or what they are called.
# Others (title, status, foreground, size, ...) fire constantly and are ignored.
RELEVANT_EVENTS = {"created", "finished", "labels"}

# Remembers which Rex window mirrors which hc terminal across restarts.
STATE = os.path.join(
    os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state")),
    "hc-rex-bridge", "windows.json",
)


def run(*cmd, check=True):
    """Run a command and return its stdout. Raise RuntimeError on failure."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        raise RuntimeError(f"`{cmd[0]}` not found on PATH") from None
    if check and p.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {p.stderr.strip()}")
    return p.stdout


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def live_hc_terminals():
    data = json.loads(run("hc", "ls", "--json"))
    return {t["address"]: t for t in data["terminals"] if t.get("state") == "live"}


def display_name(addr, t):
    """Window title: hc name, else the Herdr "where" label, else cwd name, else id.

    `t` is the terminal's entry from `hc ls`, which omits some fields; `hc get`
    returns the full record, so prefer it and fall back to `t`.
    """
    full = {}
    try:
        full = json.loads(run("hc", "get", addr))
    except Exception:
        pass
    name = full.get("name") or t.get("name")
    where = (full.get("labels") or {}).get("where") or t.get("where")
    cwd = full.get("cwd") or t.get("cwd") or ""
    return name or where or os.path.basename(cwd.rstrip("/")) or addr


def rex_windows(session):
    """Return {window_id: label} for the group session, or None if it is absent."""
    sessions = json.loads(run("rex", "ls", "--json")).get("sessions", [])
    if not any(x.get("label") == session for x in sessions):
        return None
    data = json.loads(run("rex", "window", "ls", "-s", session, "--json"))
    return {w["window_id"]: w.get("label") or "" for w in data.get("windows", [])}


def natural_key(label):
    """Case-insensitive, number-aware: 'proj / 2' sorts before 'proj / 10'."""
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", label.casefold())]


def sort_windows(session):
    """Order the group session's windows by title (directory, then number)."""
    data = json.loads(run("rex", "window", "ls", "-s", session, "--json"))
    current = [(w["window_id"], w.get("label") or "") for w in data.get("windows", [])]
    wanted = sorted(current, key=lambda w: natural_key(w[1]))
    for i, (wid, label) in enumerate(wanted):
        if current[i][0] != wid:
            run("rex", "window", "move", "-s", session, wid, "--index", str(i + 1))
            current = [w for w in current if w[0] != wid]
            current.insert(i, (wid, label))


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(state, f, indent=1)


class Bridge:
    """Keeps the Rex group session in step with hc's live terminals."""

    def __init__(self, args):
        self.args = args
        self.state = load_state()  # {hc address: rex window id}
        # Terminals this run has already given a window. A window the user closes
        # by hand is not recreated until the bridge restarts. Starts empty, so a
        # restart rebuilds anything that went missing while the bridge was down.
        self.handled = set()

    def reconcile(self):
        """Bring Rex in line with hc: close, rename, open, then sort windows."""
        group = self.args.session
        dry = self.args.dry_run
        hc = live_hc_terminals()
        wins = rex_windows(group)  # None when the group session does not exist
        present = wins or {}
        if wins is None:
            # The whole group session is gone (closed by hand, Rex restarted, or
            # --session changed): rebuild it with every live terminal.
            self.handled.clear()

        # Forget windows that no longer exist in Rex (closed by hand or session gone).
        for addr, wid in list(self.state.items()):
            if wid not in present:
                del self.state[addr]

        # Close windows for hc terminals that ended; keep titles in sync for the rest.
        for addr, wid in list(self.state.items()):
            if addr not in hc:
                log(f"- {group}: {present.get(wid)} [{addr}] (hc terminal gone)")
                if not dry:
                    run("rex", "window", "close", "-s", group, wid, check=False)
                    del self.state[addr]
                    present.pop(wid, None)
                continue
            name = display_name(addr, hc[addr])
            if present.get(wid) != name:
                log(f"~ {group}: {present.get(wid)!r} -> {name!r} [{addr}]")
                if not dry:
                    run("rex", "window", "rename", "-s", group, wid, name)

        # Open windows for new hc terminals.
        for addr, t in sorted(hc.items()):
            if addr in self.state or addr in self.handled:
                continue
            self.handled.add(addr)
            name = display_name(addr, t)
            attach = ["hc", "attach"] + (["--observe"] if self.args.observe else []) + [addr]
            log(f"+ {group}: {name} [{addr}]")
            if dry:
                continue
            cwd = t.get("cwd") or "."
            if wins is None:
                out = run("rex", "new", group, "--window", name, "--cwd", cwd,
                          "--json", "--", *attach)
                wid = json.loads(out)["initial_windows"][0]["window_id"]
                wins = {wid: name}
            else:
                out = run("rex", "window", "new", "-s", group, name, "--focus=false",
                          "--cwd", cwd, "--json", "--", *attach)
                wid = json.loads(out)["window_id"]
            self.state[addr] = wid

        self.handled.update(self.state)
        if not dry:
            save_state(self.state)
            if self.state:
                sort_windows(group)

    def follow(self):
        """Sync once, then re-sync on relevant hc events until interrupted."""
        if self.args.once:
            self.reconcile()
            return
        try:
            self.reconcile()
        except RuntimeError as e:  # e.g. Rex still starting; events will retry
            log(f"initial sync failed: {e}")
        while True:
            p = subprocess.Popen(["hc", "events", "--json"], stdout=subprocess.PIPE, text=True)
            for line in p.stdout:
                try:
                    msg = json.loads(line)
                except ValueError:
                    continue
                # Envelope: params = {type, terminal, seq, data}.
                if msg.get("params", {}).get("type") in RELEVANT_EVENTS:
                    try:
                        self.reconcile()
                    except Exception as e:  # keep running on transient errors
                        log(f"reconcile error: {e}")
            p.wait()
            log("hc events stream ended; reconnecting in 3s")
            time.sleep(3)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--observe", action="store_true",
                    help="watch only: no typing or resizing (default: interactive)")
    ap.add_argument("--once", action="store_true", help="sync once and exit")
    ap.add_argument("--dry-run", action="store_true", help="print actions only")
    ap.add_argument("--session", default=os.environ.get("HERDREX_SESSION", "herdr"),
                    help="Rex session that holds the windows "
                         "(default: $HERDREX_SESSION or 'herdr')")
    args = ap.parse_args()
    try:
        Bridge(args).follow()
    except KeyboardInterrupt:
        pass
    except RuntimeError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
