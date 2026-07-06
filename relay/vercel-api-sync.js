// Sync relay — Vercel serverless function
// -------------------------------------------------------------------
// Same job as the Cloudflare Worker, for a Vercel deploy. Drop this file at
//   api/sync.js
// in a Vercel project. The endpoint becomes  https://<project>.vercel.app/api/sync
//
// Set these as Environment Variables (Project > Settings > Environment Variables):
//   GH_TOKEN      Fine-grained PAT, repo eriic-builds/wc26-bracket,
//                 permission: Actions = Read and write. Nothing else.
//   ALLOW_ORIGIN  Your dashboard origin, e.g. https://eriic-builds.github.io
//
// Then copy the /api/sync URL into SYNC_URL at the top of scripts/build_dashboard.py.

const REPO = "eriic-builds/wc26-bracket";
const WORKFLOW = "sync-results.yml";
const REF = "main";

export default async function handler(req, res) {
  const origin = process.env.ALLOW_ORIGIN || "*";
  res.setHeader("Access-Control-Allow-Origin", origin);
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") return res.status(204).end();
  if (req.method !== "POST") return res.status(405).json({ ok: false, error: "Method Not Allowed" });

  if (process.env.ALLOW_ORIGIN) {
    const o = req.headers.origin;
    if (o && o !== process.env.ALLOW_ORIGIN)
      return res.status(403).json({ ok: false, error: "Forbidden origin" });
  }

  const gh = await fetch(
    `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.GH_TOKEN}`,
        Accept: "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "wc26-sync-relay",
      },
      body: JSON.stringify({ ref: REF }),
    }
  );

  // GitHub returns 204 No Content on a successful dispatch.
  if (gh.status === 204) return res.status(200).json({ ok: true });
  const detail = await gh.text();
  return res.status(502).json({ ok: false, status: gh.status, detail });
}
