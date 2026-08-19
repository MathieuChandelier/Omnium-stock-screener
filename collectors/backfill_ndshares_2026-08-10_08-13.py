"""
collectors/backfill_ndshares_2026-08-10_08-13.py

Script PONCTUEL (comme backfill_price_history_2026-08-10_08-13.py, meme
esprit) : ajoute ndCY/shCY (P/E ex-cash, annee en cours uniquement -
decision du 17/08/2026) aux DEUX snapshots deja backfilles le 17/08/2026
(10/08 et 13/08), qui existaient avant l'ajout de ndCY/shCY a
price_history.py. Le run automatique de ce soir (23h00 UTC) capturera
ndCY/shCY nativement pour le 3e point - ce script ne concerne QUE le
rattrapage des 2 premiers.

omniumND/omniumShares ne changent PAS aussi souvent que omniumEPS (aucun des deux
n'a bouge pour NUBANK malgre son refresh du 15/08 - verifie : memes
valeurs avant/apres), donc contrairement a epsByYear, pas de cas
particulier a gerer ici - la valeur actuelle convient pour les deux dates.

Usage : python collectors/backfill_ndshares_2026-08-10_08-13.py
Met a jour data/priceHistory.json (ajoute ndCY/shCY aux snapshots
existants du 10/08 et 13/08, ne touche a rien d'autre).
"""

import json
import os
import sys

import importlib.util as _ilu


def _load_module(rel_path, mod_name):
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)
    spec = _ilu.spec_from_file_location(mod_name, path)
    module = _ilu.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_state = _load_module("lib/state.py", "omnium_ndshares_backfill_state")
load_manifest = _state.load_manifest
load_ticker_json = _state.load_ticker_json

HISTORY_PATH = "data/priceHistory.json"
TARGET_DATES = {"2026-08-10", "2026-08-13"}


def main():
    manifest = load_manifest()
    with open(HISTORY_PATH, encoding="utf-8") as f:
        history = json.load(f)

    patched = 0
    skipped = {}

    for ticker in manifest:
        entry = history["tickers"].get(ticker)
        if not entry:
            continue
        tdata = load_ticker_json(ticker)
        if tdata is None:
            skipped[ticker] = "no_json"
            continue
        hyp = tdata.get("hypothese") or {}

        for snap in entry["snapshots"]:
            if snap["date"] not in TARGET_DATES:
                continue
            cy = snap.get("cyYear")
            nd_cy = (hyp.get("omniumND") or {}).get(str(cy))
            sh_cy = (hyp.get("omniumShares") or {}).get(str(cy))
            if isinstance(nd_cy, (int, float)):
                snap["ndCY"] = round(float(nd_cy), 2)
            if isinstance(sh_cy, (int, float)):
                snap["shCY"] = round(float(sh_cy), 2)
            if "ndCY" in snap and "shCY" in snap:
                patched += 1

    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(f"[backfill_ndshares] {patched} snapshots patches, {len(skipped)} skips ({skipped})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
