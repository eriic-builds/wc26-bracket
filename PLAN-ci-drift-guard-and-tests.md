# PLAN: CI drift guard + test suite for the sync engine

**Rank: 1 of 5 — do this first.**
**Why first:** Closed issue #2 documented a real silent regression (a CSS fix hand-patched into
`docs/index.html` was wiped when the generator re-ran). The tournament is live through July 19 and
the auto-sync rewrites `scripts/build_dashboard.py` **via regex, three times a day, unattended**.
Every other plan touches this fragile path; this plan makes all of them safe to do. It is also the
cheapest (stdlib only, no new dependencies).

## Goal

1. A `tests/` suite (pytest-compatible but runnable with plain `python -m unittest`) covering the
   sync engine's parsing, matching, and rewrite logic.
2. A CI workflow that on every push/PR: runs the tests, regenerates `docs/index.html`, and **fails
   if the committed HTML differs from what the generator produces** (the exact failure mode from
   issue #2).
3. Fix one real latent bug found during exploration (pair-collision, see Edge case 1) so the Final
   cannot be corrupted by a group-stage result.

## Exact files to touch

| File | Action |
|---|---|
| `tests/test_fetch_results.py` | **create** |
| `tests/fixtures/feed_sample.json` | **create** (committed sample feed) |
| `.github/workflows/ci.yml` | **create** |
| `scripts/fetch_results.py` | **edit** — one bug fix in `match_all` (Edge case 1 only; touch nothing else) |

Do **not** touch `scripts/build_dashboard.py` or `docs/index.html` in this plan.

## Step-by-step implementation order

1. Create `tests/fixtures/feed_sample.json` — a list of finished games in the local-JSON shape
   `results_from_json` accepts (see README "Refreshing results manually" for the shape). Include:
   a normal win, a penalty shootout (`"winner"` + `"note": "4–3 pens"` with a level score), a
   genuine draw (level score, no winner), and one game whose team names need `team_map.json`
   normalization (e.g. `"Bosnia and Herzegovina"`).
2. Create `tests/test_fetch_results.py`. Import the module with
   `sys.path.insert(0, "<repo>/scripts")` then `import fetch_results`. Write these tests:
   - **Round-trip parse/render:** `parse_res_block(render_res(res) )== res` for a dict containing
     a note with an en-dash (`"4–3 pens"`). Same for `parse_upcoming_block`/`render_upcoming`.
   - **R32/KO_FEED extraction:** `read_r32` returns exactly 16 rows and `parse_ko_feed` returns
     exactly 15 codes (M89–M102 + M104, **not** M103) when run against the real
     `build_dashboard.py` text.
   - **Shootout un-folding (football-data):** feed `score.fullTime = 5–4`,
     `score.penalties = 4–3` through `results_from_footballdata`'s logic and assert the stored
     score is 1–1 with note `"4–3 pens"`. (Extract the logic or monkeypatch `urllib`; do not hit
     the network.)
   - **Draws never enter RES:** run `match_all` with a draw in the feed for a bracket pair;
     assert the code is absent from `res`.
   - **Curated-note safety net:** existing `RES` entry `(1,1,"Paraguay","4–3 pens")`, feed offers
     `(1,1,"Paraguay","")` → assert the old value is kept (this logic lives in `main`; lift it
     into a small pure function `merge_res(old, new)` so it is testable — behavior-preserving
     refactor only).
   - **Idempotency:** applying the same feed twice yields `changed == []` the second time.
   - **AUTO_HL regex safety:** `render_auto_hl(build_auto_hl(feed))` output must contain `]` only
     as the final character (the in-place rewrite uses the non-greedy `AUTO_HL=\[.*?\]` and an
     early `]` in card text would truncate the block).
   - **Pair-collision fix** (see Edge case 1): a feed containing BOTH a group-stage meeting and a
     knockout meeting of the same two teams must resolve the knockout match from the knockout
     entry, regardless of feed order.
3. Fix Edge case 1 in `match_all` (see below for the exact change).
4. Create `.github/workflows/ci.yml`:
   ```yaml
   name: CI
   on: [push, pull_request]
   jobs:
     test:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v4
         - uses: actions/setup-python@v5
           with: { python-version: "3.12" }
         - run: python -m unittest discover -s tests -v
         - name: Generator/output drift guard
           run: |
             python scripts/build_dashboard.py
             git diff --exit-code docs/index.html
   ```
5. Run locally: `python -m unittest discover -s tests -v` and
   `python scripts/build_dashboard.py && git diff --exit-code docs/index.html` must both pass
   before committing.

## Edge cases a weaker model would miss

1. **Pair-collision in `match_all` (real latent bug).** `by_pair` is keyed by
   `frozenset((home, away))` with no stage or date discrimination, and the feed contains **every
   finished World Cup game including the group stage**. Two teams from the same group can meet
   again in the SF or Final (e.g. 1A vs 2A). When that happens, the group-stage result and the
   knockout result share the same dict key; whichever appears **last in feed order** silently wins
   and could write a wrong Final result. Fix: when building `by_pair`, prefer the entry with the
   **latest `date`**; additionally, when `orient()` is called for a knockout code, skip feed
   entries whose `stage` maps to `"group stage"` via `stage_label()`. Keep the fix minimal.
2. **`RES=\{[^}]*\}` stops at the first `}`.** The rewrite regex only works because no note string
   ever contains `}`. Don't "improve" the regex; instead assert in a test that no rendered note
   contains `}` or `{`.
3. **The `AUTO_HL` block's `]` constraint** (tested above) is documented only in a docstring —
   it's an invariant, not an accident.
4. **`ELIM` inference is name-exact.** In `build_dashboard.py`, the R32 loser is computed as
   `a if w==b else b` — if the winner string matches **neither** team (a `team_map.json` miss),
   team `b` is silently marked eliminated. Your test for name normalization protects this
   indirectly: assert `match_all` never writes a winner that isn't one of the two bracket teams.
5. **Unicode on Windows.** The workflow sets `PYTHONIOENCODING=utf-8` when re-running the
   generator; tests must not rely on the console encoding — always read/write files with
   `encoding="utf-8"`.
6. **M103 (third-place playoff) is intentionally excluded** from `KO_FEED` (confirmed in issue
   #2). Do not "fix" its absence; the extraction test pins it.
7. **The drift guard must run the generator BEFORE diffing**, and diff only `docs/index.html` —
   `scripts/build_dashboard.py` legitimately changes every sync (REFRESHED stamp), so diffing the
   whole tree would false-positive.

## Acceptance criteria

- [ ] `python -m unittest discover -s tests -v` passes locally with ≥ 8 tests.
- [ ] No test performs a network call (grep tests for `urlopen` — zero hits outside mocks).
- [ ] CI workflow runs green on push; deliberately hand-editing one character in
  `docs/index.html` and pushing makes CI **fail** on the drift step.
- [ ] The pair-collision test fails against the pre-fix `match_all` (verify by stashing the fix)
  and passes after.
- [ ] `python scripts/fetch_results.py --dry-run --input tests/fixtures/feed_sample.json` runs
  clean and reports without writing.
- [ ] `git status` shows no change to `docs/index.html` after a plain generator run (proves the
  repo is currently drift-free at merge time).
