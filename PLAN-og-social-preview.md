# PLAN: Social preview — OpenGraph/Twitter cards, meta description, favicon

**Rank: 5 of 5.**
**Why:** The dashboard exists to be shared (the SLED bracket group, the README's live link), but
the page has **no OG tags, no meta description, no favicon** — a shared link renders as a bare
URL with no image or summary in Teams/Slack/iMessage. This is pure presentation-layer work from
the README's own ideas list; it touches only the generator's `<head>` and one image asset, so
it's low-risk and independent of the other plans.

## Goal

Shared links to `https://eriic-builds.github.io/wc26-bracket/` unfurl with a title, a one-line
description, and a 1200×630 preview image; the browser tab shows a favicon; the repo itself has
a social preview image configured.

## Exact files to touch

| File | Action |
|---|---|
| `scripts/build_dashboard.py` | **edit** — `<head>` additions in the `HTML=` assembly only |
| `docs/assets/og-preview.png` | **create** — 1200×630 screenshot |
| `docs/index.html` | regenerated (never hand-edited) |
| `README.md` | **edit** — embed the screenshot near the top |

## Step-by-step implementation order

1. **Capture the preview image.** Open `docs/index.html` in a browser at a 1280px-wide window,
   dark theme, scrolled to show the hero + KPI row. Screenshot, crop/resize to exactly
   1200×630, save as `docs/assets/og-preview.png`. Keep it under 300 KB (PNG or re-export as
   JPEG if bigger; if JPEG, name it `.jpg` and adjust all references).
2. **Edit the `<head>` in `scripts/build_dashboard.py`** — in the `HTML=(...)` assembly, directly
   after the `<title>` element, insert (as adjacent f-string pieces following the file's existing
   string-concatenation style):
   ```python
   +f'<meta name="description" content="{esc(ENTRANT)}’s 2026 FIFA World Cup bracket, scored live against real results — {CONF} points confirmed, champion pick {esc(CHAMP)}.">'
   +'<link rel="canonical" href="https://eriic-builds.github.io/wc26-bracket/">'
   +f'<meta property="og:title" content="{esc(ENTRANT)}’s World Cup 2026 Bracket">'
   +f'<meta property="og:description" content="Live bracket scoring — {CONF}/{POINTS_MAX} points confirmed, backing {esc(CHAMP)}.">'
   +'<meta property="og:type" content="website">'
   +'<meta property="og:url" content="https://eriic-builds.github.io/wc26-bracket/">'
   +'<meta property="og:image" content="https://eriic-builds.github.io/wc26-bracket/assets/og-preview.png">'
   +'<meta property="og:image:width" content="1200"><meta property="og:image:height" content="630">'
   +'<meta name="twitter:card" content="summary_large_image">'
   +'<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>⚽</text></svg>">'
   ```
3. **Rebuild:** `python scripts/build_dashboard.py`, open the page, confirm the favicon shows
   and `view-source:` contains the tags.
4. **README:** add `![Dashboard preview](docs/assets/og-preview.png)` under the intro
   blockquote.
5. **Repo-level social preview:** `gh repo edit` cannot set it; do it in the browser —
   repo → Settings → General → Social preview → upload the same PNG. (One manual step; note it
   in the commit message so it isn't forgotten.)
6. Commit, push, wait for Pages deploy, then validate with an unfurl debugger (e.g. paste the
   URL into a private Slack/Teams message, or use opengraph.xyz).

## Edge cases a weaker model would miss

1. **Never hand-edit `docs/index.html`** — issue #2 documented exactly this failure: hand
   patches get wiped on the next sync's regeneration. All tags go into the generator; the HTML
   is build output.
2. **OG images must be absolute URLs.** Scrapers don't resolve relative paths — use the full
   `https://eriic-builds.github.io/wc26-bracket/assets/...` URL, and note the Pages URL has no
   `/docs/` prefix (the `docs/` folder is the site root).
3. **The description embeds live numbers (`CONF`)** and therefore changes every sync — that's
   fine and actually good (fresh unfurls), but it means the tag must be built with f-strings at
   generate time, not pasted as a constant. Mind the `esc()` on every user-derived string; the
   entrant name contains no HTML today but the generator is reused by other entrants via the
   kit.
4. **The curly apostrophe in the title** (`’`) is already in the `<title>`; reuse `’` in
   the OG title for consistency, not a straight quote — link unfurls show it verbatim.
5. **The SVG-emoji favicon keeps the page self-contained** (README promises "no external
   network requests"). Don't add a binary `.ico` fetched from elsewhere, and don't reference a
   font CDN.
6. **`docs/.nojekyll` already exists** — assets under `docs/assets/` serve fine; don't create
   `docs/assets/.nojekyll` or fiddle with Pages config.
7. **Unfurl caches are sticky.** Teams/Slack/Twitter cache the first unfurl per URL for hours
   to days; if you iterate on the image, test with a cache-busting query string
   (`/?v=2`) rather than concluding the tags are broken.
8. **The percent-encoded quotes in the favicon data URI** (`%22`) are required — raw `"` inside
   the `href="..."` attribute would terminate it. Copy the line exactly.

## Acceptance criteria

- [ ] `curl -s https://eriic-builds.github.io/wc26-bracket/ | grep -c 'og:'` ≥ 6 after deploy.
- [ ] `docs/assets/og-preview.png` is exactly 1200×630 (`sips -g pixelWidth -g pixelHeight`),
  < 300 KB.
- [ ] Pasting the live URL into a Slack/Teams private message unfurls with image + title +
  description.
- [ ] Browser tab shows the ⚽ favicon on the live site.
- [ ] CI drift guard (PLAN-ci) still green — i.e. the committed `docs/index.html` matches a
  fresh generator run.
- [ ] The GitHub repo card (share the repo URL itself) shows the uploaded social preview.
