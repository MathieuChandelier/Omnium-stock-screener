"""
collectors/web.py

Collecteur web généraliste (actualités, notes de brokers) via l'API
Anthropic + l'outil web_search, appels PARALLELISES (un par ticker).

BASCULE HEBDOMADAIRE + SONNET + CLASSEMENT PAR IMPACT (décision du
17/08/2026, remplace la rotation à 2 jours en Haiku) :
- Couverture : TOUS les tickers du portefeuille à CHAQUE run (fini la
  rotation par moitié), mais un run par SEMAINE au lieu de 5 par semaine
  (voir .github/workflows/web-collector.yml, cron hebdo isolé du pipeline
  quotidien communiques/youtube - même schéma que conferences.py/
  merge_conferences.py, voir leurs docstrings pour le détail du pourquoi
  d'un pipeline séparé et d'un état indépendant).
- Modèle Sonnet plutôt que Haiku : le classement par impact (matérialité
  d'une actualité CONTRE la thèse écrite, pas juste "trouve et résume")
  est un vrai raisonnement, pas de la recherche pure - Haiku suffisait
  pour la première tâche, pas pour la seconde.
- Le facteur "5x moins de runs" compense largement le passage Haiku->
  Sonnet et le budget de recherche plus généreux (MAX_SEARCHES_PER_TICKER
  5 au lieu de 2) : ordre de grandeur de coût comparable ou légèrement
  inférieur au pipeline quotidien précédent (estimation, pas un chiffre
  garanti - voir discussion de design).
- Classement par impact = même appel, prompt étendu : chaque item retenu
  est confronté au contexte de thèse du titre (ancrages, engagements
  structurants, guidance history, résumé - voir build_thesis_context) et
  reçoit une matérialité (nul/faible/moyen/fort) + le mécanisme précis
  touché. Le modèle N'EST JAMAIS chargé de s'auto-limiter à 2 items : le
  CODE force la troncature aux MAX_RETAINED_ITEMS_PER_TICKER items de plus
  haute matérialité après coup (même principe de défiance déjà appliqué
  au filtre de fenêtre de fraîcheur ci-dessous, et à MAX_ITEMS_PER_TICKER
  dans merge.py) - chercher large puis ne garder que le meilleur duo,
  plutôt que demander au modèle de ne chercher que 2 choses.
- max_tokens serré (MAX_TOKENS_RESPONSE) plutôt qu'une notion de "temps
  par item" (qui n'existe pas côté API) : c'est le vrai levier de coût/
  effort pour la longueur de justification produite par item, complété
  par max_uses sur web_search pour l'effort de fouille. PER_REQUEST_
  TIMEOUT_SECONDS / HARD_STOP_SECONDS restent le filet de sécurité pour le
  temps au sens propre (ne jamais rester bloqué sur un appel qui traîne) -
  budgets relevés par rapport à l'ancienne cadence quotidienne car un run
  hebdomadaire n'a plus besoin de tenir en ~60s, seulement de rester dans
  une limite raisonnable et non-bloquante.
- Détection calendrier : dans le même passage, extraction des dates
  d'événement CONFIRMÉES non déjà connues (comparées à data/nextEvents.json)
  - écrites en PROPOSITION (artifacts/webCalendarProposals.json, reprises
    par merge_web.py dans data/calendarProposals.json) plutôt qu'appliquées
  silencieusement : la création de l'événement (Google Calendar ou mise à
  jour de nextEvents.json) reste un geste manuel de l'utilisateur.

Garantie de fraîcheur : PROBABILISTE côté modèle, DETERMINISTE côté code.
1. Le prompt reçoit la fenêtre exacte (bornes explicites, pas "récent") et
   la liste des titres déjà en base pour ce ticker (contexte anti-doublon),
   avec instruction stricte : ne retourner que des FAITS dont l'événement
   sous-jacent (pas la republication) tombe dans la fenêtre, et REJETER
   plutôt qu'inclure si la date ne peut pas être établie avec confiance.
2. Indépendamment de ce que le modèle décide, le code rejette mécaniquement
   tout item dont dateEvenement sort de la fenêtre ou est absent/invalide.
   C'est ce filtre code qui constitue la vraie garantie, pas le prompt.

État de fraîcheur INDÉPENDANT du pipeline quotidien (data/webState.json,
pas data/newsState.json) : même raison que conferences.py/
merge_conferences.py - get_window_start() de lib/state.py ignore en
réalité son paramètre collector_name et ne gère qu'UNE fenêtre globale
partagée par communiques/youtube ; la réutiliser ici donnerait une fenêtre
~quotidienne au lieu de ~hebdomadaire. D'où get_web_window_start() et son
propre fichier d'état ci-dessous, écrit par merge_web.py après le job de
fusion (ce job-ci tourne dans un checkout dont les fichiers locaux ne sont
pas persistés au-delà de l'artifact uploadé).

Usage : python web.py
Nécessite ANTHROPIC_API_KEY en variable d'environnement.
Écrit artifacts/web.json (items) et artifacts/webCalendarProposals.json
(propositions de dates calendrier, peut être absent si aucune proposition).
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
make_id = _state.make_id
load_manifest = _state.load_manifest
load_ticker_json = _state.load_ticker_json
load_existing_news = _state.load_existing_news
write_artifact = _state.write_artifact

MODEL = "claude-sonnet-5"  # bascule Haiku -> Sonnet (voir docstring) : le classement par impact est un vrai raisonnement contre la these, pas de la recherche pure
WEB_STATE_PATH = "data/webState.json"
# Cadence hebdo (7j) + marge de securite pour absorber un run en retard
# (schedule GitHub Actions "best effort") sans laisser de trou silencieux -
# meme valeur/raisonnement que conferences.py.
DEFAULT_LOOKBACK_DAYS = 10
EXISTING_CONTEXT_DAYS = 30  # fenetre anti-doublon (alignee sur la cadence hebdo, comme conferences.py)
MAX_CANDIDATE_ITEMS_PER_TICKER = 6  # ce que le modele est autorise A PROPOSER (chercher large)
MAX_RETAINED_ITEMS_PER_TICKER = 2  # ce que le CODE retient apres tri par materialite (voir docstring) - le vrai plafond
MAX_SEARCHES_PER_TICKER = 5  # budget de recherche genereux (run hebdo, pas quotidien) - voir max_uses sur web_search
MAX_TOKENS_RESPONSE = 800  # serre volontairement : borne la longueur de justification par item, voir docstring
THESIS_CONTEXT_MAX_CHARS = 4000  # garde-fou cout d'entree pour un titre au contexte de these inhabituellement volumineux
DEBUG_PREVIEW_CHARS = 300  # longueur de l'extrait loggue en cas d'echec de parsing

MAX_CONCURRENCY = 20             # appels API simultanes
PER_REQUEST_TIMEOUT_SECONDS = 45   # plus genereux qu'en quotidien (25s) : Sonnet + jusqu'a 5 recherches + raisonnement de materialite prennent plus de temps par appel
HARD_STOP_SECONDS = 450            # 7.5 min - un run hebdomadaire n'a plus besoin de tenir en ~60s, seulement de rester borne et non-bloquant

# PLAFOND DE COUT (decision du 17/08/2026) : filet de securite INDEPENDANT du
# reste du design (budget de recherche, max_tokens par item, etc.) - si un
# bug fait deraper la consommation malgre tout, ce plafond borne le degat
# reel plutot que de compter sur la justesse du reste du code. Converti en
# tokens via le tarif de SORTIE Sonnet 5 ($15/MTok, hors promo) applique a la
# totalite (entree+sortie) : le tarif d'entree est moins cher, donc ce calcul
# sous-estime volontairement le nombre de tokens autorises - le cout reel
# reste toujours EN-DECA de MAX_COST_BUDGET_EUR, quel que soit le vrai mix
# entree/sortie. EUR traite comme equivalent 1 USD (approximation defavorable
# elle aussi - le taux reel EUR/USD > 1 rendrait la marge plus confortable,
# jamais moins). Ne couvre PAS le cout web_search (facture au call, deja
# borne structurellement par MAX_SEARCHES_PER_TICKER x taille du portefeuille
# = 58 x 5 = 290 recherches max = ~2,90$ - un plafond separe n'y ajouterait
# rien puisque ce nombre ne peut pas deraper independamment des tokens).
#
# Verifie au fur et a mesure que les tickers se terminent (voir main()) :
# une fois franchi, plus aucun NOUVEAU ticker n'est lance (les futures pas
# encore demarrees sont annulees), mais les appels deja en cours vont
# jusqu'au bout - jamais d'interruption brutale d'un call, meme logique que
# HARD_STOP_SECONDS. Marge de depassement possible : au plus MAX_CONCURRENCY
# appels encore en vol au moment du franchissement (~20 x 3700 tokens de
# reference =~ 74k tokens =~ 1,10$ de plus dans le pire cas).
MAX_COST_BUDGET_EUR = 5.0
SONNET_OUTPUT_PRICE_PER_MTOK_USD = 15.0
MAX_TOKENS_BUDGET = int(MAX_COST_BUDGET_EUR * 1_000_000 / SONNET_OUTPUT_PRICE_PER_MTOK_USD)

MATERIALITE_ORDER = {"fort": 3, "moyen": 2, "faible": 1, "nul": 0}
MATERIALITES_VALIDES = set(MATERIALITE_ORDER)

NEXT_EVENTS_PATH = "data/nextEvents.json"
CALENDAR_PROPOSALS_ARTIFACT = "webCalendarProposals"


def _load_web_state():
    if not os.path.exists(WEB_STATE_PATH):
        return {"lastSuccessfulRun": None}
    try:
        with open(WEB_STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"lastSuccessfulRun": None}


def get_web_window_start() -> datetime:
    """Lecture seule ici (l'ecriture de lastSuccessfulRun se fait dans
    merge_web.py, apres le job de fusion - voir docstring du module)."""
    state = _load_web_state()
    last = state.get("lastSuccessfulRun")
    if last:
        try:
            return datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc) - timedelta(days=DEFAULT_LOOKBACK_DAYS)


def load_next_events(path=NEXT_EVENTS_PATH) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def build_thesis_context(tdata: dict) -> str:
    """Condense les champs de these pertinents pour le classement par
    impact - ancrages, engagements structurants, historique de guidance,
    resume - en un bloc texte compact injecte dans le prompt. Mesure sur
    les 62 fichiers du portefeuille (17/08/2026) : ~1050 tokens en moyenne
    par titre pour ce jeu de champs precis (voir estimation de cout)."""
    hypothese = tdata.get("hypothese") or {}
    coherence = tdata.get("coherenceQualitative") or {}
    parts = []

    summary = (hypothese.get("summary") or "").strip()
    if summary:
        parts.append(f"Synthese de la these actuelle :\n{summary}")

    ancrages = hypothese.get("ancrages") or []
    if ancrages:
        lines = []
        for a in ancrages:
            moteur = (a.get("moteur") or "").strip()
            if not moteur:
                continue
            applique = ", ".join(a.get("applique") or []) or "n/a"
            lines.append(f"- [{applique}] {moteur}")
        if lines:
            parts.append("Ancrages de these (hypotheses cles qui sous-tendent le modele) :\n" + "\n".join(lines))

    guidance_history = hypothese.get("guidanceHistory") or []
    if guidance_history:
        lines = []
        for g in guidance_history[-5:]:
            if not isinstance(g, dict):
                continue
            quarter = g.get("quarter", "?")
            gdate = g.get("date", "?")
            texte = (g.get("guidanceAnnuelle") or "").strip()
            if texte:
                lines.append(f"- {quarter} ({gdate}) : {texte}")
        if lines:
            parts.append("Historique de guidance :\n" + "\n".join(lines))

    engagements = coherence.get("engagementsStructurants") or []
    if engagements:
        lines = []
        for e in engagements:
            if not isinstance(e, dict):
                continue
            engagement = (e.get("engagement") or "").strip()
            if not engagement:
                continue
            echeance = e.get("echeance", "?")
            statut = e.get("statut", "?")
            lines.append(f"- (echeance {echeance}, statut {statut}) {engagement}")
        if lines:
            parts.append("Engagements structurants suivis :\n" + "\n".join(lines))

    if not parts:
        return "(aucun contexte de these disponible pour ce titre)"

    context = "\n\n".join(parts)
    if len(context) > THESIS_CONTEXT_MAX_CHARS:
        context = context[:THESIS_CONTEXT_MAX_CHARS] + "\n[...tronque]"
    return context


def build_prompt(company_name: str, window_start: datetime, window_end: datetime,
                  existing_titles: list, thesis_context: str, current_next_event: dict) -> str:
    existing_block = (
        "\n".join(f"- {t}" for t in existing_titles) if existing_titles
        else "(aucun item récent en base)"
    )
    next_event_block = (
        f"{current_next_event.get('label', '?')} le {current_next_event.get('date', '?')}"
        if current_next_event else "(aucune date connue)"
    )
    return f"""Cherche les actualités et notes d'analystes/brokers concernant la société "{company_name}" publiées ou survenues entre {window_start.strftime('%Y-%m-%d %H:%M UTC')} et {window_end.strftime('%Y-%m-%d %H:%M UTC')}.

RÈGLE CRITIQUE - à respecter strictement :
Ne retourne un item QUE si le FAIT lui-même (publication de résultats, changement de rating/objectif de cours par un broker, déclaration officielle, annonce M&A, etc.) s'est produit dans cette fenêtre. Un article publié dans la fenêtre mais qui commente, résume ou reprend tardivement un événement ANTÉRIEUR à la fenêtre ne doit PAS être inclus, même si l'article lui-même est récent.

Si tu ne peux pas établir avec confiance la date du fait sous-jacent (pas seulement la date de publication de l'article), N'INCLUS PAS l'item - le rejet est préférable à une inclusion incertaine.

Items déjà connus pour ce ticker (ne les inclus pas à nouveau, même relayés par une autre source) :
{existing_block}

CLASSEMENT PAR IMPACT - pour CHAQUE item retenu, confronte-le au contexte de thèse ci-dessous et assigne :
- "materialite" : une valeur parmi "nul", "faible", "moyen", "fort" - à quel point ce fait remet en cause, confirme ou fait évoluer la thèse écrite (pas l'importance du fait en tant que tel dans l'absolu).
- "mecanisme" : une phrase courte identifiant PRÉCISÉMENT quel ancrage, quelle ligne de projection (ex. adjEBIT.2027) ou quel engagement structurant est touché, ou "aucun mécanisme existant touché" si le fait est notable mais hors thèse.

Contexte de thèse pour ce titre :
{thesis_context}

DÉTECTION CALENDRIER - si tu identifies, dans tes recherches, une date CONFIRMÉE (pas rumeur/estimation) d'un événement à venir (prochains résultats, investor day, capital markets day, etc.), inclus-la dans "calendarEvents" même si elle ne rentre pas dans la fenêtre ci-dessus. Prochaine date actuellement connue en base pour ce titre : {next_event_block} - ne propose que si tu trouves une date DIFFÉRENTE ou plus précise que celle-ci, ou un événement d'un autre type.

Réponds UNIQUEMENT avec un objet JSON strict, sans texte avant/après, sans balises markdown, format exact :
{{"items": [{{"title": "...", "source": "...", "url": "...", "dateEvenement": "YYYY-MM-DD", "materialite": "nul|faible|moyen|fort", "mecanisme": "..."}}], "calendarEvents": [{{"label": "...", "date": "YYYY-MM-DD", "description": "..."}}]}}

Si rien de pertinent, réponds avec des tableaux vides pour les deux clés. Maximum {MAX_CANDIDATE_ITEMS_PER_TICKER} items dans "items"."""


def extract_json_object(text: str):
    """Extrait l'objet JSON de la réponse du modèle - même logique que
    l'ancien extract_json_array (voir historique), adaptee a un objet {{}}
    plutot qu'un tableau [] puisque la reponse porte desormais deux cles
    (items + calendarEvents) au lieu d'un tableau nu."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def call_model(client, prompt: str):
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS_RESPONSE,
        # thinking desactive explicitement : sur Sonnet 5, omettre "thinking"
        # active le raisonnement adaptatif par defaut (contrairement aux
        # versions Sonnet precedentes) - non budgete dans MAX_TOKENS_RESPONSE
        # et non necessaire ici (classement materialite = extraction + jugement
        # court, pas un raisonnement multi-etapes profond).
        thinking={"type": "disabled"},
        # max_uses plafonne le nombre de recherches web par appel - sans
        # cette borne, le modele peut enchainer plusieurs recherches par
        # ticker sans limite, ce qui a fait deraper le cout d'un run.
        # Variante 20260209 (filtrage dynamique) plutot que 20250305 : Sonnet 5
        # la supporte, meilleure qualite de recherche a cout identique (facture
        # au call, pas au token).
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": MAX_SEARCHES_PER_TICKER}],
        messages=[{"role": "user", "content": prompt}],
        timeout=PER_REQUEST_TIMEOUT_SECONDS,
    )
    text_parts = [b.text for b in response.content if getattr(b, "type", None) == "text"]
    tokens_used = response.usage.input_tokens + response.usage.output_tokens
    return "\n".join(text_parts), tokens_used


def rank_and_truncate(items: list) -> list:
    """LE mecanisme qui implemente concretement le classement par impact :
    jamais de confiance aveugle dans l'auto-limitation du modele (meme
    principe que MAX_ITEMS_PER_TICKER dans merge.py) - on trie par
    materialite decroissante et on tranche mecaniquement a
    MAX_RETAINED_ITEMS_PER_TICKER, quel que soit le nombre de candidats
    proposes par le modele."""
    ranked = sorted(items, key=lambda it: MATERIALITE_ORDER.get(it.get("materialite"), 0), reverse=True)
    return ranked[:MAX_RETAINED_ITEMS_PER_TICKER]


def extract_calendar_proposals(ticker: str, candidates: list, current_next_event: dict) -> list:
    current_date = (current_next_event or {}).get("date")
    proposals = []
    for c in candidates:
        if not isinstance(c, dict):
            continue
        label = (c.get("label") or "").strip()
        date_str = (c.get("date") or "").strip()
        if not label or not date_str:
            continue
        try:
            datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue
        if date_str == current_date:
            continue  # deja connu en base, rien a proposer
        proposals.append({
            "ticker": ticker,
            "label": label,
            "date": date_str,
            "description": (c.get("description") or "").strip(),
            "currentNextEvent": current_next_event,
        })
    return proposals


def collect_for_ticker(client, ticker: str, name: str, window_start: datetime, window_end: datetime,
                        existing: list, thesis_context: str, current_next_event: dict):
    existing_titles = [it["title"] for it in existing[:EXISTING_CONTEXT_DAYS]]
    existing_ids = {it["id"] for it in existing}

    prompt = build_prompt(name, window_start, window_end, existing_titles, thesis_context, current_next_event)
    try:
        raw_text, tokens_used = call_model(client, prompt)
    except Exception as e:
        print(f"  [ERREUR] {ticker}: échec appel API ({e})", file=sys.stderr)
        return [], [], "error", 0

    parsed = extract_json_object(raw_text)
    if parsed is None:
        preview = raw_text[:DEBUG_PREVIEW_CHARS].replace("\n", " ")
        print(f"  [WARN] {ticker}: réponse non-JSON, ignorée - extrait: {preview!r}", file=sys.stderr)
        return [], [], "error", tokens_used  # l'appel a quand meme consomme des tokens, meme si le parsing echoue

    candidate_items = []
    for entry in parsed.get("items") or []:
        if not isinstance(entry, dict):
            continue
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

        materialite = (entry.get("materialite") or "").strip().lower()
        if materialite not in MATERIALITES_VALIDES:
            materialite = "nul"  # valeur du modele absente/invalide -> traitee comme non-materielle, jamais promue par defaut

        candidate_items.append({
            "id": item_id,
            "ticker": ticker,
            "type": "web",
            "dateEvenement": date_str,
            "dateCollecte": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "title": title,
            "source": (entry.get("source") or "Web").strip(),
            "url": url,
            "materialite": materialite,
            "mecanisme": (entry.get("mecanisme") or "").strip(),
        })

    retained_items = rank_and_truncate(candidate_items)
    calendar_proposals = extract_calendar_proposals(ticker, parsed.get("calendarEvents") or [], current_next_event)

    return retained_items, calendar_proposals, "ok", tokens_used


def main():
    started_at = time.monotonic()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERREUR] ANTHROPIC_API_KEY absente - collecteur web skippé entièrement", file=sys.stderr)
        write_artifact("web", [])
        return 1

    client = anthropic.Anthropic(api_key=api_key, timeout=PER_REQUEST_TIMEOUT_SECONDS)
    manifest = load_manifest()  # TOUS les tickers, plus de rotation (voir docstring)
    next_events = load_next_events()
    window_start = get_web_window_start()
    window_end = datetime.now(timezone.utc)

    all_items = []
    all_calendar_proposals = []
    error_count = 0
    completed_count = 0
    total_tokens_used = 0
    budget_exceeded = False

    # Soumission de tout le portefeuille en parallele (jusqu'a MAX_CONCURRENCY
    # requetes API simultanees) plutot qu'un traitement sequentiel.
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENCY)
    future_to_ticker = {}
    for ticker in manifest:
        tdata = load_ticker_json(ticker) or {}
        name = tdata.get("name", ticker)
        existing = load_existing_news(ticker)
        thesis_context = build_thesis_context(tdata)
        current_next_event = next_events.get(ticker)
        fut = executor.submit(
            collect_for_ticker, client, ticker, name, window_start, window_end,
            existing, thesis_context, current_next_event,
        )
        future_to_ticker[fut] = ticker

    # Traitement AU FUR ET A MESURE (pas d'attente groupee) pour pouvoir
    # verifier le plafond de cout apres chaque ticker termine, en plus du
    # HARD STOP temps existant. Les deux filets sont independants et peuvent
    # se declencher separement (le premier atteint gagne) - jamais un echec,
    # toujours un artifact ecrit avec ce qui a ete reellement collecte.
    remaining = max(0.0, HARD_STOP_SECONDS - (time.monotonic() - started_at))
    completed_futures = set()
    cancelled_by_budget = []
    try:
        for fut in concurrent.futures.as_completed(future_to_ticker.keys(), timeout=remaining):
            completed_futures.add(fut)
            ticker = future_to_ticker[fut]
            try:
                items, calendar_proposals, status, tokens_used = fut.result()
            except concurrent.futures.CancelledError:
                # Ticker delibirement annule car le plafond etait deja atteint
                # a son tour - pas une erreur, ne compte ni dans error_count
                # ni dans completed_count (voir skipped_tickers plus bas).
                cancelled_by_budget.append(ticker)
                continue
            except Exception as e:
                print(f"  [ERREUR] {ticker}: exception non geree ({e})", file=sys.stderr)
                items, calendar_proposals, status, tokens_used = [], [], "error", 0

            if status == "error":
                error_count += 1
            completed_count += 1
            all_items.extend(items)
            all_calendar_proposals.extend(calendar_proposals)
            total_tokens_used += tokens_used

            if not budget_exceeded and total_tokens_used >= MAX_TOKENS_BUDGET:
                budget_exceeded = True
                # Annule les tickers PAS ENCORE demarres (cancel() ne fait
                # rien sur une future deja en cours d'execution - elle va
                # jusqu'au bout normalement, voir docstring de la constante).
                for other_fut in future_to_ticker:
                    if other_fut not in completed_futures:
                        other_fut.cancel()
    except concurrent.futures.TimeoutError:
        pass  # HARD STOP temps atteint - voir not_done ci-dessous, meme comportement qu'avant

    not_done = [f for f in future_to_ticker if not f.done()]
    skipped_tickers = cancelled_by_budget + [future_to_ticker[f] for f in not_done]
    if skipped_tickers:
        reason = (
            f"plafond de cout atteint (~{MAX_COST_BUDGET_EUR:.0f}EUR, {total_tokens_used} tokens)"
            if budget_exceeded else f"HARD STOP a {HARD_STOP_SECONDS}s atteint"
        )
        print(f"[web] {reason} - {len(skipped_tickers)} tickers non traites, "
              f"artifact ecrit avec les {completed_count} tickers deja termines : {', '.join(skipped_tickers[:10])}"
              f"{' ...' if len(skipped_tickers) > 10 else ''}")

    # Ecriture INCONDITIONNELLE de l'artifact - complet ou partiel, c'est
    # toujours ce qui a ete reellement collecte jusqu'ici. Le job merge
    # (voir merge_web.py) traite un artifact partiel exactement comme un
    # artifact complet : rien a adapter de ce cote-la.
    write_artifact("web", all_items)
    if all_calendar_proposals:
        write_artifact(CALENDAR_PROPOSALS_ARTIFACT, all_calendar_proposals)

    elapsed = time.monotonic() - started_at
    print(f"[web] {len(all_items)} nouveaux items, {len(all_calendar_proposals)} proposition(s) calendrier, "
          f"{error_count} tickers en erreur, {completed_count}/{len(manifest)} tickers traites en {elapsed:.1f}s, "
          f"{total_tokens_used} tokens consommes (plafond {MAX_TOKENS_BUDGET})")

    # Sortie forcee et immediate : evite tout risque de rester accroche a
    # un thread du pool encore en attente reseau apres le hard stop (les
    # threads de ThreadPoolExecutor ne sont pas daemon par defaut, donc un
    # simple retour de main() attendrait leur fin naturelle - potentiellement
    # bien au-dela du budget promis). os._exit() termine le process tout de
    # suite, sans attendre quoi que ce soit d'autre.
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
