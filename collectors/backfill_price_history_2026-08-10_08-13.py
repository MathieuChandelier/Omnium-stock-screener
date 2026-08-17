"""
collectors/backfill_price_history_2026-08-10_08-13.py

Script PONCTUEL, a executer UNE SEULE FOIS puis a laisser tel quel comme
trace d'audit (ne fait PAS partie du pipeline recurrent - voir
price_history.py, qui reste "demarrage propre, aucun backfill" pour tout
ce qui suit ces deux dates).

Contexte (decision du 17/08/2026, qui deroge ponctuellement a la regle
"aucun backfill" de price_history.py) : au lieu d'attendre le premier run
programme (lundi 17/08 23h00 UTC) pour avoir un historique exploitable,
on reconstitue les DEUX points precedents - lundi 10/08 et jeudi 13/08,
cloture - a partir de donnees dejq figees :
  - prix de cloture : recupere directement via l'API historique publique
    Yahoo Finance (query1.finance.yahoo.com/v8/finance/chart), PAS via le
    proxy price.php (qui n'expose que le prix courant, pas d'historique).
  - EPS (epsByYear/epsFwd) : copie de hypothese.adjEPS/epsForward12m tel
    qu'en vigueur CE JOUR-LA. Pour la quasi-totalite des titres, identique
    a la valeur actuelle (aucun refresh n'a eu lieu entre le 10/08 et
    aujourd'hui). SEULE EXCEPTION : NUBANK, dont le call du 13/08 AU SOIR
    (apres cloture - voir hypothese.dernierCall/guidanceHistory) a
    entraine un refresh le 15/08 (adjEPS releve de 0.88/1.22/1.66/2.11/
    2.56 a 0.91/1.27/1.72/2.19/2.65$, ajout du bloc quarterlyEPS qui
    n'existait pas avant). Consequence : les DEUX points de cette semaine
    (10/08 ET 13/08, cloture - donc avant l'annonce du 13/08 au soir)
    doivent utiliser les valeurs PRE-refresh, recuperees via
    `git show b97f154:data/NUBANK.json` (dernier commit avant le refresh
    f41ad93). epsFwd est omis pour ces deux points NUBANK : le champ
    quarterlyEPS.epsForward12m n'existait pas encore dans le schema a
    cette date (voir docstring plus bas).

Usage : python collectors/backfill_price_history_2026-08-10_08-13.py
Met a jour data/priceHistory.json (ajoute 2 snapshots par ticker, insere
avant tout snapshot existant, jamais de doublon si relance).
"""

import calendar
import datetime
import json
import os
import sys
import urllib.request

import importlib.util as _ilu


def _load_module(rel_path, mod_name):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)
    spec = _ilu.spec_from_file_location(mod_name, path)
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_state = _load_module("lib/state.py", "omnium_backfill_state")
load_manifest = _state.load_manifest
load_ticker_json = _state.load_ticker_json

HISTORY_PATH = "data/priceHistory.json"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
TARGET_DATES = ["2026-08-10", "2026-08-13"]  # lundi, jeudi - cloture

# NUBANK seul : valeurs adjEPS/quarterlyEPS EN VIGUEUR au 10/08 et au
# 13/08 (avant cloture), soit AVANT le refresh du 15/08 post-call du
# 13/08 au soir (voir docstring). Source : git show b97f154:data/NUBANK.json
NUBANK_PRE_REFRESH_EPS_BY_YEAR = {
    "2026": 0.88, "2027": 1.22, "2028": 1.66, "2029": 2.11, "2030": 2.56,
}
NUBANK_PRE_REFRESH_EPS_FWD = None  # quarterlyEPS n'existait pas encore


def fetch_yahoo_closes(yahoo_symbol: str, dates: list):
    """Retourne {date_str: close} pour les dates demandees, via l'API
    historique publique Yahoo (pas de cle requise). period1/period2 pris
    avec 3 jours de marge de chaque cote pour absorber d'eventuels jours
    feries locaux sans fausser l'alignement (on ne garde que les dates
    demandees, matchees par egalite exacte de date UTC)."""
    first = min(datetime.date.fromisoformat(d) for d in dates)
    last = max(datetime.date.fromisoformat(d) for d in dates)
    p1 = calendar.timegm((first - datetime.timedelta(days=3)).timetuple())
    p2 = calendar.timegm((last + datetime.timedelta(days=3)).timetuple())
    url = YAHOO_CHART_URL.format(sym=yahoo_symbol) + f"?period1={p1}&period2={p2}&interval=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        payload = json.loads(r.read().decode("utf-8"))
    result = (payload.get("chart") or {}).get("result") or []
    if not result:
        raise ValueError(f"reponse Yahoo vide pour {yahoo_symbol}")
    r0 = result[0]
    timestamps = r0.get("timestamp") or []
    closes = ((r0.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    out = {}
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        day = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
        if day in dates:
            out[day] = float(close)
    return out


def compute_cy_ny(ticker_data: dict):
    """Identique a price_history.py::compute_cy_ny."""
    data = ticker_data.get("data") or []
    current_year = datetime.datetime.now(datetime.timezone.utc).year
    last_hist = data[-1]["year"] if data else (current_year - 1)
    cy = int(last_hist) + 1
    return cy, cy + 1


def build_eps_by_year(hyp: dict):
    raw = hyp.get("adjEPS") or {}
    out = {}
    for year_key, value in raw.items():
        if isinstance(value, (int, float)):
            out[str(year_key)] = round(float(value), 4)
    return out


def collect_earnings_dates(ticker_data: dict):
    """Identique a price_history.py::collect_earnings_dates."""
    hyp = ticker_data.get("hypothese") or {}
    dates = set()
    for row in hyp.get("guidanceHistory") or []:
        d = row.get("date")
        if d:
            dates.add(d)
    coherence = ticker_data.get("coherenceQualitative") or {}
    for row in coherence.get("historique") or []:
        d = row.get("date")
        if d:
            dates.add(d)
    if hyp.get("date"):
        dates.add(hyp["date"])
    return dates


def main():
    manifest = load_manifest()

    history = {"schemaVersion": 1, "tickers": {}, "earningsDates": {}}
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, encoding="utf-8") as f:
            history = json.load(f)
        history.setdefault("schemaVersion", 1)
        history.setdefault("tickers", {})
        history.setdefault("earningsDates", {})

    ok_count = 0
    skipped = {}

    for ticker in manifest:
        tdata = load_ticker_json(ticker)
        if tdata is None:
            skipped[ticker] = "no_json"
            continue
        sym = (tdata.get("yahooSymbol") or "").strip()
        if not sym:
            skipped[ticker] = "no_symbol"
            continue

        hyp = tdata.get("hypothese") or {}
        cy, ny = compute_cy_ny(tdata)

        if ticker == "NUBANK":
            eps_by_year = dict(NUBANK_PRE_REFRESH_EPS_BY_YEAR)
            eps_fwd = NUBANK_PRE_REFRESH_EPS_FWD
        else:
            eps_by_year = build_eps_by_year(hyp)
            eps_fwd = (hyp.get("quarterlyEPS") or {}).get("epsForward12m")
            eps_fwd = round(float(eps_fwd), 4) if isinstance(eps_fwd, (int, float)) else None

        try:
            closes = fetch_yahoo_closes(sym, TARGET_DATES)
        except Exception as e:
            print(f"  [WARN] {ticker} ({sym}): echec recuperation historique Yahoo ({e})", file=sys.stderr)
            skipped[ticker] = "fetch_error"
            continue

        missing = [d for d in TARGET_DATES if d not in closes]
        if missing:
            print(f"  [WARN] {ticker} ({sym}): pas de cloture Yahoo pour {missing} (ferie local ?)", file=sys.stderr)

        entry = history["tickers"].setdefault(ticker, {"snapshots": []})
        existing_dates = {s["date"] for s in entry["snapshots"]}

        for d in TARGET_DATES:
            if d not in closes or d in existing_dates:
                continue
            snap = {"date": d, "price": round(closes[d], 2), "cyYear": cy, "nyYear": ny}
            if eps_by_year:
                snap["epsByYear"] = eps_by_year
            if eps_fwd is not None:
                snap["epsFwd"] = eps_fwd
            entry["snapshots"].append(snap)

        entry["snapshots"].sort(key=lambda s: s["date"])

        earnings_dates = collect_earnings_dates(tdata)
        existing_ed = set(history["earningsDates"].get(ticker, []))
        existing_ed |= earnings_dates
        history["earningsDates"][ticker] = sorted(existing_ed)

        ok_count += 1

    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"[backfill] {ok_count}/{len(manifest)} tickers traites, {len(skipped)} skips ({skipped})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
