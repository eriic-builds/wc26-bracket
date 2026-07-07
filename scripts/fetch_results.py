#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sync finished 2026 World Cup results into the dashboard, then rebuild it.

What it does
------------
1. Reads the Round-of-32 fixtures from ``data/picks.json`` and the knockout
   topology from ``data/topology.json`` so it always matches the entrant's bracket.
2. Gets finished-match results from the web. The default ``--source auto`` prefers
   FIFA's free public feed (api.fifa.com/api/v3, competition 17 / season 285023 —
   no API key or signup) and automatically falls back to football-data.org on any
   FIFA outage or empty feed, so a single-source outage is a non-event. You can
   also pin one source instead:
     - ``--source fifa`` — FIFA's free feed only (no key); or
     - ``--source footballdata`` — football-data.org only (needs ``FOOTBALL_DATA_TOKEN``); or
     - ``--input results.json`` for a local/offline feed (also used by self-test).
3. Normalizes source team names to the bracket's names via ``team_map.json``.
4. Matches each finished game to a bracket match by the pair of teams, and updates
   the ``res`` / ``upcoming`` / ``ko_fix`` fields in ``data/live.json`` (finished
   games only, never clobbering a still-pending game with junk).
5. Rewrites ``auto_hl`` (in ``data/live.json``) with highlight cards for the last
   six finished games (from the whole feed, not just this bracket). For the FIFA
   source it also pulls each game's goals (scorer, minute, half) from FIFA's free
   per-match feed so the recap names scorers and flags braces/comebacks.
6. Re-runs ``build_dashboard.py`` (which reads the JSON) to regenerate
   ``docs/index.html``. The generator source is never edited by the sync.

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
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
GEN = os.path.join(HERE, "build_dashboard.py")
TEAM_MAP = os.path.join(HERE, "team_map.json")
DATA = os.path.join(os.path.dirname(HERE), "data")
PICKS = os.path.join(DATA, "picks.json")
LIVE = os.path.join(DATA, "live.json")
TOPOLOGY = os.path.join(DATA, "topology.json")

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
        return None, []
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
    return out, []  # schedule sync is FIFA-only


def _fifa_txt(field) -> str:
    """FIFA localizes text as a list of {Locale, Description}; take the first."""
    if isinstance(field, list) and field:
        return (field[0] or {}).get("Description", "") or ""
    return ""


def results_from_fifa(tmap: dict):
    """Finished 2026 World Cup games from FIFA's free public JSON feed, plus the
    schedule of not-yet-finished matches whose teams are known.

    Returns ``(out, upcoming)``: ``out`` is the finished-game feed (same dict shape
    as the other sources); ``upcoming`` is a list of ``{"home","away","date"}`` for
    scheduled/live matches with both teams resolved — used to fill kickoff times for
    pending knockout fixtures (a live match's kickoff time is still valid, so it is
    kept here; only finished games ever enter ``out``). No token required. Penalty
    scores come as their own fields (not folded into the score), so the regulation/ET
    scoreline is used as-is. ``city`` carries the host city for the highlight cards.
    """
    req = urllib.request.Request(FIFA_URL, headers={"User-Agent": FIFA_UA})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.load(resp)
    out = []
    upcoming = []
    for m in data.get("Results", []):
        H = m.get("Home") or {}
        A = m.get("Away") or {}
        home = norm(_fifa_txt(H.get("TeamName")), tmap)
        away = norm(_fifa_txt(A.get("TeamName")), tmap)
        if m.get("MatchStatus") != 0:  # not finished -> keep only its kickoff time
            # Skip placeholder/TBD fixtures (empty team names) — a knockout whose
            # feeders aren't decided yet carries no team names in the feed.
            if home and away:
                upcoming.append({"home": home, "away": away,
                                 "date": (m.get("Date") or "")})
            continue
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
    return out, upcoming


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
    return out, []  # schedule sync is FIFA-only


# ── auto-fallback resolver ───────────────────────────────────────────────────
# Network/parse errors we treat as a recoverable outage of one source (so we can
# fall back to another) rather than crashing the whole sync. urllib.error.URLError
# and TimeoutError are OSError subclasses; json.JSONDecodeError is a ValueError.
_SOURCE_ERRORS = (urllib.error.URLError, OSError, ValueError)


def _fetch_source(source: str, tmap: dict):
    """Fetch one web source resiliently.

    Returns ``(feed, is_fifa, error)`` where ``feed`` is a list (possibly empty)
    on a clean fetch, or ``None`` if the source is unavailable (e.g. no
    ``FOOTBALL_DATA_TOKEN``) or errored. ``error`` is a short reason string for
    logging (``None`` on clean success).
    """
    try:
        if source == "footballdata":
            feed, up = results_from_footballdata(tmap)
            if feed is None:
                return None, [], False, "no FOOTBALL_DATA_TOKEN set"
            return feed, up, False, None
        feed, up = results_from_fifa(tmap)
        return feed, up, True, None
    except _SOURCE_ERRORS as exc:
        return None, [], source == "fifa", f"{type(exc).__name__}: {exc}"


def results_auto(tmap: dict):
    """Prefer FIFA (free, richest feed); fall back to football-data.org on any
    FIFA outage or an empty FIFA feed.

    Returns ``(feed, upcoming, src_label, is_fifa)``. A clean-but-empty FIFA feed
    is kept as the last resort (a genuinely empty schedule is valid), so the
    fallback fires without hiding real "no games yet" states. ``upcoming`` (the
    FIFA schedule for pending-fixture times) is FIFA-only and is preserved even
    when results come from the football-data fallback. Raises ``RuntimeError``
    only if *every* candidate source fails outright.
    """
    fifa_feed, fifa_up, fifa_err = None, [], None
    for source, label in (("fifa", "FIFA public feed (api.fifa.com)"),
                          ("footballdata", "football-data.org")):
        feed, up, _is_fifa, err = _fetch_source(source, tmap)
        if source == "fifa":
            if err is None and feed:
                return feed, up, label, True          # best case: FIFA has games
            if err is None:
                fifa_feed, fifa_up = feed, up         # clean but empty -> last resort
            else:
                fifa_err = err
                print(f"  auto: FIFA source unavailable ({err}); "
                      "trying football-data.org\u2026")
            continue
        # football-data branch — only useful if it actually returns games.
        if err is None and feed:
            why = f"FIFA error ({fifa_err})" if fifa_err else "FIFA returned no finished games"
            print(f"  auto: using football-data.org fallback ({why}).")
            # Keep FIFA's schedule (empty if FIFA errored) — it's the only source of
            # kickoff times; football-data supplies results only.
            return feed, fifa_up, label, False
        if err:
            print(f"  auto: football-data.org fallback unavailable ({err}).")
    if fifa_feed is not None:
        return fifa_feed, fifa_up, "FIFA public feed (api.fifa.com)", True
    raise RuntimeError(f"all result sources failed (FIFA: {fifa_err})")


# ── matching + rewrite ───────────────────────────────────────────────────────
def match_all(r32, ko_feed, base_res, feed):
    """Resolve results for every round. Returns (res, applied).

    ``res`` = {code: (gA,gB,winner,note)} keyed to bracket order (R32 fixture order,
    then feeder-winner order for later rounds). ``applied`` = {code: dict} carrying the
    feed detail (teams in bracket order, score, date, label) for finished games — used to
    build the auto game-fact highlights.
    """
    by_pair = {}
    for f in feed:
        key = frozenset((f["home"], f["away"]))
        cur = by_pair.get(key)
        # Two teams can meet twice — a group-stage game and, if both advance, a
        # later knockout game — and collide on this frozenset key. Prefer the
        # latest-dated meeting so the knockout result wins over the earlier group
        # one regardless of feed order (previously last-in-feed silently won,
        # which could write a group-stage score into a semifinal or the Final).
        if cur is None or f.get("date", "") > cur.get("date", ""):
            by_pair[key] = f
    res = dict(base_res)
    applied = {}

    def orient(code, a, b):
        f = by_pair.get(frozenset((a, b)))
        if not f or not f.get("winner"):
            return
        # Every bracket match is a knockout game; never let a group-stage meeting
        # of the same two teams (same frozenset key) write a knockout result.
        if stage_label(f.get("stage", "")) == "group stage":
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


def merge_res(old, new):
    """Decide the stored result for one match, given the existing value ``old``
    (or ``None``) and the freshly fetched ``new``. Returns ``(value, changed)``.

    Behaviour-preserving extraction of main()'s per-code decision so it is unit
    testable:
      * no existing value, or it already equals ``new`` -> take ``new``;
        ``changed`` is False only when they are equal;
      * a curated decider note (shootout/AET — i.e. ``old``'s note is non-empty)
        must never be downgraded to a note-less value with the same winner (guards
        against a source ever mangling a shootout score back to a plain
        scoreline) -> keep ``old``, not changed;
      * otherwise -> take ``new``, changed.
    """
    if old == new:
        return new, False
    if old and old[3] and not new[3] and old[2] == new[2]:
        return old, False
    return new, True


def build_ko_fix(ko_feed, res, upcoming_feed):
    """Kickoff times for not-yet-decided knockout matches whose two feeder winners
    are known, as {code: (day, ET, CT, PT)}.

    Iterates ``ko_feed`` (which correctly lacks the third-place playoff M103), so
    that game can never appear. Only emits a row when both feeder winners are in
    ``res`` AND the scheduled feed carries that team pair. UTC kickoff is converted
    with real IANA zones (DST-safe) — never fixed offsets. Times/day are formatted
    to match R32_TIMES/R16_FIX ('Thu Jul 9', '3:00 PM' — no leading zeros)."""
    et_z, ct_z, pt_z = (ZoneInfo("America/New_York"),
                        ZoneInfo("America/Chicago"),
                        ZoneInfo("America/Los_Angeles"))
    # Index the schedule by team pair. A scheduled knockout game can't collide with
    # a *finished* group game, but filter defensively to knockout-ish entries by
    # skipping anything a group label would produce is unnecessary here (the feed
    # only carries {home,away,date}); the ko_feed membership + res gate suffice.
    by_pair = {}
    for f in upcoming_feed:
        home, away = f.get("home"), f.get("away")
        if home and away:
            by_pair[frozenset((home, away))] = f

    def _fmt(dt, z):
        return re.sub(r"^0", "", dt.astimezone(z).strftime("%I:%M %p"))

    out = {}
    for code in ko_feed:
        if code in res:
            continue                                   # already decided
        fa, fb = ko_feed[code]
        wa = res[fa][2] if fa in res else None
        wb = res[fb][2] if fb in res else None
        if not (wa and wb):
            continue                                   # feeders not both known yet
        f = by_pair.get(frozenset((wa, wb)))
        if not f:
            continue                                   # not in the schedule feed
        iso = f.get("date", "")
        if not iso:
            continue
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        day = re.sub(r"\b0(\d)", r"\1", dt.astimezone(et_z).strftime("%a %b %d"))
        out[code] = (day, _fmt(dt, et_z), _fmt(dt, ct_z), _fmt(dt, pt_z))
    return out


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


def _stable_idx(seed: str, n: int) -> int:
    """Deterministic 0..n-1 pick from a string (varies wording without RNG so the
    Action stays reproducible)."""
    if n <= 0:
        return 0
    return sum(seed.encode("utf-8")) % n


def _count_word(k: int) -> str:
    return {2: "twice", 3: "a hat-trick", 4: "four times"}.get(k, f"{k} times")


def _star_clause(star, goals, win_side) -> str:
    """A characterful clause for a multi-goal hero, e.g.
    'Kane struck twice after the break (75', 86')'. '' if not a 2+ goal game."""
    gs = [g for g in goals if g.get("side") == win_side
          and g.get("kind") in ("goal", "pen") and g.get("name") == star]
    gs.sort(key=lambda g: g.get("min_n", 0))
    if len(gs) < 2:
        return ""
    mins = []
    for g in gs:
        t = g.get("minute", "")
        if g.get("kind") == "pen":
            t = (t + " pen").strip()
        if t:
            mins.append(t)
    halves = {g.get("half") for g in gs}
    timing = " after the break" if halves == {"2H"} else \
             " in the first half" if halves == {"1H"} else ""
    verb = "fired" if len(gs) >= 3 else "struck"
    return f"{star} {verb} {_count_word(len(gs))}{timing} ({', '.join(mins)})"


def _others_phrase(goals, win_side, star) -> str:
    """Winner's other scorers (excluding the star's own goals from play)."""
    rest = [g for g in goals if not (g.get("side") == win_side
            and g.get("name") == star and g.get("kind") in ("goal", "pen"))]
    return _scorer_phrase(rest, win_side)


def _recap_win(home, away, w, loser, gh, ga, wg, lg, margin, label, note,
               goals, win_side, star, n, comeback, wphrase, seed) -> str:
    """A fun, varied one-sentence recap of a win. Deterministic wording so the
    same game always renders the same card. Falls back gracefully when no scorer
    data is available."""
    score = f"{wg}\u2013{lg}"
    starcl = _star_clause(star, goals, win_side) if star and n >= 2 else ""
    others = _others_phrase(goals, win_side, star) if star and n >= 2 else ""
    otail = f", with {others} also on the mark" if others else ""
    late = bool(margin == 1 and goals and max(
        (g.get("min_n", 0) for g in goals if g.get("side") == win_side
         and g.get("kind") in ("goal", "pen")), default=0) >= 80)

    if "pens" in note:
        opts = [
            f"{w} held their nerve, edging {loser} on penalties ({note}) after a {gh}\u2013{ga} {label} deadlock.",
            f"Shootout drama: {w} outlasted {loser} {note} following a {gh}\u2013{ga} stalemate in the {label}.",
            f"Ice-cold from twelve yards, {w} saw off {loser} on penalties ({note}) after {gh}\u2013{ga} in the {label}.",
        ]
    elif comeback:
        tl = f" \u2014 {wphrase} turning it around" if wphrase else ""
        opts = [
            f"Down at the break, {w} roared back to beat {loser} {score} in the {label}{tl}.",
            f"{w} flipped the script after falling behind, completing a {score} comeback against {loser} in the {label}{tl}.",
            f"Backs to the wall, {w} rallied to see off {loser} {score} in the {label}{tl}.",
        ]
    elif n >= 3:
        hero = starcl or f"{star} grabbed a hat-trick"
        opts = [
            f"Match ball secured \u2014 {hero} to fire {w} past {loser} {score} in the {label}{otail}.",
            f"The {star} show: {hero} powering {w} to a {score} win over {loser} in the {label}{otail}.",
        ]
    elif n >= 2:
        hero = starcl or f"{star} bagged a brace"
        opts = [
            f"{hero} as {w} beat {loser} {score} in the {label}{otail}.",
            f"{hero} to settle {w}'s {score} win over {loser} in the {label}{otail}.",
        ]
    elif note == "AET":
        tl = f" \u2014 {wphrase} decisive" if wphrase else ""
        opts = [
            f"It took extra time, but {w} got there, beating {loser} {score} in the {label}{tl}.",
            f"{w} needed the extra 30, edging {loser} {score} after extra time in the {label}{tl}.",
        ]
    elif margin >= 3:
        tl = f" \u2014 {wphrase} on the scoresheet" if wphrase else ""
        opts = [
            f"{w} ran riot, sweeping {loser} aside {score} in the {label}{tl}.",
            f"No contest: {w} cruised past {loser} {score} in the {label}{tl}.",
            f"{w} put on a show, romping to a {score} win over {loser} in the {label}{tl}.",
        ]
    elif late:
        opts = [
            f"{w} left it late, snatching a {score} {label} squeaker past {loser}" + (f" ({wphrase})" if wphrase else "") + ".",
            f"Heartbreak for {loser} \u2014 {w} nicked it {score} late in the {label}" + (f", {wphrase} on target" if wphrase else "") + ".",
        ]
    elif margin == 1:
        opts = [
            f"{w} edged a tight one {score} against {loser} in the {label}" + (f", {wphrase} making the difference" if wphrase else "") + ".",
            f"Nervy but enough: {w} saw off {loser} {score} in the {label}" + (f" thanks to {wphrase}" if wphrase else "") + ".",
        ]
    else:
        opts = [
            (f"{wphrase} on target as " if wphrase else "") + f"{w} saw off {loser} {score} in the {label}.",
            f"{w} had too much for {loser}, running out {score} winners in the {label}" + (f" \u2014 {wphrase} scoring" if wphrase else "") + ".",
            f"Job done for {w}, a composed {score} win over {loser} in the {label}" + (f" with {wphrase}" if wphrase else "") + ".",
        ]
    return opts[_stable_idx(seed, len(opts))]


def _recap_draw(home, away, gh, ga, label, goals, seed) -> str:
    """A fun, varied one-sentence recap of a draw."""
    score = f"{gh}\u2013{ga}"
    hs = _scorer_phrase(goals, "home")
    as_ = _scorer_phrase(goals, "away")
    if hs and as_:
        opts = [
            f"{home} and {away} couldn't be separated in a {score} {label} draw \u2014 {hs} for {home}, {as_} for {away}.",
            f"Honours even: {home} {score} {away} in the {label}, {hs} and {as_} trading goals.",
            f"End to end but level, {home} and {away} shared a {score} {label} draw ({hs}; {as_}).",
        ]
    else:
        opts = [
            f"{home} and {away} played out a goalless {label} stalemate." if gh == 0 else
            f"{home} and {away} shared the points in a {score} {label} draw.",
            f"Nothing between them: {home} {score} {away} in the {label}.",
            f"Points shared as {home} and {away} finished {score} in the {label}.",
        ]
    return opts[_stable_idx(seed, len(opts))]


# Fun team-nickname emojis (e.g. England = Three Lions). Anything not listed
# falls back to its national flag via _TEAM_ISO2 below.
_TEAM_NICK = {
    "England": "\U0001f981",            # lion - Three Lions
    "France": "\U0001f413",             # rooster - Les Bleus / Gallic rooster
    "Netherlands": "\U0001f7e0",        # orange circle - Oranje
    "Belgium": "\U0001f608",            # devil - Red Devils
    "Germany": "\U0001f985",            # eagle - Die Mannschaft
    "Spain": "\U0001f402",              # bull - La Furia Roja
    "Australia": "\U0001f998",          # kangaroo - Socceroos
    "Canada": "\U0001f341",             # maple leaf
    "Ivory Coast": "\U0001f418",        # elephant - Les Elephants
    "DR Congo": "\U0001f406",           # leopard - Leopards
    "South Korea": "\U0001f42f",        # tiger - Taeguk Warriors
    "Japan": "\u2694\ufe0f",            # crossed swords - Samurai Blue
    "Mexico": "\U0001f335",             # cactus - El Tri
    "United States": "\U0001f5fd",      # statue of liberty
    "New Zealand": "\U0001f95d",        # kiwifruit - All Whites
    "Algeria": "\U0001f98a",            # fox - Desert Foxes
    "Colombia": "\u2615",               # coffee - Los Cafeteros
    "Cape Verde": "\U0001f988",         # shark - Blue Sharks
    "Bosnia & Herz.": "\U0001f409",     # dragon - Zmajevi
    "Ghana": "\u2b50",                  # star - Black Stars
    "T\u00fcrkiye": "\U0001f43a",       # wolf - Crescent-Stars
    "Qatar": "\U0001f40e",              # horse - The Maroons
    "Brazil": "\U0001f49b",             # yellow heart - Selecao
    "Argentina": "\U0001f499",          # blue heart - Albiceleste
    "Egypt": "\U0001f3fa",              # amphora - Pharaohs
    "Scotland": "\U0001f3f4\U000e0067\U000e0062\U000e0073\U000e0063\U000e0074\U000e007f",  # Scotland flag
}

# ISO 3166-1 alpha-2 codes for a national-flag fallback (nations without a fun
# nickname above). England/Scotland use subdivision flags handled in _TEAM_NICK.
_TEAM_ISO2 = {
    "Argentina": "AR", "Australia": "AU", "Austria": "AT", "Belgium": "BE",
    "Bosnia & Herz.": "BA", "Brazil": "BR", "Canada": "CA", "Cape Verde": "CV",
    "Colombia": "CO", "Croatia": "HR", "Cura\u00e7ao": "CW", "Czechia": "CZ",
    "DR Congo": "CD", "Ecuador": "EC", "Egypt": "EG", "France": "FR",
    "Germany": "DE", "Ghana": "GH", "Haiti": "HT", "IR Iran": "IR", "Iraq": "IQ",
    "Ivory Coast": "CI", "Japan": "JP", "Jordan": "JO", "Mexico": "MX",
    "Morocco": "MA", "Netherlands": "NL", "New Zealand": "NZ", "Norway": "NO",
    "Panama": "PA", "Paraguay": "PY", "Portugal": "PT", "Qatar": "QA",
    "Saudi Arabia": "SA", "Senegal": "SN", "South Africa": "ZA",
    "South Korea": "KR", "Spain": "ES", "Sweden": "SE", "Switzerland": "CH",
    "Tunisia": "TN", "T\u00fcrkiye": "TR", "United States": "US",
    "Uruguay": "UY", "Uzbekistan": "UZ", "Algeria": "DZ",
}


def _flag(iso2: str) -> str:
    """ISO2 country code -> regional-indicator flag emoji ('' if invalid)."""
    if not iso2 or len(iso2) != 2 or not iso2.isalpha():
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in iso2.upper())


def _team_emoji(name: str) -> str:
    """A fun, team-relevant emoji: nickname if we have one, else national flag."""
    if name in _TEAM_NICK:
        return _TEAM_NICK[name]
    return _flag(_TEAM_ISO2.get(name, ""))


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
            emoji = _team_emoji(home) or _team_emoji(away) or "\U0001f91d"
            headline = _headline(w, "", home, away, gh, ga, note)
            body = _recap_draw(home, away, gh, ga, label, goals, title)
            entries.append((emoji, headline, title, when, body))
            if len(entries) >= limit:
                break
            continue

        win_side = "home" if w == home else "away"
        loser = away if w == home else home
        wg, lg = (gh, ga) if w == home else (ga, gh)
        margin = abs(gh - ga)
        star, n = _winner_star(goals, win_side)
        comeback = _trailed_at_half(goals, win_side)
        wphrase = _scorer_phrase(goals, win_side)

        # One emoji: the winner's nickname (Three Lions etc.), else its country flag.
        emoji = _team_emoji(w) or "\u26bd"

        # Headline: prefer a scorer story, then comeback, then plain fact.
        if star and n >= 3:
            headline = f"{star} hat-trick sinks {loser}"
        elif star and n >= 2:
            headline = f"{star}'s brace sinks {loser}"
        elif comeback:
            headline = f"{w} come from behind vs {loser}"
        else:
            headline = _headline(w, loser, home, away, gh, ga, note)

        body = _recap_win(home, away, w, loser, gh, ga, wg, lg, margin, label,
                          note, goals, win_side, star, n, comeback, wphrase, title)
        entries.append((emoji, headline, title, when, body))
        if len(entries) >= limit:
            break
    return entries


def now_pt_stamp() -> str:
    pt = timezone(timedelta(hours=-7))  # PDT (summer)
    now = datetime.now(pt)
    # Trim leading zeros on day and hour, but keep the minute zero-padded ("10:06").
    day = str(now.day)
    hour = str(int(now.strftime("%I")))
    return now.strftime(f"%B {day}, %Y \u00b7 {hour}:%M %p PT")


def _write_live(live: dict) -> None:
    """Persist data/live.json. ensure_ascii=False keeps emoji/en-dashes readable;
    indent=1 matches the committed formatting so syncs produce a minimal diff."""
    with open(LIVE, "w", encoding="utf-8") as fh:
        json.dump(live, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def _rebuild() -> None:
    """Regenerate docs/index.html from the data files (never hand-edits it)."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    subprocess.run([sys.executable, GEN], check=True, env=env)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input", help="local results.json feed (instead of the web API)")
    ap.add_argument("--source", choices=["auto", "fifa", "footballdata"], default="auto",
                    help="web source when --input is not used (default: auto — FIFA free feed, "
                         "auto-falling back to football-data.org on a FIFA outage or empty feed)")
    ap.add_argument("--dry-run", action="store_true", help="report changes, write nothing")
    ap.add_argument("--no-build", action="store_true", help="update source but skip regenerating HTML")
    args = ap.parse_args()

    tmap = load_team_map()
    with open(PICKS, encoding="utf-8") as fh:
        picks = json.load(fh)
    with open(TOPOLOGY, encoding="utf-8") as fh:
        topo = json.load(fh)
    with open(LIVE, encoding="utf-8") as fh:
        live = json.load(fh)
    r32 = [(r[0], r[2], r[3]) for r in picks["r32"]]            # (code, teamA, teamB)
    ko_feed = {k: tuple(v) for k, v in topo["ko_feed"].items()}
    cur_res = {k: tuple(v) for k, v in live["res"].items()}
    cur_up = dict(live["upcoming"])
    cur_ko_fix = {k: tuple(v) for k, v in live["ko_fix"].items()}
    cur_auto_hl = [tuple(e) for e in live["auto_hl"]]

    if args.input:
        feed, upcoming_feed = results_from_json(args.input, tmap)
        src = f"local file {args.input}"
    elif args.source == "footballdata":
        feed, upcoming_feed = results_from_footballdata(tmap)
        src = "football-data.org"
        if feed is None:
            print("No FOOTBALL_DATA_TOKEN set and no --input given \u2014 nothing to do.")
            return 0
    elif args.source == "fifa":
        feed, upcoming_feed = results_from_fifa(tmap)
        src = "FIFA public feed (api.fifa.com)"
        # Pull scorers/half/comeback context for just the games that will become
        # highlight cards (a handful of extra free FIFA calls, read-only).
        enrich_fifa_goals(feed)
    else:  # auto (default): FIFA first, football-data.org fallback on outage
        try:
            feed, upcoming_feed, src, is_fifa = results_auto(tmap)
        except RuntimeError as exc:
            print(f"All result sources failed \u2014 nothing to do this run. ({exc})")
            return 0
        # Scorer/half/comeback enrichment is FIFA-only (needs FIFA match IDs);
        # skip it when the fallback source supplied the feed.
        if is_fifa:
            enrich_fifa_goals(feed)

    # Resolve every round (R32 -> R16 -> QF -> SF -> Final) from the same feed.
    new_res, applied = match_all(r32, ko_feed, cur_res, feed)

    # Only NEW/changed finished games; never remove an existing result. The
    # per-code merge decision (including the curated-note safety net) lives in the
    # pure, tested merge_res() helper.
    changed = []
    for code in list(new_res):
        val, was_changed = merge_res(cur_res.get(code), new_res[code])
        new_res[code] = val
        if was_changed:
            changed.append(code)

    # Kickoff times for pending knockout fixtures (QF/SF/Final), derived from the
    # FIFA schedule. Recomputed every run: entries appear when both feeders are
    # known and drop out once the match is played.
    if upcoming_feed:
        new_ko_fix = build_ko_fix(ko_feed, new_res, upcoming_feed)
    else:
        # No schedule feed (local --input or football-data source): don't wipe the
        # kickoff times — keep them, dropping only matches that are now decided.
        new_ko_fix = {c: v for c, v in cur_ko_fix.items() if c not in new_res}
    ko_fix_changed = new_ko_fix != cur_ko_fix

    # Auto game-fact highlights (newest first) reflect every finished game in the
    # feed, not only the ones in this bracket.
    auto_entries = build_auto_hl(feed)
    hl_changed = auto_entries != cur_auto_hl

    if not changed and not hl_changed and not ko_fix_changed:
        if args.dry_run:
            print(f"Source: {src}. No new finished games to apply \u2014 dashboard already current (dry-run).")
            return 0
        # Nothing to apply, but record that we checked so "last synced" stays honest.
        stamp = now_pt_stamp()
        if live.get("refreshed") != stamp:
            live["refreshed"] = stamp
            _write_live(live)
            # Keep docs/index.html in lock-step with the data: REFRESHED lives in
            # live.json, so the HTML must be rebuilt or the two drift.
            if not args.no_build:
                _rebuild()
                print("Regenerated docs/index.html.")
        print(f"Source: {src}. No new finished games \u2014 refreshed sync time to {stamp}.")
        return 0

    new_up = {c: d for c, d in cur_up.items() if c not in new_res}

    print(f"Source: {src}. Applying {len(changed)} result update(s)"
          + (f": {', '.join(sorted(changed, key=lambda c: int(c[1:])))}" if changed else "")
          + (f"; refreshed {len(auto_entries)} game-fact highlight(s)" if hl_changed else "")
          + (f"; {len(new_ko_fix)} pending-fixture kickoff time(s)" if ko_fix_changed else "")
          + ".")
    for c in sorted(changed, key=lambda c: int(c[1:])):
        gA, gB, w, note = new_res[c]
        tail = f" ({note})" if note else ""
        print(f"  {c} [{ko_label(c, ko_feed)}]: {gA}\u2013{gB} \u2192 {w}{tail}")
    if ko_fix_changed:
        for c in sorted(new_ko_fix, key=lambda c: int(c[1:])):
            day, et, ct, pt = new_ko_fix[c]
            print(f"  {c} [{ko_label(c, ko_feed)}] kickoff: {day} \u00b7 {pt} PT \u00b7 {ct} CT \u00b7 {et} ET")

    if args.dry_run:
        print("dry-run: no files written.")
        return 0

    # Write data/live.json deterministically (numeric code order, unicode kept) so
    # each sync produces a minimal diff.
    live["res"] = {c: list(new_res[c]) for c in sorted(new_res, key=lambda c: int(c[1:]))}
    live["upcoming"] = {c: new_up[c] for c in sorted(new_up, key=lambda c: int(c[1:]))}
    live["ko_fix"] = {c: list(new_ko_fix[c]) for c in sorted(new_ko_fix, key=lambda c: int(c[1:]))}
    live["auto_hl"] = [list(e) for e in auto_entries]
    live["refreshed"] = now_pt_stamp()
    _write_live(live)
    print("Updated data/live.json (res / upcoming / ko_fix / auto_hl / refreshed).")

    if not args.no_build:
        _rebuild()
        print("Regenerated docs/index.html.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
