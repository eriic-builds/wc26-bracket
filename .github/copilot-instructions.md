# Copilot instructions for wc26-bracket

## What this repo is

A single-file, self-contained World Cup 2026 bracket dashboard. There is no frontend
framework and no build tool — a Python generator writes one static `docs/index.html`
(inline CSS/JS/data, zero external requests), served by GitHub Pages. A second script
keeps it current by pulling finished match results from the web and writing them to
`data/live.json`, then re-running the generator.

```
data/picks.json    ─┐
data/topology.json  ├─►  scripts/build_dashboard.py  ─►  docs/index.html  ─►  GitHub Pages
data/live.json     ─┘        (loads JSON + render)         (self-contained)     (live site)
                                        ▲
        scripts/fetch_results.py  ──────┘   (writes results/times/highlights to data/live.json, re-runs the generator)
```

## Architecture — read this before touching either script

- **`scripts/build_dashboard.py`** loads `data/{picks,live,topology}.json` at the top (tuples
  restored from JSON lists), then has a **render engine** below the `"RENDER ENGINE"` banner
  comment. The render engine is verbatim/reproducible output logic — never restyle, reorder, or
  extend it as a side effect of a data change. All page content (bracket, "How it played out"
  story cards, stage tracker, KPIs) is *derived* from the data (`RES`, `SEED`, `KO_FEED`, `R32`,
  etc.) inside functions like `story_cards()`/`build_story()`, `_build_stages_list()`, and
  `_current_round()` — never hardcode narrative text or stage state; add derivation logic instead
  so every rebuild stays in sync.
- **`docs/index.html` is build output — never hand-edit it.** Any content/markup/CSS change goes
  into `build_dashboard.py`, then regenerate and commit the generator and the HTML together
  (`python scripts/build_dashboard.py`). A hand-edit here has caused a real regression before.
  A CI drift guard (`.github/workflows/ci.yml`) enforces this: it regenerates and fails on any diff.
- **`scripts/fetch_results.py` reads/writes `data/live.json` directly** (`res`, `upcoming`,
  `ko_fix`, `auto_hl`, `refreshed`) — it does NOT edit Python source (the old regex-rewrite
  approach was retired in the JSON refactor). It never clobbers an existing result and is
  idempotent (no new finished games = no diff). It matches finished games to bracket codes
  round-by-round (R32 → R16 → QF → SF → Final, via `KO_FEED`/`match_all`), collects the FIFA
  schedule to fill `ko_fix` kickoff times for pending matches, normalizes team names via
  `scripts/team_map.json`, and rebuilds the "Game facts" `auto_hl` cards from the same feed.
  Do NOT `import build_dashboard` from the sync (it writes HTML at import time); shared constants
  like `KO_FEED` live in `data/topology.json`.
- Results source is `--source auto` by default: FIFA's free public feed
  (`api.fifa.com/api/v3`), falling back to football-data.org on an outage/empty feed (needs the
  optional `FOOTBALL_DATA_TOKEN` secret). football-data.org folds penalty-shootout goals into
  `score.fullTime` — subtract `score.penalties` to recover the true regulation/AET score.

## Data model (`data/*.json`)

`build_dashboard.py` loads three files from `data/`:

- **`picks.json`** (per-entrant): `entrant`, `tiebreaker`, `freebie_match`, `seed`, `r32`
  (`[matchcode, date, teamA, teamB, pick]`), `r16_win`, `qf_win`, `sf_win`, `champ`, `runner`.
- **`live.json`** (sync-written; the only file a sync run changes): `refreshed`, `res`
  (`{code: [gA, gB, winner, note]}`), `upcoming`, `ko_fix` (`{code: [day, ET, CT, PT]}`), `auto_hl`.
- **`topology.json`**: `ko_feed` (`{code: [feederA, feederB]}`), shared by both scripts.

`R32_TIMES`, `R16_FIX`, `KO_DATES`, `WC_HISTORY`, emoji maps, and `FEATURED` remain as constants
in `build_dashboard.py`; `HIGHLIGHTS = FEATURED + auto_hl`.

## Build / run / test commands

```bash
python scripts/build_dashboard.py                          # regenerate docs/index.html from data/*.json
python -m unittest discover -s tests -v                    # run the sync-engine unit tests (stdlib, no network)
python -m unittest tests.test_fetch_results.KoFixTests     # run a single test class
python scripts/build_dashboard.py && git diff --exit-code docs/index.html  # the CI drift guard, locally
python scripts/fetch_results.py --dry-run                   # preview live-feed changes, write nothing
python scripts/fetch_results.py --input results.json        # apply results from a local JSON feed
python scripts/fetch_results.py --source footballdata       # force football-data.org (needs FOOTBALL_DATA_TOKEN)
```
`results.json` (for `--input`) is a list of finished games: `{"home","away","homeGoals","awayGoals"}`,
plus `"winner"`/`"note"` for decided-on-penalties games (e.g. `"note": "5-4 pens"`).

CI (`.github/workflows/ci.yml`) runs the tests + drift guard on every push/PR (Python 3.12).

## Conventions

- **Python 3.12, standard library only** in `scripts/` — no pip dependencies, no
  `requirements.txt`. Match existing style: compact, comments explain *why*, f-strings,
  `encoding="utf-8"` on every file open (Windows contributors hit cp1252 errors otherwise).
- Never edit: `input/` (the entrant's source workbook/kit — read once, not a build dependency
  after that), `docs/how-i-built-this.html`, `LICENSE`, the cron lines in `sync-results.yml`,
  or `OPUS-BUILD-fan-bracket-viewer.md` (a spec for a different repo).
- `docs/.nojekyll` must stay committed even though Pages is deployed via
  `.github/workflows/deploy-pages.yml` uploading `docs/` directly (Settings → Pages → Source:
  GitHub Actions) — it's a harmless fallback if branch-based serving is ever reinstated.
- **The tournament is live**: `sync-results.yml` auto-commits to `main` up to 3×/day, writing
  `data/live.json` and regenerating the HTML. Rebase onto `main` right before opening/merging a
  PR; on conflicts in `data/live.json`, take `main`'s side for the data and re-apply your
  structural change on top.
- Pushing anything under `.github/workflows/` requires the git/gh token to carry the `workflow`
  OAuth scope (`gh auth refresh -h github.com -s workflow`) — a plain `repo`-scoped token is
  rejected.
- Workflow chaining note: a push made with the default `GITHUB_TOKEN` (as `sync-results.yml`
  does) never triggers other workflows' `push` triggers, so it explicitly dispatches
  `deploy-pages.yml` via `gh workflow run` after committing.

## History

The five ranked plans (`PLAN-*.md`, sequenced by `COPILOT-EXECUTE.md`) have all landed as
PRs #5–#10: the test suite + CI drift guard, the pair-collision fix, auto knockout kickoff times
(`ko_fix`), the `data/*.json` layer, the DST-safe timestamp + status badges + failure-alert
issues, and the OpenGraph/favicon social preview. One follow-up remains: a maintainer must add
`docs/assets/og-preview.png` (a 1200×630 screenshot — see `docs/assets/README.md`) and set the
repo's Settings → Social preview. `OPUS-BUILD-fan-bracket-viewer.md` specs a separate fork repo
and is not part of this codebase.
