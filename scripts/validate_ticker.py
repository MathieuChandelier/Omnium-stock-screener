"""
scripts/validate_ticker.py

Validation structurelle des fichiers data/CODE.json, independante du
respect du protocole par l'assistant qui les ecrit (voir E8-bis dans
INSTRUCTIONS.md). Ne juge jamais la VRAISEMBLANCE des chiffres (role de
l'assistant / de Mathieu) - seulement la CONFORMITE STRUCTURELLE au
schema attendu par index.html : un JSON valide et bien redige mais mal
forme a un endroit precis peut echouer silencieusement au chargement ou
a l'affichage cote app, sans la moindre erreur JS ni JSON.

Usage :
  python scripts/validate_ticker.py data/NIKE.json [data/NETFLIX.json ...]
  python scripts/validate_ticker.py --all   # valide tous les tickers de manifest.json

Sort avec un code non nul (et imprime chaque erreur) des qu'au moins un
fichier echoue - pense pour un job CI qui bloque le push sur echec.
"""

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

# Champs qui DOIVENT vivre a la racine du JSON (jamais imbriques dans hypothese).
ROOT_ONLY_FIELDS = ["ownership", "compliance", "coherenceQualitative", "nextEvent"]

# Champs qui DOIVENT vivre a l'interieur de hypothese (jamais a la racine).
HYPOTHESE_ONLY_FIELDS = [
    "dernierCall", "guidanceHistory", "guidanceLongTerme",
    "guidanceLongTermeHistory", "quarterlyEPS", "priorEPS", "ancrages",
]

ADJ_FIELDS = ["adjCA", "adjEBIT", "adjNet", "adjND", "adjShares", "adjEPS"]

ANCRAGE_KEYS = {"id", "moteur", "applique", "confiance"}
ANCRAGE_CONFIANCE_VALUES = {"haute", "moyenne", "basse"}

COMPLIANCE_STATUS_VALUES = {
    "sollicitation", "enquete_en_cours", "plainte_deposee", "reglee",
    "classee_sans_suite", "condamnation", "non_fondee",
}

CQ_NATURE_ECART_VALUES = {
    "contradiction_non_expliquee", "engagement_abandonne_sans_explication",
    "inversion_narratif_structurant",
}
CQ_MATERIALITE_VALUES = {"haute", "moyenne"}
CQ_HISTORIQUE_FORMAT_VALUES = {"brut", "compresse"}
CQ_ENGAGEMENT_STATUT_VALUES = {"en_cours", "confirme", "contredit", "echeance_depassee_sans_suite"}


class Errors(list):
    def add(self, msg):
        self.append(msg)


def validate_placement(d, errors):
    for field in ROOT_ONLY_FIELDS:
        if field in d.get("hypothese", {}):
            errors.add(
                f"'{field}' est imbrique dans hypothese - doit vivre a la racine "
                f"du JSON (d.{field}, jamais d.hypothese.{field})."
            )
    for field in HYPOTHESE_ONLY_FIELDS:
        if field in d:
            errors.add(
                f"'{field}' est present a la racine du JSON - doit vivre a "
                f"l'interieur de hypothese (d.hypothese.{field}, jamais d.{field})."
            )


def validate_adj_fields(d, errors):
    hyp = d.get("hypothese")
    if not isinstance(hyp, dict):
        errors.add("'hypothese' est absent ou n'est pas un objet.")
        return
    for field in ADJ_FIELDS:
        val = hyp.get(field)
        if val is None:
            errors.add(f"hypothese.{field} est absent.")
            continue
        if not isinstance(val, dict):
            errors.add(
                f"hypothese.{field} doit etre un OBJET indexe par annee "
                f"({{'2026': valeur, ...}}), pas un {type(val).__name__} "
                f"(tableau interdit - cause de bug la plus sournoise possible, "
                f"voir E8-bis)."
            )
            continue
        for year, num in val.items():
            if not isinstance(num, (int, float)) or isinstance(num, bool):
                errors.add(f"hypothese.{field}['{year}'] n'est pas un nombre : {num!r}.")


def validate_eps_coherence(d, errors):
    hyp = d.get("hypothese", {})
    adj_net = hyp.get("adjNet")
    adj_shares = hyp.get("adjShares")
    adj_eps = hyp.get("adjEPS")
    if not all(isinstance(x, dict) for x in (adj_net, adj_shares, adj_eps)):
        return
    for year in adj_eps:
        if year not in adj_net or year not in adj_shares:
            continue
        shares = adj_shares[year]
        if not shares:
            continue
        # adjNet et adjShares sont tous deux en millions -> le ratio direct est l'EPS.
        implied = adj_net[year] / shares
        given = adj_eps[year]
        if given and abs(implied - given) / abs(given) > 0.02:
            errors.add(
                f"Incoherence EPS {year} : adjEPS={given} mais "
                f"adjNet/adjShares={implied:.3f} (ecart > 2%)."
            )


def validate_ancrages(d, errors):
    ancrages = d.get("hypothese", {}).get("ancrages")
    if ancrages is None:
        return
    if not isinstance(ancrages, list):
        errors.add("hypothese.ancrages doit etre un tableau.")
        return
    for i, a in enumerate(ancrages):
        if not isinstance(a, dict):
            errors.add(f"ancrages[{i}] n'est pas un objet.")
            continue
        keys = set(a.keys())
        if keys != ANCRAGE_KEYS:
            errors.add(
                f"ancrages[{i}] (id={a.get('id')!r}) a les cles {sorted(keys)} "
                f"au lieu de exactement {sorted(ANCRAGE_KEYS)}."
            )
        if not isinstance(a.get("applique"), list):
            errors.add(f"ancrages[{i}].applique doit etre une liste de chaines 'champ.annee'.")
        if a.get("confiance") not in ANCRAGE_CONFIANCE_VALUES:
            errors.add(
                f"ancrages[{i}].confiance={a.get('confiance')!r} invalide "
                f"(attendu {sorted(ANCRAGE_CONFIANCE_VALUES)})."
            )


def validate_dernier_call(d, errors):
    dc = d.get("hypothese", {}).get("dernierCall")
    if dc is None:
        return
    if not isinstance(dc, dict):
        errors.add("hypothese.dernierCall doit etre un objet.")
        return
    for b in ("communiqueAnalyse", "transcriptAnalyse"):
        if b not in dc:
            errors.add(f"hypothese.dernierCall.{b} est absent (booleen attendu).")
        elif not isinstance(dc[b], bool):
            errors.add(f"hypothese.dernierCall.{b} n'est pas un booleen : {dc[b]!r}.")


def validate_quarterly_eps(d, errors):
    qe = d.get("hypothese", {}).get("quarterlyEPS")
    if qe is None:
        return
    if not isinstance(qe, dict):
        errors.add("hypothese.quarterlyEPS doit etre un objet.")
        return
    adj_eps = d.get("hypothese", {}).get("adjEPS", {})
    years = sorted(adj_eps.keys(), key=lambda y: int(y)) if isinstance(adj_eps, dict) else []
    for label, key in (("CY", "CY"), ("NY", "NY")):
        arr = qe.get(key)
        if arr is None:
            continue
        if not isinstance(arr, list):
            errors.add(f"hypothese.quarterlyEPS.{key} doit etre un tableau, pas un objet.")
            continue
        for i, p in enumerate(arr):
            if set(p.keys()) - {"label", "eps", "actual"}:
                errors.add(f"quarterlyEPS.{key}[{i}] a des cles inattendues : {sorted(p.keys())}.")
    py = qe.get("PY")
    if isinstance(py, list):
        for i, p in enumerate(py):
            if p.get("actual") is not True:
                errors.add(f"quarterlyEPS.PY[{i}] doit avoir actual=true (annee deja cloturee).")
    if qe.get("coherenceNoteCY") is not None:
        errors.add("hypothese.quarterlyEPS.coherenceNoteCY doit etre null (champ deprecie).")
    if qe.get("coherenceNoteNY") is not None:
        errors.add("hypothese.quarterlyEPS.coherenceNoteNY doit etre null (champ deprecie).")
    hist = qe.get("historique")
    if hist is not None:
        if not isinstance(hist, list):
            errors.add("hypothese.quarterlyEPS.historique doit etre un tableau.")
        elif len(hist) > 5:
            errors.add(f"hypothese.quarterlyEPS.historique a {len(hist)} entrees (plafond 5).")
    # Somme CY/NY vs adjEPS correspondant (les 2 premieres annees de projection).
    for idx, key in enumerate(("CY", "NY")):
        arr = qe.get(key)
        if not isinstance(arr, list) or idx >= len(years):
            continue
        year = years[idx]
        total = sum(p.get("eps", 0) for p in arr if isinstance(p.get("eps"), (int, float)))
        target = adj_eps.get(year)
        if isinstance(target, (int, float)) and abs(total - target) > 0.05:
            errors.add(
                f"quarterlyEPS.{key} somme a {total:.2f} mais adjEPS['{year}']={target} "
                f"(ecart > 0,05 - tout ecart doit avoir ete arbitre avant livraison, voir E5 ter point 4)."
            )


def validate_coherence_qualitative(d, errors):
    cq = d.get("coherenceQualitative")
    if cq is None:
        return
    if not isinstance(cq, dict):
        errors.add("coherenceQualitative doit etre un objet.")
        return
    points = cq.get("points", [])
    if not isinstance(points, list):
        errors.add("coherenceQualitative.points doit etre un tableau.")
        points = []
    if len(points) > 3:
        errors.add(f"coherenceQualitative.points a {len(points)} entrees (plafond 3).")
    statut = cq.get("statut")
    if statut == "coherent" and points:
        errors.add("coherenceQualitative.statut='coherent' mais points non vide.")
    if statut == "incoherences_detectees" and not points:
        errors.add("coherenceQualitative.statut='incoherences_detectees' mais points vide.")
    for i, p in enumerate(points):
        if p.get("natureEcart") not in CQ_NATURE_ECART_VALUES:
            errors.add(f"coherenceQualitative.points[{i}].natureEcart invalide : {p.get('natureEcart')!r}.")
        if p.get("materialite") not in CQ_MATERIALITE_VALUES:
            errors.add(f"coherenceQualitative.points[{i}].materialite invalide : {p.get('materialite')!r}.")
    hist = cq.get("historique", [])
    if isinstance(hist, list):
        if len(hist) > 4:
            errors.add(f"coherenceQualitative.historique a {len(hist)} entrees (plafond 4).")
        brut_count = sum(1 for h in hist if h.get("format") == "brut")
        if brut_count > 2:
            errors.add(f"coherenceQualitative.historique a {brut_count} entrees 'brut' (max 2).")
        for i, h in enumerate(hist):
            if h.get("format") not in CQ_HISTORIQUE_FORMAT_VALUES:
                errors.add(f"coherenceQualitative.historique[{i}].format invalide : {h.get('format')!r}.")
    eng = cq.get("engagementsStructurants", [])
    if isinstance(eng, list):
        en_cours = [e for e in eng if e.get("statut") == "en_cours"]
        if len(en_cours) > 8:
            errors.add(f"coherenceQualitative.engagementsStructurants a {len(en_cours)} entrees en_cours (max 8).")
        for i, e in enumerate(eng):
            if e.get("statut") not in CQ_ENGAGEMENT_STATUT_VALUES:
                errors.add(f"engagementsStructurants[{i}].statut invalide : {e.get('statut')!r}.")


def validate_compliance(d, errors):
    comp = d.get("compliance")
    if comp is None:
        return
    for i, item in enumerate(comp.get("items", [])):
        if item.get("status") not in COMPLIANCE_STATUS_VALUES:
            errors.add(f"compliance.items[{i}].status invalide : {item.get('status')!r}.")


def validate_file(path: Path) -> list:
    errors = Errors()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as e:
        return [f"Impossible de lire le fichier : {e}"]
    try:
        d = json.loads(text)
    except json.JSONDecodeError as e:
        return [f"JSON invalide : {e}"]

    validate_placement(d, errors)
    validate_adj_fields(d, errors)
    validate_eps_coherence(d, errors)
    validate_ancrages(d, errors)
    validate_dernier_call(d, errors)
    validate_quarterly_eps(d, errors)
    validate_coherence_qualitative(d, errors)
    validate_compliance(d, errors)
    return errors


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)

    if args == ["--all"]:
        manifest = json.loads((DATA_DIR / "manifest.json").read_text(encoding="utf-8"))
        paths = [DATA_DIR / f"{code}.json" for code in manifest.get("tickers", [])]
    else:
        paths = [Path(a) for a in args]

    total_errors = 0
    for path in paths:
        if not path.exists():
            print(f"⚠ {path} : fichier introuvable, ignore.")
            continue
        errors = validate_file(path)
        if errors:
            print(f"✗ {path} : {len(errors)} probleme(s)")
            for e in errors:
                print(f"    - {e}")
            total_errors += len(errors)
        else:
            print(f"✓ {path}")

    if total_errors:
        print(f"\n{total_errors} probleme(s) au total.")
        sys.exit(1)
    print("\nTous les fichiers valides.")


if __name__ == "__main__":
    main()
