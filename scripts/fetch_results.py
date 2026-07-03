#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sync finished 2026 World Cup results into the dashboard, then rebuild it.

What it does
------------
1. Reads the Round-of-32 fixtures straight out of ``build_dashboard.py`` (the
   ``R32`` list) so it always matches the entrant's bracket.
2. Gets finished-match results from the web:
     - default: FIFA's free public feed (api.fifa.com/api/v3), competition 17 /
       season 285023 (World Cup 2026) — no API key or signup required; or
     - ``--source footballdata`` for football-data.org (needs ``FOOTBALL_DATA_TOKEN``); or
     - ``--input results.json`` for a local/offline feed (also used by self-test).
3. Normalizes source team names to the bracket's names via ``team_map.json``.
4. Matches each finished game to a bracket match by the pair of teams, and
   updates the ``RES`` and ``UPCOMING`` blocks in ``build_dashboard.py`` in place
   (finished games only, never clobbering a still-pending game with junk).
5. Rewrites ``AUTO_HL`` with highlight cards for the last six finished games
   (from the whole feed, not just this bracket). For the FIFA source it also
   pulls each of those games' goals (scorer, minute, half) from FIFA's free
   per-match feed so the recap names scorers and flags braces/comebacks.
6. Re-runs ``build_dashboard.py`` to regenerate ``docs/index.html``.

Safety
------
- Idempotent: if nothing new is final, it changes nothing and exits 0.
- ``--dry-run`` reports what *would* change and writes nothing.
- Only whole, finished matches are written; genuine draws (no decider) are kept
  for the game-fact cards but never entered as a bracket result.
"""
from __future__ import annotations
import argparse, json, os, re, subprocess, sys, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, "build_dashboard.py")
TEAM_MAP = os.path.join(HERE, "team_map.json")

FD_URL = "https://api.football-data.org/v4/competitions/WC/matches?status=FINISHED"

# FIFA's own public results feed — free, no API key, no signup. This is the same
# JSON the fifa.com match centre uses. idCompetition 17 = FIFA World Cup, idSeason
# 285023 = the 2026 edition. count=500 covers all 104 matches in one call.
FIFA_URL = ("https://api.fifa.com/api/v3/calendar/matches"
            "?idCompetition=17&idSeason=285023&count=500&language=en")
FIFA_UA = "Mozilla/5.0 (compatible; wc-bracket-sync/1.0; +https://github.com)"


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
        elif gh == ga:  # level score
            if winner_side == "HOME_TEAM":
                w = home; note = "AET"
            elif winner_side == "AWAY_TEAM":
                w = away; note = "AET"
            else:
                w = ""; note = "draw"  # genuine draw (e.g. group stage) -> game facts only
        else:
            w = home if gh > ga else away
        out.append({"home": home, "away": away, "gh": int(gh), "ga": int(ga),
                    "winner": w, "note": note, "date": (m.get("utcDate") or ""),
                    "stage": (m.get("stage") or ""), "city": ""})
    return out


def _fifa_txt(field) -> str:
    """FIFA localizes text as a list of {Locale, Description}; take the first."""
    if isinstance(field, list) and field:
        return (field[0] or {}).get("Description", "") or ""
    return ""


def results_from_fifa(tmap: dict):
    """Finished 2026 World Cup games from FIFA's free public JSON feed.

    Returns the same feed-dict shape as the other sources. No token required.
    Penalty scores come as their own fields (not folded into the score), so the
    regulation/ET scoreline is used as-is. ``city`` carries the host city for the
    highlight cards' "day · venue" line.
    """
    req = urllib.request.Request(FIFA_URL, headers={"User-Agent": FIFA_UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    out = []
    for m in data.get("Results", []):
        if m.get("MatchStatus") != 0:  # 0 = finished
            continue
        H = m.get("Home") or {}
        A = m.get("Away") or {}
        home = norm(_fifa_txt(H.get("TeamName")), tmap)
        away = norm(_fifa_txt(A.get("TeamName")), tmap)
        gh, ga = m.get("HomeTeamScore"), m.get("AwayTeamScore")
        if gh is None or ga is None or not home or not away:
            continue
        gh, ga = int(gh), int(ga)
        stage = _fifa_txt(m.get("StageName"))
        city = _fifa_txt((m.get("Stadium") or {}).get("CityName"))
        win_id = m.get("Winner")
        ph, pa = m.get("HomeTeamPenaltyScore"), m.get("AwayTeamPenaltyScore")
        note = ""
        if ph is not None and pa is not None and int(ph) != int(pa):
            ph, pa = int(ph), int(pa)
            if win_id and win_id == A.get("IdTeam"):
                w = away
            elif win_id and win_id == H.get("IdTeam"):
                w = home
            else:
                w = home if ph > pa else away
            note = f"{max(ph, pa)}\u2013{min(ph, pa)} pens"
        elif gh == ga:  # level after normal/extra time
            if win_id == H.get("IdTeam"):
                w, note = home, "AET"
            elif win_id == A.get("IdTeam"):
                w, note = away, "AET"
            else:
                w, note = "", "draw"  # genuine draw (group stage) -> game facts only
        else:
            w = home if gh > ga else away
        out.append({"home": home, "away": away, "gh": gh, "ga": ga,
                    "winner": w, "note": note, "date": (m.get("Date") or ""),
                    "stage": stage, "city": city,
                    # IDs let enrich_fifa_goals() pull scorers for the card recap.
                    "_ids": (m.get("IdCompetition"), m.get("IdSeason"),
                             m.get("IdStage"), m.get("IdMatch"))})
    return out


# FIFA's free per-match feed. Same host/no key as the calendar feed; carries the
# goal list (scorer, minute, half) that the highlight cards use for a real recap.
FIFA_LIVE = ("https://api.fifa.com/api/v3/live/football/"
             "{ic}/{isea}/{ist}/{im}?language=en")

# FIFA goal Type enum (observed in the 2026 feed): 1=penalty, 2=goal, 3=own goal.
_GOAL_PEN, _GOAL_NORMAL, _GOAL_OG = 1, 2, 3


def _fifa_name(short) -> str:
    """FIFA short names come as 'Mikel OYARZABAL' (surname in caps). Return a
    tidy surname for headlines/recaps ('Oyarzabal'); '' if unavailable."""
    txt = _fifa_txt(short)
    if not txt:
        return ""
    caps = [w for w in txt.split() if len(w) > 1 and w.isupper()]
    surname = caps[-1] if caps else txt.split()[-1]
    return surname[:1].upper() + surname[1:].lower()


def _goal_half(minute: str) -> str:
    """'36\\'' -> '1H', '66\\'' -> '2H', '104\\'' -> 'ET' (best-effort)."""
    m = re.match(r"\s*(\d+)", minute or "")
    if not m:
        return ""
    base = int(m.group(1))
    if base <= 45:
        return "1H"
    if base <= 90:
        return "2H"
    return "ET"


def fetch_match_goals(ids) -> list:
    """Return this match's goals as ordered dicts {name, minute, half, kind, side}.

    Uses FIFA's free live endpoint (no key). ``kind`` is 'goal'/'pen'/'og';
    ``side`` is 'home'/'away' (the team credited with the goal). Own-goal scorers
    are looked up across both rosters. Returns [] on any error so cards degrade
    gracefully to the plain factual recap.
    """
    ic, isea, ist, im = ids
    if not all((ic, isea, ist, im)):
        return []
    url = FIFA_LIVE.format(ic=ic, isea=isea, ist=ist, im=im)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": FIFA_UA})
        with urllib.request.urlopen(req, timeout=30) as resp:
            d = json.load(resp)
    except (urllib.error.URLError, ValueError, TimeoutError):
        return []
    roster = {}
    for team in (d.get("HomeTeam") or {}, d.get("AwayTeam") or {}):
        for p in (team.get("Players") or []):
            roster[p.get("IdPlayer")] = _fifa_name(p.get("ShortName"))
    goals = []
    for side, key in (("home", "HomeTeam"), ("away", "AwayTeam")):
        team = d.get(key) or {}
        for g in (team.get("Goals") or []):
            t = g.get("Type")
            kind = "pen" if t == _GOAL_PEN else "og" if t == _GOAL_OG else "goal"
            minute = g.get("Minute", "") or ""
            mm = re.match(r"\s*(\d+)", minute)
            goals.append({"name": roster.get(g.get("IdPlayer"), ""),
                          "minute": minute.strip(),
                          "min_n": int(mm.group(1)) if mm else 999,
                          "half": _goal_half(minute), "kind": kind, "side": side})
    goals.sort(key=lambda x: x["min_n"])
    return goals


def enrich_fifa_goals(feed, limit=6):
    """Attach a ``goals`` list to the ~newest ``limit`` finished games so their
    highlight cards can name scorers. Only the games that will become cards are
    fetched (a handful of extra free calls), not the whole tournament."""
    games = sorted(feed, key=lambda f: (f.get("date", ""), f.get("home", "")),
                   reverse=True)
    seen, picked = set(), 0
    for f in games:
        key = (frozenset((f.get("home"), f.get("away"))), f.get("date", "")[:10])
        if key in seen:
            continue
        seen.add(key)
        ids = f.get("_ids")
        if ids:
            f["goals"] = fetch_match_goals(ids)
        picked += 1
        if picked >= limit:
            break
    return feed


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
                note = note or "draw"  # genuine draw -> game facts only
        else:
            w = home if gh > ga else away
        out.append({"home": home, "away": away, "gh": gh, "ga": ga,
                    "winner": w, "note": note, "date": (m.get("date") or ""),
                    "stage": (m.get("stage", "")), "city": (m.get("city", ""))})
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
        if not f or not f.get("winner"):
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


STAGE_LABELS = {
    "GROUP_STAGE": "group stage", "GROUP": "group stage", "FIRST_STAGE": "group stage",
    "LAST_32": "Round of 32", "ROUND_OF_32": "Round of 32",
    "LAST_16": "Round of 16", "ROUND_OF_16": "Round of 16",
    "QUARTER_FINALS": "quarterfinal", "QUARTER_FINAL": "quarterfinal",
    "SEMI_FINALS": "semifinal", "SEMI_FINAL": "semifinal",
    "THIRD_PLACE": "third-place playoff", "3RD_PLACE": "third-place playoff",
    "PLAY_OFF_FOR_THIRD_PLACE": "third-place playoff",
    "FINAL": "final",
}


def stage_label(stage: str) -> str:
    """Map a source stage string (football-data code OR FIFA display name) to a
    human round label. Normalizes spaces/hyphens so both 'LAST_16' and
    'Round of 16' / 'Quarter-final' resolve the same way."""
    if not stage:
        return "match"
    key = re.sub(r"[^A-Za-z0-9]+", "_", stage).strip("_").upper()
    return STAGE_LABELS.get(key, stage.replace("_", " ").lower())


def _headline(w, loser, a, b, gh, ga, note):
    """A short, factual card headline (the bold tag line) used when no per-scorer
    data is available for the game."""
    if not w or note == "draw":
        return f"{a} and {b} share the points"
    if "pens" in note:
        return f"{w} win on penalties"
    margin = abs(gh - ga)
    if margin >= 3:
        return f"{w} cruise past {loser}"
    if margin == 1:
        return f"{w} edge {loser}"
    return f"{w} beat {loser}"


def _scorer_phrase(goals, side) -> str:
    """'Oyarzabal (36', 89'), Pedri (66')' for a team's goals; '' if none named.

    Groups multiple goals by the same scorer, tags penalties, and renders own
    goals as 'Surname OG'. Caps the list at three names for card brevity.
    """
    order, mins = [], {}
    for g in goals:
        if g.get("side") != side:
            continue
        if g.get("kind") == "og":
            nm = (g["name"] + " OG") if g.get("name") else "an own goal"
        else:
            nm = g.get("name")
        if not nm:
            continue
        tag = g.get("minute", "")
        if g.get("kind") == "pen":
            tag = (tag + " pen").strip()
        if nm not in mins:
            order.append(nm)
            mins[nm] = []
        if tag:
            mins[nm].append(tag)
    parts = [f"{nm} ({', '.join(mins[nm])})" if mins[nm] else nm for nm in order]
    if len(parts) > 3:
        parts = parts[:3] + ["others"]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0]
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def _winner_star(goals, side):
    """(surname, goal_count) of the winner's top scorer from play/penalty; own
    goals don't count toward a player's tally. ('', 0) if none named."""
    cnt = {}
    for g in goals:
        if g.get("side") == side and g.get("kind") in ("goal", "pen") and g.get("name"):
            cnt[g["name"]] = cnt.get(g["name"], 0) + 1
    if not cnt:
        return ("", 0)
    nm = max(cnt, key=cnt.get)
    return (nm, cnt[nm])


def _trailed_at_half(goals, win_side) -> bool:
    """True if the eventual winner was behind on first-half goals."""
    lose_side = "away" if win_side == "home" else "home"
    wh = sum(1 for g in goals if g.get("side") == win_side and g.get("half") == "1H")
    lh = sum(1 for g in goals if g.get("side") == lose_side and g.get("half") == "1H")
    return wh < lh


def build_auto_hl(feed, limit=6):
    """Newest-first highlight cards for the most recent finished games.

    Pulls from the WHOLE feed (every finished World Cup game), not only games in
    the user's bracket, so a viewer sees the latest results at a glance. Each entry
    is (emoji, headline, scoreline, "day \u00b7 venue", one-sentence recap) to match
    the featured-card layout. When the game carries a ``goals`` list (FIFA source,
    via enrich_fifa_goals) the headline/recap name scorers, halves, and comebacks
    the way the hand-written cards read; otherwise it falls back to a plain factual
    recap. Kept free of the ] character so the emitted AUTO_HL block stays
    regex-rewritable.
    """
    games = sorted(feed, key=lambda f: (f.get("date", ""), f.get("home", "")),
                   reverse=True)
    entries = []
    seen = set()
    for f in games:
        home, away = f["home"], f["away"]
        if not home or not away:
            continue
        key = (frozenset((home, away)), f.get("date", "")[:10])
        if key in seen:
            continue
        seen.add(key)
        gh, ga, w, note = f["gh"], f["ga"], f["winner"], f.get("note", "")
        label = stage_label(f.get("stage", ""))
        day = _fmt_day(f.get("date", ""))
        city = f.get("city", "")
        when = " \u00b7 ".join(x for x in (day, city or label) if x) or label
        title = f"{home} {gh}\u2013{ga} {away}"
        goals = f.get("goals") or []

        if not w or note == "draw":  # genuine draw
            emoji = "\u2694\ufe0f"
            headline = _headline(w, "", home, away, gh, ga, note)
            hs = _scorer_phrase(goals, "home")
            as_ = _scorer_phrase(goals, "away")
            if hs and as_:
                body = (f"{hs} for {home} and {as_} for {away} in a {gh}\u2013{ga} "
                        f"{label} draw.")
            else:
                body = f"{home} and {away} drew {gh}\u2013{ga} in the {label}."
            entries.append((emoji, headline, title, when, body))
            if len(entries) >= limit:
                break
            continue

        win_side = "home" if w == home else "away"
        loser = away if w == home else home
        wg, lg = (gh, ga) if w == home else (ga, gh)
        star, n = _winner_star(goals, win_side)
        comeback = _trailed_at_half(goals, win_side)
        wphrase = _scorer_phrase(goals, win_side)

        # Headline: prefer a scorer story, then comeback, then plain fact.
        if star and n >= 3:
            headline = f"{star} hat-trick sinks {loser}"
        elif star and n >= 2:
            headline = f"{star}'s brace sinks {loser}"
        elif comeback:
            headline = f"{w} come from behind vs {loser}"
        else:
            headline = _headline(w, loser, home, away, gh, ga, note)

        prefix = "Down at the break, " if comeback else ""
        if "pens" in note:
            emoji = "\U0001f945"
            if wphrase or _scorer_phrase(goals, "away" if win_side == "home" else "home"):
                body = (f"{w} beat {loser} on penalties ({note}) after a "
                        f"{gh}\u2013{ga} {label} draw.")
            else:
                body = (f"{w} beat {loser} on penalties ({note}) after a "
                        f"{gh}\u2013{ga} draw in the {label}.")
        elif wphrase:
            emoji = "\u26bd"
            tail = " after extra time" if note == "AET" else ""
            body = (f"{prefix}{wphrase} scored as {w} beat {loser} "
                    f"{wg}\u2013{lg}{tail} in the {label}.")
        elif note == "AET":
            emoji = "\u26bd"
            body = f"{w} beat {loser} {wg}\u2013{lg} after extra time in the {label}."
        else:
            emoji = "\u26bd"
            body = f"{w} beat {loser} {wg}\u2013{lg} in the {label}."
        entries.append((emoji, headline, title, when, body))
        if len(entries) >= limit:
            break
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
    ap.add_argument("--source", choices=["fifa", "footballdata"], default="fifa",
                    help="web source when --input is not used (default: fifa, free/no key)")
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
    elif args.source == "footballdata":
        feed = results_from_footballdata(tmap)
        src = "football-data.org"
        if feed is None:
            print("No FOOTBALL_DATA_TOKEN set and no --input given \u2014 nothing to do.")
            return 0
    else:
        feed = results_from_fifa(tmap)
        src = "FIFA public feed (api.fifa.com)"
        # Pull scorers/half/comeback context for just the games that will become
        # highlight cards (a handful of extra free FIFA calls, read-only).
        enrich_fifa_goals(feed)

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

    # Auto game-fact highlights (newest first) reflect every finished game in the
    # feed, not only the ones in this bracket.
    auto_entries = build_auto_hl(feed)
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
