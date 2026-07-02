#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sync finished 2026 World Cup results into the dashboard, then rebuild it.

What it does
------------
1. Reads the Round-of-32 fixtures straight out of ``build_dashboard.py`` (the
   ``R32`` list) so it always matches the entrant's bracket.
2. Gets finished-match results from the web:
     - default: football-data.org (free tier), competition ``WC``, using the
       ``FOOTBALL_DATA_TOKEN`` environment variable / GitHub secret; or
     - ``--input results.json`` for a local/offline feed (also used by self-test).
3. Normalizes source team names to the bracket's names via ``team_map.json``.
4. Matches each finished game to a bracket match by the pair of teams, and
   updates the ``RES`` and ``UPCOMING`` blocks in ``build_dashboard.py`` in place
   (finished games only, never clobbering a still-pending game with junk).
5. Re-runs ``build_dashboard.py`` to regenerate ``docs/index.html``.

Safety
------
- Idempotent: if nothing new is final, it changes nothing and exits 0.
- ``--dry-run`` reports what *would* change and writes nothing.
- No token and no ``--input`` => clean no-op exit (so the scheduled workflow
  succeeds even before a token is configured).
- Only whole, finished matches are written; draws must carry a decider note
  (e.g. penalties) or they are skipped.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, "build_dashboard.py")
TEAM_MAP = os.path.join(HERE, "team_map.json")

FD_URL = "https://api.football-data.org/v4/competitions/WC/matches?status=FINISHED"


def load_team_map() -> dict:
    try:
        with open(TEAM_MAP, encoding="utf-8") as fh:
            raw = json.load(fh)
        return {k: v for k, v in raw.items() if not k.startswith("_")}
    except FileNotFoundError:
        return {}


def norm(name: str, tmap: dict) -> str:
    if name is None:
        return ""
    name = name.strip()
    return tmap.get(name, name)


def read_r32(gen_text: str):
    """Return list of (code, teamA, teamB) from the R32 block."""
    rows = re.findall(
        r'\("(M\d+)","[^"]*","([^"]*)","([^"]*)","[^"]*"\)', gen_text
    )
    return [(c, a, b) for (c, a, b) in rows]


def parse_res_block(gen_text: str) -> dict:
    """Return the current RES dict {code: (gA, gB, winner, note)}."""
    m = re.search(r"RES=\{([^}]*)\}", gen_text, re.DOTALL)
    res = {}
    if not m:
        return res
    for code, a, b, w, note in re.findall(
        r'"(M\d+)":\((\d+),(\d+),"([^"]*)","([^"]*)"\)', m.group(1)
    ):
        res[code] = (int(a), int(b), w, note)
    return res


def parse_upcoming_block(gen_text: str) -> dict:
    m = re.search(r"UPCOMING=\{([^}]*)\}", gen_text, re.DOTALL)
    up = {}
    if not m:
        return up
    for code, day in re.findall(r'"(M\d+)":"([^"]*)"', m.group(1)):
        up[code] = day
    return up


def parse_ko_feed(gen_text: str) -> dict:
    """Return the knockout topology {code: (feederA, feederB)} from KO_FEED."""
    m = re.search(r"KO_FEED=\{(.*?)\}", gen_text, re.DOTALL)
    feed = {}
    if not m:
        return feed
    for code, fa, fb in re.findall(r'"(M\d+)":\("(M\d+)","(M\d+)"\)', m.group(1)):
        feed[code] = (fa, fb)
    return feed


def ko_label(code: str, ko_feed: dict) -> str:
    """Human round label for a match code (used for auto game-fact highlights)."""
    if code not in ko_feed:
        return "Round of 32"
    n = int(code[1:])
    if n <= 96:
        return "Round of 16"
    if n <= 100:
        return "Quarterfinal"
    if n <= 102:
        return "Semifinal"
    return "Final"


# ── result sources ──────────────────────────────────────────────────────────
def results_from_footballdata(tmap: dict):
    token = os.environ.get("FOOTBALL_DATA_TOKEN", "").strip()
    if not token:
        return None
    req = urllib.request.Request(FD_URL, headers={"X-Auth-Token": token})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    out = []
    for m in data.get("matches", []):
        if m.get("status") != "FINISHED":
            continue
        home = norm((m.get("homeTeam") or {}).get("name"), tmap)
        away = norm((m.get("awayTeam") or {}).get("name"), tmap)
        score = m.get("score") or {}
        ft = score.get("fullTime") or {}
        gh, ga = ft.get("home"), ft.get("away")
        if gh is None or ga is None:
            continue
        note = ""
        winner_side = score.get("winner")
        pens = score.get("penalties") or {}
        ph, pa = pens.get("home"), pens.get("away")
        shootout = ph is not None and pa is not None and int(ph) != int(pa)
        if shootout:
            ph, pa = int(ph), int(pa)
            # football-data.org folds the shootout goals into fullTime (so a
            # 1-1 game won 4-3 on pens reports as 5-4). Recover the level
            # regulation/ET score by subtracting the shootout tally.
            if gh != ga:
                rh, ra = int(gh) - ph, int(ga) - pa
            else:
                rh, ra = int(gh), int(ga)
            if rh < 0 or ra < 0 or rh != ra:
                rh, ra = int(gh), int(ga)  # unexpected shape -> keep raw
            gh, ga = rh, ra
            if winner_side == "HOME_TEAM":
                w = home
            elif winner_side == "AWAY_TEAM":
                w = away
            else:
                w = home if ph > pa else away
            note = f"{max(ph, pa)}\u2013{min(ph, pa)} pens"
        elif gh == ga:  # level with no shootout -> decided in extra time
            if winner_side == "HOME_TEAM":
                w = home; note = "AET"
            elif winner_side == "AWAY_TEAM":
                w = away; note = "AET"
            else:
                continue  # genuine draw with no decider -> skip
        else:
            w = home if gh > ga else away
        out.append({"home": home, "away": away, "gh": int(gh), "ga": int(ga),
                    "winner": w, "note": note, "date": (m.get("utcDate") or "")})
    return out


def results_from_json(path: str, tmap: dict):
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    out = []
    for m in raw:
        home = norm(m.get("home"), tmap)
        away = norm(m.get("away"), tmap)
        gh = m.get("homeGoals", m.get("gh"))
        ga = m.get("awayGoals", m.get("ga"))
        if gh is None or ga is None:
            continue
        gh, ga = int(gh), int(ga)
        note = m.get("note", "")
        if gh == ga:
            w = norm(m.get("winner"), tmap)
            if not w:
                continue  # draw needs an explicit decider
        else:
            w = home if gh > ga else away
        out.append({"home": home, "away": away, "gh": gh, "ga": ga,
                    "winner": w, "note": note, "date": (m.get("date") or "")})
    return out


# ── matching + rewrite ───────────────────────────────────────────────────────
def match_all(r32, ko_feed, base_res, feed):
    """Resolve results for every round. Returns (res, applied).

    ``res`` = {code: (gA,gB,winner,note)} keyed to bracket order (R32 fixture order,
    then feeder-winner order for later rounds). ``applied`` = {code: dict} carrying the
    feed detail (teams in bracket order, score, date, label) for finished games — used to
    build the auto game-fact highlights.
    """
    by_pair = {frozenset((f["home"], f["away"])): f for f in feed}
    res = dict(base_res)
    applied = {}

    def orient(code, a, b):
        f = by_pair.get(frozenset((a, b)))
        if not f:
            return
        if f["home"] == a:
            gA, gB = f["gh"], f["ga"]
        else:
            gA, gB = f["ga"], f["gh"]
        res[code] = (gA, gB, f["winner"], f["note"])
        applied[code] = {"a": a, "b": b, "gA": gA, "gB": gB,
                         "winner": f["winner"], "note": f["note"], "date": f.get("date", "")}

    # Round of 32 — fixed fixtures.
    for code, a, b in r32:
        orient(code, a, b)
    # Later rounds — process ascending so feeders (smaller codes) are resolved first;
    # each match's two teams are the winners of its feeder matches.
    for code in sorted(ko_feed, key=lambda c: int(c[1:])):
        fa, fb = ko_feed[code]
        wa = res[fa][2] if fa in res else None
        wb = res[fb][2] if fb in res else None
        if wa and wb:
            orient(code, wa, wb)
    return res, applied


def _fmt_day(iso: str) -> str:
    """'2026-07-04T17:00:00Z' -> 'Sat Jul 4' (best-effort; '' if unparseable)."""
    if not iso:
        return ""
    try:
        dt = datetime.strptime(iso[:10], "%Y-%m-%d")
        return re.sub(r"\b0(\d)", r"\1", dt.strftime("%a %b %d"))
    except ValueError:
        return ""


def build_auto_hl(applied, ko_feed, limit=8):
    """Newest-first factual one-liners for finished games. Plain facts, no editorializing."""
    items = sorted(applied.items(),
                   key=lambda kv: (kv[1].get("date", ""), int(kv[0][1:])), reverse=True)
    entries = []
    for code, d in items[:limit]:
        a, b, gA, gB = d["a"], d["b"], d["gA"], d["gB"]
        w, note = d["winner"], d["note"]
        loser = a if w == b else b
        label = ko_label(code, ko_feed)
        emoji = "🥅" if "pens" in note else "⚽"
        day = _fmt_day(d.get("date", ""))
        when = (day + " · " + label) if day else label
        title = f"{a} {gA}\u2013{gB} {b}"
        if "pens" in note:
            body = f"{w} beat {loser} on penalties ({note}) after a {gA}\u2013{gB} draw in the {label}."
        else:
            wg, lg = (gA, gB) if w == a else (gB, gA)
            body = f"{w} beat {loser} {wg}\u2013{lg} in the {label}."
        # keep every field free of the ] character so the block stays regex-rewritable
        entries.append((emoji, label, title, when, body))
    return entries


def render_auto_hl(entries) -> str:
    if not entries:
        return "AUTO_HL=[]"
    lines = ["AUTO_HL=["]
    for ic, tag, ti, wh, bd in entries:
        parts = ",".join(json.dumps(x, ensure_ascii=False) for x in (ic, tag, ti, wh, bd))
        lines.append(" (" + parts + "),")
    lines.append("]")
    return "\n".join(lines)


def render_res(res: dict) -> str:
    order = sorted(res, key=lambda c: int(c[1:]))
    items = [f'"{c}":({res[c][0]},{res[c][1]},"{res[c][2]}","{res[c][3]}")'
             for c in order]
    return "RES={" + ",\n ".join(items) + "}"


def render_upcoming(up: dict) -> str:
    order = sorted(up, key=lambda c: int(c[1:]))
    items = [f'"{c}":"{up[c]}"' for c in order]
    return "UPCOMING={" + ",".join(items) + "}"


def now_pt_stamp() -> str:
    pt = timezone(timedelta(hours=-7))  # PDT (summer)
    stamp = datetime.now(pt).strftime("%B %d, %Y \u00b7 %I:%M %p PT")
    # trim leading zeros for readability ("July 02" -> "July 2", "09:00" -> "9:00")
    return re.sub(r"\b0(\d)", r"\1", stamp)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", help="local results.json feed (instead of the web API)")
    ap.add_argument("--dry-run", action="store_true", help="report changes, write nothing")
    ap.add_argument("--no-build", action="store_true", help="update source but skip regenerating HTML")
    args = ap.parse_args()

    tmap = load_team_map()
    with open(GEN, encoding="utf-8") as fh:
        gen_text = fh.read()
    r32 = read_r32(gen_text)
    ko_feed = parse_ko_feed(gen_text)
    cur_res = parse_res_block(gen_text)
    cur_up = parse_upcoming_block(gen_text)

    if args.input:
        feed = results_from_json(args.input, tmap)
        src = f"local file {args.input}"
    else:
        feed = results_from_footballdata(tmap)
        src = "football-data.org"
        if feed is None:
            print("No FOOTBALL_DATA_TOKEN set and no --input given \u2014 nothing to do.")
            return 0

    # Resolve every round (R32 -> R16 -> QF -> SF -> Final) from the same feed.
    new_res, applied = match_all(r32, ko_feed, cur_res, feed)

    # Only NEW/changed finished games; never remove an existing result.
    changed = []
    for code in list(new_res):
        old = cur_res.get(code)
        val = new_res[code]
        if old == val:
            continue
        # Safety net: never downgrade a curated shootout/AET result (which has a
        # decider note) to a note-less value with the same winner. Protects the
        # dashboard even if a data source ever mangles a shootout score again.
        if old and old[3] and not val[3] and old[2] == val[2]:
            new_res[code] = old
            continue
        changed.append(code)

    # Auto game-fact highlights (newest first) reflect whatever is finished now.
    auto_entries = build_auto_hl(applied, ko_feed)
    hl_block_new = render_auto_hl(auto_entries)
    cur_hl = re.search(r"AUTO_HL=\[.*?\]", gen_text, re.DOTALL)
    hl_changed = bool(cur_hl) and cur_hl.group(0) != hl_block_new

    if not changed and not hl_changed:
        print(f"Source: {src}. No new finished games to apply \u2014 dashboard already current.")
        return 0

    new_up = {c: d for c, d in cur_up.items() if c not in new_res}

    print(f"Source: {src}. Applying {len(changed)} result update(s)"
          + (f": {', '.join(sorted(changed, key=lambda c: int(c[1:])))}" if changed else "")
          + (f"; refreshed {len(auto_entries)} game-fact highlight(s)" if hl_changed else "")
          + ".")
    for c in sorted(changed, key=lambda c: int(c[1:])):
        gA, gB, w, note = new_res[c]
        tail = f" ({note})" if note else ""
        print(f"  {c} [{ko_label(c, ko_feed)}]: {gA}\u2013{gB} \u2192 {w}{tail}")

    if args.dry_run:
        print("dry-run: no files written.")
        return 0

    out_text = re.sub(r"RES=\{[^}]*\}", render_res(new_res), gen_text, count=1)
    out_text = re.sub(r"UPCOMING=\{[^}]*\}", render_upcoming(new_up), out_text, count=1)
    if cur_hl:
        out_text = re.sub(r"AUTO_HL=\[.*?\]", lambda _m: hl_block_new, out_text, count=1, flags=re.DOTALL)
    out_text = re.sub(r'REFRESHED="[^"]*"', f'REFRESHED="{now_pt_stamp()}"', out_text, count=1)
    with open(GEN, "w", encoding="utf-8") as fh:
        fh.write(out_text)
    print("Updated build_dashboard.py (RES / UPCOMING / AUTO_HL / REFRESHED).")

    if not args.no_build:
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        subprocess.run([sys.executable, GEN], check=True, env=env)
        print("Regenerated docs/index.html.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
