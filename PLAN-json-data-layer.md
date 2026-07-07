# PLAN: Extract the DATA block into JSON (kill the regex-rewrites-Python pattern)

**Rank: 3 of 5.**
**Why:** Today the sync engine edits `scripts/build_dashboard.py` **in place with regexes** —
`RES=\{[^}]*\}`, `AUTO_HL=\[.*?\]` (which must never contain a `]`), `REFRESHED="[^"]*"`. This is
the single biggest source of fragility (issue #2's drift bug is a cousin of it), and it blocks
every multi-entrant future: the "fan viewer" fork (solution 6) and the README's own
"multi-entrant support" idea both need picks and live results as **data files**, not Python
literals. Do this AFTER plans 1–2 (the test suite makes this refactor safe; the fixtures feature
avoids rebasing onto a moving file).

## Goal

- `data/picks.json` — the entrant's bracket (everything personal: entrant, tiebreaker, seeds,
  R32 fixtures+picks, later-round winners, champ/runner, freebie).
- `data/live.json` — everything the sync writes: `res`, `upcoming`, `ko_fix` (if plan 2 landed),
  `auto_hl`, `refreshed`.
- `build_dashboard.py` loads both files; its USER DATA section shrinks to two `json.load` calls
  plus the constants that are truly universal (`KO_FEED`, `WC_HISTORY`, emoji maps).
- `fetch_results.py` reads/writes `data/live.json` directly — **all parse/render regex functions
  are deleted.**

## Exact files to touch

| File | Action |
|---|---|
| `data/picks.json` | **create** (transcribe current values from `build_dashboard.py`) |
| `data/live.json` | **create** (transcribe current RES/UPCOMING/AUTO_HL/REFRESHED) |
| `scripts/build_dashboard.py` | **edit** — replace data literals with JSON loads |
| `scripts/fetch_results.py` | **edit** — read/write JSON; delete regex parse/render helpers |
| `.github/workflows/sync-results.yml` | **edit** — commit `data/live.json` too |
| `tests/test_fetch_results.py` | **edit** — replace round-trip regex tests with JSON I/O tests |
| `README.md` | **edit** — update "The data model" and repo-layout tables |

## Step-by-step implementation order

1. **Write the JSON schema first** (as a comment block at the top of each file's consumer):
   ```jsonc
   // picks.json
   { "entrant": "Eric Lam", "tiebreaker": 4, "freebie_match": "M73",
     "seed": {"Germany": "1E", ...},
     "r32": [["M74","Mon 6/29","Germany","Paraguay","Germany"], ...],
     "r16_win": [...8 teams...], "qf_win": [...4...], "sf_win": [...2...],
     "champ": "England", "runner": "France" }
   // live.json
   { "refreshed": "July 6, 2026 · 10:13 PM PT",
     "res": {"M73": [0,1,"Canada",""], ...},
     "upcoming": {}, "ko_fix": {"M97": ["Thu Jul 9","3:00 PM","2:00 PM","12:00 PM"]},
     "auto_hl": [["😈","headline","score","when","body"], ...] }
   ```
2. **Populate both JSON files** by hand-transcribing the current literals from
   `build_dashboard.py` (do not write a converter script; it's a one-time move). Preserve
   unicode as-is (`ensure_ascii=False` when writing later).
3. **Edit `build_dashboard.py`:** at the top, load both files relative to the script:
   ```python
   _root=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
   P=json.load(open(os.path.join(_root,"data","picks.json"),encoding="utf-8"))
   L=json.load(open(os.path.join(_root,"data","live.json"),encoding="utf-8"))
   ENTRANT=P["entrant"]; TIEBREAKER=P["tiebreaker"]; SEED=P["seed"]
   R32=[tuple(r) for r in P["r32"]]; ...
   RES={k:tuple(v) for k,v in L["res"].items()}; REFRESHED=L["refreshed"]; ...
   AUTO_HL=[tuple(x) for x in L["auto_hl"]]
   ```
   Everything below the RENDER ENGINE banner stays byte-identical. Run the generator and diff:
   `python scripts/build_dashboard.py && git diff docs/index.html` must be **empty** before
   proceeding (this is the correctness gate for the whole refactor).
4. **Edit `fetch_results.py`:** delete `read_r32`, `parse_res_block`, `parse_upcoming_block`,
   `parse_ko_feed`, `render_res`, `render_upcoming`, `render_auto_hl`(keep `build_auto_hl`),
   and every `re.sub` on `gen_text`. Instead: load `data/picks.json` for R32, load
   `data/live.json`, mutate the dicts, and `json.dump(..., ensure_ascii=False, indent=1)` back.
   `KO_FEED` moves to a shared constant: simplest correct option is to keep it defined in
   `build_dashboard.py` and have `fetch_results.py` do
   `sys.path.insert(0, HERE); from build_dashboard import KO_FEED` — **no**: importing the
   generator executes it (it writes HTML at import). Instead move `KO_FEED` into
   `data/topology.json` (create it; both scripts load it) — it is fixed FIFA structure, same
   for every entrant.
5. **Edit `sync-results.yml`:** the commit step's `git status --porcelain` and `git add` lists
   must become `docs/index.html data/live.json` (drop `scripts/build_dashboard.py` — the sync
   no longer modifies it).
6. **Update tests** (from PLAN-ci): round-trip tests become "mutate → dump → load → equal";
   the AUTO_HL `]`-constraint test is deleted (constraint gone — JSON has no such limit);
   the drift guard stays unchanged.
7. **Update README** tables and the note in "Hosting on GitHub Pages" (the drift lesson now
   reads: hand-edits to `docs/index.html` still get wiped — edit the generator; data edits go
   in `data/*.json`).

## Edge cases a weaker model would miss

1. **JSON turns tuples into lists.** The render engine indexes `RES[mc][2]` etc. (works on
   lists), but tests and any `==` comparisons against tuple literals will break — normalize to
   tuples at load (step 3 does this). Grep for `RES[` / `AUTO_HL` consumers before declaring
   done.
2. **Do not import `build_dashboard` from `fetch_results`.** The generator has top-level
   side effects (writes `docs/index.html` at the end of the module). That's why `KO_FEED` moves
   to `data/topology.json` instead of being imported.
3. **Key order and formatting must be deterministic** or every sync produces a noisy diff.
   Use `json.dump(..., indent=1, ensure_ascii=False)` and sort `res` keys numerically
   (`sorted(res, key=lambda c: int(c[1:]))` — note `"M9" < "M10"` fails lexicographically)
   by building an ordered dict before dumping.
4. **The generator/HTML must be byte-identical after step 3** — including the `REFRESHED`
   string and every emoji. If the diff isn't empty, you transcribed something wrong; fix the
   JSON, not the engine.
5. **The workflow's change-detection breaks silently if you forget step 5** — the sync would
   update `data/live.json` but `git status --porcelain docs/index.html scripts/build_dashboard.py`
   would still report... actually `docs/index.html` changes too, so commits still happen, but
   `data/live.json` would be **left uncommitted and lost on the next checkout**. Update both the
   status check and the `git add`.
6. **`input/instructions.md` (the Cowork kit) embeds the OLD generator** with the inline DATA
   block. Out of scope to regenerate the kit — add one line to README noting the kit is v10 and
   predates the JSON layer. Do not try to rewrite the 100 KB kit file.
7. **`.gitignore` may cover `data/`** — check it; the new files must be tracked.

## Acceptance criteria

- [ ] `python scripts/build_dashboard.py` immediately after step 3 produces a byte-identical
  `docs/index.html` (`git diff --exit-code docs/index.html`).
- [ ] `grep -c "re.sub" scripts/fetch_results.py` returns 0; `grep -c "gen_text"` returns 0.
- [ ] `python scripts/fetch_results.py --dry-run --input tests/fixtures/feed_sample.json` works;
  a real (non-dry) run modifies only `data/live.json` and `docs/index.html`.
- [ ] Two consecutive sync runs with no new results produce zero diff in `data/live.json`
  except the `refreshed` field.
- [ ] Full test suite green; CI drift guard green.
- [ ] `sync-results.yml` commit step lists `docs/index.html data/live.json` in both the check
  and the add.
