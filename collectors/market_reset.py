"""
collectors/market_reset.py

Job de reset quotidien (voir .github/workflows/market-action-reset.yml) :
capture le prix de tous les tickers du portefeuille pour servir de
référence ("clôture de la veille") aux calculs de variation intraday de
market_check.py. Exécuté à 01h00 heure de Paris (pas minuit - voir plus
bas), lundi à vendredi uniquement (jours fériés français exclus) - voir
lib/holidays_fr.py pour la justification de ce choix et sa limite
assumée.

Pourquoi un job dédié tôt le matin plutôt qu'une baseline "premier run de
la fenêtre horaire" (décision du 12/08/2026, corrigée en cours de
conception) : à cette heure, tous les marchés US et européens sont
fermés avec certitude, ce qui garantit que le prix capturé est bien celui
de la clôture - une capture plus tardive (ex. 08h00) reposerait sur
l'hypothèse qu'aucun marché n'a encore ouvert, hypothèse non garantie en
cas de retard du scheduler GitHub Actions.

Pourquoi 01h00 et pas minuit pile (décision du 13/08/2026) : la
notification de market_check.py de la veille reste ainsi visible côté
app jusqu'à 01h00 (voir todayParisDateStr() dans index.html, même cutoff
décalé) plutôt que de disparaître à minuit pile - utile pour un
utilisateur qui consulte tard le soir. Sans incidence sur la justesse de
la référence (les marchés sont fermés aussi bien à minuit qu'à 01h00).

Usage : python market_reset.py
Écrit data/marketActionBaseline.json.
"""

import concurrent.futures
import json
import os
import sys
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

import importlib.util as _ilu


def _load_module(rel_path, mod_name):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)
    spec = _ilu.spec_from_file_location(mod_name, path)
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_state = _load_module("lib/state.py", "omnium_market_state")
load_manifest = _state.load_manifest
load_ticker_json = _state.load_ticker_json

_hol = _load_module("lib/holidays_fr.py", "omnium_market_holidays")
is_market_day = _hol.is_market_day

PRICE_PROXY_URL = "https://model.omnium-capital.com/price.php"
BASELINE_PATH = "data/marketActionBaseline.json"
PARIS_TZ = ZoneInfo("Europe/Paris")
MAX_CONCURRENCY = 10
PER_REQUEST_TIMEOUT_SECONDS = 10


def fetch_price(yahoo_symbol: str):
    url = f"{PRICE_PROXY_URL}?ticker={yahoo_symbol}"
    with urllib.request.urlopen(url, timeout=PER_REQUEST_TIMEOUT_SECONDS) as r:
        data = json.loads(r.read().decode("utf-8"))
    price = data.get("price")
    if price is None:
        raise ValueError(f"reponse price.php sans champ 'price' pour {yahoo_symbol}")
    return float(price)


def capture_ticker(ticker: str):
    tdata = load_ticker_json(ticker) or {}
    sym = (tdata.get("yahooSymbol") or "").strip()
    if not sym:
        return ticker, None, "no_symbol"
    try:
        price = fetch_price(sym)
        return ticker, price, "ok"
    except Exception as e:
        print(f"  [WARN] {ticker} ({sym}): echec capture prix ({e})", file=sys.stderr)
        return ticker, None, "error"


def main():
    today_paris = datetime.now(PARIS_TZ).date()

    if not is_market_day(today_paris):
        print(f"[market_reset] {today_paris} n'est pas un jour de marche (week-end/ferie FR) - skip.")
        return 0

    manifest = load_manifest()
    prices = {}
    error_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as executor:
        for ticker, price, status in executor.map(capture_ticker, manifest):
            if status == "ok":
                prices[ticker] = price
            else:
                error_count += 1

    baseline = {
        "date": today_paris.strftime("%Y-%m-%d"),
        "capturedAt": datetime.now(PARIS_TZ).isoformat(),
        "prices": prices,
    }
    with open(BASELINE_PATH, "w", encoding="utf-8") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)

    print(f"[market_reset] baseline {today_paris} ecrite : {len(prices)}/{len(manifest)} tickers "
          f"({error_count} erreurs de capture)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
