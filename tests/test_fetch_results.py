#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for the results-sync engine (scripts/fetch_results.py).

Runnable with plain stdlib: ``python -m unittest discover -s tests -v``.
Zero network access — the one web-source test mocks urllib.
"""
import json
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import fetch_results as fr  # noqa: E402

FIXTURE = os.path.join(HERE, "fixtures", "feed_sample.json")


class _MockResp:
    """A tiny file-like/context-manager stand-in for an HTTP response."""

    def __init__(self, payload):
        self._data = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _mock_urlopen(payload):
    """A network-free replacement for the module's HTTP opener, serving
    ``payload`` as JSON so source parsers can be tested offline."""

    def _open(req, timeout=0):  # mock: signature-compatible, never hits network
        return _MockResp(payload)

    return _open


class RoundTripTests(unittest.TestCase):
    def test_res_roundtrip_with_endash_note(self):
        res = {"M9": (2, 0, "Spain", ""),
               "M10": (0, 0, "Brazil", "AET"),
               "M74": (1, 1, "Paraguay", "4\u20133 pens")}
        self.assertEqual(fr.parse_res_block(fr.render_res(res)), res)

    def test_upcoming_roundtrip(self):
        up = {"M97": "Thu Jul 9", "M101": "Tue Jul 14"}
        self.assertEqual(fr.parse_upcoming_block(fr.render_upcoming(up)), up)

    def test_rendered_notes_have_no_braces(self):
        # RES=\{[^}]*\} stops at the first '}', so a note containing a brace would
        # truncate the rewritten block on the next sync. Guard the invariant.
        res = {"M74": (1, 1, "Paraguay", "4\u20133 pens"),
               "M88": (1, 1, "Egypt", "4\u20132 pens")}
        block = fr.render_res(res)
        body = block[block.index("{") + 1: block.rindex("}")]
        self.assertNotIn("{", body)
        self.assertNotIn("}", body)


class ExtractionTests(unittest.TestCase):
    def setUp(self):
        with open(fr.GEN, encoding="utf-8") as fh:
            self.gen = fh.read()

    def test_read_r32_returns_16_fixtures(self):
        r32 = fr.read_r32(self.gen)
        self.assertEqual(len(r32), 16)
        for code, a, b in r32:
            self.assertRegex(code, r"^M\d+$")
            self.assertTrue(a and b)

    def test_parse_ko_feed_15_codes_excludes_m103(self):
        ko = fr.parse_ko_feed(self.gen)
        self.assertEqual(len(ko), 15)          # M89-M102 + M104
        self.assertIn("M89", ko)
        self.assertIn("M104", ko)              # the Final
        self.assertNotIn("M103", ko)           # third-place playoff intentionally out


class ShootoutTests(unittest.TestCase):
    def test_footballdata_unfolds_penalty_shootout(self):
        # A 1-1 game won 4-3 on penalties. football-data folds the shootout goals
        # into fullTime (home 1+3=4, away 1+4=5); the parser must recover the level
        # 1-1 regulation score and a "4-3 pens" note, with no network.
        payload = {"matches": [{
            "status": "FINISHED",
            "homeTeam": {"name": "Switzerland"}, "awayTeam": {"name": "Algeria"},
            "score": {"winner": "AWAY_TEAM",
                      "fullTime": {"home": 4, "away": 5},
                      "penalties": {"home": 3, "away": 4}},
            "stage": "LAST_16", "utcDate": "2026-07-04T20:00:00Z"}]}
        with mock.patch.dict(os.environ, {"FOOTBALL_DATA_TOKEN": "x"}), \
                mock.patch.object(fr.urllib.request, "urlopen", _mock_urlopen(payload)):
            feed = fr.results_from_footballdata({})
        self.assertEqual(len(feed), 1)
        g = feed[0]
        self.assertEqual((g["gh"], g["ga"]), (1, 1))
        self.assertEqual(g["winner"], "Algeria")
        self.assertEqual(g["note"], "4\u20133 pens")


class MergeResTests(unittest.TestCase):
    def test_keeps_curated_decider_note(self):
        old = (1, 1, "Paraguay", "4\u20133 pens")
        new = (1, 1, "Paraguay", "")           # a source mangled the shootout away
        self.assertEqual(fr.merge_res(old, new), (old, False))

    def test_takes_a_brand_new_result(self):
        self.assertEqual(fr.merge_res(None, (2, 0, "Spain", "")),
                         ((2, 0, "Spain", ""), True))

    def test_takes_a_genuinely_changed_result(self):
        val, changed = fr.merge_res((0, 0, "", "draw"), (2, 1, "Italy", ""))
        self.assertTrue(changed)
        self.assertEqual(val, (2, 1, "Italy", ""))

    def test_identical_is_not_a_change(self):
        v = (2, 1, "Italy", "")
        self.assertEqual(fr.merge_res(v, v), (v, False))


class MatchAllTests(unittest.TestCase):
    def test_draw_never_enters_res(self):
        r32 = [("M79", "Mexico", "Ecuador")]
        feed = [{"home": "Mexico", "away": "Ecuador", "gh": 0, "ga": 0,
                 "winner": "", "note": "draw", "date": "2026-06-20", "stage": ""}]
        res, _ = fr.match_all(r32, {}, {}, feed)
        self.assertNotIn("M79", res)

    def test_winner_is_always_a_bracket_team(self):
        # Guards the ELIM inference: a normalization miss must never write a
        # winner that is neither of the fixture's two teams.
        feed = fr.results_from_json(FIXTURE, fr.load_team_map())
        r32 = [("M83", "Portugal", "Croatia"), ("M88", "Australia", "Egypt")]
        res, _ = fr.match_all(r32, {}, {}, feed)
        for code, a, b in r32:
            if code in res:
                self.assertIn(res[code][2], (a, b))

    def test_idempotent_on_second_apply(self):
        r32 = [("M74", "Germany", "Paraguay"), ("M77", "France", "Sweden")]
        feed = [
            {"home": "Germany", "away": "Paraguay", "gh": 2, "ga": 1, "winner": "Germany",
             "note": "", "date": "2026-06-29", "stage": "Round of 32"},
            {"home": "France", "away": "Sweden", "gh": 3, "ga": 0, "winner": "France",
             "note": "", "date": "2026-06-30", "stage": "Round of 32"},
        ]
        res1, _ = fr.match_all(r32, {}, {}, feed)
        res2, _ = fr.match_all(r32, {}, res1, feed)
        self.assertEqual(res1, res2)
        changed = [c for c in res2 if fr.merge_res(res1.get(c), res2[c])[1]]
        self.assertEqual(changed, [])

    def test_pair_collision_resolves_knockout_not_group(self):
        # France & Spain meet in the group stage AND (synthetically) in a later
        # knockout round; both meetings share the frozenset key. The knockout
        # result must win regardless of feed order — the pre-fix code let the
        # last-in-feed entry (here, the group game) silently win.
        r32 = [("M74", "France", "Germany"), ("M77", "Spain", "Italy")]
        ko_feed = {"M89": ("M74", "M77")}
        base = [
            {"home": "France", "away": "Germany", "gh": 2, "ga": 0, "winner": "France",
             "note": "", "date": "2026-06-29", "stage": "Round of 32"},
            {"home": "Spain", "away": "Italy", "gh": 1, "ga": 0, "winner": "Spain",
             "note": "", "date": "2026-06-30", "stage": "Round of 32"},
        ]
        knockout = {"home": "Spain", "away": "France", "gh": 2, "ga": 1, "winner": "Spain",
                    "note": "", "date": "2026-07-15", "stage": "Semi-final"}
        group = {"home": "France", "away": "Spain", "gh": 1, "ga": 0, "winner": "France",
                 "note": "", "date": "2026-06-18", "stage": "Group Stage"}
        feed = base + [knockout, group]        # group meeting last on purpose
        res, _ = fr.match_all(r32, ko_feed, {}, feed)
        self.assertEqual(res["M89"][2], "Spain")            # not the group winner France
        self.assertEqual(sorted(res["M89"][:2]), [1, 2])    # the 2-1 knockout, not 1-0


class SourceAndHighlightTests(unittest.TestCase):
    def test_team_name_normalization(self):
        feed = fr.results_from_json(FIXTURE, fr.load_team_map())
        pairs = {frozenset((g["home"], g["away"])) for g in feed}
        self.assertIn(frozenset(("Bosnia & Herz.", "Norway")), pairs)
        for g in feed:
            self.assertNotIn("Bosnia and Herzegovina", (g["home"], g["away"]))

    def test_draw_kept_out_of_results_but_shape_ok(self):
        feed = fr.results_from_json(FIXTURE, fr.load_team_map())
        draw = next(g for g in feed if g["home"] == "Ghana")
        self.assertEqual(draw["winner"], "")
        self.assertEqual(draw["note"], "draw")

    def test_auto_hl_block_has_no_stray_bracket(self):
        # The AUTO_HL=\[.*?\] rewrite is non-greedy; a ']' inside any card would
        # truncate the block. The emitted block must contain ']' only as its close.
        feed = fr.results_from_json(FIXTURE, fr.load_team_map())
        block = fr.render_auto_hl(fr.build_auto_hl(feed))
        self.assertTrue(block.startswith("AUTO_HL=["))
        self.assertTrue(block.rstrip().endswith("]"))
        self.assertEqual(block.count("]"), 1)


if __name__ == "__main__":
    unittest.main()
