"""
collectors/merge_web.py

Job de fusion du collecteur hebdomadaire web.py (voir sa docstring pour le
pourquoi du passage en pipeline séparé du quotidien communiques/youtube).
Réutilise les briques de merge.py (dédup, écriture par ticker, newsAll.json,
notification) mais N'ÉCRIT PAS dans data/newsState.json ni
data/newsDigest.json - ce sont des fichiers du pipeline QUOTIDIEN, et les
deux workflows peuvent tourner à des horaires proches (voir cron respectifs
de web-collector.yml et news-collector.yml) : les toucher depuis ce job
créerait un risque réel de race condition, pas seulement théorique vu leur
proximité d'horaire (même raisonnement que merge_conferences.py).

Ce job gère donc son PROPRE état (data/webState.json), totalement
indépendant, mis à jour ici (pas dans web.py - ce job tourne dans un
checkout git frais qui sera commité/pushé, contrairement au job collecteur
en amont dont les fichiers locaux ne sont pas persistés au-delà de
l'artifact qu'il upload).

En plus du merge standard, reprend artifacts/webCalendarProposals.json
(s'il existe) et fusionne les propositions réellement nouvelles dans
data/calendarProposals.json (PROPOSITION persistante, jamais une écriture
silencieuse dans data/nextEvents.json - la création de l'événement, que ce
soit dans Google Calendar ou dans nextEvents.json, reste un geste manuel de
l'utilisateur qui relit ce fichier).

Usage : python merge_web.py
"""

import json
import os
import sys
from datetime import datetime, timezone

import importlib.util as _ilu


def _load_module(rel_path, mod_name):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)
    spec = _ilu.spec_from_file_location(mod_name, path)
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_merge = _load_module("merge.py", "omnium_merge")
merge_all_items = _merge.merge_all_items
write_per_ticker = _merge.write_per_ticker
write_news_all = _merge.write_news_all
notify = _merge.notify

WEB_STATE_PATH = "data/webState.json"
CALENDAR_PROPOSALS_ARTIFACT_PATH = "artifacts/webCalendarProposals.json"
CALENDAR_PROPOSALS_PATH = "data/calendarProposals.json"
MAX_CALENDAR_PROPOSALS = 50  # garde-fou taille fichier, meme esprit que MAX_ITEMS_PER_TICKER/MAX_DIGEST_DAYS dans merge.py


def update_web_state(run_ok: bool):
    """Miroir de merge_conferences.py::update_conferences_state, sur le
    fichier d'état dédié du collecteur web hebdomadaire (voir docstring du
    module) - la fenêtre ne s'avance que si le run est exploitable, sinon
    elle s'élargit naturellement au run suivant plutôt que de laisser un
    trou silencieux."""
    state = {}
    if os.path.exists(WEB_STATE_PATH):
        try:
            with open(WEB_STATE_PATH, encoding="utf-8") as f:
                state = json.load(f)
        except (json.JSONDecodeError, OSError):
            state = {}

    state["lastRunStatus"] = "ok" if run_ok else "partial"
    if run_ok:
        state["lastSuccessfulRun"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(WEB_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _proposal_key(p):
    return (p.get("ticker"), p.get("date"), p.get("label"))


def merge_calendar_proposals() -> int:
    """Fusionne artifacts/webCalendarProposals.json (propositions de ce
    run, si le collecteur en a trouvé) dans data/calendarProposals.json
    (liste persistante, dédupliquée par ticker+date+label, plafonnée -
    destinée à être relue et triée manuellement par l'utilisateur, pas
    purgée automatiquement ici). Retourne le nombre de propositions
    VRAIMENT nouvelles ajoutées ce run (pour la notification)."""
    if not os.path.exists(CALENDAR_PROPOSALS_ARTIFACT_PATH):
        return 0
    try:
        with open(CALENDAR_PROPOSALS_ARTIFACT_PATH, encoding="utf-8") as f:
            fresh = json.load(f)
    except (json.JSONDecodeError, OSError):
        return 0
    if not fresh:
        return 0

    existing = []
    if os.path.exists(CALENDAR_PROPOSALS_PATH):
        try:
            with open(CALENDAR_PROPOSALS_PATH, encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            existing = []

    existing_keys = {_proposal_key(p) for p in existing}
    new_ones = [p for p in fresh if _proposal_key(p) not in existing_keys]
    if not new_ones:
        return 0

    for p in new_ones:
        p["dateProposition"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    merged = new_ones + existing
    merged = merged[:MAX_CALENDAR_PROPOSALS]
    with open(CALENDAR_PROPOSALS_PATH, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    return len(new_ones)


def notify_calendar_proposals(new_count: int):
    """Canal de notification dédié aux propositions calendrier - séparé de
    notify() (réutilisée telle quelle depuis merge.py) pour ne pas modifier
    son contrat, partagé avec le pipeline quotidien. Mêmes deux canaux
    best-effort (résumé GitHub Actions + push ntfy.sh) que notify()."""
    if new_count <= 0:
        return
    line = f"- **{new_count}** nouvelle(s) proposition(s) de date calendrier a valider (voir data/calendarProposals.json)"

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        try:
            with open(summary_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as e:
            print(f"  [WARN] écriture GITHUB_STEP_SUMMARY (calendrier) échouée ({e})", file=sys.stderr)

    ntfy_topic = os.environ.get("NTFY_TOPIC")
    if ntfy_topic:
        import urllib.request
        try:
            req = urllib.request.Request(
                f"https://ntfy.sh/{ntfy_topic}",
                data=f"{new_count} nouvelle(s) date(s) a valider dans data/calendarProposals.json".encode("utf-8"),
                headers={"Title": "News Omnium : dates calendrier a valider", "Priority": "default"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            print(f"  [WARN] push ntfy.sh (calendrier) échoué ({e})", file=sys.stderr)


def main():
    accepted, statuses = merge_all_items(collector_names=("web",))
    by_ticker = write_per_ticker(accepted)
    write_news_all()

    counts_by_type = {}
    for items in by_ticker.values():
        for it in items:
            counts_by_type[it["type"]] = counts_by_type.get(it["type"], 0) + 1
    if not counts_by_type:
        counts_by_type = {"web": 0}

    run_ok = all(s != "error" for s in statuses.values())
    update_web_state(run_ok)

    new_calendar_count = merge_calendar_proposals()

    notify(counts_by_type, run_ok, statuses, title="News Omnium Web (hebdo)")
    notify_calendar_proposals(new_calendar_count)

    print(f"[merge_web] {sum(counts_by_type.values())} nouveaux items acceptés "
          f"({counts_by_type}), {new_calendar_count} nouvelle(s) proposition(s) calendrier - "
          f"run {'OK' if run_ok else 'PARTIEL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
