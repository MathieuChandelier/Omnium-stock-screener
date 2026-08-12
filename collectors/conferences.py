"""
collectors/conferences.py

Collecteur dédié, HEBDOMADAIRE et séparé du pipeline quotidien (voir
.github/workflows/conferences-collector.yml) : détection des annonces de
participation à des conférences investisseurs / roadshows (deal ou
non-deal), capital markets days, etc. - via l'API Anthropic + l'outil
web_search, un appel par ticker.

Pourquoi un collecteur séparé plutôt qu'une extension de web.py (décision
du 12/08/2026) :
- Ce type d'événement est rarement déposé en 8-K/6-K (communiques.py ne
  le capte donc quasiment jamais) et n'est pas l'objet du prompt général
  de web.py (résultats/ratings/M&A) - une question de recherche dédiée
  est nécessaire pour maximiser la probabilité de détection.
- Cadence HEBDOMADAIRE choisie car il y a toujours au moins une semaine
  entre l'annonce d'une conférence et l'événement lui-même (délai
  suffisant côté utilisateur pour l'ajouter à son agenda) - ce qui permet
  de couvrir TOUS les tickers à CHAQUE run (pas de rotation, contrairement
  à web.py) tout en gardant un coût marginal faible : le coût total
  hebdomadaire de ce collecteur est de l'ordre de 2 runs de web.py sur
  l'ensemble du portefeuille, mais espacé sur 7 jours plutôt que quotidien.

Garantie de fraîcheur : fenêtre glissante propre à ce collecteur, PAS
partagée avec data/newsState.json (voir data/conferencesState.json et
merge_conferences.py) - get_window_start() de lib/state.py ignore en
réalité son paramètre collector_name et ne gère qu'UNE fenêtre globale
partagée par communiques/web/youtube ; la réutiliser ici donnerait une
fenêtre ~quotidienne (alignée sur le pipeline quotidien) au lieu d'une
fenêtre ~hebdomadaire, ce qui manquerait des annonces faites entre deux
runs. D'où un état totalement indépendant.

Usage : python conferences.py
Nécessite ANTHROPIC_API_KEY en variable d'environnement.
Écrit artifacts/conferences.json (complet ou partiel selon le budget temps).
"""

import concurrent.futures
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import anthropic

import importlib.util as _ilu

def _load_state_module():
    """Charge lib/state.py par son chemin de fichier absolu - voir la même
    note dans les autres collecteurs (ModuleNotFoundError observé sur le
    runner GitHub Actions avec un import relatif classique)."""
    import os
    state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib", "state.py")
    spec = _ilu.spec_from_file_location("omnium_news_state", state_path)
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

_state = _load_state_module()
make_id = _state.make_id
load_manifest = _state.load_manifest
load_ticker_json = _state.load_ticker_json
load_existing_news = _state.load_existing_news
write_artifact = _state.write_artifact

MODEL = "claude-haiku-4-5"
CONF_STATE_PATH = "data/conferencesState.json"
# Cadence hebdo (7j) + marge de securite pour absorber un run en retard
# (schedule GitHub Actions "best effort", cf. commentaire dans le workflow
# quotidien) sans laisser de trou silencieux.
DEFAULT_LOOKBACK_DAYS = 10
EXISTING_CONTEXT_DAYS = 30  # fenetre anti-doublon plus large qu'en quotidien (cadence hebdo)
MAX_ITEMS_PER_TICKER = 5
MAX_SEARCHES_PER_TICKER = 2
DEBUG_PREVIEW_CHARS = 300

# Pas de rotation ici (contrairement a web.py) : TOUS les tickers a CHAQUE
# run, cf. docstring du module - le budget temps doit donc couvrir
# l'integralite du portefeuille (57 tickers), pas la moitie.
MAX_CONCURRENCY = 20
PER_REQUEST_TIMEOUT_SECONDS = 25
HARD_STOP_SECONDS = 180


def _load_conf_state():
    if not os.path.exists(CONF_STATE_PATH):
        return {"lastSuccessfulRun": None}
    try:
        with open(CONF_STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"lastSuccessfulRun": None}


def get_conf_window_start() -> datetime:
    """Lecture seule ici (l'ecriture de lastSuccessfulRun se fait dans
    merge_conferences.py, apres le job de fusion - voir la docstring de ce
    module pour le detail de pourquoi ce collecteur ne peut pas ecrire son
    propre etat depuis ce job)."""
    state = _load_conf_state()
    last = state.get("lastSuccessfulRun")
    if last:
        try:
            return datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc) - timedelta(days=DEFAULT_LOOKBACK_DAYS)


def build_prompt(company_name: str, window_start: datetime, window_end: datetime, existing_titles: list) -> str:
    existing_block = (
        "\n".join(f"- {t}" for t in existing_titles) if existing_titles
        else "(aucun item récent en base)"
    )
    return f"""Cherche si la société "{company_name}" a ANNONCÉ, entre le {window_start.strftime('%Y-%m-%d')} et le {window_end.strftime('%Y-%m-%d')}, sa participation à :
- une conférence investisseurs organisée par une banque/broker (ex: Morgan Stanley, Goldman Sachs, J.P. Morgan, BofA, UBS, Jefferies, etc.)
- un roadshow (deal ou non-deal)
- un capital markets day / investor day
- tout événement similaire destiné aux investisseurs, avec ou sans webcast public

RÈGLE CRITIQUE :
Ne retourne un item QUE si l'ANNONCE elle-même (pas la tenue de l'événement) a été publiée dans cette fenêtre. Inclus les événements déjà passés à ce jour si leur annonce est tombée dans la fenêtre. Si tu ne peux pas établir avec confiance la date de l'annonce, N'INCLUS PAS l'item.

Indique la date de l'événement lui-même (pas seulement la date d'annonce) directement dans le titre si elle est connue, ainsi que la banque/broker organisateur et la mention d'un webcast si disponible.

Items déjà connus pour ce ticker (ne les inclus pas à nouveau) :
{existing_block}

Réponds UNIQUEMENT avec un tableau JSON strict, sans texte avant/après, sans balises markdown, format exact :
[{{"title": "...", "source": "...", "url": "...", "dateEvenement": "YYYY-MM-DD"}}]

"dateEvenement" = date de l'ANNONCE (format YYYY-MM-DD). Si aucun événement pertinent trouvé, réponds avec un tableau vide : []
Maximum {MAX_ITEMS_PER_TICKER} items."""


def extract_json_array(text: str):
    """Voir web.py::extract_json_array - même logique, même raison d'être
    (le modèle ajoute parfois une phrase avant/après le JSON malgré la
    consigne stricte)."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    match = re.search(r"\[.*\]", text, re.S)
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        return None


def call_model(client, prompt: str):
    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": MAX_SEARCHES_PER_TICKER}],
        messages=[{"role": "user", "content": prompt}],
        timeout=PER_REQUEST_TIMEOUT_SECONDS,
    )
    text_parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    return "\n".join(text_parts)


def collect_for_ticker(client, ticker: str, name: str, window_start: datetime, window_end: datetime, existing: list):
    existing_titles = [it["title"] for it in existing[:EXISTING_CONTEXT_DAYS]]
    existing_ids = {it["id"] for it in existing}

    prompt = build_prompt(name, window_start, window_end, existing_titles)
    try:
        raw_text = call_model(client, prompt)
    except Exception as e:
        print(f"  [ERREUR] {ticker}: échec appel API ({e})", file=sys.stderr)
        return [], "error"

    parsed = extract_json_array(raw_text)
    if parsed is None:
        preview = raw_text[:DEBUG_PREVIEW_CHARS].replace("\n", " ")
        print(f"  [WARN] {ticker}: réponse non-JSON, ignorée - extrait: {preview!r}", file=sys.stderr)
        return [], "error"

    items = []
    for entry in parsed:
        title = (entry.get("title") or "").strip()
        url = (entry.get("url") or "").strip()
        date_str = (entry.get("dateEvenement") or "").strip()
        if not title or not url or not date_str:
            continue

        try:
            event_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue

        if event_date < window_start or event_date > window_end:
            continue

        item_id = make_id(url, title)
        if item_id in existing_ids:
            continue

        items.append({
            "id": item_id,
            "ticker": ticker,
            "type": "conference",
            "dateEvenement": date_str,
            "dateCollecte": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "title": title,
            "source": (entry.get("source") or "Web").strip(),
            "url": url,
        })

    return items, "ok"


def main():
    started_at = time.monotonic()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERREUR] ANTHROPIC_API_KEY absente - collecteur conferences skippé entièrement", file=sys.stderr)
        write_artifact("conferences", [])
        return 1

    client = anthropic.Anthropic(api_key=api_key, timeout=PER_REQUEST_TIMEOUT_SECONDS)
    manifest = load_manifest()  # TOUS les tickers, pas de rotation (voir docstring)
    window_start = get_conf_window_start()
    window_end = datetime.now(timezone.utc)

    all_items = []
    error_count = 0
    completed_count = 0

    executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENCY)
    future_to_ticker = {}
    for ticker in manifest:
        tdata = load_ticker_json(ticker) or {}
        name = tdata.get("name", ticker)
        existing = load_existing_news(ticker)
        fut = executor.submit(collect_for_ticker, client, ticker, name, window_start, window_end, existing)
        future_to_ticker[fut] = ticker

    remaining = max(0.0, HARD_STOP_SECONDS - (time.monotonic() - started_at))
    done, not_done = concurrent.futures.wait(
        future_to_ticker.keys(), timeout=remaining, return_when=concurrent.futures.ALL_COMPLETED
    )

    for fut in done:
        ticker = future_to_ticker[fut]
        try:
            items, status = fut.result()
        except Exception as e:
            print(f"  [ERREUR] {ticker}: exception non geree ({e})", file=sys.stderr)
            items, status = [], "error"
        if status == "error":
            error_count += 1
        completed_count += 1
        all_items.extend(items)

    if not_done:
        skipped_tickers = [future_to_ticker[f] for f in not_done]
        print(f"[conferences] HARD STOP a {HARD_STOP_SECONDS}s atteint - {len(skipped_tickers)} tickers non traites, "
              f"artifact ecrit avec les {completed_count} tickers deja termines : {', '.join(skipped_tickers[:10])}"
              f"{' ...' if len(skipped_tickers) > 10 else ''}")

    write_artifact("conferences", all_items)

    elapsed = time.monotonic() - started_at
    print(f"[conferences] {len(all_items)} nouveaux items, {error_count} tickers en erreur, "
          f"{completed_count}/{len(manifest)} tickers traites en {elapsed:.1f}s "
          f"(fenetre : {window_start.strftime('%Y-%m-%d')} -> {window_end.strftime('%Y-%m-%d')})")

    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
