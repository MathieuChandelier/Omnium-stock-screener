"""
collectors/price_history.py

Snapshot de valorisation (voir .github/workflows/price-history-collector.yml) :
2 fois par semaine (lundi et jeudi soir, apres cloture), capture le prix de
chaque ticker ET une copie complete de hypothese.adjEPS/epsForward12m au
meme instant, pour alimenter data/priceHistory.json (courbes P/E dans le
temps, classements de mouvements "Value Rankings").

Demarrage propre (aout 2026) : AUCUN backfill, on accumule uniquement a
partir de maintenant. Chaque snapshot est fige definitivement (prix ET EPS
en vigueur ce jour-la) - une revision future d'adjEPS lors d'un refresh ne
doit JAMAIS re-ecrire retroactivement le P/E d'une semaine passee, sinon un
classement "P/E en forte hausse" confondrait une vraie re-rating de marche
avec une simple revision d'estimation. Meme logique de non-alteration
retroactive que guidanceHistory/priorEPS (voir INSTRUCTIONS.md).

epsByYear est une copie INTEGRALE de hypothese.adjEPS (toutes les annees
projetees, pas seulement CY/NY) : ca permet de tracer a la fois "le P/E de
l'annee civile 2026" (courbe qui garde son identite meme quand 2026 cesse
d'etre l'annee en cours) et "le P/E de l'annee en cours" (serie glissante,
comparable entre deux annees calendaires differentes) depuis la MEME
structure - voir le plan de fonctionnalite pour le detail des deux lectures.

ndCY/shCY (ajoutes le 17/08/2026) : copie de hypothese.adjND/adjShares pour
l'ANNEE EN COURS UNIQUEMENT (pas de NY/Fwd - inutile tant qu'aucun
graphique ne les consomme), pour permettre a terme un P/E ex-cash
historise en plus du P/E classique deja archive.

earningsDates est un accumulateur PERMANENT (jamais purge) des dates de
call reellement trouvees, fusionnees a chaque run depuis
hypothese.guidanceHistory[].date / coherenceQualitative.historique[].date /
hypothese.date (repli). Necessaire car guidanceHistory se reinitialise a
chaque exercice fiscal et n'est donc pas un journal fiable a lui seul sur
plus d'un an.

Usage : python price_history.py
Ecrit/met a jour data/priceHistory.json.
"""

import concurrent.futures
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

import importlib.util as _ilu


def _load_module(rel_path, mod_name):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)
    spec = _ilu.spec_from_file_location(mod_name, path)
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_state = _load_module("lib/state.py", "omnium_price_history_state")
load_manifest = _state.load_manifest
load_ticker_json = _state.load_ticker_json

PRICE_PROXY_URL = "https://model.omnium-capital.com/price.php"
HISTORY_PATH = "data/priceHistory.json"
MAX_CONCURRENCY = 10
PER_REQUEST_TIMEOUT_SECONDS = 10
FETCH_RETRY_DELAYS_SECONDS = (1.0, 2.0)  # tentative initiale + 2 retries - un
# run hebdomadaire manque coute plus cher qu'un check intraday manque (voir
# market_check.py), meme logique de retry reprise ici.


def fetch_price(yahoo_symbol: str):
    """Identique a market_check.py::fetch_price - retry court en cas
    d'echec reseau transitoire sur le proxy price.php."""
    url = f"{PRICE_PROXY_URL}?ticker={yahoo_symbol}"
    last_error = None
    for attempt, delay in enumerate((0.0,) + FETCH_RETRY_DELAYS_SECONDS):
        if delay:
            time.sleep(delay)
        try:
            with urllib.request.urlopen(url, timeout=PER_REQUEST_TIMEOUT_SECONDS) as r:
                data = json.loads(r.read().decode("utf-8"))
            price = data.get("price")
            if price is None:
                raise ValueError(f"reponse price.php sans champ 'price' pour {yahoo_symbol}")
            return float(price)
        except Exception as e:
            last_error = e
    raise last_error


def compute_cy_ny(ticker_data: dict):
    """Port exact de yearsFor() (index.html) : CY = dernier exercice
    historique + 1, NY = CY + 1."""
    data = ticker_data.get("data") or []
    current_year = datetime.now(timezone.utc).year
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


def snapshot_ticker(ticker: str, run_date_str: str):
    tdata = load_ticker_json(ticker)
    if tdata is None:
        return ticker, None, "no_json"
    sym = (tdata.get("yahooSymbol") or "").strip()
    if not sym:
        return ticker, None, "no_symbol"

    hyp = tdata.get("hypothese") or {}
    cy, ny = compute_cy_ny(tdata)
    eps_by_year = build_eps_by_year(hyp)
    eps_fwd = (hyp.get("quarterlyEPS") or {}).get("epsForward12m")
    eps_fwd = round(float(eps_fwd), 4) if isinstance(eps_fwd, (int, float)) else None
    # P/E ex-cash : ANNEE EN COURS UNIQUEMENT (decision du 17/08/2026) - pas
    # de nd_ny/sh_ny, le graphique n'en a pas besoin pour l'instant et ca
    # double le nombre de champs pour un usage non demande.
    nd_cy = (hyp.get("adjND") or {}).get(str(cy))
    sh_cy = (hyp.get("adjShares") or {}).get(str(cy))
    nd_cy = round(float(nd_cy), 2) if isinstance(nd_cy, (int, float)) else None
    sh_cy = round(float(sh_cy), 2) if isinstance(sh_cy, (int, float)) else None

    try:
        price = fetch_price(sym)
    except Exception as e:
        print(f"  [WARN] {ticker} ({sym}): echec capture prix ({e})", file=sys.stderr)
        return ticker, None, "fetch_error"

    snap = {"date": run_date_str, "price": round(price, 2), "cyYear": cy, "nyYear": ny}
    if eps_by_year:
        snap["epsByYear"] = eps_by_year
    if eps_fwd is not None:
        snap["epsFwd"] = eps_fwd
    if nd_cy is not None:
        snap["ndCY"] = nd_cy
    if sh_cy is not None:
        snap["shCY"] = sh_cy

    earnings_dates = collect_earnings_dates(tdata)
    return ticker, (snap, earnings_dates), "ok"


def main():
    now_utc = datetime.now(timezone.utc)
    run_date_str = now_utc.strftime("%Y-%m-%d")

    history = {"schemaVersion": 1, "tickers": {}, "earningsDates": {}}
    if os.path.exists(HISTORY_PATH):
        try:
            with open(HISTORY_PATH, encoding="utf-8") as f:
                history = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[price_history] AVERTISSEMENT : {HISTORY_PATH} illisible "
                  f"({e}), reconstruction a partir d'un etat vide - les "
                  f"snapshots anterieurs seront PERDUS si ce fichier n'est "
                  f"pas restaure depuis git avant le prochain commit.",
                  file=sys.stderr)
        history.setdefault("schemaVersion", 1)
        history.setdefault("tickers", {})
        history.setdefault("earningsDates", {})

    manifest = load_manifest()
    skipped = {}
    ok_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as executor:
        futures = {executor.submit(snapshot_ticker, t, run_date_str): t for t in manifest}
        for future in concurrent.futures.as_completed(futures):
            ticker = futures[future]
            _, payload, status = future.result()
            if status != "ok":
                skipped[ticker] = status
                continue
            ok_count += 1
            snap, earnings_dates = payload

            entry = history["tickers"].setdefault(ticker, {"snapshots": []})
            snaps = entry["snapshots"]
            # Idempotent si relance manuelle le meme jour (workflow_dispatch) :
            # remplace l'entree du jour, n'ajoute jamais de doublon. Les
            # entrees des jours precedents ne sont JAMAIS modifiees ni
            # reordonnees (append-only, meme philosophie que guidanceHistory).
            if snaps and snaps[-1]["date"] == run_date_str:
                snaps[-1] = snap
            else:
                snaps.append(snap)

            existing_dates = set(history["earningsDates"].get(ticker, []))
            existing_dates |= earnings_dates
            history["earningsDates"][ticker] = sorted(existing_dates)

    history["lastRun"] = {
        "date": run_date_str,
        "capturedAt": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tickerCount": len(manifest),
        "okCount": ok_count,
        "skipped": skipped,
    }

    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"[price_history] {ok_count}/{len(manifest)} tickers captures, "
          f"{len(skipped)} skips ({skipped})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
