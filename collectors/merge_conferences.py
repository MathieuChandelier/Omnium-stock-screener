"""
collectors/merge_conferences.py

Job de fusion du collecteur hebdomadaire conferences.py (voir sa docstring
pour le pourquoi d'un pipeline séparé). Réutilise les briques de merge.py
(dédup, écriture par ticker, newsAll.json, notification) mais N'ÉCRIT PAS
dans data/newsState.json ni data/newsDigest.json - ce sont des fichiers du
pipeline QUOTIDIEN, et les deux workflows peuvent tourner à des horaires
proches (voir cron respectifs) : les toucher depuis ce job créerait un
risque réel de race condition (écrasement mutuel d'un compteur ou d'une
fenêtre de fraîcheur selon l'ordre d'arrivée des deux jobs), pas seulement
théorique vu leur proximité d'horaire.

Ce job gère donc son PROPRE état (data/conferencesState.json), totalement
indépendant, mis à jour ici (pas dans conferences.py - ce job tourne dans
un checkout git frais qui sera commité/pushé, contrairement au job
collecteur en amont dont les fichiers locaux ne sont pas persistés au-delà
de l'artifact qu'il upload).

Usage : python merge_conferences.py
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

CONF_STATE_PATH = "data/conferencesState.json"


def update_conferences_state(run_ok: bool):
    """Miroir de merge.py::update_state, mais sur un fichier d'état dédié
    (voir docstring du module) - même principe : la fenêtre ne s'avance
    que si le run est exploitable, sinon elle s'élargit naturellement au
    run suivant plutôt que de laisser un trou silencieux."""
    state = {}
    if os.path.exists(CONF_STATE_PATH):
        try:
            with open(CONF_STATE_PATH, encoding="utf-8") as f:
                state = json.load(f)
        except (json.JSONDecodeError, OSError):
            state = {}

    state["lastRunStatus"] = "ok" if run_ok else "partial"
    if run_ok:
        state["lastSuccessfulRun"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    # sinon on conserve lastSuccessfulRun tel quel (deja dans state si present)

    with open(CONF_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def main():
    accepted, statuses = merge_all_items(collector_names=("conferences",))
    by_ticker = write_per_ticker(accepted)
    write_news_all()

    counts_by_type = {}
    for items in by_ticker.values():
        for it in items:
            counts_by_type[it["type"]] = counts_by_type.get(it["type"], 0) + 1
    if not counts_by_type:
        counts_by_type = {"conference": 0}

    run_ok = all(s != "error" for s in statuses.values())
    update_conferences_state(run_ok)
    notify(counts_by_type, run_ok, statuses, title="News Omnium Conferences")

    print(f"[merge_conferences] {sum(counts_by_type.values())} nouveaux items acceptés "
          f"({counts_by_type}) - run {'OK' if run_ok else 'PARTIEL'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
