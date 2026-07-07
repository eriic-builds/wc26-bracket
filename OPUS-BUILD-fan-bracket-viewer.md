# BUILD SPEC — "Bring Your Own Bracket" fan viewer (solution 6)

**Audience: Claude Opus 4.8, executing autonomously.** This document is the complete brief for
forking `https://github.com/eriic-builds/wc26-bracket` into a new repo where **any visitor
uploads their own filled-in bracket Excel and the GitHub Page renders their personal dashboard**
— scored live against real results. All user data stays in the browser (nothing uploaded to any
server), persisted locally so the page doesn't require re-upload on every visit.

---

## 1. Mission statement

Build a static GitHub Pages site (fork of `wc26-bracket`, suggested name **`wc26-bracket-yours`**)
where:

1. A visitor drops their **"SLED World Cup 2026 bracket" Excel workbook** onto the page.
2. The page parses the workbook's **"My Bracket"** tab entirely client-side (no upload, no
   server), extracts their picks, and renders the same dashboard the source repo renders for
   Eric — bracket map with connectors, live scoring, KPIs, scorecard, round-by-round results,
   themes — but for *their* picks.
3. Live match results come from a `results.json` file in the repo, kept current by the same
   GitHub Actions sync that the source repo already runs (server-side, same for all visitors).
4. The parsed bracket is saved in `localStorage` so returning visitors see their dashboard
   immediately; explicit **Save / Load / Clear / Export JSON / Import JSON** controls are
   provided.

## 2. Architecture — the one big decision, already made

The source repo renders the dashboard **in Python at build time** (`scripts/build_dashboard.py`
concatenates HTML strings). That cannot work here: each visitor has different picks and there is
no server. **Port the render engine to client-side JavaScript.** Do not attempt the "template
with placeholder hydration" shortcut — the entrant's picks affect derived text everywhere (hero
copy, KPI notes, story cards, scorecard rows, bracket cell classes); partial hydration will drift.

What ports 1:1 (all pure functions of `(picks, results, topology)`):
`pick_status`, `reach_status`, `won_into`, `out_at_round`, `actual_advancer`, the ELIM/BUSTED
derivations, `round_tally`/current-round logic, `build_bracket`, `build_scorecard`,
`build_scorebar`, `build_kpis`, `build_finalfour`, `story_cards`, `build_results_panel`,
`build_round_results_panel`, `build_stages`, `build_legend`, `chip`, `shead`, and the HTML
assembly. The CSS (`CSS` constant) and interaction JS (`JS` constant — themes, favorites,
search, connector drawing, hover stat cards, scrollspy) are **already JavaScript/CSS — reuse
them verbatim**, they operate on the same DOM classes.

Target structure in the fork:

```
docs/
  index.html          ← landing + viewer shell (static, hand-written)
  css/dashboard.css   ← the CSS constant, extracted verbatim
  js/vendor/xlsx.full.min.js   ← SheetJS, vendored (no CDN)
  js/parse-excel.js   ← workbook → picks object
  js/render.js        ← the ported render engine: render(picks, live, topology) → HTML string
  js/interact.js      ← the JS constant, extracted verbatim + viewer glue
  js/storage.js       ← save/load/export/import
  data/results.json   ← live results, written by the sync workflow
  data/topology.json  ← KO_FEED, KO_DATES, WC_HISTORY, SEED-agnostic constants
  data/demo-picks.json ← Eric's bracket as a demo/sample
scripts/fetch_results.py   ← kept (trimmed): fetch → write docs/data/results.json
.github/workflows/sync-results.yml  ← kept: 3×/day cron + manual, commits results.json
.github/workflows/deploy-pages.yml  ← kept as-is
tests/              ← golden-file + parser tests (see §7)
```

## 3. The Excel format — exact, verified against the real workbook

Workbook sheets: `How to Play`, `My Bracket`, `Sample Bracket`. Parse **`My Bracket`** only.
Layout (verified by unzipping `input/bracket-picks.xlsx` in the source repo):

- **Row 3** is the header: `A3="Match / Date"`, `B3=ROUND OF 32`, `C3=ROUND OF 16`,
  `D3=QUARTERFINALS`, `E3=SEMIFINALS`, `F3=FINAL`, `G3=CHAMPION`.
- **16 match blocks of 4 rows**, first block at row 4 (rows 4, 8, 12, …, 64). In each block at
  top row *r*:
  - `A{r}` = match code + date, e.g. `"M74\nMon 6/29"` (multiline cell; M73's also contains
    `"★ FREEBIE"`).
  - `B{r}` = team A as `"Germany  (1E)"` — name, **two spaces**, seed in parens.
  - `B{r+2}` = team B, same format.
  - `C{r}` = the R32 pick (winner of this match), plain name, no seed.
- The sheet's block order is **not numeric**: M74, M77, M73, M75, M83, M84, M81, M82, M76,
  M78, M79, M80, M86, M88, M85, M87. **Read the code from column A — never assume order.**
- **Later-round picks** appear only at the top rows of merged ranges:
  - `D` at rows 4, 12, 20, 28, 36, 44, 52, 60 → the 8 Round-of-16 winners (order matters: it is
    bracket-tree order, pairing consecutive sheet blocks).
  - `E` at rows 4, 20, 36, 52 → the 4 QF winners.
  - `F` at rows 4, 36 → the 2 SF winners (the finalists).
  - `G4` → the champion. **Runner-up = the F-column finalist that is not the champion.**
- `C69` = entrant name (label in `A69="Your Name:"`), `C70` = tiebreaker (label in `A70`).
- Columns `U`/`V` are helper/validation lists — **ignore them**.

Parse into this object (same shape as `data/demo-picks.json`):

```json
{ "entrant": "…", "tiebreaker": 4, "freebie_match": "M73",
  "r32": [["M74","Mon 6/29","Germany","Paraguay","Germany"], …16, in SHEET order…],
  "r16_win": [8 names], "qf_win": [4], "sf_win": [2], "champ": "…", "runner": "…",
  "seed": {"Germany":"1E", …} }
```

Build `seed` from the parenthesized suffixes in column B. Strip the name with a regex like
`/^(.*?)\s{2,}\((.+)\)\s*$/` and `.trim()` — some cells may have a single space or trailing
whitespace; fall back to "split on last `(`".

### Validation (hard requirement — reject with specific messages, never render garbage)

- Exactly 16 blocks with codes matching `/^M\d+$/`; every `C{r}` pick ∈ {team A, team B} of its
  block.
- Tree consistency: each `r16_win[j]` must equal one of the two R32 picks of sheet blocks
  `2j, 2j+1`; each `qf_win[j]` one of `r16_win[2j], r16_win[2j+1]`; likewise SF, champ.
- Entrant name non-empty; tiebreaker is an integer ≥ 0 (tolerate it being a float or string).
- On failure, show a friendly panel listing every problem found (not just the first), and offer
  the demo bracket.

## 4. Live results — `results.json`

Trim the fork's `fetch_results.py`: keep the source fetching (`results_from_fifa`,
`results_from_footballdata`, `results_auto`, team-map normalization, `match_all`,
`build_auto_hl`, and — if the source repo's PLAN-auto-knockout-fixtures landed — the schedule
collection), **delete** all the regex read/rewrite of `build_dashboard.py`, and write:

```json
{ "refreshed": "July 6, 2026 · 10:13 PM PT",
  "res": {"M73": [0,1,"Canada",""], …},
  "ko_fix": {"M97": ["Thu Jul 9","3:00 PM","2:00 PM","12:00 PM"], …},
  "auto_hl": [["😈","headline","score","when","body"], …] }
```

to `docs/data/results.json`. The workflow's commit step changes to add
`docs/data/results.json` (there is no generated `docs/index.html` to commit anymore — the page
is static and renders client-side). The viewer fetches it same-origin with
`fetch('data/results.json', {cache:'no-cache'})`.

**Critical:** `match_all` needs the R32 fixture list to key results to match codes. In the
source repo it reads that from the entrant's picks — but fixtures (the 16 team pairings) are
**the same for every entrant**; only the 5th tuple element (the pick) differs. Put the fixture
list (codes, dates, team A/B) and `KO_FEED` into `data/topology.json` and have both the Python
sync and the JS renderer read it. The uploaded Excel's fixtures should be *validated against*
topology (mismatch ⇒ the user uploaded a different competition's sheet), not trusted as truth.

## 5. Save / load (the feature the user explicitly asked for)

- `localStorage` key `wcb.fan.picks.v1` = the parsed picks JSON; written after every successful
  parse. On page load: if present, render immediately (results fetched fresh); show a small
  "You're viewing {entrant}'s bracket — replace / clear" bar.
- **Export JSON** button: download the picks object as `{entrant}-bracket.json`
  (`URL.createObjectURL(new Blob(...))`).
- **Import JSON** button: file input accepting `.json`, validated through the same validator as
  Excel-derived picks.
- **Clear** wipes the key and returns to the landing/upload state.
- Note the existing interaction JS already uses localStorage keys `wcb.theme`, `wcb.favs`,
  `wcb.favonly`, `wcb.scores.v3` — keep those working; namespace new keys as above so nothing
  collides. `wcb.scores.v3` (manual what-if overrides) should be cleared when a *different*
  bracket is loaded (keyed pick IDs would otherwise leak between entrants — key the storage by
  a hash of the picks object).

## 6. Implementation order

1. **Scaffold the fork.** New repo from the source; delete `input/bracket-picks.xlsx` (Eric's
   personal file), keep the sync + deploy workflows. Set Pages to GitHub Actions as in the
   source README.
2. **`data/topology.json` + Python sync rewrite** (§4). Verify a manual workflow dispatch
   commits a fresh `results.json`.
3. **Extract CSS + interaction JS verbatim** from the `CSS` and `JS` constants in
   `scripts/build_dashboard.py` into `docs/css/dashboard.css` and `docs/js/interact.js`. The
   interaction JS is an IIFE that queries the DOM — it must run **after** `render.js` injects
   the dashboard; wrap its invocation in an exported `initInteractions()` you call post-render
   (it currently self-executes on script load; that's the one modification).
4. **Port the render engine** (`docs/js/render.js`). Work function-by-function down
   `build_dashboard.py`, keeping names. Everything from the `pairs()` helper to the `HTML=`
   assembly. Skip: file I/O, `STATS_JS` (emit `window.WCSTATS` as a plain object instead),
   `build_upcoming` (dead code in the source — do not port), `KPIS=None` (dead). Keep the
   footer's credit line but parameterize the "Thank you to Rob" host line so forks can edit it
   in one place.
5. **Golden test** (§7 — do this before the Excel work; it proves the port).
6. **`parse-excel.js`** with SheetJS (§3). Vendor `xlsx.full.min.js` (Apache-2.0; put the
   license header in the file or a NOTICE) — no CDN, keeping the "self-contained / no external
   requests" property and avoiding supply-chain drift.
7. **Landing UX** in `docs/index.html`: drop zone + file picker (`accept=".xlsx,.xlsm"`), a
   "Try the demo bracket" button (loads `data/demo-picks.json`), a plain-language privacy line:
   *"Your file is read right here in your browser — it is never uploaded anywhere."* Then the
   save/load bar (§5).
8. **Polish:** error panel styling, empty-results state (page must render sensibly with
   `res: {}` — all pending), mobile check, README rewrite for the fork (what it is, how to use,
   how it differs from the source repo).

## 7. Testing — the golden-file gate

The port is correct when JS and Python produce the same dashboard for the same inputs:

1. In the fork, temporarily keep the source `build_dashboard.py`. Generate Eric's dashboard
   with the Python engine (picks = demo-picks, results = current results.json).
2. Render the same inputs through `render.js` in Node
   (`node --experimental-vm-modules` or plain `node` if you write render.js dependency-free —
   prefer dependency-free: no DOM needed since it builds strings).
3. Compare the two HTML strings **section by section** (split on `<div class="shead"` ids).
   Whitespace-normalize. 100% of sections must match except the `<head>`/shell (which
   legitimately differs — static page vs generated).
4. Keep this as `tests/test_golden.py` + `tests/golden.mjs` runnable in CI; once green, delete
   the Python generator from the fork (the sync no longer needs it).
5. Parser tests: run `parse-excel.js` against a checked-in copy of the **Sample Bracket**
   workbook (or a synthesized minimal .xlsx) and assert the exact picks object; include a
   deliberately corrupted workbook asserting each validation message fires.

## 8. Edge cases and traps (found by exploring the source — do not skip)

1. **The freebie.** M73 is auto-credited to every entrant (Canada def. South Africa) and the
   sheet pre-fills Canada into the R16 column. The scoring engine treats it as a normal correct
   pick, plus a 🎁 badge via `FREEBIE_MATCH`. Preserve both; if an entrant somehow picked South
   Africa (the sheet allows it pre-lock), the pick simply scores as wrong — don't special-case.
2. **`"M74\nMon 6/29"` is one cell.** SheetJS gives you the raw string with the newline; split
   on the newline for code vs date, and strip the `★ FREEBIE` line from M73's cell.
3. **Merged cells:** the D/E/F/G picks live in vertically merged ranges; SheetJS reports the
   value only at the **top-left** cell of a merge — which is exactly the rows listed in §3.
   Don't iterate every row looking for values; read the specific cells.
4. **Bracket-tree order ≠ numeric match order.** All pairing logic (which two blocks feed which
   R16 slot) is positional over the *sheet order* (M74+M77 → first R16 slot, etc.). The source
   engine encodes this in `KO_FEED` + `_derive_round`; port those exactly and validate the
   uploaded sheet's A-column codes against `topology.json` order.
5. **M103 (third-place playoff) is intentionally absent** from `KO_FEED`. M104 is the Final.
   Don't "complete" the sequence.
6. **Draw results never enter `res`** (winner `""` stays out — knockout games always have a
   decider; group games in the feed are for highlight cards only). The renderer may assume
   every `res` entry has a non-empty winner.
7. **Penalty notes** (`"4–3 pens"`) and `"AET"` are display strings inside results — they
   contain an **en-dash**, not a hyphen. Keep files UTF-8; don't normalize.
8. **Names must match exactly** between topology, picks, and results (`"Bosnia & Herz."`,
   `"Ivory Coast"`, `"United States"`). Results are pre-normalized by the sync's
   `team_map.json` server-side, and picks come from a sheet using the same names — but add a
   defensive check: any pick name not present in `topology` team set → validation error naming
   the cell.
9. **The `ELIM` loser inference** (`a if w==b else b`) silently mis-eliminates on a name
   mismatch — after §8's validation this can't happen from picks, but port it with an explicit
   `w===a || w===b` guard anyway and `console.warn` otherwise.
10. **The interaction JS draws bracket connectors from live DOM geometry** (`drawConnectors`)
    and redraws on resize/theme/toggle. It must be initialized after injection AND after
    `window.WCSTATS` is set (hover cards read it). The existing `window.__drawConn` hook and
    the `load` listener assume script-at-parse-time; re-check those when converting to
    post-render init.
11. **The manual what-if scorecard** persists per-pick overrides under `wcb.scores.v3` with IDs
    like `r32-M74` / `qf-2` — these are entrant-relative. Namespace by bracket hash (§5) or
    Eric's what-ifs will haunt the next uploaded bracket on the same device.
12. **`localStorage` can throw** (Safari private browsing quota 0) — the existing JS already
    wraps every access in try/catch; keep that discipline in `storage.js`, and make Export/
    Import the fallback story when storage is unavailable.
13. **Tournament clock:** today is July 6, 2026; the Final is July 19. Ship the walking
    skeleton (steps 1–4) first — after July 19 the sync goes quiet and the site becomes a
    retrospective viewer, which must still work (all rounds final, nothing pending: check the
    current-round logic's "stays on Final once played" path).
14. **Do not modify the source repo.** All work happens in the fork. If a shared improvement
    emerges (e.g. topology.json), note it in the fork's README as a candidate to upstream.

## 9. Acceptance criteria

- [ ] Fresh visitor + demo button → full dashboard renders, visually indistinguishable from the
  source repo's live page (same sections, themes, connectors, hover cards, collapsibles).
- [ ] Uploading the real "Sample Bracket"-derived workbook renders that entrant's picks; all
  scoring numbers (confirmed/live/out/attainable) recompute correctly (spot-check by hand
  against results.json: points = 1/2/4/8/16 by round, max 80).
- [ ] Corrupt/wrong workbook → readable error list; nothing renders; no console exceptions.
- [ ] Reload after upload → dashboard appears without re-upload (localStorage). Clear → back to
  landing. Export → JSON file; Import of that file → identical render.
- [ ] DevTools Network tab during upload+render: **zero** requests carrying user data; only
  same-origin fetches of `data/*.json` and static assets.
- [ ] Sync workflow dispatch commits an updated `docs/data/results.json` and the deployed page
  reflects a new result within ~2 minutes without any rebuild of HTML.
- [ ] Golden test green in CI; parser tests green; works in Safari and Chrome, desktop + phone.
- [ ] Two different brackets on the same device don't leak what-if overrides or favorites
  between each other (favorites MAY be shared — decide and document; what-ifs MUST NOT).
