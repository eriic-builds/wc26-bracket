# PLAN: Correct timestamps + sync observability (badge, failure alerts)

**Rank: 4 of 5.**
**Why:** The repo's own README flags this as its top "high value, low effort" idea: the
`REFRESHED` stamp hardcodes UTC−7 ("PDT summer"), which is wrong half the year and wrong the
moment anyone reuses the kit outside the US summer. Separately, the sync runs 3×/day unattended
with **no visible signal when it breaks** — a red run would sit unnoticed until the dashboard
looked stale. Cheap fixes, real payoff in trust.

## Goal

1. `REFRESHED` is computed from the real `America/Los_Angeles` zone (DST-proof), labeled
   `PT` as today.
2. The README shows a live status badge for the sync workflow.
3. A failed sync run automatically opens (or comments on) a GitHub issue so it's impossible to
   miss.

## Exact files to touch

| File | Action |
|---|---|
| `scripts/fetch_results.py` | **edit** — `now_pt_stamp()` only |
| `.github/workflows/sync-results.yml` | **edit** — add a failure-alert job/step |
| `README.md` | **edit** — badge line at top |

## Step-by-step implementation order

1. **Fix `now_pt_stamp()`** in `scripts/fetch_results.py`:
   ```python
   from zoneinfo import ZoneInfo   # add to the existing datetime import block

   def now_pt_stamp() -> str:
       now = datetime.now(ZoneInfo("America/Los_Angeles"))
       day = str(now.day)
       hour = str(int(now.strftime("%I")))
       return now.strftime(f"%B {day}, %Y · {hour}:%M %p PT")
   ```
   Keep the output format byte-compatible with today's stamps (`July 6, 2026 · 10:13 PM PT`) —
   the minute stays zero-padded, day and hour lose leading zeros.
2. **Add the badge** as the first line under the H1 in `README.md`:
   ```markdown
   [![Sync World Cup results](https://github.com/eriic-builds/wc26-bracket/actions/workflows/sync-results.yml/badge.svg)](https://github.com/eriic-builds/wc26-bracket/actions/workflows/sync-results.yml)
   [![Deploy GitHub Pages](https://github.com/eriic-builds/wc26-bracket/actions/workflows/deploy-pages.yml/badge.svg)](https://github.com/eriic-builds/wc26-bracket/actions/workflows/deploy-pages.yml)
   ```
3. **Add a failure alert** to `.github/workflows/sync-results.yml` as a final step of the `sync`
   job (needs `issues: write` added to the workflow `permissions` block):
   ```yaml
       - name: Open an issue if the sync failed
         if: failure()
         env:
           GH_TOKEN: ${{ github.token }}
         run: |
           title="Sync failed: $(date -u +%Y-%m-%d) run"
           existing=$(gh issue list --state open --search "Sync failed in:title" --json number --jq '.[0].number')
           if [ -n "$existing" ]; then
             gh issue comment "$existing" --body "Another sync failure: $GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID"
           else
             gh issue create --title "$title" --body "Run: $GITHUB_SERVER_URL/$GITHUB_REPOSITORY/actions/runs/$GITHUB_RUN_ID — check the log; the usual cause is a transient feed outage."
           fi
   ```
4. Run `python scripts/fetch_results.py --dry-run` locally to confirm the new stamp renders and
   nothing else changed.

## Edge cases a weaker model would miss

1. **Do not change the stamp format** — only the offset computation. The stamp is written into
   `build_dashboard.py` (or `data/live.json` after PLAN-json) by regex/JSON and displayed
   verbatim in three places in the HTML; a format change is harmless but makes the diff noisy
   and breaks the "keep the minute zero-padded" nuance the existing comment calls out.
2. **`zoneinfo` needs tzdata present.** Stdlib `zoneinfo` on ubuntu-latest and macOS finds the
   system database — fine. If anyone ever runs this on Windows, it needs `pip install tzdata`;
   add one line to the README FAQ rather than adding a dependency.
3. **The cron schedule itself is DST-sensitive too** (cron is UTC; the comments say "Summer ET =
   UTC−4"). The tournament ends July 19 so it can't actually bite — leave the crons alone; just
   don't "fix" them to CET or anything clever.
4. **`if: failure()` only fires when a prior step fails.** Note `fetch_results.py` deliberately
   exits 0 on total source outage ("All result sources failed — nothing to do this run"), so a
   feed outage is NOT a failed run and won't open an issue. That's by design (transient outages
   self-heal on the next scheduled run); do not change the exit code, or every FIFA blip pages
   you.
5. **Duplicate-issue spam:** the search-then-comment pattern above prevents 3 failures/day from
   opening 3 issues. Keep it.
6. **Badge caching:** GitHub badge SVGs are cached by Camo for a few minutes; a badge lagging a
   just-finished run is normal, not a bug.

## Acceptance criteria

- [ ] `python -c "import sys; sys.path.insert(0,'scripts'); import fetch_results; print(fetch_results.now_pt_stamp())"`
  prints the current LA time and says `PT`; setting the system date to January and re-running
  would show a UTC−8 time (spot-check by computing manually — don't actually change the clock).
- [ ] The stamp format is unchanged: matches regex
  `^[A-Z][a-z]+ \d{1,2}, \d{4} · \d{1,2}:\d{2} (AM|PM) PT$`.
- [ ] Both badges render on the repo's GitHub front page and link to the workflow run lists.
- [ ] Manually inserting `run: exit 1` as a temporary step and dispatching the workflow opens
  exactly one issue; a second failing dispatch comments on it instead. Remove the temp step
  after verifying.
- [ ] Workflow `permissions` block includes `issues: write` (and still `contents: write`,
  `actions: write`).
