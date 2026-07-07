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


class DataFileTests(unittest.TestCase):
    """After the JSON move, data/*.json is the source of truth."""

    def test_data_files_have_expected_shape(self):
        picks = json.load(open(fr.PICKS, encoding="utf-8"))
        live = json.load(open(fr.LIVE, encoding="utf-8"))
        topo = json.load(open(fr.TOPOLOGY, encoding="utf-8"))
        self.assertEqual(len(picks["r32"]), 16)
        for r in picks["r32"]:
            self.assertRegex(r[0], r"^M\d+$")
            self.assertTrue(r[2] and r[3])                  # teamA, teamB
        for key in ("res", "upcoming", "ko_fix", "auto_hl", "refreshed"):
            self.assertIn(key, live)
        self.assertEqual(len(topo["ko_feed"]), 15)          # M89-M102 + M104
        self.assertIn("M104", topo["ko_feed"])              # the Final
        self.assertNotIn("M103", topo["ko_feed"])           # 3rd-place intentionally out

    def test_live_json_roundtrip_preserves_unicode(self):
        # mutate -> write -> read -> equal (the JSON layer replaces the old regex
        # round-trip; ensure_ascii=False must keep en-dashes/emoji intact).
        import tempfile
        live = json.load(open(fr.LIVE, encoding="utf-8"))
        live["res"]["M74"] = [1, 1, "Paraguay", "4\u20133 pens"]
        live["auto_hl"].append(["\U0001f981", "hd", "sc", "wh", "a\u2013b"])
        with tempfile.TemporaryDirectory() as d:
            tmp = os.path.join(d, "live.json")
            with mock.patch.object(fr, "LIVE", tmp):
                fr._write_live(live)
                back = json.load(open(tmp, encoding="utf-8"))
        self.assertEqual(back["res"]["M74"], [1, 1, "Paraguay", "4\u20133 pens"])
        self.assertEqual(back["auto_hl"][-1], ["\U0001f981", "hd", "sc", "wh", "a\u2013b"])

    def test_sync_no_longer_edits_the_generator(self):
        # The point of the JSON layer: the sync never regex-rewrites the Python source.
        src = open(fr.__file__, encoding="utf-8").read()
        self.assertNotIn("gen_text", src)


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
            feed, _up = fr.results_from_footballdata({})
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
        feed, _up = fr.results_from_json(FIXTURE, fr.load_team_map())
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
        feed, _up = fr.results_from_json(FIXTURE, fr.load_team_map())
        pairs = {frozenset((g["home"], g["away"])) for g in feed}
        self.assertIn(frozenset(("Bosnia & Herz.", "Norway")), pairs)
        for g in feed:
            self.assertNotIn("Bosnia and Herzegovina", (g["home"], g["away"]))

    def test_draw_kept_out_of_results_but_shape_ok(self):
        feed, _up = fr.results_from_json(FIXTURE, fr.load_team_map())
        draw = next(g for g in feed if g["home"] == "Ghana")
        self.assertEqual(draw["winner"], "")
        self.assertEqual(draw["note"], "draw")


class KoFixTests(unittest.TestCase):
    def test_build_ko_fix_converts_utc_to_et_ct_pt(self):
        # M89 (feeders M74/M77) has both feeder winners but is itself pending; a
        # scheduled France v Spain at 19:00Z on 2026-07-09 -> 3pm ET/2pm CT/12pm PT.
        ko_feed = {"M89": ("M74", "M77"), "M97": ("M89", "M90")}
        res = {"M74": (2, 1, "France", ""), "M77": (1, 0, "Spain", "")}
        upcoming = [{"home": "France", "away": "Spain", "date": "2026-07-09T19:00:00Z"}]
        kf = fr.build_ko_fix(ko_feed, res, upcoming)
        self.assertIn("M89", kf)
        day, et, ct, pt = kf["M89"]
        self.assertEqual((et, ct, pt), ("3:00 PM", "2:00 PM", "12:00 PM"))
        self.assertTrue(day.endswith("Jul 9"))          # ET day, no leading zero
        self.assertNotIn("M97", kf)                     # feeder M90 unknown -> skipped

    def test_build_ko_fix_skips_unknown_feeders(self):
        ko_feed = {"M97": ("M89", "M90")}               # feeders not in res
        kf = fr.build_ko_fix(
            ko_feed, {}, [{"home": "France", "away": "Spain", "date": "2026-07-09T19:00:00Z"}])
        self.assertEqual(kf, {})

    def test_build_ko_fix_excludes_third_place_m103(self):
        # M103 is absent from ko_feed by design; iterating ko_feed can't emit it.
        ko_feed = {"M104": ("M101", "M102")}
        res = {"M101": (1, 0, "France", ""), "M102": (2, 1, "Spain", "")}
        kf = fr.build_ko_fix(
            ko_feed, res, [{"home": "France", "away": "Spain", "date": "2026-07-19T23:00:00Z"}])
        self.assertIn("M104", kf)
        self.assertNotIn("M103", kf)

    def test_build_ko_fix_needs_the_pair_in_schedule(self):
        ko_feed = {"M89": ("M74", "M77")}
        res = {"M74": (2, 1, "France", ""), "M77": (1, 0, "Spain", "")}
        self.assertEqual(fr.build_ko_fix(ko_feed, res, []), {})           # empty schedule
        self.assertEqual(fr.build_ko_fix(                                  # different pair
            ko_feed, res, [{"home": "Brazil", "away": "Norway", "date": "2026-07-09T19:00:00Z"}]), {})


if __name__ == "__main__":
    unittest.main()
