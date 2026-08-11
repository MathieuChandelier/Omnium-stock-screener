"""
collectors/communiques.py

Collecteur 1/3 : communiqués officiels / IR, via flux RSS/Atom déclarés
dans data/newsSources.json (irFeedUrl + irFeedType).

Garantie de fraîcheur : NATIVE, pas de jugement à faire.
- id = hash(url du communiqué) -> dédup mécanique par GUID/URL.
- inclusion = date de publication du flux > fenêtre de fraîcheur.
Aucune logique de "est-ce déjà connu" au sens flou : soit l'URL est déjà
en base (skip), soit la date est hors fenêtre (skip), soit c'est nouveau.

Tickers sans irFeedUrl configuré (ou valant null) : skip propre, loggé
dans le résumé de run, jamais une erreur bloquante - voir §1 de la
conversation de design (Operation A pourra le compléter au fil de l'eau).

Usage : python communiques.py
Écrit artifacts/communiques.json (liste d'items, tous tickers confondus,
avec le champ "ticker" ajouté par item pour que le job merge sache où
les ranger).
"""

import sys
import time
import feedparser
from datetime import datetime, timezone

import importlib.util as _ilu

def _load_state_module():
    """Charge lib/state.py par son chemin de fichier absolu, sans dependre
    de sys.path ni du mecanisme de resolution de paquets Python - la
    tentative precedente (sys.path.insert + "from lib.state import")
    echouait sur le runner GitHub Actions (ModuleNotFoundError: No module
    named 'lib') pour une raison d'environnement non elucidee ; le
    chargement par chemin de fichier explicite est immune a ce type de
    probleme, quel que soit l'environnement d'execution."""
    import os
    state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib", "state.py")
    spec = _ilu.spec_from_file_location("omnium_news_state", state_path)
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

_state = _load_state_module()
get_window_start = _state.get_window_start
make_id = _state.make_id
load_manifest = _state.load_manifest
load_news_sources = _state.load_news_sources
load_existing_news = _state.load_existing_news
write_artifact = _state.write_artifact


def parse_entry_date(entry):
    """feedparser normalise déjà published_parsed/updated_parsed en
    struct_time UTC quand le flux est correctement formé - c'est la date
    de publication du FLUX (donc du communiqué lui-même pour un diffuseur
    réglementé comme GlobeNewswire/Actusnews), pas une date déduite."""
    for field in ("published_parsed", "updated_parsed"):
        t = entry.get(field)
        if t:
            return datetime(*t[:6], tzinfo=timezone.utc)
    return None



# SEC EDGAR (et d'autres emetteurs) rejettent les requetes sans User-Agent
# identifiable (403) - feedparser envoie sinon son propre UA generique,
# invisible a l'oeil (bozo=1, aucun message d'erreur explicite) tant qu'on
# n'a pas compare avec/sans ce header. Voir politique SEC :
# https://www.sec.gov/os/webmaster-faq#developers
REQUEST_HEADERS = {"User-Agent": "Omnium Invest research (contact via GitHub repo)"}


def fetch_feed(feed_url: str):
    """Recupere et parse un flux, avec retry (backoff croissant) en cas
    d'echec - observe en pratique sur sec.gov : des requetes repetees
    depuis la meme IP declenchent un throttling TRANSITOIRE (403) meme
    avec un User-Agent conforme, alors qu'une requete isolee reussit
    systematiquement. Cout nul dans le cas normal (aucun retry declenche),
    n'allonge le run que dans le cas degrade ou ca protege justement contre
    un flux marque 'casse' pour la journee a tort."""
    delays = (1.5, 3.0)
    parsed = feedparser.parse(feed_url, request_headers=REQUEST_HEADERS)
    for delay in delays:
        if not (parsed.bozo and not parsed.entries and parsed.get("status") in (403, 429, 503)):
            break
        time.sleep(delay)
        parsed = feedparser.parse(feed_url, request_headers=REQUEST_HEADERS)
    return parsed


def collect_for_ticker(ticker: str, feed_url: str, window_start: datetime, existing_ids: set):
    items = []
    try:
        parsed = fetch_feed(feed_url)
    except Exception as e:
        print(f"  [ERREUR] {ticker}: échec parsing flux ({e})", file=sys.stderr)
        return items, "error"

    if parsed.bozo and not parsed.entries:
        # Flux illisible / structure cassée (ex. refonte du site IR) :
        # on ne bloque pas le run, on signale pour réparation ultérieure.
        print(f"  [WARN] {ticker}: flux illisible ou vide (bozo={parsed.bozo})", file=sys.stderr)
        return items, "broken"

    for entry in parsed.entries:
        url = entry.get("link")
        if not url:
            continue
        item_id = make_id(url)
        if item_id in existing_ids:
            continue  # déjà en base, dédup mécanique par id

        pub_date = parse_entry_date(entry)
        if pub_date is None or pub_date < window_start:
            continue  # hors fenêtre de fraîcheur - rejet déterministe

        items.append({
            "id": item_id,
            "ticker": ticker,
            "type": "communique",
            "dateEvenement": pub_date.strftime("%Y-%m-%d"),
            "dateCollecte": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "title": entry.get("title", "").strip(),
            "source": parsed.feed.get("title", "IR").strip(),
            "url": url,
        })

    return items, "ok"


def main():
    manifest = load_manifest()
    sources = load_news_sources()
    window_start = get_window_start("communiques")

    all_items = []
    skipped_unconfigured = []
    broken_feeds = []

    for ticker in manifest:
        cfg = sources.get(ticker) or {}
        feed_url = cfg.get("irFeedUrl")
        if not feed_url:
            skipped_unconfigured.append(ticker)
            continue

        existing = load_existing_news(ticker)
        existing_ids = {it["id"] for it in existing}

        items, status = collect_for_ticker(ticker, feed_url, window_start, existing_ids)
        if status == "broken":
            broken_feeds.append(ticker)
        all_items.extend(items)

        # Pause entre chaque flux : la majorite pointe vers sec.gov (34/57
        # tickers) qui applique un throttling transitoire sur les rafales
        # de requetes meme avec un User-Agent conforme (voir fetch_feed) -
        # 0.5s empiriquement suffisant pour eliminer les echecs constates
        # a 0.25s (teste le 11/08/2026 : 34/34 flux EDGAR OK a 0.5s contre
        # de multiples echecs a 0.25s). Cout total ~30s sur le portefeuille,
        # negligeable face au budget du job.
        time.sleep(0.5)

    write_artifact("communiques", all_items)

    print(f"[communiques] {len(all_items)} nouveaux items, "
          f"{len(skipped_unconfigured)} tickers non configurés, "
          f"{len(broken_feeds)} flux cassés")
    if skipped_unconfigured:
        print(f"  non configurés : {', '.join(skipped_unconfigured)}")
    if broken_feeds:
        print(f"  flux cassés : {', '.join(broken_feeds)}")

    # Le job merge lit ce statut pour décider si collectorsStatus.communiques
    # doit rester "ok" ou passer à "partial" (n'empêche jamais le run global).
    return 0


if __name__ == "__main__":
    sys.exit(main())
