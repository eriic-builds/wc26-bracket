# PLAN: Auto-sync upcoming knockout fixtures & kickoff times (QF/SF/Final)

**Rank: 2 of 5 — hard deadline: the Quarterfinals kick off July 9.**
**Why:** Kickoff times are hand-coded for the Round of 16 only (`R16_FIX`). Once M95/M96 finish
(July 7), the dashboard has **no kickoff times for any remaining match** — the QF/SF/Final panels
fall back to vague ranges like "Jul 9–11" from `KO_DATES`. The FIFA feed already carries the
schedule (every match has a `Date`, finished or not); the sync just throws unfinished matches
away. This plan makes fixtures self-updating for the rest of the tournament, exactly like results
already are.

## Goal

The sync engine writes a `KO_FIX` block (match code → day + ET/CT/PT kickoff times) for all
not-yet-played knockout matches, computed from the FIFA feed's UTC dates. The dashboard's
round-by-round panels show real kickoff times for pending QF/SF/Final matches. Dead code from the
R16-era is removed.

## Exact files to touch

| File | Action |
|---|---|
| `scripts/fetch_results.py` | **edit** — collect scheduled matches; render/rewrite `KO_FIX` |
| `scripts/build_dashboard.py` | **edit** — add `KO_FIX` data block; use it in `build_round_results_panel`; delete dead code |
| `tests/test_fetch_results.py` | **edit** — add fixture-time tests (if PLAN-ci was done; else skip) |

## Step-by-step implementation order

1. **In `scripts/build_dashboard.py`**, in the USER DATA section directly under `R16_FIX`, add:
   ```python
   # Kickoff times for not-yet-played knockout games — AUTO, maintained by the sync
   # engine from the FIFA schedule. {code: (day, ET, CT, PT)}. Do not hand-edit.
   KO_FIX={}
   ```
2. **In `build_round_results_panel`** (same file), where a pending match currently does
   `if short=="r16" and mc in r16day: ... else: when=KO_DATES[short]` — check `KO_FIX` first:
   ```python
   if mc in KO_FIX:
       day,et,ct,ptz=KO_FIX[mc]; when=f'{day} · {ptz} PT · {ct} CT · {et} ET'
   elif short=="r16" and mc in r16day: ...   # keep existing fallback
   else: when=KO_DATES[short]
   ```
3. **Delete dead code in `build_dashboard.py`:** the function `build_upcoming` (~line 743) is
   never called from the HTML assembly — confirm with a search for `build_upcoming(` before
   deleting (there must be exactly one hit: the definition). It also contains a hardcoded
   `"your pick out (Japan)"` string that would be wrong for any other elimination. Delete the
   whole function. Do NOT delete `R16_FIX` or `R32_TIMES` — both are still referenced.
4. **In `scripts/fetch_results.py`:**
   a. In `results_from_fifa`, also collect **scheduled** matches: currently
      `if m.get("MatchStatus") != 0: continue` skips everything unfinished. Keep the finished
      list as-is, but additionally build a second list `upcoming` of matches where
      `MatchStatus != 0` and both team names resolve (skip TBD placeholder teams where the name
      is empty), each as `{"home","away","date"}` (UTC ISO string from `m["Date"]`). Return it
      alongside — change the return to `(out, upcoming)` and update **all three callers**
      (`--source fifa` branch, `_fetch_source`, and self-consistently `results_auto`). For the
      football-data and local-JSON sources return `(out, [])` — schedule sync is FIFA-only.
   b. Add `parse_ko_fix(gen_text)` / `render_ko_fix(d)` following the exact pattern of
      `parse_upcoming_block` / `render_upcoming` (regex `KO_FIX=\{[^}]*\}`, entries
      `"M97":("Thu Jul 9","3:00 PM","2:00 PM","12:00 PM")`).
   c. Add `build_ko_fix(ko_feed, res, upcoming_feed)`: for each code in `ko_feed` **not** in
      `res`, if both feeder winners are known, find the scheduled feed entry whose team pair
      matches; convert its UTC date with `zoneinfo`:
      ```python
      from zoneinfo import ZoneInfo
      dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
      et = dt.astimezone(ZoneInfo("America/New_York"))
      ct = dt.astimezone(ZoneInfo("America/Chicago"))
      pt = dt.astimezone(ZoneInfo("America/Los_Angeles"))
      ```
      Format day as `"Thu Jul 9"` (strip leading zero like `_fmt_day` does) and times as
      `"3:00 PM"` (strip the leading zero from `%I`).
   d. In `main()`, after the RES/UPCOMING rewrite, compute the new `KO_FIX` block and rewrite it
      with the same `re.sub` pattern; include it in the "what changed" decision so a
      schedule-only change still triggers a commit and rebuild.
5. Run `python scripts/fetch_results.py --dry-run` against the live feed and eyeball the
   reported KO_FIX entries, then run for real and verify the QF panel in the browser
   (`open docs/index.html`).

## Edge cases a weaker model would miss

1. **`build_upcoming` is dead code with a landmine.** It looks load-bearing (60 lines, styled)
   but is never called; its "pick out" label hardcodes `(Japan)`. Deleting is correct; wiring it
   back in is not.
2. **Do not use fixed UTC offsets.** The existing `now_pt_stamp()` hardcodes UTC−7; do NOT copy
   that pattern for kickoff times — use `zoneinfo` names as shown. (`zoneinfo` is stdlib on
   Python 3.9+; CI uses 3.12. No tzdata pip install needed on ubuntu/macOS runners.)
3. **Scheduled FIFA entries can have placeholder/TBD teams** (a match whose feeders aren't
   decided). `_fifa_txt` returns `""` for missing names — skip entries with an empty side, and
   only emit a `KO_FIX` row when **your own `res`** already knows both feeder winners. Both
   guards are needed: the feed can know teams before your RES does and vice versa.
4. **Match by team pair, not by FIFA match ID.** The bracket's match codes (M97…) are your own
   numbering; FIFA's `IdMatch` is an opaque GUID. The pair-matching must use the same
   `frozenset((a, b))` approach as `match_all` — and must apply the same group-stage collision
   guard if PLAN-ci added it (a scheduled knockout game can't collide with a *finished* group
   game in the schedule list, but filter to knockout stages anyway via `stage_label`).
5. **A match that kicks off is neither finished nor scheduled-future.** FIFA `MatchStatus 0` =
   finished; live matches carry other statuses. It's fine for a live match to appear in
   `KO_FIX` (its kickoff time is still true) — but never let it into `RES`. The existing
   `!= 0` guard already ensures that; don't weaken it.
6. **The rewrite regex requires `KO_FIX={...}` to already exist** in `build_dashboard.py`
   (step 1 creates it). If `re.sub` finds no match it silently changes nothing — after the
   rewrite, assert the rendered block is actually present in `out_text` and print a warning if
   not (mirror how `cur_hl` is checked before the AUTO_HL rewrite).
7. **Keep `M103` out.** `build_ko_fix` iterates `ko_feed`, which correctly lacks M103 — do not
   iterate the feed's knockout games instead, or the third-place playoff will appear.
8. **`R16_FIX` contains stale pre-match placeholders** (`"Portugal / Croatia"`). Leave it —
   it's only consulted for *pending* r16 matches and M95/M96 resolve real names from feeders.
   Rewriting history there churns the diff for zero display change.

## Acceptance criteria

- [ ] After a real sync run, `KO_FIX` in `build_dashboard.py` contains entries for every
  undecided knockout match whose two teams are known, with plausible ET/CT/PT triples
  (ET−1 = CT, ET−3 = PT).
- [ ] Open `docs/index.html` → Round-by-round results → Quarterfinals: pending QF matches show
  `"<Day> · <PT> PT · <CT> CT · <ET> ET"` instead of `"Jul 9–11"`.
- [ ] `grep -c "build_upcoming" scripts/build_dashboard.py` returns 0.
- [ ] `python scripts/fetch_results.py --dry-run` twice in a row: second run reports no changes
  (idempotent — schedule times don't oscillate).
- [ ] `python scripts/build_dashboard.py && git diff --stat docs/index.html` shows changes only
  when KO_FIX/RES actually changed.
- [ ] The generator still passes the CI drift guard (if PLAN-ci is merged).
