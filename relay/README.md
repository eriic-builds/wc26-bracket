# Sync relay — one-click "Sync now" from the dashboard

The dashboard's **Sync now** button triggers the `sync-results.yml` workflow so it
pulls the latest results on demand, from any browser or device. A GitHub Pages site
is static and cannot hold a secret, so the button never talks to GitHub directly.
Instead it POSTs to this small relay, which holds a token server-side and calls the
GitHub API for you. No token ever reaches the browser.

```
dashboard button  ──POST──▶  relay (holds GH_TOKEN)  ──▶  GitHub workflow_dispatch
```

Pick one host. Both files do the same thing.

- `cloudflare-worker.js` — Cloudflare Workers (free, ~5 minutes)
- `vercel-api-sync.js` — Vercel (drop in as `api/sync.js`)

## 1. Make the token

Create a **fine-grained personal access token**:

1. GitHub > Settings > Developer settings > Fine-grained tokens > Generate new token.
2. Resource owner: your account. Repository access: **Only select repositories** →
   `eriic-builds/wc26-bracket`.
3. Repository permissions: **Actions = Read and write**. Leave everything else at No
   access. This token can do one thing: start a workflow in this one repo.
4. Copy the token. You paste it into the relay host, never into the repo.

## 2. Deploy the relay

**Cloudflare Workers**

1. Create a Worker and paste in `cloudflare-worker.js` (or `npx wrangler deploy`).
2. Add secrets under Settings > Variables and Secrets:
   - `GH_TOKEN` = the token from step 1
   - `ALLOW_ORIGIN` = `https://eriic-builds.github.io`
3. Copy the Worker URL, e.g. `https://wc26-sync.<you>.workers.dev`.

**Vercel**

1. Put `vercel-api-sync.js` at `api/sync.js` in a project and deploy.
2. Add Environment Variables:
   - `GH_TOKEN` = the token from step 1
   - `ALLOW_ORIGIN` = `https://eriic-builds.github.io`
3. Your endpoint is `https://<project>.vercel.app/api/sync`.

## 3. Turn on the button

Set `SYNC_URL` at the top of `scripts/build_dashboard.py` to the relay URL, then
rebuild:

```python
SYNC_URL="https://wc26-sync.<you>.workers.dev"
```

```
python scripts/build_dashboard.py
```

Leave `SYNC_URL=""` to hide the button.

## How spam is kept out

- The button has a **60-second cooldown** (stored in `localStorage`), so rapid clicks
  and reloads on a device cannot fire repeated requests.
- The relay only accepts POST from your dashboard origin (`ALLOW_ORIGIN`).
- The workflow uses a `concurrency` group, so any overlapping runs queue instead of
  piling up, and each run is idempotent (no change means no commit).

## Test the relay directly

```
curl -i -X POST https://wc26-sync.<you>.workers.dev
```

A `200 {"ok":true}` means the workflow was dispatched. Check the Actions tab for the run.
