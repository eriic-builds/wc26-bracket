// Sync relay — Cloudflare Worker
// -------------------------------------------------------------------
// A tiny secure endpoint that triggers the wc26-bracket "Sync World Cup
// results" workflow. The dashboard's "Sync now" button POSTs here; this
// Worker calls the GitHub API with a token that never leaves the server.
//
// Set these as Worker secrets (Settings > Variables and Secrets):
//   GH_TOKEN      Fine-grained PAT, repo eriic-builds/wc26-bracket,
//                 permission: Actions = Read and write. Nothing else.
//   ALLOW_ORIGIN  Your dashboard origin, e.g. https://eriic-builds.github.io
//
// Deploy: `npx wrangler deploy`  (or paste into the Cloudflare dashboard editor)
// Then copy the Worker URL into SYNC_URL at the top of scripts/build_dashboard.py.

const REPO = "eriic-builds/wc26-bracket";
const WORKFLOW = "sync-results.yml";
const REF = "main";

export default {
  async fetch(request, env) {
    const origin = env.ALLOW_ORIGIN || "*";
    const cors = {
      "Access-Control-Allow-Origin": origin,
      "Access-Control-Allow-Methods": "POST, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type",
      "Access-Control-Max-Age": "86400",
    };

    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
    if (request.method !== "POST")
      return json({ ok: false, error: "Method Not Allowed" }, 405, cors);

    // Only accept calls from the dashboard origin (best-effort guard).
    if (env.ALLOW_ORIGIN) {
      const o = request.headers.get("Origin");
      if (o && o !== env.ALLOW_ORIGIN)
        return json({ ok: false, error: "Forbidden origin" }, 403, cors);
    }

    const gh = await fetch(
      `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`,
      {
        method: "POST",
        headers: {
          Authorization: `Bearer ${env.GH_TOKEN}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "User-Agent": "wc26-sync-relay",
        },
        body: JSON.stringify({ ref: REF }),
      }
    );

    // GitHub returns 204 No Content on a successful dispatch.
    if (gh.status === 204) return json({ ok: true }, 200, cors);
    const detail = await gh.text();
    return json({ ok: false, status: gh.status, detail }, 502, cors);
  },
};

function json(body, status, cors) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors, "Content-Type": "application/json" },
  });
}
