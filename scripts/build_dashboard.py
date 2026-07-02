# -*- coding: utf-8 -*-
"""World Cup 2026 bracket-challenge dashboard -> one self-contained HTML file.
Picks / scoring / tiebreaker come from the entrant's own 'My Bracket' Excel tab.
Live match results & kickoff times come from a verified web lookup (FIFA official + majors).
No results are invented; undecided matches are shown as pending."""
import html, json, re

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
ENTRANT="Eric Lam"; TIEBREAKER=4
REFRESHED="July 2, 2026 · 11:40 AM PT"
CREDIT="Built with Cowork"  # tiny footer signature (personalise per entrant)

SEED={"Germany":"1E","Paraguay":"3rd","France":"1I","Sweden":"3rd","South Africa":"2A","Canada":"2B",
 "Netherlands":"1F","Morocco":"2C","Portugal":"2K","Croatia":"2L","Spain":"1H","Austria":"2J",
 "United States":"1D","Bosnia & Herz.":"3rd","Belgium":"1G","Senegal":"3rd","Brazil":"1C","Japan":"2F",
 "Ivory Coast":"2E","Norway":"2I","Mexico":"1A","Ecuador":"3rd","England":"1L","DR Congo":"3rd",
 "Argentina":"1J","Cape Verde":"2H","Australia":"2D","Egypt":"2G","Switzerland":"1B","Algeria":"3rd",
 "Colombia":"1K","Ghana":"3rd"}

# (matchcode, date, teamA, teamB, the entrant's pick)
R32=[("M74","Mon 6/29","Germany","Paraguay","Germany"),
 ("M77","Tue 6/30","France","Sweden","France"),
 ("M73","Sun 6/28","South Africa","Canada","Canada"),
 ("M75","Mon 6/29","Netherlands","Morocco","Morocco"),
 ("M83","Thu 7/2","Portugal","Croatia","Portugal"),
 ("M84","Thu 7/2","Spain","Austria","Spain"),
 ("M81","Wed 7/1","United States","Bosnia & Herz.","United States"),
 ("M82","Wed 7/1","Belgium","Senegal","Belgium"),
 ("M76","Mon 6/29","Brazil","Japan","Japan"),
 ("M78","Tue 6/30","Ivory Coast","Norway","Norway"),
 ("M79","Tue 6/30","Mexico","Ecuador","Mexico"),
 ("M80","Wed 7/1","England","DR Congo","England"),
 ("M86","Fri 7/3","Argentina","Cape Verde","Argentina"),
 ("M88","Fri 7/3","Australia","Egypt","Australia"),
 ("M85","Thu 7/2","Switzerland","Algeria","Switzerland"),
 ("M87","Fri 7/3","Colombia","Ghana","Colombia")]
FREEBIE_MATCH="M73"

# LIVE RESULTS (teamA goals, teamB goals, winner, note) — only completed matches
RES={"M73":(0,1,"Canada",""),
 "M74":(4,5,"Paraguay",""),
 "M75":(3,4,"Morocco",""),
 "M76":(2,1,"Brazil",""),
 "M77":(3,0,"France",""),
 "M78":(1,2,"Norway",""),
 "M79":(2,0,"Mexico",""),
 "M80":(2,1,"England",""),
 "M81":(2,0,"United States",""),
 "M82":(3,2,"Belgium","")}
UPCOMING={"M83":"Thu Jul 2","M84":"Thu Jul 2","M85":"Thu Jul 2","M86":"Fri Jul 3","M87":"Fri Jul 3","M88":"Fri Jul 3"}

R16_WIN=["France","Morocco","Spain","United States","Japan","England","Argentina","Colombia"]
QF_WIN=["France","Spain","England","Argentina"]; SF_WIN=["France","England"]
CHAMP="England"; RUNNER="France"

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
def reach_status(team, short):
    """Did this team actually reach (win into) the round this column represents?"""
    if team in ELIM: return "lost"
    if short=="r16": return "won" if team in R32_ACTUAL_WINNERS else "pending"
    return "pending"  # later rounds not played yet

def pick_status(short, team, mc=None):
    if short=="r32":
        if mc in RES: return "won" if team==RES[mc][2] else "lost"
        return "pending"
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
assert CONF+OUT+LIVE==POINTS_MAX, (CONF,OUT,LIVE)

# Rob's OPTIONAL upset bonus: +2 for correctly picking a group runner-up (2X) or 3rd-place team to win in R32
def bonus_eligible(team):
    sd=SEED.get(team,"")
    return sd=="3rd" or (len(sd)==2 and sd[0]=="2")
BONUS_CONF=0; BONUS_POT=0; bonus_won=[]; bonus_pend=[]
for (mc,dt,a,b,pk) in R32:
    if bonus_eligible(pk):
        s=pick_status("r32",pk,mc)
        if s=="won": BONUS_CONF+=2; bonus_won.append(f"{pk} ({SEED.get(pk,'')})")
        elif s=="pending": BONUS_POT+=2; bonus_pend.append(f"{pk} ({SEED.get(pk,'')})")
ADJ=CONF+BONUS_CONF
# ---- derived copy (computed from data — NO scenario text hardcoded) ----
N_R32=len(R32); R32_DONE=sum(1 for m in R32 if m[0] in RES); REMAIN_R32=N_R32-R32_DONE
CHAMP_ALIVE = CHAMP not in ELIM
CHAMP_STATUS = "still alive" if CHAMP_ALIVE else "out"
BUSTED=[m[4] for m in R32 if m[0] in RES and m[4] in ELIM]
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
R16_PICK={"M89":"France","M90":"Morocco","M91":"Japan","M92":"England","M93":"Spain","M94":"United States","M95":"Argentina","M96":"Colombia"}

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
    badge='<span class="rb ok">✓</span>' if st=="won" else ('<span class="rb no">✕</span>' if st=="lost" else '')
    tag='<span class="tt">🏆</span>' if champ else ''
    chev='<span class="adv-arrow" title="you have this team advancing">›</span>' if (picked and not champ) else ''
    sd=seed_of(team); sh=f'<span class="seed">{esc(sd)}</span>' if sd else ''
    return (f'<div class="{" ".join(cls)}" data-team="{esc(team)}" data-round="{short}" tabindex="0">'
            f'<span class="fav-bar"></span>{sh}<span class="tname">{esc(team)}</span>{tag}{badge}{chev}</div>')

def later_cell(team, picked, short, champ=False, actual=None, mode="actual"):
    if mode=="picked":
        # Your bracket as you filled it — every pick trails forward, coloured by result.
        return _pick_box(team, picked, short, champ, reach_status(team, short))
    # Actual mode: prune eliminated picks; carry the real advancer up (blue) where known.
    if team in ELIM:
        if actual and actual not in ELIM:
            sd=seed_of(actual); sh=f'<span class="seed">{esc(sd)}</span>' if sd else ''
            return (f'<div class="team st-actual" data-team="{esc(actual)}" data-round="{short}" tabindex="0">'
                    f'<span class="fav-bar"></span>{sh}<span class="tname">{esc(actual)}</span>'
                    f'<span class="rb up" title="actually advanced — you picked '+esc(team)+'">▲</span></div>')
        return '<div class="team blank"><span class="tname">&nbsp;</span></div>'
    return _pick_box(team, picked, short, champ, reach_status(team, short))

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
    for label,short,sub,ms in meta:
        cc=[]
        for (a,b,w) in ms:
            isf=(label=="Final")
            aa=r32_pick_actual.get(a) if short=="r16" else None
            ab=r32_pick_actual.get(b) if short=="r16" else None
            cc.append('<div class="match">'+later_cell(a,w==a,short,champ=(isf and w==a),actual=aa,mode=mode)+later_cell(b,w==b,short,champ=(isf and w==b),actual=ab,mode=mode)+'</div>')
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
        if bonus_eligible(pk): detail+=' <span class="ubtag">+2 upset</span>'
        rows.append(scrow(pid,"r32",1,pk,detail,st,a,b))
    for (label,short,pts,ms) in rounds[1:]:
        for i,(a,b,w) in enumerate(ms):
            st=pick_status(short,w); pid=f"{short}-{i}"
            if st=="lost": detail="out — eliminated in the Round of 32"
            else:
                nxt={"r16":"to reach the quarterfinals","qf":"to reach the semifinals","sf":"to reach the Final","final":"to lift the trophy"}[short]
                detail=nxt
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
      '<div class="sb-cap">points confirmed</div>'
      f'<div class="sb-track"><i id="scBar" style="width:{int(CONF/POINTS_MAX*100)}%"></i></div></div>'
      '<div class="sb-stats">'
      f'<div class="sb-stat s-win"><b id="scConfirmed2">{CONF}</b><span>confirmed</span></div>'
      f'<div class="sb-stat s-live"><b id="scLive">{LIVE}</b><span>still live</span></div>'
      f'<div class="sb-stat s-out"><b id="scOut">{OUT}</b><span>eliminated</span></div>'
      f'<div class="sb-stat s-max"><b id="scMax" data-max="{POINTS_MAX}">{ATTAIN}</b><span>still attainable</span></div>'
      '</div></div>')

KPIS=[
 ("Confirmed points", f"<span id='kpiConfirmed'>{CONF}</span><span class='kunit'>/ {POINTS_MAX}</span>","✅","teal",f"{r32_correct} of {r32_decided} R32 picks right"),
 ("Round of 32", f"{r32_correct}<span class='kunit'>/ {r32_decided}</span>","⚽","blue",f"{REMAIN_R32} games left"),
 ("Still live", f"<span id='kpiLive'>{LIVE}</span>","⚡","blue","across your open picks"),
 ("Max attainable", f"{ATTAIN}","🎯","green","if your path holds"),
 ("Champion pick", CHAMP,"🏆","gold",CHAMP_STATUS),
 ("Points lost", f"{OUT}","🚫","red",BUSTED_NOTE),
]
def build_kpis():
    return ''.join(f'<div class="glass kpi t-{t}"><div class="kpi-ic">{ic}</div>'
        f'<div class="kpi-l">{esc(l)}</div><div class="kpi-v">{v}</div><div class="kpi-n">{esc(n)}</div></div>'
        for l,v,ic,t,n in KPIS)

def build_finalfour():
    out=[]
    for tm in QF_WIN:
        role="Champion" if tm==CHAMP else ("Runner-up" if tm==RUNNER else "Semifinalist")
        alive = tm not in ELIM
        state = ("won R32" if tm in [RES[m][2] for m in RES] else "R32 Jul 2–3")
        cls="ff-champ" if tm==CHAMP else ("ff-run" if tm==RUNNER else "")
        dot = '<span class="ff-live">● alive</span>' if alive else '<span class="ff-dead">✕ out</span>'
        out.append(f'<div class="ff {cls}" data-team="{esc(tm)}"><span class="ff-seed">{esc(seed_of(tm))}</span>'
                   f'<span class="ff-name">{esc(tm)}</span><span class="ff-role">{role} · {dot}</span></div>')
    return ''.join(out)

STORY=[
 ("✅","Holding strong",f"{r32_correct} of {r32_decided} in the Round of 32",
  "Canada, Morocco, France, Norway, Mexico, England, USA and Belgium all delivered. Only two of your opened games missed."),
 ("🇵🇾","Busted branch #1","Germany fell to Paraguay",
  "Your 1E pick crashed out on penalties (1–1, 4–3). You had France beating Germany in the R16 anyway, so France just meets Paraguay instead — your France pick lives."),
 ("🇧🇷","Busted branch #2","Brazil ended Japan",
  "Your boldest call didn’t land — Martinelli’s 95th-minute winner sent Japan out 2–1. That also voids your Japan Round-of-16 pick (2 pts)."),
]
def build_story():
    return ''.join(f'<div class="glass story"><div class="story-ic">{ic}</div>'
        f'<div class="story-tag">{esc(tag)}</div><div class="story-title">{esc(ti)}</div>'
        f'<div class="story-body">{esc(bd)}</div></div>' for ic,tag,ti,bd in STORY)

STAGES=[("Group stage","Ended Jun 27","done"),("Round of 32","Jun 28–Jul 3 · 10/16","active"),
 ("Round of 16","Jul 4–7","up"),("Quarterfinals","Jul 9–11","up"),
 ("Semifinals","Jul 14–15","up"),("Final","Sun Jul 19 · MetLife","up")]
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
    return ('<div class="glass rrbox"><div class="rr-h">Final results · your pick '
            f'<b>{r32_correct}/{r32_decided}</b></div>'+''.join(rows)+
            '<div class="rr-h" style="margin-top:12px">Still to play</div>'+''.join(up)+'</div>')

# ── USER DATA (game facts) — replace with a few verified storylines from the live FIFA lookup:
#    (emoji, tag, headline, "date · time played", one-sentence body). Everything else stays verbatim.
HIGHLIGHTS=[
 ("⏱️","Latest goal in WC history","Belgium 3–2 Senegal","Wed, Jul 1 · 4:00 PM ET (1:00 PM PT)",
  "Two down with five minutes left, Belgium roared back through Lukaku and Tielemans — whose winning penalty at 124:44 is the latest goal ever recorded at a World Cup."),
 ("🥅","Two giants out on penalties","Germany & Netherlands gone","Mon, Jun 29 · 4:30 PM & 9:00 PM ET",
  "Germany fell to Paraguay (1–1, 4–3) and the Netherlands to Morocco (1–1, 3–2) — both European heavyweights knocked out in Round-of-32 shootouts."),
 ("⚡","Stoppage-time stunner","Brazil 2–1 Japan","Mon, Jun 29 · 1:00 PM ET (10:00 AM PT)",
  "Japan led through Kaishu Sano before Casemiro levelled and substitute Gabriel Martinelli curled in a 95th-minute winner — Brazil's deepest scare in years."),
 ("👟","Mbappé & Haaland deliver","France roll, Norway make history","Tue, Jun 30 · 5:00 PM & 1:00 PM ET",
  "Kylian Mbappé scored twice in France's 3–0 win over Sweden, while Erling Haaland's goal earned Norway a 2–1 win over Ivory Coast — their first World Cup knockout win ever."),
 ("🦁","Kane rescues England","England 2–1 DR Congo","Wed, Jul 1 · Atlanta",
  "Trailing at the break, Harry Kane scored twice in the second half to drag the Three Lions through."),
 ("🍁","History for the hosts","Canada 1–0 South Africa","Sun, Jun 28 · 3:00 PM ET (12:00 PM PT)",
  "Stephen Eustáquio's strike gave co-hosts Canada their first knockout-round win in World Cup history — the freebie everyone was credited with."),
]
def build_highlights():
    return ''.join(f'<div class="glass story"><div class="story-ic">{ic}</div>'
        f'<div class="story-tag">{esc(tag)}</div><div class="story-title">{esc(ti)}</div>'
        f'<div class="story-when">📅 {esc(wh)}</div>'
        f'<div class="story-body">{esc(bd)}</div></div>' for ic,tag,ti,wh,bd in HIGHLIGHTS)

def build_upcoming():
    rows=[]
    for (mc,day,a,b,et,ct,ptz) in R16_FIX:
        pk=R16_PICK.get(mc); dead=(pk in ELIM) if pk else False
        def nm(t): return f'<b>{esc(t)}</b>' if (pk and t==pk) else esc(t)
        if dead: tag='<span class="up-out">your pick out (Japan)</span>'
        elif pk: tag=f'<span class="up-pick">your pick: {esc(pk)}</span>'
        else: tag=''
        rows.append(f'<div class="uf"><div class="uf-m">{esc(mc)}</div>'
            f'<div class="uf-x">{nm(a)}<span class="uf-v">vs</span>{nm(b)}</div>'
            f'<div class="uf-t">{esc(day)}<span>{ptz} PT · {ct} CT · {et} ET</span></div>'
            f'<div class="uf-p">{tag}</div></div>')
    return '<div class="glass ufbox">'+''.join(rows)+'</div>'

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
*{box-sizing:border-box}html,body{margin:0;padding:0}
body{font-family:var(--fstack);font-size:var(--fs);line-height:var(--lh);letter-spacing:var(--ls);color:var(--text);background:var(--bg);-webkit-font-smoothing:antialiased;overflow-x:hidden;position:relative;min-height:100vh}
body::before{content:"";position:fixed;inset:-20% -10% auto -10%;height:70vh;z-index:0;pointer-events:none;background:radial-gradient(closest-side,var(--g1),transparent) -8% -12%/55% 90% no-repeat,radial-gradient(closest-side,var(--g2),transparent) 108% -8%/55% 85% no-repeat,radial-gradient(closest-side,var(--g3),transparent) 60% 120%/60% 80% no-repeat;filter:blur(6px)}
.wrap{max-width:1280px;margin:0 auto;padding:26px 22px 90px;position:relative;z-index:1}
.glass{background:var(--glass);backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow)}
.topbar{display:flex;align-items:center;gap:14px;justify-content:space-between;margin-bottom:22px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:11px;font-weight:600}
.orb{width:30px;height:30px;border-radius:50%;background:var(--grad);box-shadow:0 0 16px rgba(0,151,244,.5);flex:0 0 auto}
.brand small{display:block;color:var(--muted);font-weight:500;font-size:.72rem;letter-spacing:.04em}
.modes{display:flex;gap:6px;padding:5px;border-radius:999px}
.modes button{font-family:inherit;font-size:.82rem;font-weight:600;color:var(--muted);background:transparent;border:0;padding:7px 15px;border-radius:999px;cursor:pointer;transition:.16s}
.modes button:hover{color:var(--text);background:var(--hover)}
.modes button.on{color:#fff;background:var(--blue);box-shadow:0 4px 14px rgba(0,151,244,.4)}
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
.bracket{display:flex;gap:10px;overflow-x:auto;padding:14px 8px;align-items:stretch;scrollbar-width:thin;position:relative}
.bksvg{position:absolute;top:0;left:0;pointer-events:none;z-index:0;overflow:visible}
.brk-toggle{display:inline-flex;gap:6px;padding:5px;border-radius:999px;margin-bottom:12px;background:var(--panel);border:1px solid var(--border)}
.brk-toggle button{font-family:inherit;font-size:.8rem;font-weight:600;color:var(--muted);background:transparent;border:0;padding:7px 16px;border-radius:999px;cursor:pointer;transition:.16s}
.brk-toggle button:hover{color:var(--text);background:var(--hover)}
.brk-toggle button.on{color:#fff;background:var(--blue);box-shadow:0 4px 14px rgba(0,151,244,.35)}
.brk-wrap[data-view="actual"] .bracket.mode-picked{display:none}
.brk-wrap[data-view="picked"] .bracket.mode-actual{display:none}
.round{flex:1 1 0;min-width:150px;display:flex;flex-direction:column;position:relative;z-index:1}
.conn{fill:none;stroke-width:2.5;stroke-linejoin:round;stroke-linecap:round}
.conn.c-won{stroke:var(--win)}
.conn.c-lost{stroke:var(--red)}
.conn.c-pending{stroke:var(--muted);opacity:.5;stroke-dasharray:5 5}
.conn.c-actual{stroke:var(--blue);opacity:.7;stroke-dasharray:2 4}
.team.blank{visibility:hidden}
.team.st-actual{border-color:color-mix(in srgb,var(--blue) 45%,var(--border));opacity:.9}
.team.st-actual .tname{color:var(--muted)}
.team.st-actual .rb.up{color:var(--blue)}
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
.team.st-lost{border-color:color-mix(in srgb,var(--red) 50%,var(--border))}
.team.st-lost .tname{text-decoration:line-through;color:var(--lose-ink)}
.team.advancer .tname{font-weight:750}
.adv-arrow{color:var(--muted);font-weight:800;margin-left:2px;flex:0 0 auto}
.matches{flex:1;display:flex;flex-direction:column;justify-content:space-around}
.champcol .matches{justify-content:center}
.rhead{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);text-align:center;padding:4px 0 8px}
.rhead span{display:block;font-size:.6rem;font-weight:600;color:var(--muted);opacity:.8;text-transform:none;margin-top:2px}
.match{position:relative;height:132px;display:flex;flex-direction:column;justify-content:center}
.mlabel{font-size:.58rem;font-weight:700;color:var(--muted);opacity:.75;text-align:center}
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
.team.busted{border-color:color-mix(in srgb,var(--red) 50%,var(--border))}
.team.busted .tname{text-decoration:line-through;color:var(--lose-ink)}
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
.ubtag{font-size:.58rem;font-weight:700;color:var(--gold-ink);background:color-mix(in srgb,var(--gold) 16%,transparent);border-radius:6px;padding:1px 6px;margin-left:6px;white-space:nowrap}
.bonusbox{display:flex;gap:20px;align-items:center;justify-content:space-between;padding:18px 22px;margin:var(--gap) 0;flex-wrap:wrap;border-left:3px solid var(--gold)}
.bb-l{flex:1;min-width:260px}.bb-h{font-weight:700;margin-bottom:6px}
.bb-tag{font-size:.58rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--gold-ink);background:color-mix(in srgb,var(--gold) 16%,transparent);border-radius:6px;padding:2px 7px;margin-left:8px}
.bb-txt{font-size:.86rem;color:var(--text2);line-height:1.55}
.bb-r{text-align:right;min-width:150px}.bb-big{font-size:2rem;font-weight:800;color:var(--gold-ink);line-height:1}
.bb-cap{font-size:.66rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-top:2px}
.bb-sub{font-size:.74rem;color:var(--muted);margin-top:4px}
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
"""

JS=r"""
(function(){
 var root=document.documentElement,LS=window.localStorage;
 var KTHEME='wcb.theme',KFAV='wcb.favs',KFO='wcb.favonly',KSC='wcb.scores.v3';
 function setTheme(t){root.setAttribute('data-theme',t);document.querySelectorAll('.modes button').forEach(function(b){b.classList.toggle('on',b.dataset.mode===t)});try{LS.setItem(KTHEME,t)}catch(e){}if(window.__drawConn)setTimeout(window.__drawConn,80);}
 document.querySelectorAll('.modes button').forEach(function(b){b.addEventListener('click',function(){setTheme(b.dataset.mode)})});
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
  set('scConfirmed',conf);set('scConfirmed2',conf);set('scLive',live);set('scOut',out);set('scMax',conf+live);
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
       var p=document.createElementNS('http://www.w3.org/2000/svg','path');
       p.setAttribute('d',d);p.setAttribute('class','conn c-'+st);svg.appendChild(p);
     });
   }
 }
 window.__drawConn=drawConnectors;
 document.querySelectorAll('.brk-toggle button').forEach(function(bt){bt.addEventListener('click',function(){var w=document.querySelector('.brk-wrap');w.setAttribute('data-view',bt.dataset.view);document.querySelectorAll('.brk-toggle button').forEach(function(x){x.classList.toggle('on',x===bt);});setTimeout(drawConnectors,60);});});
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
})();
"""

def chip(t):
    el = ' eliminated' if t in ELIM else ''
    return (f'<button class="chip{el}" data-team="{esc(t)}"><span class="star" data-star="{esc(t)}" role="button" aria-label="favorite" tabindex="0">☆</span>'
            f'<span class="cseed">{esc(seed_of(t))}</span><span class="ctxt">{esc(t)}</span></button>')

HTML=('<!DOCTYPE html><html lang="en" data-theme="dark"><head><meta charset="utf-8">'
f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(ENTRANT)}’s World Cup 2026 Bracket</title>'+'<style>'+CSS+'</style></head><body><div class="wrap">'
'<div class="topbar"><div class="brand"><span class="orb"></span><div>Bracket dashboard<small>SLED World Cup 2026 Challenge · live</small></div></div>'
'<div class="modes glass"><button data-mode="dark" class="on">Dark</button><button data-mode="light">Light</button>'
'<button data-mode="easy" title="Reading mode — a highly legible font, larger text, extra line and letter spacing, sentence case (no all-caps), left-aligned text and a soft, glare-free background">Easy</button></div></div>'
f'<section class="hero glass"><div class="eyebrow">{esc(ENTRANT)} · live results vs your picks</div>'
f'<h1>Backing <span class="g">{esc(CHAMP)}</span> {"— and still in it" if CHAMP_ALIVE else "— but knocked out"}</h1>'
f'<p class="sub">{R32_DONE} of {N_R32} Round-of-32 games are final — you\'re <b>{r32_correct} of {r32_decided} right</b>, '
f'with <b>{CONF} points</b> banked and <b>{LIVE}</b> still live. Your champion pick {esc(CHAMP)} is <b>{CHAMP_STATUS}</b>{esc(BUSTED_PHRASE)}.</p>'
'<div class="badges">'
f'<span class="pill live"><span class="dot"></span>{CONF} pts confirmed</span>'
f'<span class="pill"><span class="dot"></span>R32 {r32_correct}/{r32_decided}</span>'
f'<span class="pill"><span class="dot"></span>Max attainable {ATTAIN}</span>'
f'<span class="pill"><span class="dot"></span>+{BONUS_CONF} upset bonus (optional)</span>'
f'<span class="pill"><span class="dot"></span>{esc(CHAMP)} alive</span></div>'
'<div class="composer"><span class="corb"></span><span class="plus">+</span>'
'<input id="search" type="text" placeholder="Track a team through the bracket — try England, Morocco, Paraguay…" autocomplete="off">'
'<span class="mic">🎤</span><button class="clr" id="clear">Clear</button></div></section>'
'<div class="filterbar glass"><div class="chips">'+''.join(chip(t) for t in r32_win)+
'</div><label class="toggle"><input type="checkbox" id="favonly"><span class="tsw"></span>Favorites only</label><span class="count" id="count"></span></div>'
'<div class="shead"><span class="tile">📊</span><h2>Your live standing</h2><span class="cap">6 signals</span></div>'
f'<div class="kpigrid">{build_kpis()}</div>'
'<div class="shead"><span class="tile">🧮</span><h2>Scorecard — your path, scored live</h2>'
f'<span class="cap">{CONF} confirmed · {LIVE} live</span></div>'
'<div class="note"><b>How this is scored.</b> Results are pulled from live web coverage (ESPN, CBS Sports, FIFA) and matched to your Excel picks. '
f'The Round of 32 is <b>{R32_DONE} of {N_R32} games</b> final — you sit on <b>{CONF} points</b> ({r32_correct}/{r32_decided} correct). '
'The six remaining R32 games play July 2–3; those rows and every later round stay <b>pending</b> until they’re played. '
'Flip any row yourself as games finish — totals recompute and save on this device.</div>'
+ build_scorebar()
+ f'<div class="glass">{build_scorecard()}</div>'
'<div style="text-align:right;margin-top:10px"><button class="chip" id="scReset" style="cursor:pointer">↺ Reset to live results</button></div>'
'<div class="glass bonusbox">'
'<div class="bb-l"><div class="bb-h">Optional upset bonus<span class="bb-tag">host\'s choice</span></div>'
'<div class="bb-txt">Rob\'s rule awards <b>+2</b> for correctly picking a group runner-up or third-place team to win in the Round of 32. '
f'You\'ve hit <b>{len(bonus_won)}</b> so far — {esc(", ".join(bonus_won))} — for <b>+{BONUS_CONF}</b>'
+ (f', and {esc(", ".join(bonus_pend))} can add up to +{BONUS_POT} more.' if bonus_pend else '.')
+ ' It is Rob\'s discretion whether the bonus applies and whether the Canada freebie counts.</div></div>'
f'<div class="bb-r"><div class="bb-big">{ADJ}</div><div class="bb-cap">unofficial adjusted total</div>'
f'<div class="bb-sub">{CONF} base + {BONUS_CONF} bonus</div></div></div>'
'<div class="shead"><span class="tile">⚽</span><h2>Round of 32 results</h2><span class="cap">10 final · 6 to play</span></div>'
f'{build_results_panel()}'
'<div class="shead"><span class="tile">📅</span><h2>Next up — Round of 16</h2><span class="cap">Jul 4–7 · PT / CT / ET</span></div>'
f'{build_upcoming()}'
'<div class="shead"><span class="tile">📰</span><h2>Around the Round of 32</h2><span class="cap">game facts</span></div>'
f'<div class="g3">{build_highlights()}</div>'
'<div class="shead"><span class="tile">🗺️</span><h2>Your bracket, marked up</h2><span class="cap">✓ hit · ✕ miss · ▲ who went through</span></div>'
f'{build_legend()}'
'<div class="brk-toggle"><button data-view="actual" class="on">Actual path</button><button data-view="picked">My picks</button></div>'
f'<div class="glass brk-wrap" data-view="actual">{build_bracket("actual")}{build_bracket("picked")}</div>'
'<div class="shead"><span class="tile">🏅</span><h2>Your final four</h2><span class="cap">'+f'{FF_ALIVE}/{len(QF_WIN)} still alive'+'</span></div>'
f'<div class="ffgrid">{build_finalfour()}</div>'
'<div class="shead"><span class="tile">✨</span><h2>How it played out</h2><span class="cap">so far</span></div>'
f'<div class="g3">{build_story()}</div>'
'<div class="shead"><span class="tile">🎯</span><h2>Scoring &amp; schedule</h2><span class="cap">80 max</span></div>'
'<div class="g2"><div class="glass" style="padding:20px"><div style="font-weight:700;margin-bottom:12px">Points double every round</div>'
'<div class="scard" style="padding:0">'
'<div class="scrow schead" style="grid-template-columns:1fr 70px 70px 70px"><div class="tc">Round</div><div class="tc">Games</div><div class="tc">Pts/pick</div><div class="tc">Max</div></div>'
'<div class="scrow" style="grid-template-columns:1fr 70px 70px 70px"><div class="tc">Round of 32</div><div class="tc">16</div><div class="tc">1</div><div class="tc">16</div></div>'
'<div class="scrow" style="grid-template-columns:1fr 70px 70px 70px"><div class="tc">Round of 16</div><div class="tc">8</div><div class="tc">2</div><div class="tc">16</div></div>'
'<div class="scrow" style="grid-template-columns:1fr 70px 70px 70px"><div class="tc">Quarterfinals</div><div class="tc">4</div><div class="tc">4</div><div class="tc">16</div></div>'
'<div class="scrow" style="grid-template-columns:1fr 70px 70px 70px"><div class="tc">Semifinals</div><div class="tc">2</div><div class="tc">8</div><div class="tc">16</div></div>'
'<div class="scrow" style="grid-template-columns:1fr 70px 70px 70px"><div class="tc"><b>Final (Champion)</b></div><div class="tc">1</div><div class="tc">16</div><div class="tc">16</div></div>'
'<div class="scrow" style="grid-template-columns:1fr 70px 70px 70px;border-top:1px solid var(--border)"><div class="tc"><b>Total</b></div><div class="tc">31</div><div class="tc"></div><div class="tc"><b>80</b></div></div>'
'</div><div style="font-size:.8rem;color:var(--muted);margin-top:12px;line-height:1.5">Each pick scored on its own; Champion is worth a full 16. '
'Tiebreaker: total goals in the Final at the end of extra time — penalties don’t count. Your tiebreaker: <b>4</b>.</div></div>'
'<div class="glass" style="padding:20px"><div style="font-weight:700;margin-bottom:4px">Where the tournament stands</div>'
f'<div style="font-size:.8rem;color:var(--muted);margin-bottom:8px">Live results as of {REFRESHED}</div>'
f'<div class="stages" style="grid-template-columns:1fr;padding:0;gap:8px">{build_stages()}</div></div></div>'
'<div class="glass foot"><b>Sources.</b> Your picks, scoring, tiebreaker and any host bonus rule from your <b>SLED World Cup 2026 bracket workbook</b> and the challenge instructions. '
'Match results, scores and kickoff times from <b>FIFA official match records</b> (fifa.com), corroborated by NBC Sports, CBS Sports, ESPN and Sporting News, for the 2026 FIFA World Cup. Kickoff times anchored to ET, converted to CT/PT. Hover-card country pedigree (titles, best finish) from public FIFA World Cup historical records.'
f'<div class="src"><b>Status.</b> Round of 32 is {R32_DONE} of {N_R32} games final; {REMAIN_R32} still to play, and every later round is pending. '
f'You have <b>{CONF} points</b> confirmed ({ADJ} with the optional upset bonus), <b>{LIVE}</b> live, max attainable <b>{ATTAIN}</b>. '
f'This is your personal, <b>unofficial</b> tally for Rob to review — his scoring is authoritative. Champion {esc(CHAMP)} · runner-up {esc(RUNNER)}.</div>'
f'<div class="src">Live results as of <b>{REFRESHED}</b> · reading mode, favorites and any manual score edits are saved on this device.</div>'
+ (f'<div class="src credit">{esc(CREDIT)}</div>' if CREDIT else '') + '</div>'
'</div><button class="dab" id="dab" title="Back to top" aria-label="Back to top">↑</button>'
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

