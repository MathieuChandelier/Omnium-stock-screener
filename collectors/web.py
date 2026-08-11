"""
collectors/web.py

Collecteur 2/3 : web généraliste (actualités, notes de brokers) via l'API
Anthropic + l'outil web_search, appels PARALLELISES (un par ticker).

Garantie de fraîcheur : PROBABILISTE côté modèle, DETERMINISTE côté code.
1. Le prompt reçoit la fenêtre exacte (bornes explicites, pas "récent") et
   la liste des titres déjà en base pour ce ticker (contexte anti-doublon),
   avec instruction stricte : ne retourner que des FAITS dont l'événement
   sous-jacent (pas la republication) tombe dans la fenêtre, et REJETER
   plutôt qu'inclure si la date ne peut pas être établie avec confiance.
2. Indépendamment de ce que le modèle décide, le code rejette mécaniquement
   tout item dont dateEvenement sort de la fenêtre ou est absent/invalide.
   C'est ce filtre code qui constitue la vraie garantie, pas le prompt.

ROTATION A 2 JOURS (cout /2, decision du 11/08/2026) : ce collecteur ne
traite que LA MOITIE du portefeuille par run (alternance deterministe par
parite du jour, voir select_rotation_half) - chaque ticker est donc couvert
par l'IA un jour ouvre sur deux, jamais tous les jours. C'est le seul poste
de cout reel du pipeline (web_search facture au call), les deux autres
collecteurs (communiques.py, gratuit via flux SEC EDGAR/IR officiels ;
youtube.py, quota gratuit) continuent de couvrir TOUS les tickers TOUS les
jours - aucune perte de fraicheur sur les faits reglementaires/officiels,
seule la couche notes de brokers/actualite generaliste passe a J+1 pour la
moitie du portefeuille non tiree aujourd'hui.

BUDGET TEMPS (voir discussion de design) :
- Visée ~60s pour l'ensemble des tickers, via parallelisation (MAX_CONCURRENCY
  appels simultanes) plutot qu'un traitement sequentiel un par un.
- Hard stop absolu a HARD_STOP_SECONDS : au-dela, on cesse d'attendre les
  requetes encore en cours, on ecrit l'artifact avec CE QUI A ETE COLLECTE
  jusque-la (jamais un artifact vide par choix, seulement par absence
  reelle de resultats), et on force la sortie du process pour ne jamais
  rester bloque sur un thread encore en attente reseau. Le job merge
  tolere deja un artifact partiel ou absent (voir merge.py) - un hard stop
  ne bloque donc jamais la production de la ligne de notif portefeuille.

Usage : python web.py
Nécessite ANTHROPIC_API_KEY en variable d'environnement.
Écrit artifacts/web.json (complet ou partiel selon le budget temps).
"""

import concurrent.futures
import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone

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

MODEL = "claude-haiku-4-5"  # bascule Sonnet -> Haiku pour reduire le cout par run (voir discussion : ~35-43% de reduction attendue, le web_search reste facture au meme tarif quel que soit le modele)
EXISTING_CONTEXT_DAYS = 14  # fenêtre du contexte anti-doublon envoyé au modèle
MAX_ITEMS_PER_TICKER = 8
MAX_SEARCHES_PER_TICKER = 2  # plafonne le cout par ticker (voir max_uses sur web_search)
DEBUG_PREVIEW_CHARS = 300  # longueur de l'extrait loggue en cas d'echec de parsing

MAX_CONCURRENCY = 20            # appels API simultanes - vise ~60s pour 56 tickers
PER_REQUEST_TIMEOUT_SECONDS = 25  # aucune requete individuelle ne peut depasser ca
HARD_STOP_SECONDS = 90           # budget total absolu, non negociable

# ROTATION A 2 JOURS (reduction de cout /2, decision du 11/08/2026) : ce
# collecteur est le seul poste de cout reel du pipeline (web_search facture
# au call, ~3€/jour a couvrir la totalite du portefeuille chaque jour).
# Plutot que de reduire la qualite par ticker (moins de recherches, prompt
# degrade), on reduit la FREQUENCE par ticker : chaque titre est couvert un
# jour sur deux au lieu de chaque jour, le reste du pipeline (communiques.py,
# gratuit, flux SEC EDGAR/IR officiels) continue de couvrir TOUS les tickers
# TOUS les jours - aucune perte de fraicheur sur les faits les plus
# importants (resultats, depots reglementaires), seule la couche notes de
# brokers/actualite generaliste passe a une cadence 1 jour sur 2 par titre.
# Alternance DETERMINISTE sans etat externe (pas de fichier a maintenir, pas
# de risque de derive) : parite du jour ordinal (proleptic Gregorian, stable
# et continu meme apres un week-end ou un jour sans run).


def select_rotation_half(manifest: list) -> list:
    """Retourne la moitie du portefeuille a traiter AUJOURD'HUI. Split par
    parite d'INDEX (pas en deux blocs contigus) pour eviter qu'un
    regroupement geographique/sectoriel fortuit dans manifest.json ne
    biaise systematiquement quelle moitie du portefeuille est couverte tel
    ou tel jour de la semaine."""
    parity = date.today().toordinal() % 2
    return [t for i, t in enumerate(manifest) if i % 2 == parity]


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
        # ticker sans limite, ce qui a fait deraper le cout d'un run.
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
        # Extrait de la reponse brute loggue pour pouvoir diagnostiquer SANS
        # relancer un run payant a l'aveugle si ce cas se represente sous
        # une forme differente.
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
    started_at = time.monotonic()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERREUR] ANTHROPIC_API_KEY absente - collecteur web skippé entièrement", file=sys.stderr)
        write_artifact("web", [])
        return 1

    client = anthropic.Anthropic(api_key=api_key, timeout=PER_REQUEST_TIMEOUT_SECONDS)
    manifest = load_manifest()
    todays_tickers = select_rotation_half(manifest)
    # La fenetre de fraicheur reste globale (depuis le dernier run reussi,
    # peu importe quels tickers y ont ete traites) : un ticker saute hier
    # est donc bien couvert sur les DERNIERES 48h aujourd'hui, jamais un
    # trou silencieux - voir get_window_start dans lib/state.py.
    window_start = get_window_start("web")
    window_end = datetime.now(timezone.utc)

    all_items = []
    error_count = 0
    completed_count = 0

    # Soumission de la moitie du jour en parallele (jusqu'a MAX_CONCURRENCY
    # requetes API simultanees) plutot qu'un traitement sequentiel - c'est
    # ce qui fait passer le temps total de plusieurs minutes a ~30s pour
    # cette moitie du portefeuille.
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENCY)
    future_to_ticker = {}
    for ticker in todays_tickers:
        tdata = load_ticker_json(ticker) or {}
        name = tdata.get("name", ticker)
        existing = load_existing_news(ticker)
        fut = executor.submit(collect_for_ticker, client, ticker, name, window_start, window_end, existing)
        future_to_ticker[fut] = ticker

    # HARD STOP : on n'attend jamais plus de HARD_STOP_SECONDS au total,
    # meme si des requetes sont encore en cours. concurrent.futures.wait
    # avec timeout retourne immediatement passe ce delai, avec les futures
    # non terminees dans "not_done" - on ne bloque jamais dessus.
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
        print(f"[web] HARD STOP a {HARD_STOP_SECONDS}s atteint - {len(skipped_tickers)} tickers non traites, "
              f"artifact ecrit avec les {completed_count} tickers deja termines : {', '.join(skipped_tickers[:10])}"
              f"{' ...' if len(skipped_tickers) > 10 else ''}")

    # Ecriture INCONDITIONNELLE de l'artifact - complet ou partiel, c'est
    # toujours ce qui a ete reellement collecte jusqu'ici. Le job merge
    # (voir merge.py) traite un artifact partiel exactement comme un
    # artifact complet : rien a adapter de ce cote-la.
    write_artifact("web", all_items)

    elapsed = time.monotonic() - started_at
    print(f"[web] {len(all_items)} nouveaux items, {error_count} tickers en erreur, "
          f"{completed_count}/{len(todays_tickers)} tickers traites (rotation : "
          f"{len(todays_tickers)}/{len(manifest)} du portefeuille aujourd'hui) en {elapsed:.1f}s")

    # Sortie forcee et immediate : evite tout risque de rester accroche a
    # un thread du pool encore en attente reseau apres le hard stop (les
    # threads de ThreadPoolExecutor ne sont pas daemon par defaut, donc un
    # simple retour de main() attendrait leur fin naturelle - potentiellement
    # bien au-dela des 90s promis). os._exit() termine le process tout de
    # suite, sans attendre quoi que ce soit d'autre.
    #
    # Code de sortie : jamais bloquant pour merge (voir if: always() sur ce
    # job dans le workflow) - un hard stop ou des erreurs partielles restent
    # une sortie normale, pas un echec du collecteur dans son ensemble.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
