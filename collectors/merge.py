"""
collectors/merge.py

Job de fusion (4e job du workflow, tourne après les 3 collecteurs même si
un ou plusieurs ont échoué - if: always() côté GitHub Actions).

Responsabilités :
1. Lire les artifacts de communiques.json / web.json / youtube.json
   (absence tolérée si un collecteur a échoué - cette source est juste
   vide pour ce run).
2. Dédoublonner : par id (mécanique) + fuzzy-match titre/ticker/jour
   résiduel pour le cas "plusieurs sources couvrent le même fait le même
   jour" (filet de sécurité, pas le mécanisme principal de fraîcheur).
3. Append dans data/news/TICKER.json (cap à 20 items les plus récents).
4. Régénérer data/newsAll.json en entier (agrégat plat, pas d'append).
5. Ajouter une entrée du jour à data/newsDigest.json (borné à 30 jours).
6. Mettre à jour data/newsState.json - SEULEMENT si aucune erreur bloquante
   n'est survenue dans ce script lui-même (les échecs de collecteurs
   individuels sont déjà gérés en amont et ne bloquent pas ce point).

Usage : python merge.py
"""

import json
import os
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher

from lib.state import load_manifest, load_ticker_json, load_existing_news, utcnow_iso, STATE_PATH

ARTIFACTS_DIR = "artifacts"
NEWS_DIR = "data/news"
DIGEST_PATH = "data/newsDigest.json"
ALL_PATH = "data/newsAll.json"
MAX_ITEMS_PER_TICKER = 20
MAX_DIGEST_DAYS = 30
TITLE_SIMILARITY_THRESHOLD = 0.82  # fuzzy-match same-day residuel


def load_artifact(name):
    path = os.path.join(ARTIFACTS_DIR, f"{name}.json")
    if not os.path.exists(path):
        print(f"  [WARN] artifact {name}.json absent - collecteur probablement en échec, source vide pour ce run")
        return [], "missing"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f), "ok"
    except (json.JSONDecodeError, OSError) as e:
        print(f"  [ERREUR] artifact {name}.json illisible ({e})")
        return [], "error"


def is_near_duplicate(item, existing_batch):
    """Filet résiduel : même ticker, même jour, titres très proches ->
    probable couverture multiple du même fait par des sources différentes.
    Ne remplace jamais le filtre de fenêtre de fraîcheur (déjà appliqué en
    amont par chaque collecteur) - traite un problème de comptage, pas de
    fraîcheur."""
    for other in existing_batch:
        if other["ticker"] != item["ticker"]:
            continue
        if other["dateEvenement"] != item["dateEvenement"]:
            continue
        sim = SequenceMatcher(None, other["title"].lower(), item["title"].lower()).ratio()
        if sim >= TITLE_SIMILARITY_THRESHOLD:
            return True
    return False


def merge_all_items():
    combined = []
    statuses = {}
    for name in ("communiques", "web", "youtube"):
        items, status = load_artifact(name)
        statuses[name] = status
        combined.append((name, items))

    accepted = []
    for name, items in combined:
        for item in items:
            if is_near_duplicate(item, accepted):
                continue
            accepted.append(item)

    return accepted, statuses


def write_per_ticker(accepted_items):
    os.makedirs(NEWS_DIR, exist_ok=True)
    by_ticker = {}
    for item in accepted_items:
        by_ticker.setdefault(item["ticker"], []).append(item)

    manifest = load_manifest()
    for ticker in manifest.keys():
        existing = load_existing_news(ticker)
        existing_ids = {it["id"] for it in existing}
        new_for_ticker = [it for it in by_ticker.get(ticker, []) if it["id"] not in existing_ids]
        if not new_for_ticker:
            continue

        merged = new_for_ticker + existing
        merged.sort(key=lambda x: x["dateEvenement"], reverse=True)
        merged = merged[:MAX_ITEMS_PER_TICKER]

        # Le champ "ticker" ne va pas dans le fichier par-ticker (redondant
        # avec le nom de fichier) - retiré à l'écriture, ré-ajouté dans
        # newsAll.json.
        out = [{k: v for k, v in it.items() if k != "ticker"} for it in merged]
        with open(os.path.join(NEWS_DIR, f"{ticker}.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

    return by_ticker


def write_news_all():
    manifest = load_manifest()
    all_items = []
    for ticker in manifest.keys():
        items = load_existing_news(ticker)
        if not items:
            continue
        tdata = load_ticker_json(ticker) or {}
        name = tdata.get("name", ticker)
        for it in items:
            all_items.append({"ticker": ticker, "name": name, **it})

    all_items.sort(key=lambda x: x["dateEvenement"], reverse=True)
    with open(ALL_PATH, "w", encoding="utf-8") as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
    return all_items


def update_digest(new_items_count_by_type):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    digest = []
    if os.path.exists(DIGEST_PATH):
        try:
            with open(DIGEST_PATH, encoding="utf-8") as f:
                digest = json.load(f)
        except (json.JSONDecodeError, OSError):
            digest = []

    # Une entrée par jour, jamais recalculée rétroactivement une fois écrite
    # (voir design : le compteur d'un jour passé ne doit plus bouger).
    digest = [d for d in digest if d["date"] != today]

    total = sum(new_items_count_by_type.values())
    if total > 0:
        digest.insert(0, {
            "date": today,
            "total": total,
            "communique": new_items_count_by_type.get("communique", 0),
            "web": new_items_count_by_type.get("web", 0),
            "youtube": new_items_count_by_type.get("youtube", 0),
        })

    digest = digest[:MAX_DIGEST_DAYS]
    with open(DIGEST_PATH, "w", encoding="utf-8") as f:
        json.dump(digest, f, ensure_ascii=False, indent=2)


def update_state(collector_statuses, run_ok: bool):
    state = {
        "lastRunStatus": "ok" if run_ok else "partial",
        "collectorsStatus": {
            name: ("ok" if status == "ok" else status)
            for name, status in collector_statuses.items()
        },
    }
    # lastSuccessfulRun n'avance que si le run global est jugé exploitable
    # (au moins un collecteur a tourné sans erreur bloquante) - sinon on
    # laisse la fenêtre s'élargir naturellement au run suivant.
    if run_ok:
        state["lastSuccessfulRun"] = utcnow_iso()
    else:
        prev = {}
        if os.path.exists(STATE_PATH):
            try:
                with open(STATE_PATH, encoding="utf-8") as f:
                    prev = json.load(f)
            except (json.JSONDecodeError, OSError):
                prev = {}
        state["lastSuccessfulRun"] = prev.get("lastSuccessfulRun")

    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def main():
    accepted, statuses = merge_all_items()
    by_ticker = write_per_ticker(accepted)
    write_news_all()

    counts_by_type = {"communique": 0, "web": 0, "youtube": 0}
    for items in by_ticker.values():
        for it in items:
            counts_by_type[it["type"]] = counts_by_type.get(it["type"], 0) + 1
    update_digest(counts_by_type)

    # Run jugé "ok" si au moins un collecteur n'est pas en erreur franche -
    # un collecteur "missing" (artifact absent, ex. clé API manquante ce
    # run) n'est pas bloquant en soi, seul "error" l'est vraiment.
    run_ok = all(s != "error" for s in statuses.values())
    update_state(statuses, run_ok)

    print(f"[merge] {sum(counts_by_type.values())} nouveaux items acceptés "
          f"({counts_by_type}) - run {'OK' if run_ok else 'PARTIEL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
