#!/usr/bin/env python3
"""Reconstruit le classement jour par jour d'une saison régulière passée
à partir des résultats de matchs ESPN. Usage : backfill_season.py 2026
(année de fin de saison). Écrit data/<saison>/history.json et standings.json."""
import json, sys, urllib.request, time
from datetime import date, timedelta
from pathlib import Path

END_YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
LABEL = f"{END_YEAR-1}-{str(END_YEAR)[2:]}"
OUT = Path(__file__).resolve().parent.parent / "data" / LABEL
OUT.mkdir(parents=True, exist_ok=True)
START, END = date(END_YEAR - 1, 10, 15), date(END_YEAR, 4, 20)
HOSTS = ["https://site.web.api.espn.com", "https://site.api.espn.com"]

EAST = ["76ers","Knicks","Celtics","Pistons","Raptors","Cavaliers","Heat","Pacers","Hawks","Magic","Hornets","Wizards","Bulls","Bucks","Nets"]
WEST = ["Thunder","Spurs","Nuggets","Timberwolves","Warriors","Lakers","Trail Blazers","Rockets","Clippers","Suns","Mavericks","Jazz","Pelicans","Grizzlies","Kings"]
ALL = EAST + WEST
LOG = []
def log(*a):
    m = " ".join(str(x) for x in a); print(m); LOG.append(m)

def nick(name):
    for t in sorted(ALL, key=len, reverse=True):
        if name.endswith(t): return t
    return None

def get(path):
    last = None
    for h in HOSTS:
        try:
            req = urllib.request.Request(h + path, headers={"User-Agent": "Mozilla/5.0 (pronos-nba)"})
            with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
        except Exception as e: last = e
    raise last

rec = {t: {"w": 0, "l": 0, "pf": 0, "pa": 0} for t in ALL}
history, games_seen = [], set()
d = START
while d <= END:
    try:
        data = get(f"/apis/site/v2/sports/basketball/nba/scoreboard?dates={d:%Y%m%d}&limit=50")
    except Exception as e:
        log(f"{d} : échec {type(e).__name__} {e}"); d += timedelta(days=1); time.sleep(1); continue
    played = 0
    for ev in data.get("events", []):
        if (ev.get("season") or {}).get("type") != 2: continue  # saison régulière seulement
        comp = (ev.get("competitions") or [{}])[0]
        if not (comp.get("status") or {}).get("type", {}).get("completed"): continue
        if ev["id"] in games_seen: continue
        # finale de la NBA Cup (Las Vegas) : ne compte pas au classement
        venue = ((comp.get("venue") or {}).get("fullName") or "")
        notes = " ".join((n.get("headline") or "") for n in comp.get("notes", []))
        if "Cup" in notes and "Championship" in notes:
            log(f"{d} : finale NBA Cup ignorée ({venue} / {notes})"); continue
        teams = comp.get("competitors", [])
        if len(teams) != 2: continue
        names = [nick(c["team"].get("displayName", "")) for c in teams]
        if None in names: continue
        games_seen.add(ev["id"]); played += 1
        for c, n in zip(teams, names):
            s = int(float(c.get("score") or 0)); o = int(float([x for x in teams if x is not c][0].get("score") or 0))
            rec[n]["pf"] += s; rec[n]["pa"] += o
            if c.get("winner"): rec[n]["w"] += 1
            else: rec[n]["l"] += 1
    if played:
        def order(lst):
            return sorted(lst, key=lambda t: (-(rec[t]["w"] / max(1, rec[t]["w"] + rec[t]["l"])), -rec[t]["w"], -(rec[t]["pf"] - rec[t]["pa"]), t))
        history.append({"date": d.isoformat(), "east": order(EAST), "west": order(WEST),
                        "rec": {t: [rec[t]["w"], rec[t]["l"]] for t in ALL}})
    d += timedelta(days=1); time.sleep(0.3)

log(f"{len(games_seen)} matchs, {len(history)} journées")
(OUT / "history.json").write_text(json.dumps(history, ensure_ascii=False))
if history:
    last = history[-1]
    mk = lambda lst: [{"team": t, "w": rec[t]["w"], "l": rec[t]["l"], "pct": round(rec[t]["w"] / max(1, rec[t]["w"] + rec[t]["l"]), 3)} for t in lst]
    (OUT / "standings.json").write_text(json.dumps({"updated": last["date"] + "T12:00:00+00:00", "season": LABEL, "started": True,
        "east": mk(last["east"]), "west": mk(last["west"])}, ensure_ascii=False, indent=1))
(OUT / "robot.log").write_text("\n".join(LOG) + "\n")
