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
import feedparser
from datetime import datetime, timezone

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # garantit que lib/ est trouve quel que soit l'environnement d'execution

from lib.state import (
    get_window_start, make_id, load_manifest, load_news_sources,
    load_existing_news, write_artifact,
)


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


def collect_for_ticker(ticker: str, feed_url: str, window_start: datetime, existing_ids: set):
    items = []
    try:
        parsed = feedparser.parse(feed_url)
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
