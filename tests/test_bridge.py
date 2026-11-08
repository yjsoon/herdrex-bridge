"""Unit tests for the pure logic in hc_rex_bridge. Run: python3 -m unittest -v"""
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


if __name__ == "__main__":
    unittest.main()
