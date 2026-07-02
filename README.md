# Eric — 2026 FIFA World Cup Bracket Dashboard

> An interactive, single-file web dashboard that scores my 2026 FIFA World Cup
> bracket-challenge picks against real results — and visualizes the whole knockout bracket.
> It builds itself from my picks and keeps itself up to date after games finish.

**Live dashboard:** https://eriic-builds.github.io/Eric-fifa26-wc-bracket-dashboard/

---

## Table of contents

- [What it does](#what-it-does)
- [What's in it for me](#whats-in-it-for-me)
- [How it's built](#how-its-built)
- [The data model (the `DATA` block)](#the-data-model-the-data-block)
- [Hosting on GitHub Pages](#hosting-on-github-pages)
- [Auto-sync automation (Phase 2)](#auto-sync-automation-phase-2)
- [Refreshing results manually](#refreshing-results-manually)
- [Repo layout](#repo-layout)
- [Replicate this yourself (from zero)](#replicate-this-yourself-from-zero)
- [Troubleshooting & FAQ](#troubleshooting--faq)
- [Ideas & how to improve](#ideas--how-to-improve)
- [Credits & disclaimer](#credits--disclaimer)

---

## What it does

- **Knockout tree** with colored connectors showing the path from the Round of 32 to the Final.
- **Live scoring** of my picks against actual results as games finish (confirmed points, points
  still live, points lost, and maximum attainable).
- **"Actual vs my picks" toggle** — flip between how the tournament really went and what I
  predicted.
- **Hover-for-country-stats** cards (titles, best finish) on each team.
- **Interactive scorecard** you can hand-adjust in the browser (stored locally) to play out
  "what if" scenarios.
- **Dark / Light / Easy reading modes** for comfortable viewing.
- **Upcoming matches** with kickoff times shown in ET / CT / PT.

Everything runs client-side. Open the page and it just works — on desktop or phone.

---

## What's in it for me

I filled out a bracket. Instead of manually checking scores and re-tallying a spreadsheet,
this dashboard does it for me: at a glance I can see how many picks I've hit, where my bracket
broke, and how the real tournament diverged from my predictions — all on a page I can share.
And once the automation is on, I don't even have to update it: it refreshes itself after games.

---

## How it's built

The dashboard is **one self-contained static `index.html`** — vanilla HTML/CSS/JS, no
frameworks, no build step, and **no external network requests** (all CSS/JS/data are inlined).
That makes it ideal for GitHub Pages: there's nothing to compile and nothing to break.

That HTML is produced by a small generator:

- **`scripts/build_dashboard.py`** — Python 3, standard-library only. It has a **`DATA` block**
  at the top (the picks + results — the only part that changes per person or per refresh) and a
  **verbatim render engine** below that turns the data into the finished page. The render engine
  is never edited; only the data changes.
- **The instructions kit** (`input/instructions.md`, currently **v8**) is the build spec: the
  exact layout, scoring rules, colors, bracket geometry, and interactions the generator
  reproduces.
- **My picks** (`input/bracket-picks.xlsx`) are the source of the `DATA` block — read once from
  the workbook's **"My Bracket"** tab.

### Build flow (one picture)

```
input/bracket-picks.xlsx  ─┐
                           ├─►  scripts/build_dashboard.py  ─►  docs/index.html  ─►  GitHub Pages
input/instructions.md  ────┘        (DATA block + render)         (self-contained)     (live site)
                                            ▲
        scripts/fetch_results.py  ──────────┘   (Phase 2: writes finished results into DATA)
```

---

## The data model (the `DATA` block)

Everything the page shows comes from a handful of variables at the top of
`build_dashboard.py`. The important ones:

| Variable | What it holds |
| --- | --- |
| `ENTRANT`, `TIEBREAKER` | Name on the dashboard and the Final total-goals tiebreaker. |
| `REFRESHED` | "Last updated" timestamp shown in the header. |
| `SEED` | Every team → its group seed (e.g. `"England":"1L"`). |
| `R32` | The 16 Round-of-32 fixtures: `(matchcode, date, teamA, teamB, my pick)`. |
| `FREEBIE_MATCH` | The match everyone is auto-credited (Canada vs South Africa). |
| `RES` | **Finished** results, keyed by match code: `(goalsA, goalsB, winner, note)`. |
| `UPCOMING` | Not-yet-played matches → their kickoff day label. |
| `R32_TIMES`, `R16_FIX`, `R16_PICK` | Kickoff times and later-round fixtures/picks. |
| `R16_WIN`, `QF_WIN`, `SF_WIN`, `CHAMP`, `RUNNER` | My picks for each later round. |
| `FEATURED` / `AUTO_HL` | Game-fact recaps in the "Game facts" strip. `FEATURED` is hand-written; `AUTO_HL` is auto-appended by the sync (newest game first). `HIGHLIGHTS = FEATURED + AUTO_HL`. |

**Scoring in plain terms:** each correct advancing pick earns points by round; `winner:null`
(or a match not in `RES`) means the game is still pending and counts toward *live* points, not
lost ones. When a result is added, the engine recomputes confirmed / live / lost / attainable
and marks eliminated teams automatically.

---

## Hosting on GitHub Pages

Because the dashboard is a single static file, hosting is trivial:

1. The generated dashboard lives at **`docs/index.html`**.
2. In the repo: **Settings → Pages → Deploy from a branch → `main`, `/docs`**.
3. It goes live at `https://eriic-builds.github.io/Eric-fifa26-wc-bracket-dashboard/`
   (rebuilds within ~1 minute of any push that changes `docs/`).

---

## Auto-sync automation (Phase 2)

A GitHub Action keeps the dashboard current **without any manual work** — it's already set up
and running.

**How to think about it — "set up once, then automatic."** There is no server and no bot you
have to babysit. The automation is a **GitHub Actions workflow** (a small YAML file in the repo)
that GitHub itself runs on a schedule. On each run it calls **FIFA's free public results feed**
(`api.fifa.com` — the same data fifa.com's match centre uses; **no API key, no signup, no cost**),
grabs any newly *finished* matches, writes them into the dashboard's data, refreshes the "Game
facts" cards, rebuilds the page, and commits the change back. The only "manual" part is adding the
workflow once — and, if you're impatient, an optional **"Run workflow"** button click. After that
it runs itself.

**When it runs:** aligned to when games actually finish, not every hour. Three scheduled runs a
day, each just after a block of matches ends (games kick off ~12 PM–11 PM ET and last ~2 hours),
so a result appears within roughly **30–60 minutes of the final whistle** — never mid-game.

| Run | Approx. time (ET) | Catches games that kicked off… | Cron (UTC) |
| --- | --- | --- | --- |
| ☀️ Afternoon | ~6:00 PM ET | noon–3 PM ET | `0 22 * * *` |
| 🌆 Evening | ~9:30 PM ET | 5–6:30 PM ET | `30 1 * * *` |
| 🌙 Late night | ~2:00 AM ET | 8–11 PM ET | `0 6 * * *` |

You can also run it on demand: **Actions → Sync World Cup results → Run workflow**.

**What each run does** (`scripts/fetch_results.py`):

1. Reads the Round-of-32 fixtures **and the knockout topology** (`KO_FEED`: R16 → QF → SF →
   Final) straight from `build_dashboard.py` so it always matches my bracket.
2. Pulls **finished** 2026 World Cup matches from **FIFA's public feed**
   (`api.fifa.com/api/v3/calendar/matches`, competition `17` / season `285023`) — no token
   required. (`--source footballdata` is still available if you'd rather use that API + token.)
3. Normalizes source team names to the bracket's spellings via **`scripts/team_map.json`**
   (e.g. "Bosnia and Herzegovina" → "Bosnia & Herz.", "Côte d'Ivoire" → "Ivory Coast").
4. Matches each finished game to a bracket match by the pair of teams — first the Round of 32,
   then **every later round** (R16, QF, SF, Final), since each knockout match's teams are the
   winners of its two feeder matches — and writes it into the `RES` / `UPCOMING` / `REFRESHED`
   blocks.
5. **Auto-writes the "Game facts" highlight cards** — it rebuilds `AUTO_HL` with the **last six
   finished games** from the whole feed (not just my bracket), each as a card with an emoji, a
   short headline, the scoreline, the **day · host city**, and a one-sentence factual recap — so
   a visitor instantly sees what just happened.
6. Re-runs the generator to rebuild `docs/index.html`, then commits & pushes if anything
   changed (which triggers the Pages redeploy).

**Why it's safe:**

- **Finished games only** — a match still in progress or not started is never written.
- **Never clobbers** an existing result and is **idempotent**: if nothing new is final, it
  changes nothing and exits cleanly.
- **No key, no secret to leak** — the default FIFA feed needs no token, so there's nothing to
  configure and nothing that can expire.
- **Draws stay out of the bracket** — a genuine draw (no decider) is shown in the game-fact
  cards but never recorded as a knockout result.

### First-time setup (already done here, kept for reference)

Nothing to configure for data access — the default source is FIFA's free public feed (no token).
Setup is just: commit `.github/workflows/sync-results.yml`, then test with **Actions → Sync World
Cup results → Run workflow**. A green ✅ and the log line `Source: FIFA public feed …` means it's
live. *(Optional: to use football-data.org instead, add a free `FOOTBALL_DATA_TOKEN` secret and
run the script with `--source footballdata`.)*

---

## Refreshing results manually

You don't need the automation to update the board — any of these work:

```bash
# 1) Edit the DATA block directly, then rebuild:
python scripts/build_dashboard.py

# 2) Feed results from a local JSON file (same shape the fetcher uses):
python scripts/fetch_results.py --input results.json

# 3) Preview what a sync WOULD change, writing nothing:
python scripts/fetch_results.py --dry-run          # (default FIFA feed, no token)
python scripts/fetch_results.py --input results.json --dry-run
```

A local `results.json` is just a list of finished games, e.g.:

```json
[
  {"home": "Portugal", "away": "Croatia", "homeGoals": 2, "awayGoals": 1},
  {"home": "Switzerland", "away": "Algeria", "homeGoals": 1, "awayGoals": 1,
   "winner": "Algeria", "note": "5-4 pens"}
]
```

Then commit and push — Pages redeploys in about a minute.

---

## Repo layout

| Path | What it is |
| --- | --- |
| `input/instructions.md` | The **v8 build kit** — the spec the generator reproduces. |
| `input/bracket-picks.xlsx` | My bracket picks (the "My Bracket" tab seeds the `DATA` block). |
| `scripts/build_dashboard.py` | Stdlib generator: `DATA` block + render engine → `index.html`. |
| `scripts/fetch_results.py` | Web/offline results sync that updates `DATA` and rebuilds. |
| `scripts/team_map.json` | Source-name → bracket-name mapping (16 known variants). |
| `docs/index.html` | The generated, self-contained dashboard (served by Pages). |
| `.github/workflows/sync-results.yml` | The scheduled auto-sync workflow. |
| `README.md` | This file. |
| `.gitignore` | Ignores Python/editor/secret cruft. |

---

## Replicate this yourself (from zero)

Want your own copy — for your picks, or a friend's? Follow these steps end to end. You'll go from
an empty repo to a live, self-updating dashboard. Commands are shown for **Windows PowerShell**;
macOS/Linux users can drop the `.exe`/`py` differences.

### 0. Prerequisites (one-time, on your machine)

- A **GitHub account**.
- **Git** installed — check with `git --version`.
- **Python 3.10+** installed — check with `python --version`.
- The two source files:
  - the **build kit** (`instructions.md` — the generator + spec; this repo uses **v8**), and
  - your **bracket picks** as an Excel file (the workbook's **"My Bracket"** tab).

> No other dependencies. The generator is **standard-library only** — nothing to `pip install`.

### 1. Create an empty repo on GitHub

- **Web:** github.com → **New repository** → name it (e.g. `my-wc2026-bracket`) → **Public** →
  *don't* add a README/`.gitignore` (you'll push your own) → **Create repository**.
- **Or with the GitHub CLI:** `gh repo create my-wc2026-bracket --public --clone`

### 2. Clone it and scaffold the folders

```powershell
git clone https://github.com/<you>/my-wc2026-bracket.git
cd my-wc2026-bracket
mkdir input, docs, scripts, .github\workflows
```

### 3. Add the four code files

Copy these in from the kit / this repo (they're generic — only the **data** at the top of
`build_dashboard.py` is personal):

| File | Where it comes from |
| --- | --- |
| `scripts/build_dashboard.py` | The Python generator inside the **build kit** (`input/instructions.md`). Point its output at `docs/index.html`. |
| `scripts/fetch_results.py` | The results-sync script (copy from this repo). |
| `scripts/team_map.json` | The source-name → bracket-name map (copy from this repo). |
| `.github/workflows/sync-results.yml` | The scheduled workflow (copy from this repo). |

Also drop your kit + Excel into `input/` for reference:

```powershell
copy <path-to>\instructions.md      input\instructions.md
copy <path-to>\your-picks.xlsx      input\bracket-picks.xlsx
```

### 4. Put in your picks (the `DATA` block)

Open `scripts/build_dashboard.py` and edit only the **`DATA` block** at the top (see
[the data model](#the-data-model-the-data-block)) to match your workbook's "My Bracket" tab:

- `ENTRANT`, `TIEBREAKER` — your name and Final total-goals tiebreaker.
- `R32` — your 16 Round-of-32 fixtures and picks.
- `R16_PICK`, `R16_WIN`, `QF_WIN`, `SF_WIN`, `CHAMP`, `RUNNER` — your later-round picks.
- Leave `RES` empty (or with only truly-finished games) — the automation fills it as games play.

**Everything below the `RENDER ENGINE` banner stays verbatim — don't edit it.**

### 5. Build, then push

```powershell
$env:PYTHONIOENCODING="utf-8"      # Windows: avoid cp1252 errors on ★ / – characters
python scripts\build_dashboard.py  # writes docs\index.html
git add .
git commit -m "Initial dashboard"
git push
```

### 6. Turn on GitHub Pages

Repo **Settings → Pages → Build and deployment → Deploy from a branch → `main` / `/docs` →
Save**. Within ~1 minute it's live at `https://<you>.github.io/my-wc2026-bracket/`.

### 7. Results source — nothing to configure

The sync uses **FIFA's free public feed** (`api.fifa.com/api/v3`, competition `17` / season
`285023` = World Cup 2026) by default. It needs **no API key, no account, and no repo secret** —
it only reads **finished** matches. There's nothing to set up here.

> *Optional alternative:* to use football-data.org instead, register for a free token at
> [football-data.org](https://www.football-data.org/client/register), add it as a repo secret named
> `FOOTBALL_DATA_TOKEN` (**Settings → Secrets and variables → Actions**), and change the workflow
> step to `python scripts/fetch_results.py --source footballdata`.

### 8. Test the automation

Repo **Actions → Sync World Cup results → Run workflow → Run**. A green ✅ with a log line like
`Source: FIFA public feed …` means it's wired up. If no games are newly final it will correctly
report `No new finished games to apply` — that's success, not a failure.

### 9. Done — it now runs itself

From here the workflow fires on its schedule (see the table above), pulls any finished games,
rebuilds `docs/index.html`, and pushes — which redeploys Pages automatically. To change *when* it
runs, edit the `cron` lines in `.github/workflows/sync-results.yml` (times are **UTC**).

---

## How this repo was built (history)

1. Scaffolded the repo (`input/`, `docs/`, `scripts/`, `.github/workflows/`) with an `input/`
   drop-zone for the two source files.
2. Saved the kit's Python generator verbatim to `scripts/build_dashboard.py` and
   repointed its output to `docs/index.html`.
3. **Verified my picks against the Excel "My Bracket" tab** — all Round-of-32 picks, the
   R16/QF/SF winners, `CHAMP` (England), `RUNNER` (France) and the tiebreaker (4) matched — then
   personalized `ENTRANT` and the refresh timestamp.
4. Generated the dashboard, enabled GitHub Pages from `/docs`, and confirmed it served (HTTP
   200).
5. Added the Phase 2 sync script, team map, and workflow; verified the update logic with a mock
   feed (including a penalty shootout) and a live workflow run.
6. **Kit v7:** added a sticky left side-navigation rail (with scrollspy) and a top "last refreshed"
   indicator to the render engine, and bumped `input/instructions.md` to v7 so the rail is
   reproduced for any future build.
7. **Kit v8:** added a live knockout board (R16/QF/SF/Final) that scores from real results via a
   shared bracket topology (`KO_FEED`) and derived per-round picks, extended the sync to resolve
   every knockout round, and made it auto-append factual game-fact highlights.

---

## Troubleshooting & FAQ

- **A game finished but the board didn't update yet.** The next scheduled run picks it up
  (within ~30–60 min of full time). To see it now: **Actions → Sync World Cup results → Run
  workflow**.
- **The run is green but nothing changed.** That's normal when there are no *newly* finished
  games — the log will say `No new finished games to apply`.
- **The run failed (red ❌).** Open the failed run's log. With the default FIFA feed there's no
  token to expire; the usual cause is a transient network/API hiccup — just re-run it. (If you
  switched to `--source footballdata`, also check the `FOOTBALL_DATA_TOKEN` secret and rate limit.)
- **A team's result didn't match up.** The feed may spell a country differently — add the
  variant to `scripts/team_map.json` (left side = feed spelling, right side = bracket spelling).
- **I want to change when it runs.** Edit the `cron` lines in
  `.github/workflows/sync-results.yml` (times are in UTC; summer ET = UTC − 4).

---

## Ideas & how to improve

Honest analysis of what could make this better, roughly by value vs. effort:

**High value, low effort**
- **Add a `LICENSE`** (e.g. MIT) so others can reuse the generator cleanly.
- **Timezone accuracy for the timestamp.** `REFRESHED` currently assumes summer PDT (UTC−7); it
  should compute the offset (or label UTC) so it stays correct year-round.
- **Skip empty commits in CI.** Already handled (commit only on change) — worth keeping an eye on
  as rounds grow.

**Medium value**
- **A tiny GitHub Actions badge** in this README showing the last sync status.
- **A fallback results source.** The default is FIFA's free feed; football-data.org is already
  wired as an alternate (`--source footballdata`). A small auto-fallback between them would make a
  single outage a non-event.
- **Unit tests** for `fetch_results.py` (name normalization, team-pair matching, draw handling)
  using a committed sample feed under `tests/`.
- **Deploy via GitHub Pages Actions** (instead of branch-based) to make the redeploy explicit and
  add a build check.

**Nice to have**
- **Multi-entrant support** — the generator already isolates `DATA` per person; a small wrapper
  could build several brackets (mine + friends') and a shared leaderboard page.
- **Accessibility pass** — verify color-contrast in all three themes and keyboard navigation of
  the bracket.
- **A screenshot / social preview image** in the README and as an OpenGraph tag so shared links
  look good.

---

## Credits & disclaimer

Match results, scores, and kickoff times come from a verified web lookup (FIFA official records,
corroborated by major outlets). Historical country stats are public World Cup records. Built
with the reusable World Cup Bracket Dashboard kit (v8).

> Personal project. Not affiliated with FIFA, GitHub, or Microsoft.
