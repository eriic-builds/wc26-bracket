# Eric — 2026 FIFA World Cup Bracket Dashboard

> An interactive, single-file web dashboard that scores my 2026 FIFA World Cup
> bracket-challenge picks against real results — and visualizes the whole bracket.

**Live dashboard:** https://eriic-builds.github.io/Eric-fifa26-wc-bracket-dashboard/

---

## What it does

- **Knockout tree** with colored connectors showing the path from Round of 32 to the Final.
- **Live scoring** of my picks against actual results as games finish.
- **"Actual vs my picks" toggle** — flip between how the tournament really went and what I predicted.
- **Hover-for-country-stats** on each team.
- **Dark / Light / Easy reading modes** for comfortable viewing.

Everything runs client-side. Open the page and it just works.

---

## What''s in it for me

I filled out a bracket. Instead of manually checking scores and re-tallying a spreadsheet,
this dashboard does it for me: at a glance I can see how many picks I''ve hit, where my bracket
broke, and how the real tournament diverged from my predictions — all on a page I can share.

---

## How it''s built

The dashboard is **one self-contained static `index.html`** — vanilla HTML/CSS/JS, no
frameworks, no build step, and **no external network requests** (everything is inlined). That
makes it perfect for GitHub Pages: there''s nothing to compile.

That HTML is produced by a small generator:

- **`scripts/build_dashboard.py`** — Python 3, standard library only. It has a **`DATA` block**
  at the top (the picks + results you swap per person or per refresh) and a **verbatim render
  engine** below that turns the data into the finished `index.html`.
- **The instructions kit** (`input/instructions.md`) is the build spec: layout, scoring rules,
  and behavior the generator follows.
- **My picks** (`input/bracket-picks.xlsx`) seed the `DATA` block.

### Refreshing results

1. Update the match results in the `DATA` block of `build_dashboard.py`.
2. Re-run it: `python scripts/build_dashboard.py`.
3. It regenerates `docs/index.html`.
4. Commit and push — GitHub Pages redeploys in about a minute.

---

## Hosting on GitHub Pages

Because the dashboard is a single static file, hosting is trivial:

1. The generated dashboard lives at **`docs/index.html`**.
2. In the repo: **Settings → Pages → Deploy from a branch → `main`, `/docs`**.
3. It goes live at `https://eriic-builds.github.io/Eric-fifa26-wc-bracket-dashboard/`.

---

## Repo layout

| Path | What it is |
| --- | --- |
| `input/instructions.md` | The instructions kit — the build spec the generator follows. |
| `input/bracket-picks.xlsx` | My bracket picks (teams, seeds, match ids, predicted winners). |
| `scripts/build_dashboard.py` | Stdlib generator: `DATA` block + render engine to `index.html`. |
| `docs/index.html` | The generated, self-contained dashboard (served by Pages). |
| `scripts/fetch_results.py` | *(Phase 2)* pulls latest results into `DATA` before a rebuild. |
| `.github/workflows/` | *(Phase 2)* the scheduled auto-rebuild automation. |

---

## Two phases

- **Phase 1 — Build + host.** Generate the dashboard from my picks + the kit, publish on Pages.
  Results are refreshed by updating the `DATA` block and re-running the generator.
- **Phase 2 — Auto-sync from the web.** A scheduled GitHub Action pulls the latest match
  results into the `DATA` block, re-runs `build_dashboard.py`, and commits the updated
  `index.html` — so the dashboard refreshes on its own about an hour after games.

### Turning on auto-sync (Phase 2)

The automation lives in **`.github/workflows/sync-results.yml`** and runs
**`scripts/fetch_results.py`** every hour (and on demand from the Actions tab). To activate it:

1. Get a **free** API token from [football-data.org](https://www.football-data.org/) (register → your account shows a token). No cost.
2. In this repo: **Settings → Secrets and variables → Actions → New repository secret**,
   name it **`FOOTBALL_DATA_TOKEN`**, paste the token.
3. That's it. The workflow fetches finished World Cup games, updates results, and redeploys.
   Until the token is added, the workflow simply does nothing (a safe no-op).

**How the sync stays safe:** it only writes *finished* games, never overwrites a pending
match, and is idempotent (re-running changes nothing if there's nothing new). Team names from
the feed are mapped to the bracket's names via **`scripts/team_map.json`** (e.g.
"Bosnia and Herzegovina" → "Bosnia & Herz.").

**Manual / offline update:** you can also feed results from a local file —
`python scripts/fetch_results.py --input results.json` — or preview with `--dry-run`.

> **Note on Phase 2:** result-fetching happens *outside* the generator. The automation adds a
> step that pulls the latest results into the `DATA` block **before** running the generator.

---

> Personal project. Not affiliated with FIFA, GitHub, or Microsoft.
