# -*- coding: utf-8 -*-
"""World Cup 2026 bracket-challenge dashboard -> one self-contained HTML file.
Picks / scoring / tiebreaker come from the entrant's own 'My Bracket' Excel tab.
Live match results & kickoff times come from a verified web lookup (FIFA official + majors).
No results are invented; undecided matches are shown as pending."""
import html, json, os, re

# ══════════════════════════════════════════════════════════════════════════════
#  USER DATA — the ONLY part you change per entrant.
#    • From THEIR uploaded "My Bracket" Excel tab: ENTRANT, TIEBREAKER, SEED, R32
#      (each = matchcode, date, teamA, teamB, THEIR pick), FREEBIE_MATCH, R16_WIN,
#      QF_WIN, SF_WIN, CHAMP, RUNNER — exactly as they entered them.
#    • From a live FIFA lookup (same for everyone at a given time): REFRESHED, RES,
#      UPCOMING, R32_TIMES, R16_FIX, R16_PICK, and the HIGHLIGHTS list (further down).
#  Everything below the "RENDER ENGINE" banner is kept VERBATIM — it reproduces the
#  exact dashboard design / UI / format. Do not restyle, re-order, or add to it.
# ══════════════════════════════════════════════════════════════════════════════
# Data is loaded from data/*.json — picks.json (this entrant's bracket),
# live.json (FIFA-synced results/schedule/highlights, written by the sync engine),
# topology.json (the fixed KO bracket). Everything below the RENDER ENGINE banner
# is verbatim. The tuple() restores are because JSON has only lists.
_DATA=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),"data")
def _load(_name):
    with open(os.path.join(_DATA,_name),encoding="utf-8") as _fh: return json.load(_fh)
P=_load("picks.json"); L=_load("live.json"); T=_load("topology.json")
ENTRANT=P["entrant"]; TIEBREAKER=P["tiebreaker"]
REFRESHED=L["refreshed"]
CREDIT="Built With Cowork — Imagined by Eric Lam"  # tiny footer signature — fixed, do not change
SYNC_URL="https://github.com/eriic-builds/wc26-bracket/actions/workflows/sync-results.yml"  # "Sync now" button: opens the workflow's Run page on GitHub (tap "Run workflow" to sync). No relay, no token. Leave "" to hide the button.

SEED=P["seed"]

# (matchcode, date, teamA, teamB, the entrant's pick) — from picks.json
R32=[tuple(r) for r in P["r32"]]
FREEBIE_MATCH=P["freebie_match"]

# LIVE RESULTS (teamA goals, teamB goals, winner, note) — from live.json (sync-written)
RES={c:tuple(v) for c,v in L["res"].items()}
UPCOMING=dict(L["upcoming"])

R16_WIN=P["r16_win"]
QF_WIN=P["qf_win"]; SF_WIN=P["sf_win"]
CHAMP=P["champ"]; RUNNER=P["runner"]

# Knockout topology — which two prior matches feed each match (fixed FIFA bracket, same
# for every entrant). Single source of truth, shared with the sync engine
# (scripts/fetch_results.py). R32 codes feed the Round of 16.
KO_FEED={c:tuple(v) for c,v in T["ko_feed"].items()}
KO_DATES={"r16":"Jul 4–7","qf":"Jul 9–11","sf":"Jul 14–15","final":"Sun Jul 19 · MetLife"}
KO_ROUND_ORDER=[("Round of 16","r16",[f"M{n}" for n in range(89,97)]),
 ("Quarterfinals","qf",[f"M{n}" for n in range(97,101)]),
 ("Semifinals","sf",["M101","M102"]),("Final","final",["M104"])]
# Derive each round's per-match pick (by code) from the entrant's tree picks + topology,
# so no extra per-match data entry is needed. Tree slot i in a round pairs the two prior
# matches (2i, 2i+1); the code is looked up from KO_FEED.
_feed_to_code={v:k for k,v in KO_FEED.items()}
def _code_for(fa,fb): return _feed_to_code.get((fa,fb)) or _feed_to_code.get((fb,fa))
PICK_BY_CODE={}; KO_ROUND={}
def _derive_round(prev_codes, wins, short):
    codes=[]
    for j,w in enumerate(wins):
        c=_code_for(prev_codes[2*j], prev_codes[2*j+1])
        PICK_BY_CODE[c]=w; KO_ROUND[c]=short; codes.append(c)
    return codes
_r32codes=[m[0] for m in R32]
_r16codes=_derive_round(_r32codes, R16_WIN, "r16")
_qfcodes=_derive_round(_r16codes, QF_WIN, "qf")
_sfcodes=_derive_round(_qfcodes, SF_WIN, "sf")
_finalcodes=_derive_round(_sfcodes, [CHAMP], "final")
R16_PICK={c:PICK_BY_CODE[c] for c in _r16codes}
CODE_OF_PICK={}
for _c,_t in PICK_BY_CODE.items(): CODE_OF_PICK[(KO_ROUND[_c],_t)]=_c

def pairs(s): return [(s[i],s[i+1]) for i in range(0,len(s),2)]
r32_win=[m[4] for m in R32]
rounds=[("Round of 32","r32",1,[(m[2],m[3],m[4]) for m in R32])]
def build(field,w,label,short,pts):
    return (label,short,pts,[(a,b,x) for (a,b),x in zip(pairs(field),w)])
rounds.append(build(r32_win,R16_WIN,"Round of 16","r16",2))
rounds.append(build(R16_WIN,QF_WIN,"Quarterfinals","qf",4))
rounds.append(build(QF_WIN,SF_WIN,"Semifinals","sf",8))
rounds.append(build(SF_WIN,[CHAMP],"Final","final",16))
PTS={"r32":1,"r16":2,"qf":4,"sf":8,"final":16}
POINTS_MAX=80

# eliminated teams (losers of completed R32 matches)
ELIM=set()
for (mc,dt,a,b,pk) in R32:
    if mc in RES:
        w=RES[mc][2]; ELIM.add(a if w==b else b)
R32_ACTUAL_WINNERS={RES[mc][2] for mc in RES}
r32_pick_actual={m[4]:RES[m[0]][2] for m in R32 if m[0] in RES}  # your pick -> team that actually advanced
# later-round eliminations (losers of finished knockout matches) feed the live bracket + scoring
for _mc,(_fa,_fb) in KO_FEED.items():
    if _mc in RES:
        _wa=RES[_fa][2] if _fa in RES else None
        _wb=RES[_fb][2] if _fb in RES else None
        _w=RES[_mc][2]
        _loser=_wa if _w==_wb else (_wb if _w==_wa else None)
        if _loser: ELIM.add(_loser)
KO_WINNERS_BY_ROUND={}
for _mc in KO_FEED:
    if _mc in RES: KO_WINNERS_BY_ROUND.setdefault(KO_ROUND[_mc],set()).add(RES[_mc][2])
_PREV_ROUND={"r16":"r32","qf":"r16","sf":"qf","final":"sf"}
def actual_advancer(short, team):
    """The team that ACTUALLY occupies this bracket slot — the real winner of the
    previous-round match the entrant had ``team`` winning. Returns None while that
    feeder match is still unplayed. Unlike a plain 'is it eliminated?' test, this keeps
    surfacing a team that reached this round even after it has since been knocked out,
    so no actually-advanced team ever drops off the bracket map in a later column."""
    prev=_PREV_ROUND.get(short)
    if not prev: return None
    if prev=="r32": return r32_pick_actual.get(team)
    code=CODE_OF_PICK.get((prev,team))
    if code and code in RES: return RES[code][2]
    return None
_PREV_OF={"r16":"r32","qf":"r16","sf":"qf","final":"sf","champion":"final"}
_NEXT_OF={"r32":"r16","r16":"qf","qf":"sf","sf":"final","final":"champion"}
def won_into(team, short):
    """True if the team actually won into (reached) the round this column shows."""
    prev=_PREV_OF.get(short)
    if prev=="r32": return team in R32_ACTUAL_WINNERS
    if prev: return team in KO_WINNERS_BY_ROUND.get(prev,set())
    return False
def reach_status(team, short):
    """Did this team actually reach (win into) the round this column represents?

    A team that reached this round is "won" here even if it was later knocked
    out — being eliminated in a *later* round doesn't retroactively make it wrong
    to have reached *this* one. Only teams that never reached this round are
    "lost" (eliminated earlier) or "pending" (round not yet decided). Checking
    "did it win into this round" before the ELIM test is what keeps a correct
    pick green in the round it reached instead of flipping blue once it bows out."""
    if won_into(team, short): return "won"
    if team in ELIM: return "lost"
    return "pending"
def out_at_round(team, short):
    """True when this column is where the team actually bowed out: it reached
    this round (green path in) but lost its match here (didn't win into the next
    round) and is now eliminated. Such a box stays green — the pick to get here
    was correct — but is greyed out to show the team is done."""
    if team not in ELIM: return False
    if not won_into(team, short): return False        # never reached this round
    nxt=_NEXT_OF.get(short)
    if nxt and won_into(team, nxt): return False       # advanced past this round
    return True

def pick_status(short, team, mc=None):
    if short=="r32":
        if mc in RES: return "won" if team==RES[mc][2] else "lost"
        return "pending"
    code=CODE_OF_PICK.get((short,team))
    if code and code in RES:
        return "won" if team==RES[code][2] else "lost"
    return "lost" if team in ELIM else "pending"

# compute totals
CONF=OUT=LIVE=0
r32_decided=r32_correct=0
for (mc,dt,a,b,pk) in R32:
    st=pick_status("r32",pk,mc)
    if st=="won": CONF+=1; r32_decided+=1; r32_correct+=1
    elif st=="lost": OUT+=1; r32_decided+=1
    else: LIVE+=1
for (label,short,pts,ms) in rounds[1:]:
    for (a,b,w) in ms:
        st=pick_status(short,w)
        if st=="won": CONF+=pts
        elif st=="lost": OUT+=pts
        else: LIVE+=pts
ATTAIN=CONF+LIVE
DECIDED=CONF+OUT   # points already settled (won + lost) — the "so far" denominator
assert CONF+OUT+LIVE==POINTS_MAX, (CONF,OUT,LIVE)

# ---- derived copy (computed from data — NO scenario text hardcoded) ----
N_R32=len(R32); R32_DONE=sum(1 for m in R32 if m[0] in RES); REMAIN_R32=N_R32-R32_DONE
CHAMP_ALIVE = CHAMP not in ELIM
CHAMP_STATUS = "still alive" if CHAMP_ALIVE else "out"
# Genuine "busted branches" = the entrant's own picks that lost a match they were picked
# to win (an R32 miss, or a later-round pick that reached its match and lost) — NOT a
# correct pick that fell to another of your picks. Keeps the KPI note in step with the
# scoring (OUT points) and the "How it played out" story.
BUSTED=[m[4] for m in R32 if m[0] in RES and RES[m[0]][2]!=m[4]]
for _code,(_fa,_fb) in KO_FEED.items():
    if _code in RES:
        _pk=PICK_BY_CODE.get(_code)
        _wa=RES[_fa][2] if _fa in RES else None
        _wb=RES[_fb][2] if _fb in RES else None
        if _pk and _pk in (_wa,_wb) and _pk!=RES[_code][2]: BUSTED.append(_pk)
BUSTED_TXT=" & ".join(BUSTED) if BUSTED else ""
BUSTED_PHRASE=("; busted so far: "+BUSTED_TXT) if BUSTED else ""
BUSTED_NOTE=(BUSTED_TXT+" branch"+("es" if len(BUSTED)>1 else "")) if BUSTED else "none yet"
if CHAMP in ELIM: CHAMP_NOTE=f"{CHAMP} is out"
elif CHAMP in R32_ACTUAL_WINNERS: CHAMP_NOTE=f"Alive — {CHAMP} has advanced so far"
else: CHAMP_NOTE="Your champion pick"
FF_ALIVE=sum(1 for t in QF_WIN if t not in ELIM)

# Kickoff times for future games — anchored to ET (NBC / Sporting News), CT = ET-1, PT = ET-3
R32_TIMES={  # match: (day, ET, CT, PT)
 "M84":("Thu Jul 2","3:00 PM","2:00 PM","12:00 PM"),
 "M83":("Thu Jul 2","7:00 PM","6:00 PM","4:00 PM"),
 "M85":("Thu Jul 2","11:00 PM","10:00 PM","8:00 PM"),
 "M88":("Fri Jul 3","2:00 PM","1:00 PM","11:00 AM"),
 "M86":("Fri Jul 3","6:00 PM","5:00 PM","3:00 PM"),
 "M87":("Fri Jul 3","9:30 PM","8:30 PM","6:30 PM")}
R16_FIX=[  # match, day, teamA, teamB, ET, CT, PT
 ("M90","Sat Jul 4","Canada","Morocco","1:00 PM","12:00 PM","10:00 AM"),
 ("M89","Sat Jul 4","Paraguay","France","5:00 PM","4:00 PM","2:00 PM"),
 ("M91","Sun Jul 5","Brazil","Norway","4:00 PM","3:00 PM","1:00 PM"),
 ("M92","Sun Jul 5","Mexico","England","8:00 PM","7:00 PM","5:00 PM"),
 ("M93","Mon Jul 6","Portugal / Croatia","Spain / Austria","3:00 PM","2:00 PM","12:00 PM"),
 ("M94","Mon Jul 6","United States","Belgium","8:00 PM","7:00 PM","5:00 PM"),
 ("M95","Tue Jul 7","Argentina / Cape Verde","Australia / Egypt","12:00 PM","11:00 AM","9:00 AM"),
 ("M96","Tue Jul 7","Switzerland / Algeria","Colombia / Ghana","4:00 PM","3:00 PM","1:00 PM")]
# Kickoff times for not-yet-played knockout games (QF/SF/Final) — AUTO, maintained
# by the sync engine (scripts/fetch_results.py) from the FIFA schedule, DST-safe.
# {code: (day, ET, CT, PT)} — from live.json. Do not hand-edit.
KO_FIX={c:tuple(v) for c,v in L["ko_fix"].items()}

def esc(s): return html.escape(str(s))
def seed_of(t): return SEED.get(t,"")
DASH="–"

# Country World Cup pedigree (public historical record: titles won, best-ever finish).
# Constant reference data — same for every entrant; teams not listed fall back to "—".
WC_HISTORY={
 "Brazil":(5,"Champions ×5 (last 2002)"),"Germany":(4,"Champions ×4 (last 2014)"),
 "Argentina":(3,"Champions ×3 (2022)"),"France":(2,"Champions ×2 (2018)"),
 "Spain":(1,"Champions (2010)"),"England":(1,"Champions (1966)"),
 "Netherlands":(0,"Runners-up ×3"),"Croatia":(0,"Runners-up (2018)"),"Sweden":(0,"Runners-up (1958)"),
 "Portugal":(0,"Third place (1966)"),"United States":(0,"Third place (1930)"),
 "Belgium":(0,"Third place (2018)"),"Austria":(0,"Third place (1954)"),"Morocco":(0,"Fourth place (2022)"),
 "Mexico":(0,"Quarterfinals (1970, 1986)"),"Switzerland":(0,"Quarterfinals"),
 "Colombia":(0,"Quarterfinals (2014)"),"Ghana":(0,"Quarterfinals (2010)"),
 "Senegal":(0,"Quarterfinals (2002)"),"Paraguay":(0,"Quarterfinals (2010)"),
 "Japan":(0,"Round of 16 (×4)"),"Australia":(0,"Round of 16 (2006, 2022)"),
 "Norway":(0,"Round of 16 (1998)"),"Ecuador":(0,"Round of 16 (2006)"),"Algeria":(0,"Round of 16 (2014)"),
 "Ivory Coast":(0,"Group stage"),"Egypt":(0,"Group stage"),"South Africa":(0,"Group stage"),
 "Canada":(0,"Group stage"),"DR Congo":(0,"Group stage (as Zaire, 1974)"),
 "Bosnia & Herz.":(0,"Group stage (2014)"),"Cape Verde":(0,"Debut (2026)"),
}
def team_2026(team):
    if team in ELIM: return "Out — Round of 32"
    if team in R32_ACTUAL_WINNERS: return "Into the Round of 16"
    return "Round of 32 — to play"
STATS_JS = "window.WCSTATS="+json.dumps({t:{"t":WC_HISTORY.get(t,(0,"—"))[0],"b":WC_HISTORY.get(t,(0,"—"))[1],
    "y":team_2026(t),"s":seed_of(t)} for t in SEED},ensure_ascii=False)+";"

# ---------------- bracket ----------------
def r32_cell(team, picked, decided, real_winner, freebie):
    cls=["team"]
    badge=""
    if decided:
        if picked and real_winner: cls.append("adv"); badge='<span class="rb ok">✓</span>'
        elif picked and not real_winner: cls.append("busted"); badge='<span class="rb no">✕</span>'
        elif (not picked) and real_winner: cls.append("realadv"); badge='<span class="rb up">▲</span>'
        else: cls.append("out")
    else:
        cls.append("adv" if picked else "out")
    sd=seed_of(team); sh=f'<span class="seed">{esc(sd)}</span>' if sd else ''
    ftag='<span class="tt" title="Freebie — Canada 1–0 South Africa, auto-credited">🎁</span>' if freebie else ''
    return (f'<div class="{" ".join(cls)}" data-team="{esc(team)}" data-round="r32" tabindex="0">'
            f'<span class="fav-bar"></span>{sh}<span class="tname">{esc(team)}</span>{ftag}{badge}</div>')

def _pick_box(team, picked, short, champ, st):
    cls=["team","st-"+st]
    if champ: cls.append("champ")
    if picked and not champ: cls.append("advancer")
    # A correct pick that reached this round but has since bowed out here keeps its
    # green (the pick to get here was right) but is greyed out to show it's done,
    # and drops the ✓ so it doesn't read as "still through".
    gone=(st=="won" and out_at_round(team, short))
    if gone: cls.append("gone")
    badge=('' if gone else '<span class="rb ok">✓</span>') if st=="won" else ('<span class="rb no">✕</span>' if st=="lost" else '')
    tag='<span class="tt">🏆</span>' if champ else ''
    chev='<span class="adv-arrow" title="you have this team advancing">›</span>' if (picked and not champ) else ''
    sd=seed_of(team); sh=f'<span class="seed">{esc(sd)}</span>' if sd else ''
    return (f'<div class="{" ".join(cls)}" data-team="{esc(team)}" data-round="{short}" tabindex="0">'
            f'<span class="fav-bar"></span>{sh}<span class="tname">{esc(team)}</span>{tag}{badge}{chev}</div>')

def later_cell(team, picked, short, champ=False, actual=None, mode="actual"):
    if mode=="picked":
        # Your bracket as you filled it — every pick trails forward, coloured by result.
        return _pick_box(team, picked, short, champ, reach_status(team, short))
    # Actual mode: a pick that correctly reached this round stays as itself
    # (green) even if it was later knocked out — only its onward path to the next
    # round turns red/blue. Prune a pick to the team that actually advanced (blue)
    # only when the pick never reached this round.
    st=reach_status(team, short)
    if st!="won" and team in ELIM:
        if actual:
            sd=seed_of(actual); sh=f'<span class="seed">{esc(sd)}</span>' if sd else ''
            gone=actual in ELIM
            cls="team st-actual"+(" gone" if gone else "")
            rnd={"r16":"Round of 16","qf":"Quarterfinal","sf":"Semifinal","final":"Final"}.get(short,"this round")
            if actual==team:
                tip=f"{actual} reached the {rnd}"+(", but is now out" if gone else "")
            elif gone:
                tip=f"{actual} advanced in your {team} pick's place, but is now out"
            else:
                tip=f"actually advanced — you picked {team}"
            return (f'<div class="{cls}" data-team="{esc(actual)}" data-round="{short}" tabindex="0">'
                    f'<span class="fav-bar"></span>{sh}<span class="tname">{esc(actual)}</span>'
                    f'<span class="rb up" title="{esc(tip)}">▲</span></div>')
        return '<div class="team blank"><span class="tname">&nbsp;</span></div>'
    return _pick_box(team, picked, short, champ, st)

def build_bracket(mode="actual"):
    cols=[]; cells=[]
    for (mc,dt,a,b,pk) in R32:
        dec=mc in RES; rw=RES[mc][2] if dec else None
        cap=""
        if dec:
            gA,gB,w,note=RES[mc]
            cap=f'<div class="mscore">{esc(a)} {gA}{DASH}{gB} {esc(b)}{(" · "+note) if note else ""}</div>'
        else:
            cap=f'<div class="mscore up">kick-off {esc(UPCOMING.get(mc,dt))}</div>'
        fb=(mc==FREEBIE_MATCH)
        cells.append('<div class="match" data-status="'+pick_status("r32",pk,mc)+'"><div class="mlabel">'+esc(mc)+' · '+esc(dt)+'</div>'+cap
            +r32_cell(a, pk==a, dec, rw==a, fb and pk==a)
            +r32_cell(b, pk==b, dec, rw==b, fb and pk==b)+'</div>')
    cols.append('<div class="round"><div class="rhead">Round of 32<span>'+f'{R32_DONE} of {N_R32} final'+'</span></div><div class="matches">'+''.join(cells)+'</div></div>')
    meta=[("Round of 16","r16","Jul 4–7",rounds[1][3]),("Quarterfinals","qf","Jul 9–11",rounds[2][3]),
          ("Semifinals","sf","Jul 14–15",rounds[3][3]),("Final","final","Jul 19",rounds[4][3])]
    round_codes={"r16":_r16codes,"qf":_qfcodes,"sf":_sfcodes,"final":_finalcodes}
    r16_day={mc:day for (mc,day,a,b,et,ct,ptz) in R16_FIX}
    for label,short,sub,ms in meta:
        cc=[]
        codes=round_codes.get(short,[])
        for j,(a,b,w) in enumerate(ms):
            isf=(label=="Final")
            aa=actual_advancer(short,a)
            ab=actual_advancer(short,b)
            code=codes[j] if j<len(codes) else ""
            when=r16_day.get(code,"")
            lab=(esc(code)+(' · '+esc(when) if when else '')) if code else ""
            mlab=f'<div class="mlabel up">{lab}</div>' if lab else ""
            cc.append('<div class="match">'+mlab+later_cell(a,w==a,short,champ=(isf and w==a),actual=aa,mode=mode)+later_cell(b,w==b,short,champ=(isf and w==b),actual=ab,mode=mode)+'</div>')
        cols.append(f'<div class="round"><div class="rhead">{esc(label)}<span>{esc(sub)}</span></div><div class="matches">'+''.join(cc)+'</div></div>')
    cols.append('<div class="round champcol"><div class="rhead">Champion<span>your pick</span></div><div class="matches">'
        '<div class="match">'+later_cell(CHAMP,True,"champion",champ=True,mode=mode)+
        '<div class="champ-note">'+esc(CHAMP_NOTE)+'</div></div></div></div>')
    return f'<div class="bracket mode-{mode}"><svg class="bksvg" aria-hidden="true"></svg>'+''.join(cols)+'</div>'

# ---------------- scorecard ----------------
def build_scorecard():
    rows=[]
    for (mc,dt,a,b,pk) in R32:
        st=pick_status("r32",pk,mc); pid="r32-"+mc
        if mc in RES:
            gA,gB,w,note=RES[mc]; loser=a if w==b else b
            if st=="won":
                detail=f'beat {esc(loser)} {gA if a==w else gB}{DASH}{gB if a==w else gA}{(" ("+note+")") if note else ""}'
            else:
                detail=f'lost to {esc(w)} {gA}{DASH}{gB}{(" ("+note+")") if note else ""}'
        else:
            detail=f'vs {esc(b if pk==a else a)} · {esc(UPCOMING.get(mc,dt))}'
        rows.append(scrow(pid,"r32",1,pk,detail,st,a,b))
    for (label,short,pts,ms) in rounds[1:]:
        for i,(a,b,w) in enumerate(ms):
            st=pick_status(short,w); pid=f"{short}-{i}"
            code=CODE_OF_PICK.get((short,w))
            if st=="won":
                if code and code in RES:
                    gA,gB,ww,note=RES[code]
                    detail=f'won {gA}{DASH}{gB}{(" ("+note+")") if note else ""} — '+{
                        "r16":"into the quarterfinals","qf":"into the semifinals",
                        "sf":"into the Final","final":"champions 🏆"}[short]
                else:
                    detail={"r16":"through to the quarterfinals","qf":"through to the semifinals",
                            "sf":"through to the Final","final":"lifted the trophy 🏆"}[short]
            elif st=="lost":
                parts=set()
                if code:
                    for f in KO_FEED[code]:
                        if f in RES: parts.add(RES[f][2])
                if code and code in RES and w in parts:
                    gA,gB,ww,note=RES[code]
                    detail=f'lost to {esc(ww)} {gA}{DASH}{gB}{(" ("+note+")") if note else ""}'
                else:
                    detail="out — pick eliminated earlier"
            else:
                detail={"r16":"to reach the quarterfinals","qf":"to reach the semifinals",
                        "sf":"to reach the Final","final":"to lift the trophy"}[short]
            rows.append(scrow(pid,short,pts,w,detail,st,a,b))
    head=('<div class="scrow schead"><div class="tc">Round</div><div class="tc">Your pick &amp; result</div>'
          '<div class="tc">Value</div><div class="tc">Status</div></div>')
    return '<div class="scard" id="scard">'+head+''.join(rows)+'</div>'

def scrow(pid,short,pts,pick,detail,default,a,b):
    return (f'<div class="scrow" data-pick="{pid}" data-round="{short}" data-pts="{pts}" '
            f'data-default="{default}" data-team="{esc(a)}|{esc(b)}">'
            f'<div class="tc"><span class="rpill r-{short}">{esc(short.upper())}</span></div>'
            f'<div class="tc match-cell"><span class="win">{esc(pick)}</span>'
            f'<span class="det">{detail}</span></div>'
            f'<div class="tc pts-cell">{pts}<span class="ptsu">pt{"s" if pts>1 else ""}</span></div>'
            f'<div class="tc seg-cell"><div class="seg" role="group">'
            f'<button data-set="won" title="Correct">✓</button>'
            f'<button data-set="pending" title="Not decided">–</button>'
            f'<button data-set="lost" title="Wrong / out">✕</button></div></div></div>')

def build_scorebar():
    return ('<div class="scorebar glass" id="scorebar"><div class="sb-main">'
      f'<div class="sb-big"><span id="scConfirmed">{CONF}</span><span class="sb-slash">/ {POINTS_MAX}</span></div>'
      '<div class="sb-cap">points confirmed · <b id="scSoFar">'+f'{CONF}/{DECIDED}'+'</b> so far</div>'
      f'<div class="sb-track"><i id="scBar" style="width:{int(CONF/POINTS_MAX*100)}%"></i></div></div>'
      '<div class="sb-stats">'
      f'<div class="sb-stat s-win"><b id="scConfirmed2">{CONF}</b><span>confirmed</span></div>'
      f'<div class="sb-stat s-live"><b id="scLive">{LIVE}</b><span>still live</span></div>'
      f'<div class="sb-stat s-out"><b id="scOut">{OUT}</b><span>eliminated</span></div>'
      f'<div class="sb-stat s-max"><b id="scMax" data-max="{POINTS_MAX}">{ATTAIN}</b><span>still attainable</span></div>'
      '</div></div>')

KPIS=None  # KPIs are built live in build_kpis() so they can follow the current round
def build_kpis():
    rnd_full=_ROUND_FULL.get(CURRENT_ROUND,CUR_LABEL)
    if CUR_REMAIN: rnd_note=f"{CUR_REMAIN} game{'s' if CUR_REMAIN!=1 else ''} left"
    elif NEXT_LABEL: rnd_note=f"{NEXT_LABEL} next"
    else: rnd_note="round complete"
    kpis=[
     ("Confirmed points", f"<span id='kpiConfirmed'>{CONF}</span><span class='kunit'>/ {POINTS_MAX}</span>","✅","teal",f"{r32_correct} of {r32_decided} R32 picks right"),
     (rnd_full, f"{CUR_CORR}<span class='kunit'>/ {CUR_DEC}</span>","⚽","blue",rnd_note),
     ("Still live", f"<span id='kpiLive'>{LIVE}</span>","⚡","blue","across your open picks"),
     ("Max attainable", f"{ATTAIN}","🎯","green","if your path holds"),
     ("Champion pick", CHAMP,"🏆","gold",CHAMP_STATUS),
     ("Points lost", f"{OUT}","🚫","red",BUSTED_NOTE),
    ]
    return ''.join(f'<div class="glass kpi t-{t}"><div class="kpi-ic">{ic}</div>'
        f'<div class="kpi-l">{esc(l)}</div><div class="kpi-v">{v}</div><div class="kpi-n">{esc(n)}</div></div>'
        for l,v,ic,t,n in kpis)

def build_finalfour():
    out=[]
    for tm in QF_WIN:
        role="Champion" if tm==CHAMP else ("Runner-up" if tm==RUNNER else "Semifinalist")
        alive = tm not in ELIM
        cls="ff-champ" if tm==CHAMP else ("ff-run" if tm==RUNNER else "")
        dot = '<span class="ff-live">● alive</span>' if alive else '<span class="ff-dead">✕ out</span>'
        out.append(f'<div class="ff {cls}" data-team="{esc(tm)}"><span class="ff-seed">{esc(seed_of(tm))}</span>'
                   f'<span class="ff-name">{esc(tm)}</span><span class="ff-role">{role} · {dot}</span></div>')
    return ''.join(out)

# ── "How it played out" — fully DERIVED from the live data (picks + RES + topology),
#    so every auto-sync/rebuild refreshes it on its own with nothing hand-written to go
#    stale. It emits: a running Round-of-32 scoreline, one card for every branch that
#    actually busted (a pick that played its own match and lost) in round order, and a
#    champion outlook. Team emoji reuse the same nickname/flag scheme as the sync engine.
_STORY_NICK={"England":"\U0001f981","France":"\U0001f413","Netherlands":"\U0001f7e0",
 "Belgium":"\U0001f608","Germany":"\U0001f985","Spain":"\U0001f402","Australia":"\U0001f998",
 "Canada":"\U0001f341","Ivory Coast":"\U0001f418","DR Congo":"\U0001f406","Japan":"\u2694\ufe0f",
 "Mexico":"\U0001f335","United States":"\U0001f5fd","Algeria":"\U0001f98a","Colombia":"\u2615",
 "Cape Verde":"\U0001f988","Bosnia & Herz.":"\U0001f409","Ghana":"\u2b50","Brazil":"\U0001f49b",
 "Argentina":"\U0001f499","Egypt":"\U0001f3fa"}
_STORY_ISO2={"Argentina":"AR","Australia":"AU","Austria":"AT","Belgium":"BE","Bosnia & Herz.":"BA",
 "Brazil":"BR","Canada":"CA","Cape Verde":"CV","Colombia":"CO","Croatia":"HR","DR Congo":"CD",
 "Ecuador":"EC","Egypt":"EG","France":"FR","Germany":"DE","Ghana":"GH","Ivory Coast":"CI","Japan":"JP",
 "Mexico":"MX","Morocco":"MA","Netherlands":"NL","Norway":"NO","Paraguay":"PY","Portugal":"PT",
 "Senegal":"SN","South Africa":"ZA","Spain":"ES","Sweden":"SE","Switzerland":"CH","United States":"US",
 "Algeria":"DZ"}
def _story_flag(iso2):
    if not iso2 or len(iso2)!=2 or not iso2.isalpha(): return ""
    return "".join(chr(0x1F1E6+ord(c)-ord("A")) for c in iso2.upper())
def team_emoji(name):
    return _STORY_NICK.get(name) or _story_flag(_STORY_ISO2.get(name,"")) or "\u26bd"

_STORY_ROUND_NAME={0:"Round of 32",1:"Round of 16",2:"Quarterfinal",3:"Semifinal",4:"Final"}
_STORY_LEVEL_PTS=[1,2,4,8,16]
_STORY_KO_LEVEL={"r16":1,"qf":2,"sf":3,"final":4}
def _levels_picked(team):
    lv=[0]  # every branch begins as a Round-of-32 pick
    if team in R16_WIN: lv.append(1)
    if team in QF_WIN: lv.append(2)
    if team in SF_WIN: lv.append(3)
    if team==CHAMP: lv.append(4)
    return lv
def _forfeited(team, elim_level):
    return sum(_STORY_LEVEL_PTS[l] for l in _levels_picked(team) if l>=elim_level)

def _collect_busts():
    """Every branch that actually played its own match and lost (an upset that cost the
    entrant), newest-round first, richest detail — shared by the story's turning-point card."""
    busts=[]
    for (mc,dt,a,b,pk) in R32:
        if mc in RES:
            gA,gB,w,note=RES[mc]
            if pk!=w: busts.append((0,int(mc[1:]),pk,w,a,b,gA,gB,note))
    for code,(fa,fb) in KO_FEED.items():
        if code in RES:
            wa=RES[fa][2] if fa in RES else None
            wb=RES[fb][2] if fb in RES else None
            pk=PICK_BY_CODE.get(code); gA,gB,w,note=RES[code]
            if pk and pk in (wa,wb) and pk!=w:
                busts.append((_STORY_KO_LEVEL[KO_ROUND[code]],int(code[1:]),pk,w,wa,wb,gA,gB,note))
    return busts

def story_cards():
    """A tight 3-card narrative arc — momentum, the turning point, the stakes ahead — all
    derived live so it tracks the current round and never repeats the game-by-game recaps
    already shown in Game facts / the bracket. Capped at three so it stays a visual aid."""
    cards=[]
    # 1) MOMENTUM — the entrant's record across the rounds played so far
    played=[(s,round_tally(s)) for s in _ROUND_SEQ]
    bits=[f"{c} of {d} in the {_ROUND_FULL[s]}" for (s,(c,d,l)) in played if d]
    tot_c=sum(c for (_s,(c,d,l)) in played); tot_d=sum(d for (_s,(c,d,l)) in played)
    if not bits:
        cards.append(("\u26bd","The story so far","Kicking off",
            "No games are final yet — your first results will land here as they finish."))
    else:
        head=("Perfect run" if tot_c==tot_d else "Holding strong" if tot_c*2>=tot_d else "Bumpy road")
        body=(" · ".join(bits))+f". {CONF} points banked, {LIVE} still live."
        cards.append(("\u2705" if tot_c==tot_d else "\U0001f4ca",
            f"{tot_c} of {tot_d} picks right so far",head,body))
    # 2) TURNING POINT — the single costliest upset against you (not a list; a highlight)
    busts=_collect_busts()
    if busts:
        busts.sort(key=lambda x:(-_forfeited(x[2],x[0]),-x[0],x[1]))
        lvl,_n,pk,w,a,b,gA,gB,note=busts[0]
        sc=f"{a} {gA}{DASH}{gB} {b}"+(f" ({note})" if note else "")
        forfeit=_forfeited(pk,lvl); n=len(busts)
        lead=(f"{w} knocked out your {pk} pick — {sc}." if lvl==0
              else f"{w} ended your {pk} run in the {_STORY_ROUND_NAME[lvl]} — {sc}.")
        if n>1:
            tail=f" It's the costliest of {n} branches that have busted, {OUT} points gone in all."
        else:
            tail=f" That's {forfeit} point{'s' if forfeit!=1 else ''} off your board."
        cards.append((team_emoji(w),"Biggest swing",f"{w} over {pk}",lead+tail))
    else:
        cards.append(("\U0001f3af","Clean sheet","No busted branches yet",
            "Every team you've backed so far is still standing — nothing off your board."))
    # 3) STAKES AHEAD — champion + final-four watch + what's next
    ce=team_emoji(CHAMP)
    if CHAMP in ELIM:
        cards.append((ce,"What's at stake",f"{CHAMP} is out",
            f"Your title pick is gone, so the Champion’s 16 points are off the board — {ATTAIN} still attainable."))
    else:
        ff=", ".join(t for t in QF_WIN if t not in ELIM) or "—"
        nxt=f" Up next: the {NEXT_LABEL}." if NEXT_LABEL else ""
        cards.append((ce,"What's at stake",f"{CHAMP} still standing",
            f"{CHAMP} is alive, with {FF_ALIVE} of your final four ({ff}) still in it.{nxt}"))
    return cards[:3]
def build_story():
    return ''.join(f'<div class="glass story"><div class="story-ic">{ic}</div>'
        f'<div class="story-tag">{esc(tag)}</div><div class="story-title">{esc(ti)}</div>'
        f'<div class="story-body">{esc(bd)}</div></div>' for ic,tag,ti,bd in story_cards())

# Tournament-stage tracker — "done"/"active"/"up" is derived from actual match counts
# (not hand-set), so it advances correctly on its own as each round finishes: the first
# round that isn't 100% final becomes "active", everything before it is "done", everything
# after stays "up". This is what keeps the Round of 32 -> Round of 16 handoff (and every
# later one) accurate without manual edits.
_STAGE_ROUNDS=[("Round of 32","r32","Jun 28–Jul 3",R32_DONE,N_R32)]
for (label,short,codes) in KO_ROUND_ORDER:
    _dates={"r16":"Jul 4–7","qf":"Jul 9–11","sf":"Jul 14–15","final":"Sun Jul 19 · MetLife"}[short]
    _STAGE_ROUNDS.append((label,short,_dates,sum(1 for mc in codes if mc in RES),len(codes)))
def _build_stages_list():
    stages=[("Group stage","Ended Jun 27","done")]
    active_taken=False
    for (label,short,dates,done,total) in _STAGE_ROUNDS:
        if total>0 and done==total:
            stages.append((label,f"{dates} · {done}/{total}","done"))
        elif not active_taken:
            stages.append((label,f"{dates} · {done}/{total}" if total else dates,"active"))
            active_taken=True
        else:
            stages.append((label,dates,"up"))
    return stages
STAGES=_build_stages_list()

# Default the round-by-round results view to whichever round the tournament is
# actually in right now: the first round that isn't fully final (the same "active"
# round the stage tracker highlights). This makes the dashboard follow the
# tournament on its own — once the Round of 32 is complete the results panel
# defaults to the Round of 16, then the Quarterfinals, and so on; once the Final
# is played it stays there. Recomputed on every build, so each auto-sync that
# finishes a round advances the default with no manual edit.
_ROUND_TAGS={"r32":"R32","r16":"R16","qf":"QF","sf":"SF","final":"Final"}
def _current_round():
    for (label,short,dates,done,total) in _STAGE_ROUNDS:
        if total==0 or done<total:
            return short
    return _STAGE_ROUNDS[-1][1]
CURRENT_ROUND=_current_round()
_CUR=next((r for r in _STAGE_ROUNDS if r[1]==CURRENT_ROUND), _STAGE_ROUNDS[0])
CUR_LABEL,CUR_DONE,CUR_TOTAL=_CUR[0],_CUR[3],_CUR[4]
CUR_REMAIN=CUR_TOTAL-CUR_DONE
def _round_subtitle():
    tag=_ROUND_TAGS.get(CURRENT_ROUND,CUR_LABEL)
    if CUR_TOTAL and CUR_DONE>=CUR_TOTAL:
        return f"All {CUR_TOTAL} {tag} final"
    if CUR_DONE==0:
        return f"{tag} up next · {CUR_TOTAL} to play"
    return f"{CUR_DONE} of {CUR_TOTAL} {tag} final · {CUR_REMAIN} to play"
CUR_SUBTITLE=_round_subtitle()

# The entrant's record in a given round (won / decided / still-live), plus the record in
# the round the tournament is currently in, the next round up, and a one-line live status.
# All recomputed each build, so the hero, KPI, scorecard and story copy follow the live
# round on their own instead of staying frozen on the Round of 32.
_ROUND_PICKS={"r16":R16_WIN,"qf":QF_WIN,"sf":SF_WIN,"final":[CHAMP]}
_ROUND_FULL={"r32":"Round of 32","r16":"Round of 16","qf":"Quarterfinals","sf":"Semifinals","final":"Final"}
_ROUND_SEQ=["r32","r16","qf","sf","final"]
def round_tally(short):
    if short=="r32":
        seq=[pick_status("r32",pk,mc) for (mc,dt,a,b,pk) in R32]
    else:
        seq=[pick_status(short,w) for w in _ROUND_PICKS.get(short,[])]
    corr=sum(1 for s in seq if s=="won"); dec=sum(1 for s in seq if s!="pending")
    return corr,dec,len(seq)-dec
CUR_CORR,CUR_DEC,CUR_LIVE=round_tally(CURRENT_ROUND)
def _next_round(short):
    i=_ROUND_SEQ.index(short) if short in _ROUND_SEQ else -1
    return _ROUND_SEQ[i+1] if 0<=i<len(_ROUND_SEQ)-1 else None
NEXT_ROUND=_next_round(CURRENT_ROUND)
NEXT_LABEL=_ROUND_FULL.get(NEXT_ROUND,"") if NEXT_ROUND else ""
def _live_status():
    full=_ROUND_FULL.get(CURRENT_ROUND,CUR_LABEL)
    if CUR_TOTAL and CUR_DONE>=CUR_TOTAL:
        return f"The {full} is complete." + (f" The {NEXT_LABEL} is up next." if NEXT_LABEL else "")
    if CUR_DONE==0:
        return f"The {full} is up next — {CUR_TOTAL} games to play."
    nxt=f", then the {NEXT_LABEL}" if NEXT_LABEL else ""
    return f"The {full} is underway — {CUR_DONE} of {CUR_TOTAL} final, {CUR_REMAIN} to go{nxt}."
LIVE_STATUS=_live_status()
def build_stages():
    return ''.join(f'<div class="stage s-{st}"><span class="sdot">{ {"done":"●","active":"◉","up":"○"}[st] }</span>'
        f'<div><div class="sname">{esc(n)}</div><div class="sdate">{esc(d)}</div></div></div>' for n,d,st in STAGES)

# a compact "who advanced" results strip
def build_results_panel():
    rows=[]
    for (mc,dt,a,b,pk) in R32:
        if mc in RES:
            gA,gB,w,note=RES[mc]; ok=(w==pk)
            badge=('<span class="res-ok">✓ you</span>' if ok else '<span class="res-no">✕ you</span>')
            rows.append(f'<div class="rr"><div class="rr-m">{esc(mc)}</div>'
                f'<div class="rr-s"><b class="{"w" if w==a else "l"}">{esc(a)}</b> {gA}{DASH}{gB} <b class="{"w" if w==b else "l"}">{esc(b)}</b>'
                f'{(" <i>"+note+"</i>") if note else ""}</div>'
                f'<div class="rr-p">{badge}</div></div>')
    up=[]
    for (mc,dt,a,b,pk) in R32:
        if mc not in RES:
            d,et,ct,ptz=R32_TIMES[mc]
            up.append(f'<div class="rr up"><div class="rr-m">{esc(mc)}</div>'
                f'<div class="rr-s">{esc(a)} vs {esc(b)}<span class="rr-t">{d} · {ptz} PT · {ct} CT · {et} ET</span></div>'
                f'<div class="rr-p"><span class="res-soon">your pick: {esc(pk)}</span></div></div>')
    return ('<div class="glass rrbox res-panel" data-round="r32"><div class="rr-h">Round of 32 results · your pick '
            f'<b>{r32_correct}/{r32_decided}</b></div>'+''.join(rows)+
            '<div class="rr-h" style="margin-top:12px">Still to play</div>'+''.join(up)+'</div>')

# Toggleable results panels for the later knockout rounds (Round of 16 = "round of 16",
# Quarterfinals = "round of 8", Semifinals = "round of 4"), built from the exact same
# live topology (KO_FEED/RES/PICK_BY_CODE/ELIM) as the bracket map and knockout scoring
# above, so the match list, scores and pick badges can never drift out of sync with it.
def build_round_results_panel(label, short, codes):
    r16day={mc:(day,et,ct,ptz) for (mc,day,a,b,et,ct,ptz) in R16_FIX}
    rows=[]; done=0; dec=0; corr=0
    for mc in codes:
        fa,fb=KO_FEED[mc]
        a=RES[fa][2] if fa in RES else None
        b=RES[fb][2] if fb in RES else None
        pk=PICK_BY_CODE.get(mc)
        if mc in RES:
            done+=1; dec+=1
            gA,gB,w,note=RES[mc]
            an=a or "?"; bn=b or "?"
            if pk==w: badge='<span class="res-ok">✓ you</span>'; corr+=1
            elif pk in ELIM: badge='<span class="res-no">✕ pick out</span>'
            else: badge='<span class="res-no">✕ you</span>'
            sc=(f'<b class="{"w" if w==an else "l"}">{esc(an)}</b> {gA}{DASH}{gB} '
                f'<b class="{"w" if w==bn else "l"}">{esc(bn)}</b>'+((' <i>'+esc(note)+'</i>') if note else ''))
            rows.append(f'<div class="rr"><div class="rr-m">{esc(mc)}</div>'
                f'<div class="rr-s">{sc}</div><div class="rr-p">{badge}</div></div>')
        else:
            if mc in KO_FIX:
                day,et,ct,ptz=KO_FIX[mc]; when=f'{day} · {ptz} PT · {ct} CT · {et} ET'
            elif short=="r16" and mc in r16day:
                day,et,ct,ptz=r16day[mc]; when=f'{day} · {ptz} PT · {ct} CT · {et} ET'
            else: when=KO_DATES[short]
            ta=a or ("Winner "+fa); tb=b or ("Winner "+fb)
            if pk and pk in ELIM: pkt=f'<span class="res-no">pick {esc(pk)} out</span>'
            elif pk: pkt=f'<span class="res-soon">your pick: {esc(pk)}</span>'
            else: pkt=''
            rows.append(f'<div class="rr up"><div class="rr-m">{esc(mc)}</div>'
                f'<div class="rr-s">{esc(ta)} vs {esc(tb)}<span class="rr-t">{when}</span></div>'
                f'<div class="rr-p">{pkt}</div></div>')
    acc=f'{corr}/{dec}' if dec else '—'
    return (f'<div class="glass rrbox res-panel" data-round="{short}">'
            f'<div class="rr-h">{esc(label)} results · your pick <b>{acc}</b> · {done}/{len(codes)} final</div>'
            +''.join(rows)+'</div>')

# ── GAME FACTS — the last six finished games, newest first, shown as highlight cards.
#    Each card is (emoji, headline, scoreline, "day · venue", one-sentence recap).
#    The sync engine (scripts/fetch_results.py) pulls these automatically from FIFA's
#    free public feed and rewrites AUTO_HL on every run, so the section stays current
#    with no manual editing. FEATURED is an optional slot for a hand-written story you
#    want pinned above the auto cards; leave it empty to show only the live last-six.
FEATURED=[]
AUTO_HL=[tuple(e) for e in L["auto_hl"]]  # from live.json (sync-written, last six games)
HIGHLIGHTS=FEATURED+AUTO_HL
def build_highlights():
    return ''.join(f'<div class="glass story"><div class="story-ic">{ic}</div>'
        f'<div class="story-tag">{esc(tag)}</div><div class="story-title">{esc(ti)}</div>'
        f'<div class="story-when">📅 {esc(wh)}</div>'
        f'<div class="story-body">{esc(bd)}</div></div>' for ic,tag,ti,wh,bd in HIGHLIGHTS)

# Live knockout board — Round of 16, Quarterfinals, Semifinals, Final. Actual teams and
# scores come from RES (kept current by the sync engine); teams for each match are the
# winners of its two feeder matches (KO_FEED). Pending matches show the known/So-far teams.
# Rendered as toggleable result panels alongside the Round of 32 panel (see RESULTS_ROUNDS
# below) rather than a second always-visible grid, so viewing every round needs no extra
# scrolling.

def build_legend():
    items=[
     ('<span class="lg-box lg-won">✓</span>','Your pick — won / through'),
     ('<span class="lg-box lg-lost">✕</span>','Your pick — out'),
     ('<span class="lg-line lg-line-won"></span>','Your path so far (correct)'),
     ('<span class="lg-line lg-line-pend"></span>','Your pick — still to play'),
     ('<span class="lg-box lg-actual">▲</span>','Who actually advanced (you had the other team)'),
     ('<span class="lg-line lg-line-actual"></span>','Actual path'),
     ('<span class="lg-chev">›</span>','You have this team advancing'),
     ('<span class="lg-box lg-champ">🏆</span>','Your champion pick'),
    ]
    return ('<div class="legend glass"><span class="lg-cap">How to read this bracket</span>'
            +''.join(f'<div class="lg-item">{sw}<span>{esc(t)}</span></div>' for sw,t in items)+'</div>')

CSS=r"""
:root{--blue:#0097F4;--purple:#CB85FF;--pink:#FF32A3;--orange:#FFA200;--yellow:#FFCE20;--green:#9BC72A;--teal:#00B291;--red:#E5484D;
 --grad:linear-gradient(120deg,#0097F4,#00B291);
 --radius:18px;--radius-sm:12px;--fs:16px;--lh:1.5;--ls:0em;--gap:16px;--fstack:"Segoe UI","Segoe Sans Display",system-ui,-apple-system,sans-serif;}
html[data-theme="dark"]{--bg:#141317;--panel:#1c1b21;--text:#FFF;--text2:#F4F7EE;--muted:#9aa2ad;--border:rgba(255,255,255,.10);--border2:rgba(255,255,255,.16);
 --glass:linear-gradient(160deg,rgba(255,255,255,.075),rgba(255,255,255,.028));--shadow:0 10px 30px rgba(0,0,0,.45);--hover:rgba(255,255,255,.05);
 --gold:#FFCE20;--gold-ink:#FFCE20;--win:#00B291;--win-ink:#4fd8bf;--out:#7c828d;--lose-ink:#f2757a;--g1:rgba(0,151,244,.22);--g2:rgba(0,178,145,.16);--g3:rgba(0,178,145,.16);}
html[data-theme="light"]{--bg:#EEF1F4;--panel:#FFF;--text:#323139;--text2:#323139;--muted:#6C6C6C;--border:rgba(0,0,0,.08);--border2:rgba(0,0,0,.14);
 --glass:linear-gradient(160deg,rgba(255,255,255,.85),rgba(255,255,255,.55));--shadow:0 10px 26px rgba(20,30,50,.10);--hover:rgba(0,0,0,.035);
 --gold:#E0A500;--gold-ink:#B57F00;--win:#00926f;--win-ink:#00805f;--out:#9aa0a8;--lose-ink:#C4353A;--g1:rgba(0,151,244,.14);--g2:rgba(0,178,145,.10);--g3:rgba(0,178,145,.10);}
html[data-theme="easy"]{--bg:#F6F1E6;--panel:#FCFAF3;--text:#2b2a30;--text2:#33323a;--muted:#55545c;--border:rgba(0,0,0,.08);--border2:rgba(0,0,0,.14);
 --glass:linear-gradient(160deg,rgba(255,255,255,.92),rgba(255,255,255,.66));--shadow:0 8px 22px rgba(40,40,30,.10);--hover:rgba(0,0,0,.03);
 --gold:#C98A00;--gold-ink:#8f6300;--win:#0a7d54;--win-ink:#0a6b49;--out:#8a8790;--lose-ink:#A63A2E;--g1:rgba(0,151,244,.10);--g2:rgba(0,178,145,.08);--g3:rgba(0,178,145,.08);
 --fs:18px;--lh:1.8;--ls:.03em;--radius:22px;--radius-sm:15px;--gap:22px;--fstack:"Verdana","Tahoma","Trebuchet MS","Segoe UI",system-ui,sans-serif;}
/* Fun · GeoCities — 90s web nostalgia: neon on midnight, rainbow headers, Comic Sans, ridge borders, tiled starfield */
html[data-theme="geocities"]{--bg:#000018;--panel:#1a0038;--text:#FFFF66;--text2:#7CFC00;--muted:#41E0E0;--border:#FF00FF;--border2:#00FFFF;
 --glass:linear-gradient(160deg,#2b005f,#12002f);--shadow:0 0 0 2px #00FFFF,0 6px 0 #FF00FF;--hover:rgba(255,0,255,.28);
 --gold:#FFD700;--gold-ink:#FFE94D;--win:#39FF14;--win-ink:#7CFC00;--out:#9aa0c8;--lose-ink:#FF3131;--g1:rgba(255,0,255,.28);--g2:rgba(0,255,255,.22);--g3:rgba(255,255,0,.18);
 --blue:#FF00FF;--purple:#00FFFF;--pink:#FFFF00;--orange:#FF7F00;--green:#39FF14;--teal:#00FFFF;
 --grad:linear-gradient(90deg,#FF0000,#FF7F00,#FFFF00,#00FF00,#00BFFF,#8B00FF);
 --radius:0;--radius-sm:0;--fs:16px;--lh:1.5;--ls:0em;--fstack:"Comic Sans MS","Comic Sans","Chalkboard SE","Marker Felt",cursive;}
/* Fun · Minecraft — blocky stone-and-grass: dark stone panels, white text with drop shadow, grass-green accents, sky-blue world, no rounded corners, pixelated */
html[data-theme="minecraft"]{--bg:#79A6FF;--panel:#565656;--text:#FFFFFF;--text2:#EDEDED;--muted:#C2C2C2;--border:#2b2b2b;--border2:#1d1d1d;
 --glass:linear-gradient(180deg,#6b6b6b,#4e4e4e);--shadow:inset -3px -3px 0 rgba(0,0,0,.45),inset 3px 3px 0 rgba(255,255,255,.16),0 4px 0 rgba(0,0,0,.35);--hover:rgba(255,255,255,.14);
 --gold:#FCDB05;--gold-ink:#FFE94D;--win:#5AAE3A;--win-ink:#8CE05A;--out:#8a8a8a;--lose-ink:#FF6B6B;--g1:rgba(0,0,0,0);--g2:rgba(0,0,0,0);--g3:rgba(0,0,0,0);
 --blue:#5AAE3A;--purple:#7B5B31;--pink:#C1440E;--orange:#D07B1E;--green:#5AAE3A;--teal:#4C7A34;--grad:linear-gradient(180deg,#6AA84F,#4C7A34);
 --radius:0;--radius-sm:0;--fs:15px;--lh:1.55;--ls:.02em;--fstack:ui-monospace,"Consolas","Lucida Console","Courier New",monospace;}
/* Fun · Windows XP — Luna blue, Bliss green-hills desktop, cream dialogs, rounded blue title bars, Tahoma */
html[data-theme="winxp"]{--bg:#5B9BD5;--panel:#ECE9D8;--text:#000000;--text2:#10161f;--muted:#404b56;--border:#7A96DF;--border2:#FFFFFF;
 --glass:#ECE9D8;--shadow:0 6px 18px rgba(10,36,106,.28);--hover:#D8E5F8;
 --gold:#2A5BDA;--gold-ink:#0A246A;--win:#3B9E1F;--win-ink:#2E7D18;--out:#8a94a0;--lose-ink:#C4262E;--g1:rgba(42,91,218,.10);--g2:rgba(59,158,31,.10);--g3:rgba(255,255,255,.10);
 --blue:#2A5BDA;--purple:#0A246A;--pink:#C4262E;--green:#3B9E1F;--teal:#245EDB;--grad:linear-gradient(180deg,#3D95FF,#0A3FC0);
 --radius:6px;--radius-sm:4px;--fs:15px;--lh:1.5;--ls:0em;--fstack:"Tahoma","Franklin Gothic","Segoe UI",sans-serif;}
/* Fun · Doodle — hand-drawn pencil sketch on paper: warm off-white paper with faint ruled lines and grain, graphite strokes, wobbly hand-drawn borders, handwriting font, grayscale (penciled) flags */
html[data-theme="doodle"]{--bg:#F4EFE1;--panel:#FBF7EC;--text:#333029;--text2:#4b473e;--muted:#8b857a;--border:#3a362f;--border2:#6f6a60;
 --glass:#FBF7EC;--shadow:2px 3px 0 rgba(58,54,47,.16);--hover:#efe7d3;
 --gold:#b1892f;--gold-ink:#8a6a20;--win:#5f7d40;--win-ink:#48602f;--out:#9a948a;--lose-ink:#a6453b;--g1:rgba(58,54,47,.05);--g2:rgba(58,54,47,.04);--g3:rgba(58,54,47,.03);
 --blue:#3b5a78;--purple:#5b4a6b;--pink:#a6453b;--orange:#b1732f;--green:#5f7d40;--teal:#3f6b64;--grad:linear-gradient(90deg,#4a463d,#6f6a60);
 --radius:14px;--radius-sm:10px;--fs:16px;--lh:1.55;--ls:.01em;--fstack:"Segoe Print","Bradley Hand","Comic Sans MS","Chalkboard SE",cursive;}
/* Fun · Hong Kong 1989 — neon-noir Kowloon nightscape: deep-midnight sky, glowing neon-sign colours (electric red, jade, cyan, gold), Chinese-friendly font and a 香港 · 1989 badge for nostalgia */
html[data-theme="hongkong"]{--bg:#0a0a14;--panel:#14121f;--text:#F6ECD8;--text2:#FFE3B3;--muted:#8a90b5;--border:#FF2D6B;--border2:#00E5FF;
 --glass:linear-gradient(160deg,rgba(40,10,42,.72),rgba(10,10,26,.86));--shadow:0 0 0 1px rgba(255,45,107,.45),0 0 22px rgba(255,45,107,.30),0 12px 34px rgba(0,0,0,.62);--hover:rgba(255,45,107,.16);
 --gold:#FFC531;--gold-ink:#FFD75E;--win:#00E5A0;--win-ink:#5affc7;--out:#6b7398;--lose-ink:#FF4D6D;--g1:rgba(255,45,107,.30);--g2:rgba(0,229,255,.22);--g3:rgba(255,197,49,.20);
 --blue:#00E5FF;--purple:#C77DFF;--pink:#FF2D6B;--orange:#FF7A1A;--green:#00E5A0;--teal:#00E5FF;
 --grad:linear-gradient(120deg,#FF2D6B,#FFC531,#00E5A0);
 --radius:14px;--radius-sm:10px;--fs:16px;--lh:1.55;--ls:.01em;--fstack:"PingFang HK","Hiragino Sans GB","Microsoft JhengHei","Noto Sans HK","Segoe UI",system-ui,sans-serif;}
/* Fun · BART Third Rail — SF BART traction-power control room for an electrician / electrical
   engineer: deep tunnel-dark with a faint blueprint grid, high-voltage hazard yellow, BART
   route-line accents (yellow/orange/red/green/blue), monospace schematic type, and a 1000V DC
   third-rail badge. */
html[data-theme="bart"]{--bg:#0B0F17;--panel:#131A24;--text:#EAF2FA;--text2:#CFE0EF;--muted:#8497A8;--border:#22303F;--border2:#FFD21E;
 --glass:linear-gradient(180deg,#131A24,#0E141D);--shadow:0 0 0 1px rgba(255,210,30,.12),0 10px 30px rgba(0,0,0,.55);--hover:rgba(255,210,30,.12);
 --gold:#FFD21E;--gold-ink:#FFDE5A;--win:#4DB748;--win-ink:#79E06E;--out:#7789a0;--lose-ink:#FF5A4D;--g1:rgba(255,210,30,.14);--g2:rgba(0,114,188,.16);--g3:rgba(229,0,43,.09);
 --blue:#2E9BE6;--purple:#7A5CFF;--pink:#E4002B;--orange:#F57F00;--green:#4DB748;--teal:#00B3C4;
 --grad:linear-gradient(90deg,#FFCF00,#F57F00,#E4002B,#4DB748,#0072BC);
 --radius:8px;--radius-sm:6px;--fs:15px;--lh:1.5;--ls:.01em;--fstack:ui-monospace,"SFMono-Regular","Consolas","Roboto Mono","Courier New",monospace;}
*{box-sizing:border-box}html,body{margin:0;padding:0}
html{scroll-behavior:smooth;scroll-padding-top:24px}
body{font-family:var(--fstack);font-size:var(--fs);line-height:var(--lh);letter-spacing:var(--ls);color:var(--text);background:var(--bg);-webkit-font-smoothing:antialiased;overflow-x:hidden;position:relative;min-height:100vh}
body::before{content:"";position:fixed;inset:-20% -10% auto -10%;height:70vh;z-index:0;pointer-events:none;background:radial-gradient(closest-side,var(--g1),transparent) -8% -12%/55% 90% no-repeat,radial-gradient(closest-side,var(--g2),transparent) 108% -8%/55% 85% no-repeat,radial-gradient(closest-side,var(--g3),transparent) 60% 120%/60% 80% no-repeat;filter:blur(6px)}
.wrap{max-width:1280px;margin:0 auto;padding:26px 22px 90px;position:relative;z-index:1}
.glass{background:var(--glass);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow)}
.topbar{display:flex;align-items:center;gap:14px;justify-content:space-between;margin-bottom:22px;flex-wrap:wrap}
.upd-group{display:inline-flex;align-items:center;gap:10px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:11px;font-weight:600}
.orb{width:30px;height:30px;border-radius:50%;background:var(--grad);box-shadow:0 0 16px rgba(0,151,244,.5);flex:0 0 auto}
.brand small{display:block;color:var(--muted);font-weight:500;font-size:.72rem;letter-spacing:.04em}
.modes{display:flex;gap:6px;padding:5px;border-radius:999px;position:relative;z-index:200}
.modes button{font-family:inherit;font-size:.82rem;font-weight:600;color:var(--muted);background:transparent;border:0;padding:7px 15px;border-radius:999px;cursor:pointer;transition:.16s}
.modes button:hover{color:var(--text);background:var(--hover)}
.modes button.on{color:#fff;background:var(--blue);box-shadow:0 4px 14px rgba(0,151,244,.4)}
.fun-wrap{position:relative;display:inline-flex}
.fun-btn{font-family:inherit;font-size:.82rem;font-weight:600;color:var(--muted);background:transparent;border:0;padding:7px 13px;border-radius:999px;cursor:pointer;transition:.16s;display:inline-flex;align-items:center;gap:5px}
.fun-btn:hover{color:var(--text);background:var(--hover)}
.fun-btn.on{color:#fff;background:var(--blue);box-shadow:0 4px 14px rgba(0,151,244,.4)}
.fun-car{font-size:.7em;transition:transform .16s}
.fun-wrap.open .fun-car{transform:rotate(180deg)}
.fun-menu{position:absolute;top:calc(100% + 8px);right:0;min-width:176px;display:none;flex-direction:column;gap:3px;padding:8px;border-radius:14px;z-index:60}
.fun-wrap.open .fun-menu{display:flex}
.fun-menu button{font-family:inherit;font-size:.9rem;font-weight:600;color:var(--text);background:transparent;border:0;padding:9px 12px;border-radius:10px;cursor:pointer;text-align:left;transition:.14s;white-space:nowrap;display:flex;align-items:center;gap:9px}
.fun-menu button:hover{background:var(--hover)}
.fun-menu button.on{background:var(--blue);color:#fff}
.fun-menu .fm-em{font-size:1.05em;line-height:1}
.refreshed{display:inline-flex;align-items:center;gap:8px;padding:7px 14px;border-radius:999px;font-size:.76rem;font-weight:600;color:var(--text2)}
.refreshed .rf-dot{width:8px;height:8px;border-radius:50%;background:var(--win);box-shadow:0 0 8px var(--win);flex:0 0 auto;animation:rfpulse 2.4s ease-in-out infinite}
@keyframes rfpulse{0%,100%{opacity:.45}50%{opacity:1}}
.synbtn{display:inline-flex;align-items:center;gap:7px;padding:7px 14px;border-radius:999px;font-family:inherit;font-size:.76rem;font-weight:700;color:var(--text);text-decoration:none;cursor:pointer;transition:.16s}
.synbtn:hover{background:var(--hover);transform:translateY(-1px)}
.synbtn:active{transform:translateY(0)}
.synbtn .syn-ic{display:inline-block;font-size:.92rem;line-height:1}
.shell{display:grid;grid-template-columns:186px minmax(0,1fr);gap:22px;align-items:start}
.content{min-width:0}
.rail{position:sticky;top:20px;max-height:calc(100vh - 40px);overflow:auto;padding:14px 12px;align-self:start;z-index:5}
.rail .rt{font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);padding:4px 10px 8px}
.rail .links{display:flex;flex-direction:column;gap:2px}
.rail a{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:10px;border-left:2px solid transparent;color:var(--muted);font-size:.82rem;font-weight:600;text-decoration:none;line-height:1.25;transition:color .14s,background .14s,border-color .14s}
.rail a .ic{font-size:.95rem;flex:0 0 auto;width:20px;text-align:center}
.rail a:hover{color:var(--text);background:var(--hover)}
.rail a:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.rail a.active{color:var(--text);background:var(--g2);border-left-color:var(--teal)}
.navtoggle{display:none}
@media(max-width:1200px){
 .shell{grid-template-columns:1fr;gap:0}
 .rail{position:static;max-height:none;overflow:visible;order:-1;margin-bottom:16px;padding:8px 10px}
 .rail .rt{display:none}
 .navtoggle{display:flex;align-items:center;justify-content:center;gap:10px;width:100%;font-family:inherit;font-size:.86rem;font-weight:700;color:var(--text);background:transparent;border:0;padding:11px;border-radius:12px;cursor:pointer}
 .rail .links{display:none;margin-top:6px}
 .rail.open .links{display:flex}
}
.hero{padding:34px 32px 30px;margin-bottom:var(--gap);position:relative;overflow:hidden}
.eyebrow{font-size:.74rem;font-weight:700;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}
.hero h1{font-size:clamp(2rem,5.4vw,3.5rem);line-height:1.05;margin:.34em 0 .28em;font-weight:700;letter-spacing:-.01em}
.hero h1 .g{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.hero p.sub{margin:0;color:var(--text2);max-width:64ch;font-size:1.02rem}
.hero .badges{display:flex;gap:9px;flex-wrap:wrap;margin-top:18px}
.pill{display:inline-flex;align-items:center;gap:7px;font-size:.78rem;font-weight:600;padding:6px 13px;border-radius:999px;border:1px solid var(--border);background:var(--panel);color:var(--text2)}
.pill .dot{width:8px;height:8px;border-radius:50%;background:var(--teal)}
.pill.live .dot{background:var(--green);animation:pulse 1.8s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(155,199,42,.6)}70%{box-shadow:0 0 0 8px rgba(155,199,42,0)}100%{box-shadow:0 0 0 0 rgba(155,199,42,0)}}
.composer{display:flex;align-items:center;gap:12px;margin-top:22px;padding:11px 12px 11px 16px;border-radius:999px;border:1px solid var(--border2);background:var(--panel);position:relative}
.composer::after{content:"";position:absolute;left:16px;right:16px;bottom:6px;height:2px;border-radius:2px;background:var(--grad);opacity:.55}
.composer .corb{width:22px;height:22px;border-radius:50%;background:var(--grad);flex:0 0 auto;box-shadow:0 0 12px rgba(203,133,255,.5)}
.composer .plus{color:var(--muted);font-size:1.1rem;font-weight:700}
.composer input{flex:1;border:0;outline:0;background:transparent;color:var(--text);font-family:inherit;font-size:1rem;min-width:0}
.composer input::placeholder{color:var(--muted)}
.composer .mic{color:var(--muted);font-size:1rem}
.composer .clr{font-family:inherit;font-weight:600;font-size:.8rem;color:var(--muted);background:var(--hover);border:1px solid var(--border);border-radius:999px;padding:6px 13px;cursor:pointer}
.filterbar{position:sticky;top:0;z-index:40;padding:13px 16px;margin-bottom:var(--gap);display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.chips{display:flex;gap:8px;overflow-x:auto;padding-bottom:2px;flex:1;scrollbar-width:thin}
.chip{flex:0 0 auto;display:inline-flex;align-items:center;gap:7px;font-family:inherit;font-size:.8rem;font-weight:600;color:var(--text2);background:var(--panel);border:1px solid var(--border);border-radius:999px;padding:6px 12px;cursor:pointer;transition:.16s;white-space:nowrap}
.chip:hover{border-color:var(--border2);transform:translateY(-1px)}
.chip.on{border-color:var(--blue);color:var(--text);box-shadow:inset 0 0 0 1px var(--blue)}
.chip.eliminated{opacity:.5}.chip.eliminated .ctxt{text-decoration:line-through}
.chip .cseed{font-size:.64rem;color:var(--muted);font-weight:700}
.chip .star{font-size:.95rem;line-height:1;color:var(--muted)}
.chip .star.fav{color:var(--gold-ink)}
.toggle{display:inline-flex;align-items:center;gap:9px;font-size:.8rem;font-weight:600;color:var(--muted);cursor:pointer;white-space:nowrap}
.toggle input{display:none}
.tsw{width:38px;height:22px;border-radius:999px;background:var(--hover);border:1px solid var(--border2);position:relative;transition:.18s}
.tsw::after{content:"";position:absolute;top:2px;left:2px;width:16px;height:16px;border-radius:50%;background:var(--muted);transition:.18s}
.toggle input:checked + .tsw{background:var(--blue);border-color:var(--blue)}
.toggle input:checked + .tsw::after{left:18px;background:#fff}
.count{font-size:.76rem;font-weight:600;color:var(--muted);white-space:nowrap}
.shead{display:flex;align-items:center;gap:12px;margin:30px 2px 15px}
.shead .tile{width:30px;height:30px;border-radius:9px;background:var(--grad);display:grid;place-items:center;font-size:.95rem;flex:0 0 auto;box-shadow:0 4px 14px rgba(0,151,244,.3)}
.shead h2{font-size:1.16rem;margin:0;font-weight:700;letter-spacing:-.01em}
.shead .cap{margin-left:auto;font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.09em;color:var(--muted)}
.sec-toggle{flex:0 0 auto;width:26px;height:26px;border-radius:8px;border:1px solid var(--border);background:var(--panel);color:var(--muted);cursor:pointer;font-size:.85rem;line-height:1;transition:.16s;display:grid;place-items:center}
.sec-toggle:hover{color:var(--text);background:var(--hover)}
.sec-toggle[aria-expanded="false"]{transform:rotate(-90deg)}
.sec-body{overflow:hidden}
.sec-body.collapsed{display:none}
.g2{display:grid;grid-template-columns:repeat(2,1fr);gap:var(--gap)}
.g3{display:grid;grid-template-columns:repeat(3,1fr);gap:var(--gap)}
.kpigrid{display:grid;grid-template-columns:repeat(6,1fr);gap:var(--gap)}
.kpi{padding:17px 17px 15px;position:relative;overflow:hidden;transition:.16s}
.kpi:hover{transform:translateY(-2px)}
.kpi-ic{font-size:1.05rem;position:absolute;top:14px;right:15px}
.kpi-l{font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--muted)}
.kpi-v{font-size:1.7rem;font-weight:750;margin:6px 0 2px;line-height:1.05;letter-spacing:-.01em}
.kpi-v .kunit{font-size:.72rem;font-weight:600;color:var(--muted);margin-left:5px}
.kpi-n{font-size:.76rem;color:var(--muted)}
.kpi::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;border-radius:3px}
.kpi.t-gold::before{background:var(--gold)}.kpi.t-gold .kpi-v{color:var(--gold-ink)}
.kpi.t-blue::before{background:var(--blue)}.kpi.t-teal::before{background:var(--teal)}
.kpi.t-purple::before{background:var(--purple)}.kpi.t-pink::before{background:var(--pink)}.kpi.t-green::before{background:var(--green)}
.kpi.t-red::before{background:var(--red)}.kpi.t-red .kpi-v{color:var(--lose-ink)}
.scorebar{display:flex;gap:22px;align-items:center;padding:18px 22px;margin-bottom:var(--gap);flex-wrap:wrap}
.sb-main{flex:1;min-width:220px}
.sb-big{font-size:2.2rem;font-weight:800;line-height:1;letter-spacing:-.02em;color:var(--win-ink)}
.sb-big .sb-slash{font-size:.9rem;font-weight:600;color:var(--muted);margin-left:6px}
.sb-cap{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin:4px 0 10px}
.sb-track{height:10px;border-radius:999px;background:var(--hover);border:1px solid var(--border);overflow:hidden}
.sb-track i{display:block;height:100%;background:var(--grad);border-radius:999px;transition:width .35s}
.sb-stats{display:grid;grid-template-columns:repeat(4,auto);gap:20px}
.sb-stat{text-align:center}.sb-stat b{display:block;font-size:1.5rem;font-weight:800;line-height:1}
.sb-stat span{font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}
.sb-stat.s-win b{color:var(--win-ink)}.sb-stat.s-live b{color:var(--blue)}.sb-stat.s-out b{color:var(--lose-ink)}.sb-stat.s-max b{color:var(--text)}
.brk-wrap{padding:8px;overflow:hidden}
.bracket{display:flex;gap:10px;overflow-x:auto;overflow-y:hidden;padding:14px 8px;align-items:stretch;scrollbar-width:none;-ms-overflow-style:none;position:relative}
.bracket::-webkit-scrollbar{display:none}
.bksvg{position:absolute;top:0;left:0;pointer-events:none;z-index:0;overflow:visible}
.brk-toggle,.res-toggle{display:inline-flex;gap:6px;padding:5px;border-radius:999px;margin-bottom:12px;background:var(--panel);border:1px solid var(--border)}
.brk-toggle button,.res-toggle button{font-family:inherit;font-size:.8rem;font-weight:600;color:var(--muted);background:transparent;border:0;padding:7px 16px;border-radius:999px;cursor:pointer;transition:.16s}
.brk-toggle button:hover,.res-toggle button:hover{color:var(--text);background:var(--hover)}
.brk-toggle button.on,.res-toggle button.on{color:#fff;background:var(--blue);box-shadow:0 4px 14px rgba(0,151,244,.35)}
.brk-wrap[data-view="actual"] .bracket.mode-picked{display:none}
.brk-wrap[data-view="picked"] .bracket.mode-actual{display:none}
.res-toggle{flex-wrap:wrap}
.res-wrap .res-panel{display:none}
.res-wrap[data-view="r32"] .res-panel[data-round="r32"]{display:block}
.res-wrap[data-view="r16"] .res-panel[data-round="r16"]{display:block}
.res-wrap[data-view="qf"] .res-panel[data-round="qf"]{display:block}
.res-wrap[data-view="sf"] .res-panel[data-round="sf"]{display:block}
.res-wrap[data-view="final"] .res-panel[data-round="final"]{display:block}
.round{flex:1 1 0;min-width:150px;display:flex;flex-direction:column;position:relative;z-index:1}
.conn{fill:none;stroke-width:2.5;stroke-linejoin:round;stroke-linecap:round}
.conn.c-won{stroke:var(--win)}
.conn.c-lost{stroke:var(--red)}
.conn.c-pending{stroke:var(--muted);opacity:.5;stroke-dasharray:5 5}
.conn.c-actual{stroke:var(--blue);opacity:.7;stroke-dasharray:2 4}
.conn.gone{opacity:.4}
.team.blank{visibility:hidden}
.team.st-actual{border-color:color-mix(in srgb,var(--blue) 45%,var(--border));opacity:.9}
.team.st-actual .tname{color:var(--muted)}
.team.st-actual .rb.up{color:var(--blue)}
.team.st-actual.gone{opacity:.62}
.team[data-team]{cursor:help}
.statcard{position:fixed;z-index:80;min-width:212px;max-width:250px;padding:13px 15px;border-radius:14px;
  background:var(--glass);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);border:1px solid var(--border2);
  box-shadow:var(--shadow);opacity:0;transform:translateY(4px);pointer-events:none;transition:opacity .12s,transform .12s}
.statcard.show{opacity:1;transform:translateY(0)}
.sc-name{font-weight:750;font-size:1rem;display:flex;align-items:center;gap:8px;margin-bottom:6px}
.sc-name .seed{font-size:.6rem;font-weight:700;color:var(--muted);background:var(--hover);border-radius:5px;padding:2px 5px}
.sc-row{display:flex;justify-content:space-between;gap:14px;align-items:baseline;padding:6px 0;border-top:1px solid var(--border)}
.sc-row .k{color:var(--muted);font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;flex:0 0 auto}
.sc-row .v{font-weight:600;font-size:.82rem;text-align:right}
.sc-row .v.gold{color:var(--gold-ink)}
.legend{display:flex;flex-wrap:wrap;gap:11px 20px;padding:14px 18px;margin-bottom:12px;align-items:center}
.legend .lg-cap{font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);width:100%;margin-bottom:2px}
.lg-item{display:flex;align-items:center;gap:8px;font-size:.78rem;color:var(--text2)}
.lg-box{width:22px;height:22px;border-radius:6px;border:1px solid var(--border2);display:grid;place-items:center;font-size:.7rem;font-weight:800;flex:0 0 auto;background:var(--panel)}
.lg-box.lg-won{border-color:color-mix(in srgb,var(--win) 55%,var(--border));color:var(--win-ink)}
.lg-box.lg-lost{border-color:color-mix(in srgb,var(--red) 50%,var(--border));color:var(--lose-ink)}
.lg-box.lg-actual{border-color:color-mix(in srgb,var(--blue) 50%,var(--border));color:var(--blue)}
.lg-box.lg-champ{border-color:var(--gold);color:var(--gold-ink)}
.lg-chev{color:var(--muted);font-weight:800;font-size:1.05rem;width:20px;text-align:center;flex:0 0 auto}
.lg-line{width:28px;height:0;flex:0 0 auto;border-top:3px solid var(--win);border-radius:3px}
.lg-line.lg-line-pend{border-top:3px dashed var(--muted);opacity:.75}
.lg-line.lg-line-actual{border-top:3px dashed var(--blue);opacity:.8}
.team.st-won{border-color:color-mix(in srgb,var(--win) 55%,var(--border));box-shadow:0 2px 10px rgba(0,178,145,.12)}
.team.st-won .tname{color:var(--win-ink)}
.team.st-won.gone{opacity:.55;box-shadow:none;border-color:var(--border)}
.team.st-won.gone .tname{color:var(--muted)}
.team.st-lost{border-color:var(--border);opacity:.55}
.team.st-lost .tname{color:var(--muted)}
.team.advancer .tname{font-weight:750}
.adv-arrow{color:var(--muted);font-weight:800;margin-left:2px;flex:0 0 auto}
.matches{flex:1;display:flex;flex-direction:column;justify-content:space-around}
.champcol .matches{justify-content:center}
.rhead{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);text-align:center;padding:4px 0 8px}
.rhead span{display:block;font-size:.6rem;font-weight:600;color:var(--muted);opacity:.8;text-transform:none;margin-top:2px}
.match{position:relative;height:132px;display:flex;flex-direction:column;justify-content:center}
.mlabel{font-size:.58rem;font-weight:700;color:var(--muted);opacity:.75;text-align:center}
.mlabel.up{opacity:.85;margin-bottom:3px;letter-spacing:.02em}
.mscore{font-size:.57rem;color:var(--text2);text-align:center;margin:1px 0 4px;font-weight:600}
.mscore.up{color:var(--muted);opacity:.8;font-weight:600;font-style:italic}
.team{position:relative;display:flex;align-items:center;gap:7px;padding:8px 10px;margin:3px 0;border-radius:10px;border:1px solid var(--border);background:var(--panel);font-size:.82rem;font-weight:600;transition:.16s}
.round:not(:first-child) .team::before{content:"";position:absolute;left:-7px;top:50%;width:7px;height:1px;background:var(--border2)}
.team .seed{font-size:.6rem;font-weight:700;color:var(--muted);background:var(--hover);border-radius:5px;padding:2px 5px;flex:0 0 auto}
.team .tname{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.team .tt{font-size:.9rem}
.team .rb{font-size:.72rem;font-weight:800;flex:0 0 auto}
.team .rb.ok{color:var(--win-ink)}.team .rb.no{color:var(--lose-ink)}.team .rb.up{color:var(--muted);opacity:.85}
.team .fav-bar{position:absolute;left:0;top:6px;bottom:6px;width:3px;border-radius:3px;background:transparent;transition:.16s}
.team.adv{border-color:color-mix(in srgb,var(--win) 55%,var(--border));box-shadow:0 2px 10px rgba(0,178,145,.14)}
.team.adv .tname{color:var(--win-ink)}
.team.realadv{border-color:var(--border2)}
.team.realadv .tname{color:var(--muted)}
.team.busted{border-color:var(--border);opacity:.55}
.team.busted .tname{color:var(--muted)}
.team.busted .rb.no,.team.st-lost .rb.no{color:var(--muted)}
.team.champ{border-color:var(--gold);background:color-mix(in srgb,var(--gold) 14%,var(--panel));box-shadow:0 0 20px rgba(255,206,32,.28)}
.team.champ .tname{color:var(--gold-ink);font-weight:750}
.team.out{opacity:.5}.team.out .tname{color:var(--out)}
.team.dead{opacity:.75}.team.dead .tname{text-decoration:line-through;color:var(--lose-ink)}
.team.fav .fav-bar{background:var(--blue)}
.team:hover{transform:translateY(-1px);border-color:var(--border2)}
.champcol .match{height:auto;display:flex;flex-direction:column;align-items:center;gap:10px}
.champcol .team.champ{width:100%}
.champ-note{font-size:.72rem;color:var(--muted);text-align:center;max-width:22ch;line-height:1.4}
.team.dim{opacity:.16!important;filter:saturate(.4)}
.scrow.dim,.ff.dim{opacity:.2}
.scard{display:flex;flex-direction:column;gap:2px;padding:8px}
.scrow{display:grid;grid-template-columns:64px 1fr 60px 116px;align-items:center;gap:12px;padding:10px 14px;border-radius:10px;transition:.14s;border-left:3px solid transparent}
.scrow:hover:not(.schead){background:var(--hover)}
.scrow.schead{font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);padding:8px 14px}
.scrow.is-won{border-left-color:var(--win)}.scrow.is-lost{border-left-color:var(--red)}
.scrow.is-won .win{color:var(--win-ink)}
.scrow.is-lost .win{text-decoration:line-through;color:var(--out)}
.rpill{display:inline-block;font-size:.64rem;font-weight:700;padding:3px 8px;border-radius:999px;border:1px solid var(--border2);color:var(--text2);background:var(--panel)}
.r-r32{border-color:color-mix(in srgb,var(--blue) 40%,var(--border))}
.r-r16{border-color:color-mix(in srgb,var(--teal) 40%,var(--border))}
.r-qf{border-color:color-mix(in srgb,var(--blue) 40%,var(--border))}
.r-sf{border-color:color-mix(in srgb,var(--teal) 45%,var(--border))}
.r-final{border-color:var(--gold);color:var(--gold-ink)}
.match-cell{display:flex;flex-direction:column;gap:1px}
.match-cell .win{font-weight:700;font-size:.92rem}
.match-cell .det{font-size:.74rem;color:var(--muted)}
.pts-cell{font-weight:750;font-size:1.02rem}.pts-cell .ptsu{font-size:.62rem;color:var(--muted);font-weight:600;margin-left:3px}
.seg{display:inline-flex;border:1px solid var(--border2);border-radius:999px;overflow:hidden;background:var(--panel)}
.seg button{font-family:inherit;font-weight:700;font-size:.9rem;border:0;background:transparent;color:var(--muted);width:34px;height:30px;cursor:pointer;transition:.14s}
.seg button:hover{background:var(--hover);color:var(--text)}
.seg button[data-set="won"].on{background:var(--win);color:#fff}
.seg button[data-set="lost"].on{background:var(--red);color:#fff}
.seg button[data-set="pending"].on{background:var(--muted);color:#fff}
.rrbox{padding:18px}
.rr-h{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:8px}
.rr{display:grid;grid-template-columns:44px 1fr 66px;align-items:center;gap:10px;padding:7px 6px;border-radius:8px}
.rr:hover{background:var(--hover)}
.rr.up{opacity:.72}
.rr-m{font-size:.66rem;font-weight:700;color:var(--muted)}
.rr-s{font-size:.86rem}.rr-s b.w{color:var(--win-ink);font-weight:750}.rr-s b.l{color:var(--out);font-weight:500;text-decoration:line-through}
.rr-s i{color:var(--muted);font-size:.72rem;font-style:normal}
.rr-p{text-align:right;font-size:.7rem;font-weight:700}
.res-ok{color:var(--win-ink)}.res-no{color:var(--lose-ink)}.res-soon{color:var(--muted);font-weight:600}
.ffgrid{display:grid;grid-template-columns:repeat(4,1fr);gap:var(--gap)}
.ff{padding:16px;border-radius:var(--radius-sm);border:1px solid var(--border);background:var(--panel);display:flex;flex-direction:column;gap:4px;transition:.16s;border-left:3px solid var(--blue)}
.ff:hover{transform:translateY(-2px)}
.ff.ff-champ{border-left-color:var(--gold);background:color-mix(in srgb,var(--gold) 8%,var(--panel))}
.ff.ff-run{border-left-color:var(--teal)}
.ff-seed{font-size:.62rem;font-weight:700;color:var(--muted)}
.ff-name{font-size:1.12rem;font-weight:750}.ff.ff-champ .ff-name{color:var(--gold-ink)}
.ff-role{font-size:.72rem;color:var(--muted);font-weight:600}
.ff-live{color:var(--win-ink);font-weight:700}.ff-dead{color:var(--lose-ink);font-weight:700}
.story{padding:18px;position:relative;overflow:hidden;transition:.16s}
.story:hover{transform:translateY(-2px)}
.story::after{content:"";position:absolute;right:-30px;bottom:-30px;width:110px;height:110px;border-radius:50%;background:var(--g2);filter:blur(10px);pointer-events:none}
.story-ic{font-size:1.5rem}.story-tag{font-size:.64rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-top:8px}
.story-title{font-size:1.02rem;font-weight:700;margin:3px 0 6px}
.story-when{font-size:.72rem;font-weight:700;color:var(--win-ink);margin:2px 0 7px;letter-spacing:.01em}
.story-body{font-size:.86rem;color:var(--text2);line-height:1.5;position:relative;z-index:1}
.stages{display:grid;grid-template-columns:repeat(6,1fr);gap:10px;padding:16px}
.stage{display:flex;align-items:center;gap:10px;padding:12px;border-radius:var(--radius-sm);border:1px solid var(--border);background:var(--panel)}
.stage .sdot{font-size:.9rem}.stage .sname{font-size:.82rem;font-weight:700}.stage .sdate{font-size:.68rem;color:var(--muted);margin-top:1px}
.stage.s-done{opacity:.72}.stage.s-done .sdot{color:var(--win-ink)}
.stage.s-active{border-color:var(--blue);box-shadow:inset 0 0 0 1px var(--blue)}.stage.s-active .sdot{color:var(--blue)}
.stage.s-up .sdot{color:var(--muted)}
.note{padding:14px 16px;border-radius:var(--radius-sm);border:1px solid var(--border);background:color-mix(in srgb,var(--blue) 6%,var(--panel));border-left:3px solid var(--blue);font-size:.84rem;color:var(--text2);line-height:1.55;margin-bottom:var(--gap)}
.note b{color:var(--text)}
.foot{margin-top:34px;padding:20px 22px;font-size:.78rem;color:var(--muted);line-height:1.6}
.foot b{color:var(--text2)}.foot .src{margin-top:8px}
.foot .credit{font-size:.66rem;opacity:.6;margin-top:10px;letter-spacing:.02em}
.dab{position:fixed;right:24px;bottom:24px;width:54px;height:54px;border-radius:50%;border:0;cursor:pointer;background:var(--grad);box-shadow:0 8px 24px rgba(0,151,244,.45);z-index:60;display:grid;place-items:center;font-size:1.3rem;color:#fff;transition:.18s}
.dab:hover{transform:translateY(-2px) scale(1.04)}
.dab::before{content:"";position:absolute;inset:-6px;border-radius:50%;background:var(--grad);filter:blur(14px);opacity:.5;z-index:-1}
.rr-t{display:block;font-size:.68rem;color:var(--muted);font-weight:600;margin-top:1px}
.ufbox{padding:8px 18px}
.uf{display:grid;grid-template-columns:44px 1fr 210px 132px;align-items:center;gap:10px;padding:10px 6px;border-bottom:1px solid var(--border)}
.uf:last-child{border-bottom:0}
.uf-m{font-size:.66rem;font-weight:700;color:var(--muted)}
.uf-x{font-size:.9rem;font-weight:600}.uf-x b{color:var(--win-ink)}
.uf-v{color:var(--muted);font-size:.72rem;font-weight:600;margin:0 5px}
.uf-t{font-size:.74rem;color:var(--text2);text-align:right}.uf-t span{display:block;font-size:.66rem;color:var(--muted);margin-top:1px}
.uf-p{text-align:right;font-size:.68rem;font-weight:700}.up-pick{color:var(--win-ink)}.up-out{color:var(--lose-ink)}
@media(max-width:560px){.uf{grid-template-columns:40px 1fr;row-gap:3px}.uf-t,.uf-p{grid-column:2;text-align:left}}
@media(max-width:1000px){.kpigrid{grid-template-columns:repeat(3,1fr)}.ffgrid{grid-template-columns:repeat(2,1fr)}.stages{grid-template-columns:repeat(3,1fr)}.g3{grid-template-columns:1fr}.g2{grid-template-columns:1fr}}
@media(max-width:560px){.wrap{padding:18px 13px 90px}.kpigrid{grid-template-columns:repeat(2,1fr)}.ffgrid{grid-template-columns:1fr}.stages{grid-template-columns:1fr}.filterbar{position:static}.hero{padding:24px 20px}.scrow{grid-template-columns:52px 1fr 104px}.scrow .pts-cell{display:none}.scrow.schead .tc:nth-child(3){display:none}.sb-stats{grid-template-columns:repeat(2,1fr);gap:12px}}
/* Keyboard focus + reduced motion (all modes) */
a:focus-visible,button:focus-visible,input:focus-visible,[tabindex]:focus-visible{outline:2px solid var(--blue);outline-offset:2px;border-radius:4px}
@media(prefers-reduced-motion:reduce){*{animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important;scroll-behavior:auto!important}}
/* Easy — high-legibility reading mode: sentence case, no italics, roomier, left-aligned prose, single calm background */
html[data-theme="easy"] body::before{display:none}
html[data-theme="easy"] body{word-spacing:.1em}
html[data-theme="easy"] .eyebrow,html[data-theme="easy"] .kpi-l,html[data-theme="easy"] .sb-cap,html[data-theme="easy"] .shead .cap,html[data-theme="easy"] .rr-h,html[data-theme="easy"] .story-tag,html[data-theme="easy"] .bb-cap,html[data-theme="easy"] .bb-tag,html[data-theme="easy"] .rhead,html[data-theme="easy"] .sb-stat span{text-transform:none;letter-spacing:.012em}
html[data-theme="easy"] .story-title,html[data-theme="easy"] .kpi-v,html[data-theme="easy"] .hero h1,html[data-theme="easy"] .sb-big,html[data-theme="easy"] .bb-big{letter-spacing:0}
html[data-theme="easy"] .mscore.up,html[data-theme="easy"] .rr-s i,html[data-theme="easy"] em,html[data-theme="easy"] i{font-style:normal}
html[data-theme="easy"] .pill.live .dot{animation:none}
html[data-theme="easy"] .g3{grid-template-columns:repeat(2,1fr)}
html[data-theme="easy"] .hero p.sub,html[data-theme="easy"] .note,html[data-theme="easy"] .story-body,html[data-theme="easy"] .bb-txt,html[data-theme="easy"] .foot,html[data-theme="easy"] .kpi-n{max-width:66ch;text-align:left}
@media(max-width:1000px){html[data-theme="easy"] .g3{grid-template-columns:1fr}}
/* ---- Fun · GeoCities look ---- */
html[data-theme="geocities"] body::before{display:none}
html[data-theme="geocities"] body{background-color:#000018;background-image:radial-gradient(1.5px 1.5px at 18% 22%,#fff,transparent),radial-gradient(1.5px 1.5px at 72% 38%,#fff,transparent),radial-gradient(1px 1px at 42% 72%,#FFFF66,transparent),radial-gradient(1.5px 1.5px at 88% 82%,#00FFFF,transparent),radial-gradient(1px 1px at 8% 88%,#FF66FF,transparent),repeating-linear-gradient(0deg,transparent 0 44px,rgba(255,255,255,.035) 44px 45px),repeating-linear-gradient(90deg,transparent 0 44px,rgba(255,255,255,.035) 44px 45px)}
html[data-theme="geocities"] .glass{backdrop-filter:none;-webkit-backdrop-filter:none;border:3px ridge #FF00FF}
html[data-theme="geocities"] h1,html[data-theme="geocities"] h2,html[data-theme="geocities"] .story-title,html[data-theme="geocities"] .hero h1{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent;-webkit-text-fill-color:transparent;text-shadow:none;font-weight:800}
html[data-theme="geocities"] a{color:#00FFFF;text-decoration:underline}
html[data-theme="geocities"] a:visited{color:#FF66FF}
html[data-theme="geocities"] .modes,html[data-theme="geocities"] .fun-menu{border:2px ridge #00FFFF}
html[data-theme="geocities"] .modes button,html[data-theme="geocities"] .fun-btn,html[data-theme="geocities"] .chip,html[data-theme="geocities"] .seg button{border:3px outset #FF00FF;background:#2b005f;color:#FFFF66}
html[data-theme="geocities"] .modes button.on,html[data-theme="geocities"] .fun-btn.on,html[data-theme="geocities"] .fun-menu button.on{background:#FF00FF;color:#000;border-style:inset}
html[data-theme="geocities"] .team{border:2px ridge #00FFFF}
html[data-theme="geocities"] .pill.live .dot,html[data-theme="geocities"] .rf-dot,html[data-theme="geocities"] .orb{animation:gc-blink 1.1s steps(1) infinite}
@keyframes gc-blink{50%{opacity:.25}}
/* ---- Fun · Minecraft look ---- */
html[data-theme="minecraft"] *{image-rendering:pixelated;border-radius:0 !important}
html[data-theme="minecraft"] body::before{display:none}
html[data-theme="minecraft"] body{background-color:#79A6FF;background-image:repeating-linear-gradient(0deg,rgba(0,0,0,.05) 0 24px,rgba(255,255,255,.05) 24px 48px),repeating-linear-gradient(90deg,rgba(0,0,0,.04) 0 24px,rgba(255,255,255,.04) 24px 48px)}
html[data-theme="minecraft"] .glass{backdrop-filter:none;-webkit-backdrop-filter:none;border:3px solid #2b2b2b}
html[data-theme="minecraft"] h1,html[data-theme="minecraft"] h2,html[data-theme="minecraft"] .story-title,html[data-theme="minecraft"] .hero h1,html[data-theme="minecraft"] .tname,html[data-theme="minecraft"] .kpi-v,html[data-theme="minecraft"] .sb-big{text-shadow:2px 2px 0 rgba(0,0,0,.55)}
html[data-theme="minecraft"] .modes button,html[data-theme="minecraft"] .fun-btn,html[data-theme="minecraft"] .chip,html[data-theme="minecraft"] .seg button{border:2px solid #1d1d1d;background:linear-gradient(180deg,#7c7c7c,#616161);color:#fff;box-shadow:inset -2px -2px 0 rgba(0,0,0,.4),inset 2px 2px 0 rgba(255,255,255,.15)}
html[data-theme="minecraft"] .modes button.on,html[data-theme="minecraft"] .fun-btn.on,html[data-theme="minecraft"] .fun-menu button.on{background:linear-gradient(180deg,#6AA84F,#4C7A34);color:#fff}
html[data-theme="minecraft"] .team{border:2px solid #2b2b2b}
html[data-theme="minecraft"] .orb{background:linear-gradient(180deg,#6AA84F,#4C7A34);box-shadow:inset -2px -2px 0 rgba(0,0,0,.4)}
/* ---- Fun · Windows XP look ---- */
html[data-theme="winxp"] body::before{display:none}
html[data-theme="winxp"] body{background:linear-gradient(180deg,#4d8fd6 0%,#6aa8e0 34%,#8fc36a 46%,#6bab4e 62%,#4f9440 100%)}
html[data-theme="winxp"] .glass{background:#ECE9D8;backdrop-filter:none;-webkit-backdrop-filter:none;border:1px solid #0A246A;border-radius:8px 8px 6px 6px;box-shadow:0 6px 18px rgba(10,36,106,.28)}
html[data-theme="winxp"] .modes,html[data-theme="winxp"] .fun-menu{border:1px solid #0A246A}
html[data-theme="winxp"] .modes button,html[data-theme="winxp"] .fun-btn,html[data-theme="winxp"] .chip,html[data-theme="winxp"] .seg button{background:linear-gradient(180deg,#FDFDFD,#E4E4D8);color:#000;border:1px solid #7A96DF;border-radius:4px}
html[data-theme="winxp"] .modes button:hover,html[data-theme="winxp"] .fun-btn:hover{border-color:#2A5BDA;color:#000}
html[data-theme="winxp"] .modes button.on,html[data-theme="winxp"] .fun-btn.on,html[data-theme="winxp"] .fun-menu button.on{background:linear-gradient(180deg,#3D95FF,#0A3FC0);color:#FFF;border-color:#0A246A}
html[data-theme="winxp"] .shead h2,html[data-theme="winxp"] .hero h1,html[data-theme="winxp"] .story-title{background:linear-gradient(180deg,#2F8AF0,#0A3FC0);color:#FFF;padding:3px 10px;border-radius:6px 6px 0 0;display:inline-block;text-shadow:0 1px 1px rgba(0,0,0,.35)}
html[data-theme="winxp"] a{color:#0A3FC0}
html[data-theme="winxp"] .team{background:#FFFFFF;color:#000;border:1px solid #7A96DF;border-radius:4px}
/* Fun · Doodle decorative — paper texture (faint ruled lines + red margin + grain), wobbly hand-drawn borders, wavy underlines, grayscale flags */
html[data-theme="doodle"] body::before{display:none}
html[data-theme="doodle"] body{background-color:#F4EFE1;background-image:repeating-linear-gradient(0deg,transparent 0 27px,rgba(90,120,160,.10) 27px 28px),linear-gradient(90deg,transparent 46px,rgba(200,90,80,.20) 46px 47px,transparent 48px),radial-gradient(circle at 18% 26%,rgba(0,0,0,.022),transparent 55%),radial-gradient(circle at 82% 72%,rgba(0,0,0,.022),transparent 55%)}
html[data-theme="doodle"] *{text-shadow:none}
html[data-theme="doodle"] .glass{background:var(--panel);backdrop-filter:none;-webkit-backdrop-filter:none;border:2px solid var(--border);border-radius:255px 12px 225px 15px/15px 225px 18px 255px;box-shadow:2px 2px 0 rgba(58,54,47,.14),-1px 1px 0 rgba(58,54,47,.10)}
html[data-theme="doodle"] .card,html[data-theme="doodle"] .team,html[data-theme="doodle"] .chip,html[data-theme="doodle"] .modes button,html[data-theme="doodle"] .fun-btn,html[data-theme="doodle"] .seg button,html[data-theme="doodle"] .pill{border:2px solid var(--border);border-radius:225px 15px 235px 15px/15px 235px 15px 225px;background:var(--panel)}
html[data-theme="doodle"] .modes button.on,html[data-theme="doodle"] .fun-btn.on,html[data-theme="doodle"] .fun-menu button.on,html[data-theme="doodle"] .seg button.on{background:#e9e0cc;color:var(--text);box-shadow:inset 1px 1px 0 rgba(58,54,47,.22)}
html[data-theme="doodle"] h1,html[data-theme="doodle"] h2,html[data-theme="doodle"] .story-title,html[data-theme="doodle"] .hero h1{background:none;color:var(--text);-webkit-text-fill-color:currentColor;text-shadow:none;text-decoration:underline wavy rgba(58,54,47,.5);text-underline-offset:6px}
html[data-theme="doodle"] a{color:#3b5a78;text-decoration:underline wavy}
html[data-theme="doodle"] img,html[data-theme="doodle"] .flag{filter:grayscale(1) contrast(1.15) brightness(.98)}
html[data-theme="doodle"] .orb,html[data-theme="doodle"] .pill.live .dot,html[data-theme="doodle"] .rf-dot{filter:grayscale(1)}
/* ---- Fun · Hong Kong 1989 look — neon-noir Kowloon night, glowing signage, bilingual 香港 badge ---- */
html[data-theme="hongkong"] body::before{display:none}
html[data-theme="hongkong"] body{background-color:#0a0a14;background-image:radial-gradient(circle at 12% 16%,rgba(255,45,107,.22),transparent 40%),radial-gradient(circle at 86% 24%,rgba(0,229,255,.16),transparent 42%),radial-gradient(circle at 70% 82%,rgba(255,197,49,.14),transparent 44%),radial-gradient(circle at 24% 80%,rgba(0,229,160,.14),transparent 44%),repeating-linear-gradient(90deg,transparent 0 40px,rgba(255,255,255,.02) 40px 41px)}
html[data-theme="hongkong"] .glass{backdrop-filter:blur(9px);-webkit-backdrop-filter:blur(9px);border:1px solid rgba(255,45,107,.5)}
html[data-theme="hongkong"] h1,html[data-theme="hongkong"] h2,html[data-theme="hongkong"] .story-title,html[data-theme="hongkong"] .hero h1,html[data-theme="hongkong"] .shead h2{background:none;color:#fff;-webkit-text-fill-color:#fff;text-shadow:0 0 3px #fff,0 0 9px #FF2D6B,0 0 20px #FF2D6B,0 0 40px rgba(255,45,107,.65);font-weight:800;letter-spacing:.02em}
html[data-theme="hongkong"] .eyebrow{color:#00E5FF;text-shadow:0 0 6px rgba(0,229,255,.85)}
html[data-theme="hongkong"] a{color:#00E5FF;text-shadow:0 0 6px rgba(0,229,255,.7)}
html[data-theme="hongkong"] .modes button,html[data-theme="hongkong"] .fun-btn,html[data-theme="hongkong"] .chip,html[data-theme="hongkong"] .seg button{border:1px solid rgba(0,229,255,.35);background:rgba(255,255,255,.03);color:var(--text)}
html[data-theme="hongkong"] .modes button.on,html[data-theme="hongkong"] .fun-btn.on,html[data-theme="hongkong"] .fun-menu button.on,html[data-theme="hongkong"] .seg button.on{background:#FF2D6B;color:#0a0a14;border-color:#FF2D6B;box-shadow:0 0 12px rgba(255,45,107,.8)}
html[data-theme="hongkong"] .team{border:1px solid rgba(0,229,255,.30)}
html[data-theme="hongkong"] .orb{background:var(--grad);box-shadow:0 0 10px #FF2D6B,0 0 22px rgba(255,45,107,.55)}
html[data-theme="hongkong"] .pill.live .dot,html[data-theme="hongkong"] .rf-dot{box-shadow:0 0 8px currentColor,0 0 16px rgba(0,229,160,.6)}
html[data-theme="hongkong"] .brand>div{position:relative}
html[data-theme="hongkong"] .brand>div::after{content:"香港 · 1989 · HONG KONG";display:block;margin-top:3px;font-size:.7rem;font-weight:800;letter-spacing:.14em;color:#FF2D6B;text-shadow:0 0 6px rgba(255,45,107,.9),0 0 14px rgba(255,45,107,.55)}
html[data-theme="bart"] body::before{display:none}
html[data-theme="bart"] body{background-color:#0B0F17;background-image:linear-gradient(rgba(255,210,30,.035) 1px,transparent 1px),linear-gradient(90deg,rgba(46,155,230,.05) 1px,transparent 1px),radial-gradient(circle at 84% 6%,rgba(255,210,30,.12),transparent 40%),radial-gradient(circle at 10% 92%,rgba(0,114,188,.14),transparent 44%);background-size:28px 28px,28px 28px,auto,auto}
html[data-theme="bart"] .glass{background:linear-gradient(180deg,#131A24,#0E141D);backdrop-filter:none;-webkit-backdrop-filter:none;border:1px solid rgba(255,210,30,.22)}
html[data-theme="bart"] .hero{border-top:4px solid transparent;border-image:repeating-linear-gradient(45deg,#FFD21E 0 14px,#0B0F17 14px 28px) 4}
html[data-theme="bart"] h1,html[data-theme="bart"] h2,html[data-theme="bart"] h3,html[data-theme="bart"] .story-title,html[data-theme="bart"] .shead h2{background:none;color:#FFD21E;-webkit-text-fill-color:#FFD21E;text-shadow:0 0 8px rgba(255,210,30,.4);letter-spacing:.02em}
html[data-theme="bart"] .eyebrow,html[data-theme="bart"] .kicker{color:#2E9BE6;text-shadow:0 0 6px rgba(46,155,230,.55);text-transform:uppercase;letter-spacing:.16em}
html[data-theme="bart"] a{color:#2E9BE6}
html[data-theme="bart"] .modes button,html[data-theme="bart"] .fun-btn,html[data-theme="bart"] .chip,html[data-theme="bart"] .seg button,html[data-theme="bart"] .fun-menu button{border:1px solid rgba(255,210,30,.30);background:rgba(255,255,255,.03);color:var(--text)}
html[data-theme="bart"] .modes button.on,html[data-theme="bart"] .fun-btn.on,html[data-theme="bart"] .fun-menu button.on,html[data-theme="bart"] .seg button.on{background:#FFD21E;color:#0B0F17;border-color:#FFD21E;box-shadow:0 0 12px rgba(255,210,30,.65)}
html[data-theme="bart"] .team{border:1px solid rgba(46,155,230,.28)}
html[data-theme="bart"] .orb{background:var(--grad);box-shadow:0 0 10px rgba(255,210,30,.75),0 0 22px rgba(46,155,230,.45)}
html[data-theme="bart"] .brand>div{position:relative}
html[data-theme="bart"] .brand>div::after{content:"⚡ 1000 V DC · THIRD RAIL · SFBART";display:inline-block;margin-top:4px;font-size:.63rem;font-weight:800;letter-spacing:.14em;color:#FFD21E;background:rgba(255,210,30,.08);border:1px solid rgba(255,210,30,.45);border-left:5px solid #FFD21E;padding:2px 9px;border-radius:3px;text-shadow:0 0 6px rgba(255,210,30,.45)}
"""

JS=r"""
(function(){
 var root=document.documentElement,LS=window.localStorage;
 var KTHEME='wcb.theme',KFAV='wcb.favs',KFO='wcb.favonly',KSC='wcb.scores.v3';
 function setTheme(t){root.setAttribute('data-theme',t);document.querySelectorAll('.modes button').forEach(function(b){if(b.dataset.mode)b.classList.toggle('on',b.dataset.mode===t)});if(funBtn)funBtn.classList.toggle('on',!!FUN[t]);try{LS.setItem(KTHEME,t)}catch(e){}closeFun();if(window.__drawConn)setTimeout(window.__drawConn,80);}
 var FUN={geocities:1,minecraft:1,winxp:1,doodle:1,hongkong:1,bart:1};
 var funWrap=document.getElementById('funWrap'),funBtn=document.getElementById('funBtn');
 function closeFun(){if(funWrap){funWrap.classList.remove('open');if(funBtn)funBtn.setAttribute('aria-expanded','false');}}
 document.querySelectorAll('.modes button').forEach(function(b){if(b.dataset.mode)b.addEventListener('click',function(){setTheme(b.dataset.mode)})});
 if(funBtn){funBtn.addEventListener('click',function(e){e.stopPropagation();var open=funWrap.classList.toggle('open');funBtn.setAttribute('aria-expanded',open?'true':'false');});}
 document.addEventListener('click',function(e){if(funWrap&&!funWrap.contains(e.target))closeFun();});
 document.addEventListener('keydown',function(e){if(e.key==='Escape')closeFun();});
 var t0;try{t0=LS.getItem(KTHEME)}catch(e){}setTheme(t0||'dark');
 var favs={};try{favs=JSON.parse(LS.getItem(KFAV)||'{}')||{}}catch(e){favs={}}
 function saveFav(){try{LS.setItem(KFAV,JSON.stringify(favs))}catch(e){}}
 function isFav(t){return !!favs[t]}
 var search=document.getElementById('search'),favOnly=document.getElementById('favonly'),countEl=document.getElementById('count');
 var chips=[].slice.call(document.querySelectorAll('.chip'));
 var teamCells=[].slice.call(document.querySelectorAll('.team[data-team]'));
 var ffCells=[].slice.call(document.querySelectorAll('.ff[data-team]'));
 var scRows=[].slice.call(document.querySelectorAll('.scrow[data-team]'));
 var allTeams={};teamCells.forEach(function(c){allTeams[c.dataset.team]=1});var TOTAL=Object.keys(allTeams).length;
 function paintFav(){document.querySelectorAll('.star').forEach(function(s){s.classList.toggle('fav',isFav(s.dataset.star));s.textContent=isFav(s.dataset.star)?'★':'☆';});teamCells.forEach(function(c){c.classList.toggle('fav',isFav(c.dataset.team))});}
 function apply(){var q=(search.value||'').trim().toLowerCase(),fo=favOnly.checked,shown={};
  function ok(t){if(fo&&!isFav(t))return false;if(q&&t.toLowerCase().indexOf(q)===-1)return false;return true;}
  teamCells.forEach(function(c){var g=ok(c.dataset.team);c.classList.toggle('dim',!g);if(g)shown[c.dataset.team]=1;});
  ffCells.forEach(function(c){c.classList.toggle('dim',!ok(c.dataset.team))});
  scRows.forEach(function(r){r.classList.toggle('dim',!r.dataset.team.split('|').some(ok))});
  chips.forEach(function(ch){ch.classList.toggle('on',q&&ch.dataset.team.toLowerCase()===q)});
  countEl.textContent='Showing '+((q||fo)?Object.keys(shown).length:TOTAL)+' of '+TOTAL+' teams';}
 search.addEventListener('input',apply);
 favOnly.addEventListener('change',function(){try{LS.setItem(KFO,favOnly.checked?'1':'0')}catch(e){}apply();});
 chips.forEach(function(ch){ch.addEventListener('click',function(e){if(e.target.classList.contains('star'))return;var t=ch.dataset.team;search.value=(search.value.trim().toLowerCase()===t.toLowerCase())?'':t;apply();});});
 document.querySelectorAll('.star').forEach(function(s){function tg(ev){ev.stopPropagation();var t=s.dataset.star;favs[t]=!isFav(t);if(!favs[t])delete favs[t];saveFav();paintFav();apply();}s.addEventListener('click',tg);s.addEventListener('keydown',function(ev){if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();tg(ev);}});});
 document.getElementById('clear').addEventListener('click',function(){search.value='';favOnly.checked=false;try{LS.setItem(KFO,'0')}catch(e){}apply();});
 document.getElementById('dab').addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'})});
 try{if(LS.getItem(KFO)==='1')favOnly.checked=true;}catch(e){}
 var scores={};try{scores=JSON.parse(LS.getItem(KSC)||'{}')||{}}catch(e){scores={}}
 var rows=[].slice.call(document.querySelectorAll('.scrow[data-pick]'));
 function statusOf(r){return scores[r.dataset.pick]||r.dataset.default;}
 function saveScores(){try{LS.setItem(KSC,JSON.stringify(scores))}catch(e){}}
 function recalc(){var conf=0,live=0,out=0,MAXP=parseInt(document.getElementById('scMax').dataset.max||'80',10);
  rows.forEach(function(r){var st=statusOf(r),pts=+r.dataset.pts;
   r.classList.toggle('is-won',st==='won');r.classList.toggle('is-lost',st==='lost');
   r.querySelectorAll('.seg button').forEach(function(b){b.classList.toggle('on',b.dataset.set===st)});
   if(st==='won')conf+=pts;else if(st==='lost')out+=pts;else live+=pts;});
  function set(id,v){var el=document.getElementById(id);if(el)el.textContent=v;}
  set('scConfirmed',conf);set('scConfirmed2',conf);set('scLive',live);set('scOut',out);set('scMax',conf+live);set('scSoFar',conf+'/'+(conf+out));
  set('kpiConfirmed',conf);set('kpiLive',live);
  var bar=document.getElementById('scBar');if(bar)bar.style.width=Math.round(conf/MAXP*100)+'%';}
 rows.forEach(function(r){r.querySelectorAll('.seg button').forEach(function(b){b.addEventListener('click',function(){var id=r.dataset.pick,s=b.dataset.set;if(s===r.dataset.default)delete scores[id];else scores[id]=s;saveScores();recalc();});});});
 var rst=document.getElementById('scReset');if(rst)rst.addEventListener('click',function(){scores={};saveScores();recalc();});
 // ---- bracket connector lines (elbow paths, coloured by whether each pick came true) ----
 function activeBracket(){var w=document.querySelector('.brk-wrap');if(!w)return document.querySelector('.bracket');return w.querySelector('.bracket.mode-'+(w.getAttribute('data-view')||'actual'));}
 function drawConnectors(){
   var bracket=activeBracket();if(!bracket)return;
   var svg=bracket.querySelector('.bksvg');
   if(!bracket||!svg) return;
   var brect=bracket.getBoundingClientRect(),W=bracket.scrollWidth,Hh=bracket.scrollHeight;
   svg.setAttribute('width',W);svg.setAttribute('height',Hh);svg.setAttribute('viewBox','0 0 '+W+' '+Hh);
   while(svg.firstChild)svg.removeChild(svg.firstChild);
   function P(el){var r=el.getBoundingClientRect();return{r:r.right-brect.left+bracket.scrollLeft,l:r.left-brect.left+bracket.scrollLeft,y:(r.top+r.bottom)/2-brect.top+bracket.scrollTop};}
   var rounds=[].slice.call(bracket.querySelectorAll('.round'));
   // Link each still-advancing team's box to the same team's box in the previous round.
   for(var ri=1;ri<rounds.length;ri++){
     var targets=[].slice.call(rounds[ri].querySelectorAll('.team[data-team]'));
     targets.forEach(function(tb){
       var team=tb.getAttribute('data-team');
       var src=rounds[ri-1].querySelector('.team[data-team="'+team+'"]');
       if(!src) return;
       var a=P(src),b=P(tb),x1=a.r+1,x2=b.l-1,xm=Math.round((x1+x2)/2);
       var d='M'+Math.round(x1)+' '+Math.round(a.y)+' H'+xm+' V'+Math.round(b.y)+' H'+Math.round(x2);
       var st=tb.classList.contains('st-won')?'won':tb.classList.contains('st-lost')?'lost':tb.classList.contains('st-actual')?'actual':'pending';
       var gone=tb.classList.contains('gone');
       var p=document.createElementNS('http://www.w3.org/2000/svg','path');
       p.setAttribute('d',d);p.setAttribute('class','conn c-'+st+(gone?' gone':''));svg.appendChild(p);
     });
   }
 }
 window.__drawConn=drawConnectors;
 document.querySelectorAll('.brk-toggle button').forEach(function(bt){bt.addEventListener('click',function(){var w=document.querySelector('.brk-wrap');w.setAttribute('data-view',bt.dataset.view);document.querySelectorAll('.brk-toggle button').forEach(function(x){x.classList.toggle('on',x===bt);});setTimeout(drawConnectors,60);});});
 document.querySelectorAll('.res-toggle button').forEach(function(bt){bt.addEventListener('click',function(){var w=document.querySelector('.res-wrap');w.setAttribute('data-view',bt.dataset.view);document.querySelectorAll('.res-toggle button').forEach(function(x){x.classList.toggle('on',x===bt);});});});
 document.querySelectorAll('.sec-toggle').forEach(function(bt){bt.addEventListener('click',function(){var body=document.getElementById(bt.getAttribute('aria-controls'));if(!body)return;var open=bt.getAttribute('aria-expanded')!=='false';bt.setAttribute('aria-expanded',open?'false':'true');body.classList.toggle('collapsed',open);});});
 var _rt;window.addEventListener('resize',function(){clearTimeout(_rt);_rt=setTimeout(drawConnectors,120);});
 window.addEventListener('load',function(){setTimeout(drawConnectors,60);});
 // ---- hover: quick World Cup stat card on each team box ----
 var card=document.getElementById('statcard');
 function posCard(ev){var pad=14,w=card.offsetWidth,h=card.offsetHeight,x=ev.clientX+16,y=ev.clientY+16;
   if(x+w>window.innerWidth-pad)x=ev.clientX-w-16; if(x<pad)x=pad;
   if(y+h>window.innerHeight-pad)y=window.innerHeight-h-pad; if(y<pad)y=pad;
   card.style.left=x+'px'; card.style.top=y+'px';}
 function showCard(el,ev){var t=el.getAttribute('data-team'),s=window.WCSTATS&&window.WCSTATS[t]; if(!s||!card)return;
   card.innerHTML='<div class="sc-name"><span class="seed">'+(s.s||'')+'</span>'+t+'</div>'
     +'<div class="sc-row"><span class="k">World Cup titles</span><span class="v gold">'+(s.t?('🏆 '+s.t):'—')+'</span></div>'
     +'<div class="sc-row"><span class="k">Best finish</span><span class="v">'+s.b+'</span></div>'
     +'<div class="sc-row"><span class="k">This World Cup</span><span class="v">'+s.y+'</span></div>';
   posCard(ev); card.classList.add('show');}
 document.querySelectorAll('.team[data-team]').forEach(function(el){
   el.addEventListener('mouseenter',function(ev){showCard(el,ev)});
   el.addEventListener('mousemove',posCard);
   el.addEventListener('mouseleave',function(){card.classList.remove('show')});});
 paintFav();apply();recalc();drawConnectors();
 // ── side-nav rail: mobile toggle + scrollspy ──
 var rail=document.getElementById('rail'),navToggle=document.getElementById('navToggle');
 if(navToggle&&rail){navToggle.addEventListener('click',function(){var o=rail.classList.toggle('open');navToggle.setAttribute('aria-expanded',o?'true':'false');});}
 var railLinks=rail?rail.querySelectorAll('.links a'):[];
 if(railLinks.length){
   var linkFor={};
   railLinks.forEach(function(a){linkFor[a.getAttribute('href').slice(1)]=a;a.addEventListener('click',function(){rail.classList.remove('open');if(navToggle)navToggle.setAttribute('aria-expanded','false');});});
   var secs=document.querySelectorAll('#intro, .shead[id]');
   var spy=new IntersectionObserver(function(entries){entries.forEach(function(e){if(e.isIntersecting){railLinks.forEach(function(l){l.classList.remove('active');});var a=linkFor[e.target.id];if(a)a.classList.add('active');}});},{rootMargin:'-45% 0px -50% 0px',threshold:0});
   secs.forEach(function(s){spy.observe(s);});
 }
})();
"""

def chip(t):
    el = ' eliminated' if t in ELIM else ''
    return (f'<button class="chip{el}" data-team="{esc(t)}"><span class="star" data-star="{esc(t)}" role="button" aria-label="favorite" tabindex="0">☆</span>'
            f'<span class="cseed">{esc(seed_of(t))}</span><span class="ctxt">{esc(t)}</span></button>')

def shead(sid, icon, title, cap):
    """Section header + the opening tag of its collapsible body. Every collapsible
    section is shead(...) + <content> + '</div>' (closing div.sec-body) — the toggle
    arrow just shows/hides that one wrapper via CSS/JS, nothing else changes."""
    return (f'<div class="shead" id="{sid}">'
            f'<button class="sec-toggle" type="button" aria-expanded="true" aria-controls="{sid}-body" aria-label="Collapse section">▾</button>'
            f'<span class="tile">{icon}</span><h2>{title}</h2>'
            f'<span class="cap">{cap}</span></div>'
            f'<div class="sec-body" id="{sid}-body">')

HTML=('<!DOCTYPE html><html lang="en" data-theme="dark"><head><meta charset="utf-8">'
+f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(ENTRANT)}’s World Cup 2026 Bracket</title>'
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
+'<style>'+CSS+'</style></head><body><div class="wrap">'
+'<div class="topbar"><div class="brand"><span class="orb"></span><div>2026 FIFA World Cup - Bracket Dashboard - MSFT SLED<small>Live results vs your picks</small></div></div>'
+'<div class="upd-group">'
+f'<div class="refreshed glass" id="topRefreshed" title="When live results were last synced"><span class="rf-dot"></span>Updated {REFRESHED}</div>'
+(f'<a class="synbtn glass" id="syncBtn" href="{esc(SYNC_URL)}" target="_blank" rel="noopener" '
  'title="Pull the latest results: opens the sync workflow on GitHub — tap Run workflow, and the dashboard updates in about 1-2 minutes.">'
  '<span class="syn-ic">🔄</span><span class="syn-tx">Sync now</span></a>' if SYNC_URL else '')
+'</div>'
+'<div class="modes glass"><button data-mode="dark" class="on">Dark</button><button data-mode="light">Light</button>'
+'<button data-mode="easy" title="Reading mode — a highly legible font, larger text, extra line and letter spacing, sentence case (no all-caps), left-aligned text and a soft, glare-free background">Easy</button>'
+'<div class="fun-wrap" id="funWrap"><button class="fun-btn" id="funBtn" aria-haspopup="true" aria-expanded="false" title="Fun themes">Fun <span class="fun-car">▾</span></button>'
+'<div class="fun-menu glass" id="funMenu" role="menu">'
+'<button data-mode="geocities" role="menuitem" title="90s web nostalgia — neon, rainbow headers, Comic Sans, tiled starfield"><span class="fm-em">🌐</span> GeoCities</button>'
+'<button data-mode="minecraft" role="menuitem" title="Blocky stone-and-grass — pixelated panels, drop-shadow text, sky-blue world"><span class="fm-em">⛏️</span> Minecraft</button>'
+'<button data-mode="winxp" role="menuitem" title="Windows XP — Luna blue, Bliss green-hills desktop, cream dialogs, rounded blue title bars, Tahoma"><span class="fm-em">🪟</span> Windows XP</button>'
+'<button data-mode="doodle" role="menuitem" title="Hand-drawn pencil sketch — warm paper with faint ruled lines, graphite wobbly borders, handwriting font, grayscale flags"><span class="fm-em">✏️</span> Doodle</button>'
+'<button data-mode="hongkong" role="menuitem" title="Hong Kong 1989 — neon-noir Kowloon nightscape, glowing neon-sign colours, bilingual 香港 · 1989 badge"><span class="fm-em">🌃</span> Hong Kong 1989</button>'
+'<button data-mode="bart" role="menuitem" title="BART Third Rail — SF BART traction-power control room: tunnel-dark blueprint grid, high-voltage hazard yellow, BART route-line accents, monospace schematic type and a 1000V DC third-rail badge"><span class="fm-em">⚡</span> BART · Third Rail</button>'
+'</div></div></div></div>'
+'<div class="shell"><nav class="rail glass" id="rail">'
+'<button class="navtoggle" id="navToggle" aria-expanded="false" aria-controls="railLinks">📑 Contents ☰</button>'
+'<div class="links" id="railLinks"><div class="rt">On this page</div>'
+'<a href="#intro"><span class="ic">🔎</span> Overview</a>'
+'<a href="#sec-standing"><span class="ic">📊</span> Live standing</a>'
+'<a href="#sec-scorecard"><span class="ic">🧮</span> Scorecard</a>'
+'<a href="#sec-r32"><span class="ic">⚽</span> Round-by-round results</a>'
+'<a href="#sec-news"><span class="ic">📰</span> Game facts</a>'
+'<a href="#sec-bracket"><span class="ic">🗺️</span> Bracket map</a>'
+'<a href="#sec-finalfour"><span class="ic">🏅</span> Final four</a>'
+'<a href="#sec-story"><span class="ic">✨</span> How it played out</a>'
+'<a href="#sec-scoring"><span class="ic">🎯</span> Scoring &amp; schedule</a>'
+'</div></nav><div class="content">'
+f'<section class="hero glass" id="intro"><div class="eyebrow">{esc(ENTRANT)} · live results vs your picks</div>'
+f'<h1>Backing <span class="g">{esc(CHAMP)}</span> {"— and still in it" if CHAMP_ALIVE else "— but knocked out"}</h1>'
+f'<p class="sub">The <b>{esc(CUR_LABEL)}</b> is <b>{CUR_DONE} of {CUR_TOTAL} final</b> — you\'re <b>{CUR_CORR} of {CUR_DEC} right</b> this round, '
+f'with <b>{CONF} points</b> banked and <b>{LIVE}</b> still live. Your champion {esc(CHAMP)} is <b>{CHAMP_STATUS}</b>.'
+ (f' The {esc(NEXT_LABEL)} is up next.' if NEXT_LABEL else '') + '</p>'
+'<div class="badges">'
+f'<span class="pill live"><span class="dot"></span>{CONF} pts confirmed</span>'
+f'<span class="pill"><span class="dot"></span>{esc(_ROUND_TAGS.get(CURRENT_ROUND,CUR_LABEL))} {CUR_CORR}/{CUR_DEC}</span>'
+f'<span class="pill"><span class="dot"></span>Max attainable {ATTAIN}</span>'
+f'<span class="pill"><span class="dot"></span>{esc(CHAMP)} {"alive" if CHAMP_ALIVE else "out"}</span></div>'
+'<div class="composer"><span class="corb"></span><span class="plus">+</span>'
+'<input id="search" type="text" placeholder="Track a team through the bracket — try England, Morocco, Paraguay…" autocomplete="off">'
+'<span class="mic">🎤</span><button class="clr" id="clear">Clear</button></div></section>'
+'<div class="filterbar glass"><div class="chips">'+''.join(chip(t) for t in r32_win)+
'</div><label class="toggle"><input type="checkbox" id="favonly"><span class="tsw"></span>Favorites only</label><span class="count" id="count"></span></div>'
+shead("sec-standing","📊","Your live standing","6 signals")
+f'<div class="kpigrid">{build_kpis()}</div>'
+'</div>'
+shead("sec-scorecard","🧮","Scorecard — your path, scored live",f"{CONF} confirmed · {LIVE} live")
+'<div class="note"><b>How this is scored.</b> Results are pulled from live web coverage (ESPN, CBS Sports, FIFA) and matched to your Excel picks. '
+f'The <b>{esc(CUR_LABEL)}</b> stands at <b>{CUR_DONE} of {CUR_TOTAL}</b> — you sit on <b>{CONF} points</b> ({CUR_CORR}/{CUR_DEC} right this round). '
+f'{esc(LIVE_STATUS)} Later rounds stay <b>pending</b> until they’re played. '
+'Flip any row yourself as games finish — totals recompute and save on this device.</div>'
+ build_scorebar()
+ f'<div class="glass">{build_scorecard()}</div>'
+ '<div style="text-align:right;margin-top:10px"><button class="chip" id="scReset" style="cursor:pointer">↺ Reset to live results</button></div>'
+ '</div>'
+ shead("sec-r32","⚽","Round-by-round results",CUR_SUBTITLE)
+ '<div class="res-toggle">'
+f'<button data-view="r32" class="{"on" if CURRENT_ROUND=="r32" else ""}">Round of 32</button>'
+''.join(f'<button data-view="{short}" class="{"on" if short==CURRENT_ROUND else ""}">{esc(label)}</button>' for (label,short,codes) in KO_ROUND_ORDER)
+'</div>'
+f'<div class="res-wrap" data-view="{CURRENT_ROUND}">{build_results_panel()}'
+''.join(build_round_results_panel(label,short,codes) for (label,short,codes) in KO_ROUND_ORDER)
+'</div>'
+ '</div>'
+ shead("sec-news","📰","Game facts — recent games","newest first")
+ f'<div class="g3">{build_highlights()}</div>'
+ '</div>'
+ shead("sec-bracket","🗺️","Your bracket, marked up","✓ hit · ✕ miss · ▲ who went through")
+ f'{build_legend()}'
+'<div class="brk-toggle"><button data-view="actual" class="on">Actual path</button><button data-view="picked">My picks</button></div>'
+f'<div class="glass brk-wrap" data-view="actual">{build_bracket("actual")}{build_bracket("picked")}</div>'
+ '</div>'
+ shead("sec-finalfour","🏅","Your final four",f'{FF_ALIVE}/{len(QF_WIN)} still alive')
+ f'<div class="ffgrid">{build_finalfour()}</div>'
+ '</div>'
+ shead("sec-story","✨","How it played out","so far")
+ f'<div class="g3">{build_story()}</div>'
+ '</div>'
+ shead("sec-scoring","🎯","Scoring &amp; schedule","80 max")
+ '<div class="g2"><div class="glass" style="padding:20px"><div style="font-weight:700;margin-bottom:12px">Points double every round</div>'
+'<div class="scard" style="padding:0">'
+'<div class="scrow schead" style="grid-template-columns:1fr 70px 70px 70px"><div class="tc">Round</div><div class="tc">Games</div><div class="tc">Pts/pick</div><div class="tc">Max</div></div>'
+'<div class="scrow" style="grid-template-columns:1fr 70px 70px 70px"><div class="tc">Round of 32</div><div class="tc">16</div><div class="tc">1</div><div class="tc">16</div></div>'
+'<div class="scrow" style="grid-template-columns:1fr 70px 70px 70px"><div class="tc">Round of 16</div><div class="tc">8</div><div class="tc">2</div><div class="tc">16</div></div>'
+'<div class="scrow" style="grid-template-columns:1fr 70px 70px 70px"><div class="tc">Quarterfinals</div><div class="tc">4</div><div class="tc">4</div><div class="tc">16</div></div>'
+'<div class="scrow" style="grid-template-columns:1fr 70px 70px 70px"><div class="tc">Semifinals</div><div class="tc">2</div><div class="tc">8</div><div class="tc">16</div></div>'
+'<div class="scrow" style="grid-template-columns:1fr 70px 70px 70px"><div class="tc"><b>Final (Champion)</b></div><div class="tc">1</div><div class="tc">16</div><div class="tc">16</div></div>'
+'<div class="scrow" style="grid-template-columns:1fr 70px 70px 70px;border-top:1px solid var(--border)"><div class="tc"><b>Total</b></div><div class="tc">31</div><div class="tc"></div><div class="tc"><b>80</b></div></div>'
+'</div><div style="font-size:.8rem;color:var(--muted);margin-top:12px;line-height:1.5">Each pick scored on its own; Champion is worth a full 16. '
+'Tiebreaker: total goals in the Final at the end of extra time — penalties don’t count. Your tiebreaker: <b>4</b>.</div></div>'
+'<div class="glass" style="padding:20px"><div style="font-weight:700;margin-bottom:4px">Where the tournament stands</div>'
+f'<div style="font-size:.8rem;color:var(--muted);margin-bottom:8px">Live results as of {REFRESHED}</div>'
+f'<div class="stages" style="grid-template-columns:1fr;padding:0;gap:8px">{build_stages()}</div></div></div>'
+ '</div>'
+'<div class="glass foot"><b>Sources.</b> Your picks, scoring, tiebreaker and any host bonus rule from your <b>SLED World Cup 2026 bracket workbook</b> and the challenge instructions. '
'Match results, scores and kickoff times from <b>FIFA official match records</b> (fifa.com), corroborated by NBC Sports, CBS Sports, ESPN and Sporting News, for the 2026 FIFA World Cup. Kickoff times anchored to ET, converted to CT/PT. Hover-card country pedigree (titles, best finish) from public FIFA World Cup historical records.'
f'<div class="src"><b>Status.</b> {esc(LIVE_STATUS)} '
f'You have <b>{CONF} points</b> confirmed, <b>{LIVE}</b> live, max attainable <b>{ATTAIN}</b>. '
f'This is your personal, <b>unofficial</b> tally for Rob to review — his scoring is authoritative. Champion {esc(CHAMP)} · runner-up {esc(RUNNER)}.</div>'
f'<div class="src">Live results as of <b>{REFRESHED}</b> · reading mode, favorites and any manual score edits are saved on this device.</div>'
'<div class="src">🏆 Thank you to <b>Rob Brautigam</b> for hosting the 2026 FIFA World Cup bracket challenge for SLED.</div>'
+ (f'<div class="src credit">{esc(CREDIT)}</div>' if CREDIT else '') + '</div>'
'</div></div></div><button class="dab" id="dab" title="Back to top" aria-label="Back to top">↑</button>'
'<div class="statcard" id="statcard" aria-hidden="true"></div>'
'<script>'+STATS_JS+'</script>'
'<script>'+JS+'</script></body></html>')

import os
_docs=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),'docs')
os.makedirs(_docs,exist_ok=True)
out=os.path.join(_docs,'index.html')
open(out,'w',encoding='utf-8').write(HTML)
print("WROTE",out,len(HTML),"chars")
print("Confirmed",CONF,"Live",LIVE,"Out",OUT,"Attainable",ATTAIN,"R32",str(r32_correct)+"/"+str(r32_decided))
print("Eliminated teams:",sorted(ELIM))

