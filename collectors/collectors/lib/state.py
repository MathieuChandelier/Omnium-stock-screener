"""
lib/state.py

Gestion de data/newsState.json (fenêtre de fraîcheur) et utilitaires communs
aux 3 collecteurs (communiques, web, youtube).

Principe : la fenêtre de fraîcheur est [lastSuccessfulRun, maintenant].
Un item n'est retenu par un collecteur que si sa date d'événement tombe
dans cette fenêtre - jamais sur la base d'un dédoublonnage a posteriori.
newsState.json n'est mis à jour (par le job merge) que si le run se termine
sans erreur, pour que la fenêtre s'élargisse automatiquement après un run
manqué plutôt que de laisser un trou silencieux.
"""

import hashlib
import json
import os
from datetime import datetime, timezone

STATE_PATH = "data/newsState.json"

# Fenêtre de repli si newsState.json n'existe pas encore (premier run) :
# on ne remonte pas indéfiniment dans le passé, on prend une fenêtre de
# sécurité raisonnable pour ne pas noyer le premier run sous des mois
# d'historique.
DEFAULT_LOOKBACK_HOURS = 48


def utcnow_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_state():
    """Charge newsState.json. Retourne un état par défaut si absent
    (premier run) ou si le fichier est corrompu (fail-safe : on préfère
    une fenêtre large ponctuelle à un crash du pipeline)."""
    if not os.path.exists(STATE_PATH):
        return {
            "lastSuccessfulRun": None,
            "lastRunStatus": "never_run",
            "collectorsStatus": {"communiques": "never_run", "web": "never_run", "youtube": "never_run"},
        }
    try:
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {
            "lastSuccessfulRun": None,
            "lastRunStatus": "corrupted_fallback",
            "collectorsStatus": {"communiques": "unknown", "web": "unknown", "youtube": "unknown"},
        }


def get_window_start(collector_name: str) -> datetime:
    """Détermine le début de fenêtre pour un collecteur donné.

    - Si le run précédent a réussi globalement : lastSuccessfulRun.
    - Sinon (premier run, ou run précédent en échec/inconnu) : fenêtre de
      repli DEFAULT_LOOKBACK_HOURS, pour ne jamais bloquer le pipeline sur
      un état absent ou corrompu."""
    state = load_state()
    last = state.get("lastSuccessfulRun")
    if last:
        try:
            return datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    from datetime import timedelta
    return datetime.now(timezone.utc) - timedelta(hours=DEFAULT_LOOKBACK_HOURS)


def make_id(*parts: str) -> str:
    """Hash court et stable servant de clé de dédup mécanique entre runs.
    communiques/youtube : hash(url). web : hash(url + titre normalisé)."""
    raw = "|".join(p.strip().lower() for p in parts if p)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def load_manifest(path="data/manifest.json"):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_ticker_json(ticker: str, path_tpl="data/{}.json"):
    p = path_tpl.format(ticker)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def load_news_sources(path="data/newsSources.json"):
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_existing_news(ticker: str, path_tpl="data/news/{}.json"):
    """Items déjà en base pour un ticker - sert de contexte anti-doublon
    au collecteur web (injecté dans le prompt) et de base de dédup id."""
    p = path_tpl.format(ticker)
    if not os.path.exists(p):
        return []
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def write_artifact(collector_name: str, items: list, out_dir="artifacts"):
    """Chaque collecteur écrit son résultat brut dans un artifact temporaire
    - pas de commit direct - pour que le job merge fusionne en un seul commit
    et que l'échec d'un collecteur n'affecte pas les autres."""
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{collector_name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    return path
