#!/usr/bin/env python3
"""Récupère le classement NBA (saison régulière) depuis l'API publique ESPN
et met à jour data/standings.json + data/history.json.

Lancé chaque nuit par GitHub Actions (voir .github/workflows/update.yml).
"""
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SEASON_END_YEAR = 2027  # saison 2026-27
BASES = [
    "https://site.web.api.espn.com/apis/v2/sports/basketball/nba/standings",
    "https://site.api.espn.com/apis/v2/sports/basketball/nba/standings",
]
URLS = [f"{b}?season={SEASON_END_YEAR}&seasontype=2" for b in BASES]
LOG = []


def log(*a):
    msg = " ".join(str(x) for x in a)
    print(msg)
    LOG.append(msg)

TEAMS = {
    "east": ["76ers", "Knicks", "Celtics", "Pistons", "Raptors", "Cavaliers", "Heat",
             "Pacers", "Hawks", "Magic", "Hornets", "Wizards", "Bulls", "Bucks", "Nets"],
    "west": ["Thunder", "Spurs", "Nuggets", "Timberwolves", "Warriors", "Lakers",
             "Trail Blazers", "Rockets", "Clippers", "Suns", "Mavericks", "Jazz",
             "Pelicans", "Grizzlies", "Kings"],
}
ALL_TEAMS = TEAMS["east"] + TEAMS["west"]


def nickname(display_name: str):
    """'Boston Celtics' -> 'Celtics', 'Portland Trail Blazers' -> 'Trail Blazers'."""
    for t in sorted(ALL_TEAMS, key=len, reverse=True):
        if display_name.endswith(t):
            return t
    return None


def stat(entry, *names):
    for s in entry.get("stats", []):
        if s.get("name") in names or s.get("type") in names:
            v = s.get("value")
            if v is None:
                try:
                    v = float(s.get("displayValue"))
                except (TypeError, ValueError):
                    v = None
            return v
    return None


def fetch_one(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (pronos-nba)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_and_parse():
    """Essaie chaque adresse ESPN jusqu'à obtenir un classement complet."""
    last_err = None
    for url in URLS:
        try:
            payload = fetch_one(url)
            season = payload.get("season") or {}
            log("Réponse de", url, "| clés :", list(payload.keys())[:8], "| saison :", season.get("year") or season)
            if int(season.get("year") or SEASON_END_YEAR) != SEASON_END_YEAR:
                log("Mauvaise saison, on passe.")
                continue
            parsed = parse(payload)
            if parsed is None:
                log("Saison pas encore commencée (aucune entrée).")
                # test de lecture sur la saison précédente, pour vérifier que le format est bon
                try:
                    prev = parse(fetch_one(url.replace(f"season={SEASON_END_YEAR}", f"season={SEASON_END_YEAR-1}")))
                    log("Test saison précédente OK, top 3 Est :", [t["team"] for t in prev["east"][:3]],
                        "| Ouest :", [t["team"] for t in prev["west"][:3]])
                except Exception as e:  # noqa: BLE001
                    log("Test saison précédente raté :", type(e).__name__, e)
            return parsed
        except Exception as e:  # noqa: BLE001
            last_err = e
            log("Échec", url, "->", type(e).__name__, e)
    raise RuntimeError(f"Aucune adresse n'a fonctionné : {last_err}")


def parse(payload):
    out = {"east": [], "west": []}
    groups = payload.get("children") or []
    for g in groups:
        name = (g.get("name") or g.get("abbreviation") or "").lower()
        conf = "east" if "east" in name else "west" if "west" in name else None
        if conf is None:
            continue
        for e in (g.get("standings") or {}).get("entries", []):
            team = e.get("team", {})
            nick = nickname(team.get("displayName", "")) or nickname(team.get("name", "") or "")
            if not nick:
                log("Équipe inconnue :", team.get("displayName"))
                continue
            out[conf].append({
                "team": nick,
                "w": int(stat(e, "wins") or 0),
                "l": int(stat(e, "losses") or 0),
                "pct": float(stat(e, "winPercent") or 0),
                "seed": stat(e, "playoffSeed"),
            })
    if not out["east"] and not out["west"]:
        return None
    for conf in out:
        out[conf].sort(key=lambda t: (-t["pct"], -t["w"], t["seed"] if t["seed"] is not None else 99, t["team"]))
        missing = set(TEAMS[conf]) - {t["team"] for t in out[conf]}
        if missing or len(out[conf]) != 15:
            raise RuntimeError(f"Conférence {conf} incomplète, manquent : {missing}")
    return out


def write_log(ok):
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (DATA / "robot.log").write_text(f"{now} — {'OK' if ok else 'ECHEC'}\n" + "\n".join(LOG) + "\n")


def main():
    try:
        parsed = fetch_and_parse()
    except Exception as e:  # noqa: BLE001
        log("Abandon :", e)
        write_log(False)
        return
    now = datetime.now(timezone.utc)
    if parsed is None:
        standings = {"updated": now.isoformat(timespec="seconds"), "season": f"{SEASON_END_YEAR - 1}-{str(SEASON_END_YEAR)[2:]}",
                     "started": False, "east": [], "west": []}
        (DATA / "standings.json").write_text(json.dumps(standings, ensure_ascii=False, indent=1))
        write_log(True)
        return
    started = any(t["w"] + t["l"] > 0 for c in parsed.values() for t in c)
    standings = {
        "updated": now.isoformat(timespec="seconds"),
        "season": f"{SEASON_END_YEAR - 1}-{str(SEASON_END_YEAR)[2:]}",
        "started": started,
        "east": [{k: v for k, v in t.items() if k != "seed"} for t in parsed["east"]],
        "west": [{k: v for k, v in t.items() if k != "seed"} for t in parsed["west"]],
    }
    (DATA / "standings.json").write_text(json.dumps(standings, ensure_ascii=False, indent=1))

    if started:
        hist_path = DATA / "history.json"
        history = json.loads(hist_path.read_text() or "[]")
        today = now.date().isoformat()
        snapshot = {
            "date": today,
            "east": [t["team"] for t in parsed["east"]],
            "west": [t["team"] for t in parsed["west"]],
        }
        history = [h for h in history if h["date"] != today] + [snapshot]
        hist_path.write_text(json.dumps(history, ensure_ascii=False))
    log("OK — saison commencée :", started)
    write_log(True)


if __name__ == "__main__":
    main()
