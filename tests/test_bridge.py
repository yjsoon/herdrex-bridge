"""Unit tests for the pure logic in hc_rex_bridge. Run: python3 -m unittest -v"""
import argparse
import importlib.util
import json
import pathlib
import unittest
from unittest import mock

_path = pathlib.Path(__file__).resolve().parent.parent / "hc_rex_bridge.py"
_spec = importlib.util.spec_from_file_location("hc_rex_bridge", _path)
bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bridge)


class NaturalKey(unittest.TestCase):
    def sort(self, labels):
        return sorted(labels, key=bridge.natural_key)

    def test_numbers_sort_numerically(self):
        self.assertEqual(self.sort(["p / 10", "p / 2", "p / 1"]), ["p / 1", "p / 2", "p / 10"])

    def test_case_insensitive_and_grouped_by_name(self):
        self.assertEqual(
            self.sort(["zeta / 1", "Alpha / 2", "alpha / 1"]),
            ["alpha / 1", "Alpha / 2", "zeta / 1"],
        )

    def test_empty_label(self):
        self.assertEqual(self.sort(["b", ""]), ["", "b"])


class DisplayName(unittest.TestCase):
    def name(self, full, listed=None):
        with mock.patch.object(bridge, "run", return_value=json.dumps(full)):
            return bridge.display_name("t1", listed or {})

    def test_name_beats_where(self):
        self.assertEqual(self.name({"name": "build", "labels": {"where": "p / 1"}}), "build")

    def test_where_label(self):
        self.assertEqual(self.name({"name": None, "labels": {"where": "p / 1"}}), "p / 1")

    def test_falls_back_to_directory(self):
        self.assertEqual(self.name({"cwd": "/home/me/proj/"}), "proj")

    def test_falls_back_to_address(self):
        self.assertEqual(self.name({}), "t1")

    def test_hc_get_failure_uses_listing(self):
        with mock.patch.object(bridge, "run", side_effect=RuntimeError("boom")):
            self.assertEqual(bridge.display_name("t1", {"where": "p / 3"}), "p / 3")


class SortWindows(unittest.TestCase):
    def test_moves_only_out_of_place_windows(self):
        listing = {"windows": [
            {"window_id": "w1", "label": "b / 1"},
            {"window_id": "w2", "label": "a / 1"},
            {"window_id": "w3", "label": "a / 2"},
        ]}
        calls = []

        def fake_run(*cmd, check=True):
            calls.append(cmd)
            return json.dumps(listing) if cmd[:3] == ("rex", "window", "ls") else ""

        with mock.patch.object(bridge, "run", side_effect=fake_run):
            bridge.sort_windows("hc")
        moves = [c for c in calls if c[:3] == ("rex", "window", "move")]
        # w2 -> 1, then w3 -> 2; w1 ends up last without its own move.
        self.assertEqual([m[5] for m in moves], ["w2", "w3"])
        self.assertEqual([m[-1] for m in moves], ["1", "2"])


class FakeRex:
    """Stands in for hc and rex so Bridge.reconcile can run without either."""

    def __init__(self, terminals):
        self.terminals = terminals  # {address: terminal dict}
        self.windows = None         # {window_id: label}, or None = no session
        self.created = []           # addresses given a window, in order
        self._n = 0

    def run(self, *cmd, check=True):
        attach = cmd[cmd.index("--") + 1:] if "--" in cmd else []
        self._n += 1
        wid = f"w{self._n}"
        if cmd[:2] == ("rex", "new"):
            self.windows = {wid: cmd[cmd.index("--window") + 1]}
            self.created.append(attach[-1])
            return json.dumps({"initial_windows": [{"window_id": wid}]})
        if cmd[:3] == ("rex", "window", "new"):
            self.windows[wid] = cmd[5]
            self.created.append(attach[-1])
            return json.dumps({"window_id": wid})
        if cmd[:3] == ("rex", "window", "close"):
            self.windows.pop(cmd[5], None)
        return ""

    def patch(self):
        return mock.patch.multiple(
            bridge,
            run=self.run,
            live_hc_terminals=lambda: self.terminals,
            display_name=lambda addr, t: t["name"],
            rex_windows=lambda session: None if self.windows is None else dict(self.windows),
            sort_windows=lambda session: None,
            save_state=lambda state: None,
            load_state=lambda: dict(self.saved),
        )

    saved = {}


def make_bridge(fake, saved=None):
    fake.saved = saved or {}
    args = argparse.Namespace(session="herdr", dry_run=False, observe=False, once=False)
    with fake.patch():
        return bridge.Bridge(args)


class Reconcile(unittest.TestCase):
    def fake(self):
        return FakeRex({"t1": {"name": "a / 1"}, "t2": {"name": "a / 2"}})

    def test_first_run_creates_session_with_every_terminal(self):
        fake = self.fake()
        b = make_bridge(fake)
        with fake.patch():
            b.reconcile()
        self.assertEqual(fake.created, ["t1", "t2"])

    def test_window_closed_by_hand_stays_closed(self):
        fake = self.fake()
        b = make_bridge(fake)
        with fake.patch():
            b.reconcile()
            wid = b.state["t2"]
            del fake.windows[wid]  # user closes one window
            b.reconcile()
        self.assertEqual(fake.created, ["t1", "t2"])

    def test_closed_session_is_rebuilt(self):
        fake = self.fake()
        b = make_bridge(fake)
        with fake.patch():
            b.reconcile()
            fake.windows = None  # user closes the whole session
            b.reconcile()
        self.assertEqual(fake.created, ["t1", "t2", "t1", "t2"])

    def test_restart_rebuilds_windows_missing_while_stopped(self):
        fake = self.fake()
        fake.windows = {"w1": "a / 1"}  # t2's window vanished while stopped
        b = make_bridge(fake, saved={"t1": "w1", "t2": "w9"})
        with fake.patch():
            b.reconcile()
        self.assertEqual(fake.created, ["t2"])

    def test_restart_with_new_session_name_rebuilds_everything(self):
        fake = self.fake()  # no session of the new name exists
        b = make_bridge(fake, saved={"t1": "old1", "t2": "old2"})
        with fake.patch():
            b.reconcile()
        self.assertEqual(fake.created, ["t1", "t2"])

    def test_ended_terminal_window_is_closed(self):
        fake = self.fake()
        b = make_bridge(fake)
        with fake.patch():
            b.reconcile()
            del fake.terminals["t2"]
            b.reconcile()
        self.assertEqual(sorted(fake.windows.values()), ["a / 1"])


if __name__ == "__main__":
    unittest.main()
