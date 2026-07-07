# Copilot instructions for wc26-bracket

## What this repo is

A single-file, self-contained World Cup 2026 bracket dashboard. There is no frontend
framework and no build tool — a Python generator writes one static `docs/index.html`
(inline CSS/JS/data, zero external requests), served by GitHub Pages. A second script
keeps it current by pulling finished match results from the web and rewriting the
generator's data.

```
input/bracket-picks.xlsx  ─┐
                           ├─►  scripts/build_dashboard.py  ─►  docs/index.html  ─►  GitHub Pages
input/instructions.md  ────┘        (DATA block + render)         (self-contained)     (live site)
                                            ▲
        scripts/fetch_results.py  ──────────┘   (writes finished results into DATA, then re-runs the generator)
```

## Architecture — read this before touching either script

- **`scripts/build_dashboard.py`** has a `DATA` block (top) and a **render engine** below the
  `"RENDER ENGINE"` banner comment. The render engine is verbatim/reproducible output logic —
  never restyle, reorder, or extend it as a side effect of a data change. All page content
  (bracket, "How it played out" story cards, stage tracker, KPIs) is *derived* from the data
  (`RES`, `SEED`, `KO_FEED`, `R32`, etc.) inside functions like `story_cards()`/`build_story()`,
  `_build_stages_list()`, and `_current_round()` — never hardcode narrative text or stage state;
  add derivation logic instead so every rebuild stays in sync.
- **`docs/index.html` is build output — never hand-edit it.** Any content/markup/CSS change goes
  into `build_dashboard.py`, then regenerate and commit the generator and the HTML together
  (`python scripts/build_dashboard.py`). A hand-edit here has caused a real regression before.
- **`scripts/fetch_results.py` rewrites `build_dashboard.py`'s source with regex**, targeting the
  literal `RES={...}`, `UPCOMING={...}`, `AUTO_HL=[...]`, and `REFRESHED="..."` assignments, then
  re-runs the generator. It never clobbers an existing result and is idempotent (no new finished
  games = no diff). It matches finished games to bracket codes round-by-round (R32 → R16 → QF →
  SF → Final, via `KO_FEED`/`match_all`), normalizes team names via `scripts/team_map.json`, and
  auto-builds the "Game facts" `AUTO_HL` cards (scorers/half/comeback context) from the same feed.
- Results source is `--source auto` by default: FIFA's free public feed
  (`api.fifa.com/api/v3`), falling back to football-data.org on an outage/empty feed (needs the
  optional `FOOTBALL_DATA_TOKEN` secret). football-data.org folds penalty-shootout goals into
  `score.fullTime` — subtract `score.penalties` to recover the true regulation/AET score.

## Data model (`DATA` block in `scripts/build_dashboard.py`)

| Variable | Holds |
| --- | --- |
| `ENTRANT`, `TIEBREAKER` | Entrant name and Final total-goals tiebreaker. |
| `SEED` | Team → group seed. |
| `R32` | The 16 Round-of-32 fixtures: `(matchcode, date, teamA, teamB, pick)`. |
| `RES` | Finished results by match code: `(goalsA, goalsB, winner, note)`. |
| `UPCOMING` | Not-yet-played matches → kickoff day label. |
| `KO_FEED` | Knockout topology: each later-round match code → its two feeder match codes. |
| `R32_TIMES`, `R16_FIX`, `R16_PICK` | Kickoff times / later fixtures/picks. |
| `R16_WIN`, `QF_WIN`, `SF_WIN`, `CHAMP`, `RUNNER` | Picks per later round. |
| `FEATURED` / `AUTO_HL` | Game-fact cards; `FEATURED` is hand-written, `AUTO_HL` is sync-generated (newest first). `HIGHLIGHTS = FEATURED + AUTO_HL`. |

## Build / run commands

```bash
python scripts/build_dashboard.py                          # regenerate docs/index.html from DATA
python scripts/fetch_results.py --dry-run                   # preview live-feed changes, write nothing
python scripts/fetch_results.py --input results.json        # apply results from a local JSON feed
python scripts/fetch_results.py --dry-run --input results.json
python scripts/fetch_results.py --source footballdata       # force football-data.org (needs FOOTBALL_DATA_TOKEN)
```
`results.json` is a list of finished games: `{"home","away","homeGoals","awayGoals"}`, plus
`"winner"`/`"note"` for decided-on-penalties games (e.g. `"note": "5-4 pens"`).

There is currently no automated test suite or CI workflow in this repo (only
`sync-results.yml` and `deploy-pages.yml` exist under `.github/workflows/`). `PLAN-ci-drift-guard-and-tests.md`
specifies adding `tests/` + a drift-guard CI job — check whether it has landed before assuming
either exists.

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
- **The tournament is live**: `sync-results.yml` auto-commits to `main` up to 3×/day, rewriting
  `RES=`/`UPCOMING=`/`AUTO_HL=`/`REFRESHED=` and regenerating the HTML. Rebase onto `main` right
  before opening/merging a PR; on conflicts in those data blocks, take `main`'s side and re-apply
  your structural change on top.
- Workflow chaining note: a push made with the default `GITHUB_TOKEN` (as `sync-results.yml`
  does) never triggers other workflows' `push` triggers, so it explicitly dispatches
  `deploy-pages.yml` via `gh workflow run` after committing.

## Pending work

`COPILOT-EXECUTE.md` is an agent runbook that sequences five root-level plan files
(`PLAN-ci-drift-guard-and-tests.md`, `PLAN-auto-knockout-fixtures.md`,
`PLAN-json-data-layer.md`, `PLAN-timezone-and-sync-observability.md`,
`PLAN-og-social-preview.md`) as ordered, dependent tasks (one branch/PR per task). Read the
relevant plan file in full, and `COPILOT-EXECUTE.md`'s global rules, before starting any of
that work — each plan contains edge cases and exact file lists the summary above omits.
