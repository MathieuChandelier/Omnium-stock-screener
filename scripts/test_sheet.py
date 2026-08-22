"""scripts/test_sheet.py — le classeur dit-il la meme chose que le moteur ?

Recalcule les formules du .xlsx et les confronte, cellule a cellule, aux
valeurs de engine/model.py. Un ecart est une erreur de traduction, jamais une
tolerance : le miroir doit etre le modele, pas une approximation.

Usage :  python3 scripts/test_sheet.py inputs/SYNTHETIQUE.json
"""
import json
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import formulas  # noqa: E402
from engine.model import projette  # noqa: E402

LIGNES = {"ca": 3, "ebitda": 6, "ebit": 10, "finNet": 14,
          "avantImpot": 15, "impot": 17, "net": 19, "eps": 21}


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "inputs/SYNTHETIQUE.json"
    base = os.path.basename(src).replace(".json", "")
    xlsx = "artifacts/%s.xlsx" % base
    sol = formulas.ExcelModel().loads(xlsx).finish().calculate()

    def val(cell):
        suffixe = "'[%s.XLSX]MODELE'!%s" % (base.upper(), cell)
        for k, v in sol.items():
            if k.upper().endswith(suffixe):
                try:
                    return float(v.value[0, 0])
                except Exception:
                    return None
        return None

    proj = projette(json.load(open(src, encoding="utf-8")))
    cols = "CDEFGHIJ"
    ecarts, total = [], 0
    for cle, ligne in LIGNES.items():
        for i, p in enumerate(proj):
            f = val("%s%d" % (cols[i], ligne))
            if f is None:
                continue
            total += 1
            if abs(f - p[cle]) > 0.01:
                ecarts.append((cle, p["annee"], f, p[cle]))
    for cle, an, f, m in ecarts:
        print("  ECART  %-12s %d : formule %.4f vs moteur %.4f" % (cle, an, f, m))
    print("%s : %d cellules comparees, %d ecart(s)" % (xlsx, total, len(ecarts)))
    return 1 if ecarts else 0


if __name__ == "__main__":
    sys.exit(main())
