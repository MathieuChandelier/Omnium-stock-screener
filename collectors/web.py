"""
collectors/web.py

Collecteur 2/3 : web généraliste (actualités, notes de brokers) via l'API
Anthropic + l'outil web_search, un appel par ticker.

Garantie de fraîcheur : PROBABILISTE côté modèle, DETERMINISTE côté code.
1. Le prompt reçoit la fenêtre exacte (bornes explicites, pas "récent") et
   la liste des titres déjà en base pour ce ticker (contexte anti-doublon),
   avec instruction stricte : ne retourner que des FAITS dont l'événement
   sous-jacent (pas la republication) tombe dans la fenêtre, et REJETER
   plutôt qu'inclure si la date ne peut pas être établie avec confiance.
2. Indépendamment de ce que le modèle décide, le code rejette mécaniquement
   tout item dont dateEvenement sort de la fenêtre ou est absent/invalide.
   C'est ce filtre code qui constitue la vraie garantie, pas le prompt.

Usage : python web.py
Nécessite ANTHROPIC_API_KEY en variable d'environnement.
Écrit artifacts/web.json.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

import anthropic

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

MODEL = "claude-sonnet-5"
EXISTING_CONTEXT_DAYS = 14  # fenêtre du contexte anti-doublon envoyé au modèle
MAX_ITEMS_PER_TICKER = 8
MAX_SEARCHES_PER_TICKER = 2  # plafonne le cout : voir max_uses sur l'outil web_search
DEBUG_PREVIEW_CHARS = 300  # longueur de l'extrait logue en cas d'echec de parsing


def build_prompt(company_name: str, window_start: datetime, window_end: datetime, existing_titles: list) -> str:
    existing_block = (
        "\n".join(f"- {t}" for t in existing_titles) if existing_titles
        else "(aucun item récent en base)"
    )
    return f"""Cherche les actualités et notes d'analystes/brokers concernant la société "{company_name}" publiées ou survenues entre {window_start.strftime('%Y-%m-%d %H:%M UTC')} et {window_end.strftime('%Y-%m-%d %H:%M UTC')}.

RÈGLE CRITIQUE - à respecter strictement :
Ne retourne un item QUE si le FAIT lui-même (publication de résultats, changement de rating/objectif de cours par un broker, déclaration officielle, annonce M&A, etc.) s'est produit dans cette fenêtre. Un article publié dans la fenêtre mais qui commente, résume ou reprend tardivement un événement ANTÉRIEUR à la fenêtre ne doit PAS être inclus, même si l'article lui-même est récent.

Si tu ne peux pas établir avec confiance la date du fait sous-jacent (pas seulement la date de publication de l'article), N'INCLUS PAS l'item - le rejet est préférable à une inclusion incertaine.

Items déjà connus pour ce ticker (ne les inclus pas à nouveau, même relayés par une autre source) :
{existing_block}

Réponds UNIQUEMENT avec un tableau JSON strict, sans texte avant/après, sans balises markdown, format exact :
[{{"title": "...", "source": "...", "url": "...", "dateEvenement": "YYYY-MM-DD"}}]

Si aucun item pertinent n'est trouvé, réponds avec un tableau vide : []
Maximum {MAX_ITEMS_PER_TICKER} items, les plus significatifs uniquement."""


def extract_json_array(text: str):
    """Extrait le tableau JSON de la réponse du modèle.

    Robuste au fait que le modèle, malgré la consigne stricte, ajoute
    parfois une courte phrase d'introduction ou une citation avant/après
    le tableau (constaté en pratique avec l'outil web_search : 100% des
    réponses échouaient au parsing strict avant ce correctif, alors que le
    JSON attendu était bien présent dans le texte). On cherche donc la
    PREMIERE structure [...] dans le texte plutôt que d'exiger une
    correspondance exacte sur l'ensemble de la réponse."""
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
        # max_uses plafonne le nombre de recherches web par appel - sans
        # cette borne, le modele peut enchainer plusieurs recherches par
        # ticker sans limite, ce qui a fait deraper le cout d'un run complet
        # bien au-dela de l'estimation (voir diagnostic du run #9).
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": MAX_SEARCHES_PER_TICKER}],
        messages=[{"role": "user", "content": prompt}],
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
        # Extrait de la reponse brute loggue pour pouvoir diagnostiquer SANS
        # relancer un run payant a l'aveugle si ce cas se represente sous
        # une forme differente (ex. le modele ignore completement la
        # consigne de format plutot que d'ajouter juste une phrase autour).
        preview = raw_text[:DEBUG_PREVIEW_CHARS].replace("\n", " ")
        print(f"  [WARN] {ticker}: réponse non-JSON, ignorée - extrait: {preview!r}", file=sys.stderr)
        return [], "error"

    items = []
    for entry in parsed:
        title = (entry.get("title") or "").strip()
        url = (entry.get("url") or "").strip()
        date_str = (entry.get("dateEvenement") or "").strip()
        if not title or not url or not date_str:
            continue  # champ requis manquant -> rejet, pas de best-effort

        try:
            event_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            continue  # date mal formée -> rejet déterministe côté code

        if event_date < window_start or event_date > window_end:
            continue  # hors fenêtre -> rejet déterministe côté code, quel que soit l'avis du modèle

        item_id = make_id(url, title)
        if item_id in existing_ids:
            continue

        items.append({
            "id": item_id,
            "ticker": ticker,
            "type": "web",
            "dateEvenement": date_str,
            "dateCollecte": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "title": title,
            "source": (entry.get("source") or "Web").strip(),
            "url": url,
        })

    return items, "ok"


def main():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERREUR] ANTHROPIC_API_KEY absente - collecteur web skippé entièrement", file=sys.stderr)
        write_artifact("web", [])
        return 1

    client = anthropic.Anthropic(api_key=api_key)
    manifest = load_manifest()
    window_start = get_window_start("web")
    window_end = datetime.now(timezone.utc)

    all_items = []
    error_count = 0
    for ticker in manifest:
        tdata = load_ticker_json(ticker) or {}
        name = tdata.get("name", ticker)
        existing = load_existing_news(ticker)

        items, status = collect_for_ticker(client, ticker, name, window_start, window_end, existing)
        if status == "error":
            error_count += 1
        all_items.extend(items)

    write_artifact("web", all_items)
    print(f"[web] {len(all_items)} nouveaux items, {error_count} tickers en erreur sur {len(manifest)}")

    # Erreur bloquante seulement si (quasi) tout a échoué - un ou deux
    # tickers en erreur isolée ne doit pas marquer tout le collecteur "error"
    # dans newsState.json (voir merge.py : "error" empêche l'avancée de la
    # fenêtre pour ce collecteur).
    if manifest and error_count >= len(manifest) * 0.8:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
