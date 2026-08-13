"""
collectors/market_check.py

Job de vérification (voir .github/workflows/market-action-check.yml) :
toutes les 15 minutes, lundi à vendredi entre 08h00 et 22h30 heure de
Paris (jours fériés français exclus), compare le prix actuel de chaque
ticker à la baseline du jour (voir market_reset.py) et écrit la liste des
titres en hausse de 2% ou plus.

Seuil HAUSSES UNIQUEMENT (pas de valeur absolue) - décision explicite du
12/08/2026.

data/marketAction.json est réécrit intégralement à chaque run, à partir
du SEUL état courant (pas de persistance intra-journée - retirée le
13/08/2026 : elle faisait ressortir des titres repassés sous 2% depuis,
ce qui n'est pas voulu - seuls les titres réellement au-dessus de 2%
AU MOMENT DU RUN doivent apparaître). Protégé contre les pannes réseau
transitoires par un garde-fou dédié (voir plus bas) : un run qui échoue
massivement à récupérer les prix n'écrit RIEN plutôt que de remplacer un
état valide par une liste vide erronée (incident du 12/08/2026, où une
panne réseau simultanée sur tous les tickers avait effacé un mouvement
réel de +9,91% sur Arista Networks).

Usage : python market_check.py
Écrit data/marketAction.json.
"""

import concurrent.futures
import json
import os
import sys
import time
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

_hours = _load_module("lib/market_hours.py", "omnium_market_hours")
market_has_opened = _hours.market_has_opened

PRICE_PROXY_URL = "https://model.omnium-capital.com/price.php"
BASELINE_PATH = "data/marketActionBaseline.json"
OUTPUT_PATH = "data/marketAction.json"
PARIS_TZ = ZoneInfo("Europe/Paris")
MAX_CONCURRENCY = 10
PER_REQUEST_TIMEOUT_SECONDS = 10
THRESHOLD_PERCENT = 2.0


FETCH_RETRY_DELAYS_SECONDS = (1.0, 2.0)  # tentative initiale + 2 retries


def fetch_price(yahoo_symbol: str):
    """Retry court en cas d'echec reseau transitoire (observe le 12/08/2026 :
    panne reseau totale et simultanee sur les 57 tickers d'un run, tres
    probablement un souci IPv6 ponctuel du runner GitHub Actions - voir
    docstring du module). Le retry seul ne suffit pas a couvrir une panne
    plus longue, voir le garde-fou complementaire dans main()."""
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


def compute_ticker(ticker: str, base_price: float):
    """Calcule l'etat actuel d'un ticker (prix, variation) SANS filtrer sur
    le seuil - le filtrage se fait dans main(), pour separer proprement le
    calcul du garde-fou anti-ecrasement (voir plus bas). Retourne
    (resultat, statut) - statut in {"ok","not_open","error","no_data"} :
    "not_open" (marche pas encore ouvert) est un skip ATTENDU, exclu du
    calcul de taux d'echec dans main() ; "error" (echec reseau) est ce qui
    declenche le garde-fou anti-ecrasement en cas de panne massive."""
    tdata = load_ticker_json(ticker) or {}
    sym = (tdata.get("yahooSymbol") or "").strip()
    name = tdata.get("name", ticker)
    if not sym or not base_price:
        return None, "no_data"

    # Ne jamais evaluer un titre avant l'ouverture (+ marge de securite)
    # de SA place boursiere - voir lib/market_hours.py pour le contexte du
    # bug du 12/08/2026 (des tickers US remontaient une "variation" avant
    # 15h30 heure de Paris, alors que leur session n'avait pas commence -
    # price.php/Google Finance renvoie un prix pre-marche peu fiable avant
    # l'ouverture officielle).
    if not market_has_opened(sym):
        return None, "not_open"

    try:
        price = fetch_price(sym)
    except Exception as e:
        print(f"  [WARN] {ticker} ({sym}): echec recuperation prix ({e})", file=sys.stderr)
        return None, "error"

    change_percent = (price - base_price) / base_price * 100.0
    return {
        "ticker": ticker,
        "name": name,
        "price": round(price, 2),
        "basePrice": round(base_price, 2),
        "changePercent": round(change_percent, 2),
    }, "ok"


def write_output(today_str: str, movers: list, note: str = None):
    output = {
        "date": today_str,
        "computedAt": datetime.now(PARIS_TZ).isoformat(),
        "movers": sorted(movers, key=lambda m: m["changePercent"], reverse=True),
    }
    if note:
        output["note"] = note
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


def main():
    today_paris = datetime.now(PARIS_TZ).date()
    today_str = today_paris.strftime("%Y-%m-%d")

    if not is_market_day(today_paris):
        print(f"[market_check] {today_paris} n'est pas un jour de marche (week-end/ferie FR) - skip.")
        return 0

    if not os.path.exists(BASELINE_PATH):
        print("[market_check] aucune baseline trouvee - skip (le job market_reset n'a peut-etre pas encore tourne).")
        write_output(today_str, [], note="baseline absente")
        return 0

    with open(BASELINE_PATH, encoding="utf-8") as f:
        baseline = json.load(f)

    if baseline.get("date") != today_str:
        print(f"[market_check] baseline perimee (date={baseline.get('date')}, attendu={today_str}) - skip.")
        write_output(today_str, [], note="baseline perimee")
        return 0

    base_prices = baseline.get("prices", {})
    manifest = load_manifest()

    movers = []
    status_counts = {"ok": 0, "not_open": 0, "error": 0, "no_data": 0}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENCY) as executor:
        futures = {
            executor.submit(compute_ticker, ticker, base_prices.get(ticker)): ticker
            for ticker in manifest if ticker in base_prices
        }
        for fut in concurrent.futures.as_completed(futures):
            result, status = fut.result()
            status_counts[status] = status_counts.get(status, 0) + 1
            if not result:
                continue
            # Seuil evalue AU MOMENT DU RUN uniquement (pas de persistance
            # intra-journee - voir docstring du module).
            if result["changePercent"] >= THRESHOLD_PERCENT:
                movers.append(result)

    # Garde-fou anti-ecrasement (ajoute suite a l'incident du 12/08/2026 :
    # panne reseau simultanee sur les 57 tickers d'un run, qui aurait
    # silencieusement efface des mouvements reels (+9,91% sur Arista
    # Networks entre autres) en ecrivant une liste vide sans que rien ne
    # le signale). "not_open"/"no_data" sont des skips ATTENDUS, exclus du
    # taux d'echec - seul "error" (echec reseau/prix) compte. Si plus de
    # la moitie des tickers effectivement tentes echouent, le run est jugé
    # non fiable : on n'ecrit RIEN plutot que de remplacer un etat valide
    # par un resultat corrompu par la panne.
    attempted = status_counts["ok"] + status_counts["error"]
    if attempted > 0 and status_counts["error"] / attempted > 0.5:
        print(f"[market_check] ABANDON : {status_counts['error']}/{attempted} echecs de recuperation "
              f"de prix (probable panne reseau transitoire) - data/marketAction.json NON touche pour "
              f"ne pas ecraser un etat valide.", file=sys.stderr)
        return 1

    write_output(today_str, movers)
    print(f"[market_check] {len(movers)} titre(s) en hausse >= {THRESHOLD_PERCENT}% "
          f"({status_counts['error']} erreurs isolees) sur {len(base_prices)} tickers avec baseline.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
