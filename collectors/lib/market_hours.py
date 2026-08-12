"""
lib/market_hours.py

Heure d'ouverture (heure de Paris) par place boursière, déduite du
suffixe yahooSymbol - utilisé par market_check.py pour ne JAMAIS calculer
de variation sur un titre dont le marché n'a pas encore ouvert
aujourd'hui.

Contexte (bug du 12/08/2026) : les tickers US remontaient une
"variation" avant 15h30 heure de Paris alors que leur session n'avait pas
commencé - price.php/Google Finance renvoie visiblement un prix
pré-marché/indicatif peu fiable avant l'ouverture officielle, pas
représentatif du "mouvement de session" recherché par cette
fonctionnalité.

Toutes les places européennes du portefeuille (Paris, Amsterdam, Milan,
Madrid, Francfort, Zurich) partagent le même fuseau horaire que Paris et
ouvrent à 09h00 heure locale - un seul horaire suffit pour les 6 suffixes
actuellement présents (AS/DE/MC/MI/PA/SW). Marge de sécurité de 15 min
appliquée uniformément (demandée par l'utilisateur pour les US -
généralisée ici car le même risque existe pour toute place vérifiée trop
tôt après sa propre ouverture).
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

PARIS_TZ = ZoneInfo("Europe/Paris")
SAFETY_BUFFER_MINUTES = 15

# (heure, minute) d'ouverture LOCALE PARIS, AVANT marge de sécurité.
# "" = pas de suffixe (US, Nasdaq/NYSE).
OPEN_TIME_PARIS = {
    "": time(15, 30),    # US (Nasdaq/NYSE), 9h30 ET
    "AS": time(9, 0),    # Amsterdam
    "DE": time(9, 0),    # Francfort/Xetra
    "MC": time(9, 0),    # Madrid
    "MI": time(9, 0),    # Milan
    "PA": time(9, 0),    # Paris
    "SW": time(9, 0),    # Zurich/SIX
}
DEFAULT_OPEN_TIME_PARIS = time(9, 0)  # repli pour un suffixe non liste


def _suffix(yahoo_symbol: str) -> str:
    return yahoo_symbol.split(".")[-1] if "." in yahoo_symbol else ""


def market_has_opened(yahoo_symbol: str, now_paris: datetime = None) -> bool:
    """True si la place boursiere de ce ticker a ouvert AUJOURD'HUI, marge
    de securite (SAFETY_BUFFER_MINUTES) incluse."""
    now_paris = now_paris or datetime.now(PARIS_TZ)
    open_t = OPEN_TIME_PARIS.get(_suffix(yahoo_symbol), DEFAULT_OPEN_TIME_PARIS)
    open_dt = now_paris.replace(hour=open_t.hour, minute=open_t.minute, second=0, microsecond=0)
    return now_paris >= open_dt + timedelta(minutes=SAFETY_BUFFER_MINUTES)
