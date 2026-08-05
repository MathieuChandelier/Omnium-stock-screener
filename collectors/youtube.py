"""
collectors/youtube.py

Collecteur 3/3 : interviews CEO/PDG via l'API YouTube Data v3.

Garantie de fraîcheur : NATIVE, pas de jugement à faire.
publishedAfter est un paramètre de l'API elle-même - YouTube ne retourne
que des vidéos publiées après cette date, ce n'est pas un filtre appliqué
après coup côté script.

Dédup : par videoId (unique par nature, pas de fuzzy-matching nécessaire).

Usage : python youtube.py
Nécessite YOUTUBE_API_KEY en variable d'environnement.
Écrit artifacts/youtube.json.
"""

import os
import sys
from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

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
load_ticker_json = _state.load_ticker_json
load_existing_news = _state.load_existing_news
write_artifact = _state.write_artifact

MAX_RESULTS_PER_TICKER = 5


def collect_for_ticker(youtube, ticker: str, name: str, window_start: datetime, existing_ids: set):
    query = f'"{name}" CEO PDG interview'
    published_after = window_start.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        request = youtube.search().list(
            part="snippet",
            q=query,
            type="video",
            order="date",
            publishedAfter=published_after,
            maxResults=MAX_RESULTS_PER_TICKER,
        )
        response = request.execute()
    except HttpError as e:
        print(f"  [ERREUR] {ticker}: échec appel YouTube API ({e})", file=sys.stderr)
        return [], "error"

    items = []
    for entry in response.get("items", []):
        video_id = entry.get("id", {}).get("videoId")
        if not video_id:
            continue
        item_id = make_id(video_id)
        if item_id in existing_ids:
            continue

        snippet = entry.get("snippet", {})
        published_at = snippet.get("publishedAt", "")  # ISO8601, ex. 2026-08-04T10:00:00Z
        date_evenement = published_at[:10] if published_at else datetime.now(timezone.utc).strftime("%Y-%m-%d")

        items.append({
            "id": item_id,
            "ticker": ticker,
            "type": "youtube",
            "dateEvenement": date_evenement,
            "dateCollecte": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "title": snippet.get("title", "").strip(),
            "source": snippet.get("channelTitle", "YouTube").strip(),
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "channel": snippet.get("channelTitle", "").strip(),
        })

    return items, "ok"


def main():
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("[ERREUR] YOUTUBE_API_KEY absente - collecteur youtube skippé entièrement", file=sys.stderr)
        write_artifact("youtube", [])
        return 1

    youtube = build("youtube", "v3", developerKey=api_key)
    manifest = load_manifest()
    window_start = get_window_start("youtube")

    all_items = []
    error_count = 0
    for ticker in manifest:
        tdata = load_ticker_json(ticker) or {}
        name = tdata.get("name", ticker)
        existing = load_existing_news(ticker)
        existing_ids = {it["id"] for it in existing}

        items, status = collect_for_ticker(youtube, ticker, name, window_start, existing_ids)
        if status == "error":
            error_count += 1
        all_items.extend(items)

    write_artifact("youtube", all_items)
    print(f"[youtube] {len(all_items)} nouveaux items, {error_count} tickers en erreur sur {len(manifest)}")

    if manifest and error_count >= len(manifest) * 0.8:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
