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
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

# Champs qui DOIVENT vivre a la racine du JSON (jamais imbriques dans hypothese).
ROOT_ONLY_FIELDS = ["ownership", "compliance", "coherenceQualitative", "nextEvent", "comptes"]

# Champs qui DOIVENT vivre a l'interieur de hypothese (jamais a la racine).
HYPOTHESE_ONLY_FIELDS = [
    "dernierCall", "guidanceHistory", "guidanceLongTerme",
    "guidanceLongTermeHistory", "quarterlyEPS", "priorEPS", "ancrages",
]

ADJ_FIELDS = ["omniumCA", "omniumEBIT", "omniumNet", "omniumND", "omniumShares", "omniumEPS"]

ANCRAGE_KEYS = {"id", "moteur", "applique", "confiance"}
ANCRAGE_OPTIONAL_KEYS = {"versusPublie"}
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
CQ_SENS_VALUES = {"positif", "negatif", "neutre"}
CQ_STATUT_VALUES = {"coherent", "rupture_positive", "incoherences_detectees"}
CQ_HISTORIQUE_FORMAT_VALUES = {"brut", "compresse"}
CQ_HISTORIQUE_TYPE_VALUES = {"resultats", "evenement_annexe"}
CQ_ENGAGEMENT_STATUT_VALUES = {"en_cours", "confirme", "contredit", "echeance_depassee_sans_suite"}

# Regle du 21/08/2026, datee comme les regles du 18/08 dans la batterie :
# un transcript LU ce tour-ci OBLIGE une synthese narrative. La doctrine
# l'exigeait deja ("TOUJOURS CONSTRUITE des lors qu'un transcript a ete lu
# [...] jamais vide dans ce cas") et l'app sait l'afficher - mais rien ne
# l'imposait, et 5 fiches sur 59 seulement la portaient : le bloc "Narrative
# & coherence tracking" se reduisait alors a sa ligne de statut, sans le
# detail. Les fiches anterieures sont tolerees jusqu'a leur prochain refresh.
SUIVI_NARRATIF_RULE_DATE = "2026-08-21"

# ── comptes (21/08/2026) ──────────────────────────────────────────────
# La fiche stockait le chiffre DERIVE (data, base Omnium) et racontait le
# chiffre SOURCE en prose (E5 d-bis : hypothese.text "reste l'unique
# endroit ou le chiffre publie BRUT est trace"). Consequence mesuree : rien
# ne pouvait comparer la base DECLAREE d'une fiche a la base EMPLOYEE, et
# DIASORIN a glisse du publie vers l'ajuste entre 2025 et 2026 sans qu'un
# seul controle bronche. `comptes` inverse le montage : on stocke la
# source (le publie + les retraitements), on CALCULE le derive.
COMPTES_PERIODE_RE = r"^\d{4}-(FY|H[12]|Q[1-4])$"
COMPTES_BASE_VALUES = {"US-GAAP", "IFRS"}
COMPTES_CLASSE_VALUES = {"oneOff", "recurrent", "indetermine"}
COMPTES_RUPTURE_TYPE_VALUES = {"retraitement", "perimetre"}
COMPTES_RUPTURE_PAR_VALUES = {"emetteur", "omnium"}
# kebab-case strict : c'est l'identifiant qui, relu periode apres periode,
# forme la SERIE d'un poste. Sans stabilite, pas de serie, donc pas de
# projection possible du poste (cas Luminex/PPA).
COMPTES_ID_RE = r"^[a-z0-9]+(-[a-z0-9]+)*$"


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
    # Emetteurs financiers (bank/insurer/broker) : la dette nette n'a pas de
    # sens economique - index.html ignore omniumND via isFinancialIssuer() et
    # la convention de la fiche est de le laisser absent ou a null (cf.
    # commentaire "omniumND y est volontairement absent" dans index.html et
    # C14 qui interdit un omniumND numerique sans ndCY dans les captures).
    financial_issuer = d.get("issuerType") in ("bank", "insurer", "broker")
    for field in ADJ_FIELDS:
        val = hyp.get(field)
        if val is None:
            if field == "omniumND" and financial_issuer:
                continue
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
            if num is None and field == "omniumND" and financial_issuer:
                continue
            if not isinstance(num, (int, float)) or isinstance(num, bool):
                errors.add(f"hypothese.{field}['{year}'] n'est pas un nombre : {num!r}.")


def validate_eps_coherence(d, errors):
    hyp = d.get("hypothese", {})
    adj_net = hyp.get("omniumNet")
    adj_shares = hyp.get("omniumShares")
    adj_eps = hyp.get("omniumEPS")
    if not all(isinstance(x, dict) for x in (adj_net, adj_shares, adj_eps)):
        return
    for year in adj_eps:
        if year not in adj_net or year not in adj_shares:
            continue
        shares = adj_shares[year]
        if not shares:
            continue
        # omniumNet et omniumShares sont tous deux en millions -> le ratio direct est l'EPS.
        implied = adj_net[year] / shares
        given = adj_eps[year]
        if given and abs(implied - given) / abs(given) > 0.02:
            errors.add(
                f"Incoherence EPS {year} : omniumEPS={given} mais "
                f"omniumNet/omniumShares={implied:.3f} (ecart > 2%)."
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
        extra_keys = keys - ANCRAGE_KEYS - ANCRAGE_OPTIONAL_KEYS
        missing_keys = ANCRAGE_KEYS - keys
        if extra_keys or missing_keys:
            errors.add(
                f"ancrages[{i}] (id={a.get('id')!r}) a les cles {sorted(keys)} "
                f"au lieu de {sorted(ANCRAGE_KEYS)} (+ {sorted(ANCRAGE_OPTIONAL_KEYS)} optionnel)."
            )
        if "versusPublie" in a and not isinstance(a["versusPublie"], str):
            errors.add(f"ancrages[{i}].versusPublie doit etre une chaine si present.")
        if not isinstance(a.get("applique"), list):
            errors.add(f"ancrages[{i}].applique doit etre une liste de chaines 'champ.annee'.")
        if a.get("confiance") not in ANCRAGE_CONFIANCE_VALUES:
            errors.add(
                f"ancrages[{i}].confiance={a.get('confiance')!r} invalide "
                f"(attendu {sorted(ANCRAGE_CONFIANCE_VALUES)})."
            )


def validate_comptes(d, errors):
    """Structure de `comptes` (optionnel, absent = fiche pas encore migree).

    Ne juge PAS la vraisemblance des chiffres. Verifie la forme, et la
    seule arithmetique qui soit purement interne : le BOUCLAGE de la table
    sur l'ajuste publie par la societe quand celui-ci est renseigne. Un
    bouclage qui tombe faux ne peut etre qu'une erreur de recopie - c'est
    le controle le moins cher et le plus efficace de la structure.
    """
    comptes = d.get("comptes")
    if comptes is None:
        return
    if not isinstance(comptes, dict):
        errors.add("comptes doit etre un objet indexe par periode ('2025-FY', '2026-H1'...).")
        return

    for per, c in comptes.items():
        if not re.match(COMPTES_PERIODE_RE, str(per)):
            errors.add(f"comptes['{per}'] : cle de periode invalide (attendu 'AAAA-FY', 'AAAA-H1', 'AAAA-Q3'...).")
        if not isinstance(c, dict):
            errors.add(f"comptes['{per}'] n'est pas un objet.")
            continue
        if c.get("base") not in COMPTES_BASE_VALUES:
            errors.add(f"comptes['{per}'].base={c.get('base')!r} invalide (attendu {sorted(COMPTES_BASE_VALUES)}).")
        if not isinstance(c.get("source"), str) or not c["source"].strip():
            errors.add(f"comptes['{per}'].source doit nommer le document et sa date.")

        pub = c.get("publie")
        if not isinstance(pub, dict):
            errors.add(f"comptes['{per}'].publie doit etre un objet {{ca, ebit, net}}.")
            pub = {}
        else:
            for k in ("ca", "ebit", "net"):
                if not isinstance(pub.get(k), (int, float)):
                    errors.add(f"comptes['{per}'].publie.{k} doit etre un nombre.")
            if "ebitda" in pub and not isinstance(pub["ebitda"], (int, float)):
                errors.add(f"comptes['{per}'].publie.ebitda doit etre un nombre si present.")

        rup = c.get("rupture")
        if rup is not None:
            if not isinstance(rup, dict):
                errors.add(f"comptes['{per}'].rupture doit etre null ou un objet {{par, motif}}.")
            else:
                # Deux ruptures de nature differente, et elles n'appellent pas
                # le meme geste : 'retraitement' = quelqu'un a REECRIT les
                # comparatifs (l'emetteur fait autorite, on realigne
                # l'historique ; si c'est nous, ca se notifie) ; 'perimetre' =
                # personne n'a rien reecrit, un EVENEMENT rend la serie non
                # comparable (acquisition, cession, changement de norme) et un
                # CAGR ne doit jamais franchir cette borne.
                typ = rup.get("type")
                if typ not in COMPTES_RUPTURE_TYPE_VALUES:
                    errors.add(
                        f"comptes['{per}'].rupture.type={typ!r} invalide "
                        f"(attendu {sorted(COMPTES_RUPTURE_TYPE_VALUES)})."
                    )
                if typ == "retraitement" and rup.get("par") not in COMPTES_RUPTURE_PAR_VALUES:
                    errors.add(
                        f"comptes['{per}'].rupture.par={rup.get('par')!r} invalide "
                        f"(attendu {sorted(COMPTES_RUPTURE_PAR_VALUES)}) - qui a retraite "
                        f"decide si on suit ou si on notifie."
                    )
                if not isinstance(rup.get("motif"), str) or not rup["motif"].strip():
                    errors.add(f"comptes['{per}'].rupture.motif doit etre une phrase non vide.")

        rets = c.get("retraitements")
        if not isinstance(rets, list):
            errors.add(f"comptes['{per}'].retraitements doit etre un tableau (vide si aucun).")
            continue
        seen = set()
        for i, r in enumerate(rets):
            where = f"comptes['{per}'].retraitements[{i}]"
            if not isinstance(r, dict):
                errors.add(f"{where} n'est pas un objet.")
                continue
            rid = r.get("id")
            if not isinstance(rid, str) or not re.match(COMPTES_ID_RE, rid or ""):
                errors.add(f"{where}.id={rid!r} doit etre un identifiant kebab-case stable (ex. 'luminex-ppa-amort').")
            elif rid in seen:
                errors.add(f"{where}.id={rid!r} est duplique dans la meme periode.")
            else:
                seen.add(rid)
            if not isinstance(r.get("libelle"), str) or not r["libelle"].strip():
                errors.add(f"{where}.libelle doit etre une chaine non vide.")
            for k in ("ebit", "net"):
                if not isinstance(r.get(k), (int, float)):
                    errors.add(f"{where}.{k} doit etre un nombre (0 si la ligne ne touche pas ce niveau).")
            if "ebitda" in r and not isinstance(r["ebitda"], (int, float)):
                errors.add(f"{where}.ebitda doit etre un nombre si present.")
            if "impot" in r and not isinstance(r["impot"], (int, float)):
                errors.add(f"{where}.impot doit etre un nombre si present (effet d'impot PROPRE a cette ligne).")
            cl = r.get("classe")
            if cl not in COMPTES_CLASSE_VALUES:
                errors.add(f"{where}.classe={cl!r} invalide (attendu {sorted(COMPTES_CLASSE_VALUES)}).")
            elif cl == "indetermine" and not (isinstance(r.get("note"), str) and r["note"].strip()):
                errors.add(f"{where} est 'indetermine' sans note : la raison du doute doit etre ecrite.")

        # BOUCLAGE : publie + tous les retraitements + impot == ajuste publie.
        aj = c.get("ajustePublie")
        imp = c.get("impotSurRetraitements", 0)
        if isinstance(aj, dict) and isinstance(imp, (int, float)):
            for k, tax in (("ebitda", 0), ("ebit", 0), ("net", imp)):
                if not isinstance(aj.get(k), (int, float)) or not isinstance(pub.get(k), (int, float)):
                    continue
                calc = pub[k] + sum(r.get(k, 0) for r in rets if isinstance(r, dict)) + tax
                if abs(calc - aj[k]) > max(1.0, abs(aj[k]) * 0.005):
                    errors.add(
                        f"comptes['{per}'] : la table ne BOUCLE pas sur {k} - "
                        f"publie {pub[k]} + retraitements {calc - pub[k] - tax:+g} + impot {tax:+g} "
                        f"= {calc:g}, or l'ajuste publie vaut {aj[k]}. Erreur de recopie."
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
    basis = ((dc.get("resultatsVsConsensus") or {}).get("epsAdj") or {}).get("basis")
    if basis is not None and basis not in ("GAAP", "non-GAAP"):
        errors.add(
            f"hypothese.dernierCall.resultatsVsConsensus.epsAdj.basis={basis!r} invalide - "
            "doit etre exactement 'GAAP' ou 'non-GAAP', jamais une phrase explicative."
        )


def validate_quarterly_eps(d, errors):
    qe = d.get("hypothese", {}).get("quarterlyEPS")
    if qe is None:
        return
    if not isinstance(qe, dict):
        errors.add("hypothese.quarterlyEPS doit etre un objet.")
        return
    adj_eps = d.get("hypothese", {}).get("omniumEPS", {})
    years = sorted(adj_eps.keys(), key=lambda y: int(y)) if isinstance(adj_eps, dict) else []
    ancrage_ids = {
        a.get("id") for a in (d.get("hypothese", {}).get("ancrages") or [])
        if isinstance(a, dict) and a.get("id")
    }
    def validate_retraitements(period_key, i, p):
        r = p.get("retraitements")
        if r is None:
            return
        if not isinstance(r, list) or not r:
            errors.add(f"quarterlyEPS.{period_key}[{i}].retraitements doit etre un tableau non vide si present.")
            return
        for j, item in enumerate(r):
            if not isinstance(item, dict) or set(item.keys()) != {"raison", "impact"}:
                errors.add(f"quarterlyEPS.{period_key}[{i}].retraitements[{j}] doit avoir exactement les cles raison/impact.")
                continue
            raison = item.get("raison")
            if not isinstance(raison, str) or not raison.strip():
                errors.add(f"quarterlyEPS.{period_key}[{i}].retraitements[{j}].raison doit etre une chaine non vide.")
            elif any(aid and aid in raison for aid in ancrage_ids) or "voir AN-" in raison or "(voir " in raison:
                errors.add(
                    f"quarterlyEPS.{period_key}[{i}].retraitements[{j}].raison={raison!r} contient un renvoi "
                    "interne (id d'ancrage ou 'voir ...') - la legende doit etre une phrase autonome et limpide "
                    "pour le lecteur, jamais un pointeur vers un autre champ (voir SCHEMA, regle du 18/08/2026)."
                )
            if not isinstance(item.get("impact"), (int, float)):
                errors.add(f"quarterlyEPS.{period_key}[{i}].retraitements[{j}].impact doit etre un nombre.")

    for label, key in (("CY", "CY"), ("NY", "NY")):
        arr = qe.get(key)
        if arr is None:
            continue
        if not isinstance(arr, list):
            errors.add(f"hypothese.quarterlyEPS.{key} doit etre un tableau, pas un objet.")
            continue
        for i, p in enumerate(arr):
            if set(p.keys()) - {"label", "eps", "actual", "retraitements"}:
                errors.add(f"quarterlyEPS.{key}[{i}] a des cles inattendues : {sorted(p.keys())}.")
            validate_retraitements(key, i, p)
    py = qe.get("PY")
    if isinstance(py, list):
        for i, p in enumerate(py):
            if p.get("actual") is not True:
                errors.add(f"quarterlyEPS.PY[{i}] doit avoir actual=true (annee deja cloturee).")
            if set(p.keys()) - {"label", "eps", "actual", "retraitements"}:
                errors.add(f"quarterlyEPS.PY[{i}] a des cles inattendues : {sorted(p.keys())}.")
            validate_retraitements("PY", i, p)
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
    # Somme CY/NY vs omniumEPS correspondant (les 2 premieres annees de projection).
    for idx, key in enumerate(("CY", "NY")):
        arr = qe.get(key)
        if not isinstance(arr, list) or idx >= len(years):
            continue
        year = years[idx]
        total = sum(p.get("eps", 0) for p in arr if isinstance(p.get("eps"), (int, float)))
        target = adj_eps.get(year)
        if isinstance(target, (int, float)) and abs(total - target) > 0.05:
            errors.add(
                f"quarterlyEPS.{key} somme a {total:.2f} mais omniumEPS['{year}']={target} "
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
    if statut is not None and statut not in CQ_STATUT_VALUES:
        errors.add(f"coherenceQualitative.statut invalide : {statut!r}.")
    if statut == "coherent" and points:
        errors.add("coherenceQualitative.statut='coherent' mais points non vide.")
    if statut in ("rupture_positive", "incoherences_detectees") and not points:
        errors.add(f"coherenceQualitative.statut={statut!r} mais points vide.")
    # 'sens' est absent sur les entrees ecrites avant l'introduction de ce
    # champ (voir INSTRUCTIONS.md, non-alteration retroactive) - le
    # croisement statut/sens ne s'applique QUE si TOUS les points portent
    # deja un 'sens' explicite ; un tableau partiellement/jamais modernise
    # n'est pas une erreur, juste une donnee heritee non re-derivable.
    dict_points = [p for p in points if isinstance(p, dict)]
    all_have_sens = bool(dict_points) and all("sens" in p for p in dict_points)
    has_negatif = any(p.get("sens") == "negatif" for p in dict_points)
    if all_have_sens:
        if statut == "incoherences_detectees" and not has_negatif:
            errors.add("coherenceQualitative.statut='incoherences_detectees' mais aucun point n'a sens='negatif' (devrait etre 'rupture_positive').")
        if statut == "rupture_positive" and has_negatif:
            errors.add("coherenceQualitative.statut='rupture_positive' mais au moins un point a sens='negatif' (devrait etre 'incoherences_detectees').")
    for i, p in enumerate(points):
        if not isinstance(p, dict):
            errors.add(f"coherenceQualitative.points[{i}] doit etre un objet.")
            continue
        if p.get("natureEcart") not in CQ_NATURE_ECART_VALUES:
            errors.add(f"coherenceQualitative.points[{i}].natureEcart invalide : {p.get('natureEcart')!r}.")
        if p.get("materialite") not in CQ_MATERIALITE_VALUES:
            errors.add(f"coherenceQualitative.points[{i}].materialite invalide : {p.get('materialite')!r}.")
        # 'sens' tolere absent (entree heritee) mais valide si present.
        if "sens" in p and p.get("sens") not in CQ_SENS_VALUES:
            errors.add(f"coherenceQualitative.points[{i}].sens invalide : {p.get('sens')!r}.")
    suivi = cq.get("suiviNarratif")
    if suivi is not None:
        if not isinstance(suivi, list):
            errors.add("coherenceQualitative.suiviNarratif doit etre un tableau.")
        else:
            if not (1 <= len(suivi) <= 4):
                errors.add(f"coherenceQualitative.suiviNarratif a {len(suivi)} entrees (attendu 1 a 4).")
            for i, s in enumerate(suivi):
                if not isinstance(s, str) or not s.strip():
                    errors.add(f"coherenceQualitative.suiviNarratif[{i}] doit etre une chaine non vide.")
    transcript_lu = (d.get("hypothese", {}).get("dernierCall") or {}).get("transcriptAnalyse") is True
    date_fiche = (d.get("hypothese", {}) or {}).get("date") or ""
    if transcript_lu and date_fiche >= SUIVI_NARRATIF_RULE_DATE and not (
        isinstance(suivi, list) and any(isinstance(x, str) and x.strip() for x in suivi)
    ):
        errors.add(
            "coherenceQualitative.suiviNarratif est vide alors que "
            "dernierCall.transcriptAnalyse=true : un transcript lu impose 2 a 4 "
            "phrases de synthese narrative (confirme / nuance / inflechi vs les "
            "evenements de reference). Sans elles, le bloc de suivi n'affiche que "
            "son statut, sans le detail."
        )
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
            # 'type' tolere absent (entrees heritees d'avant l'introduction du
            # champ, voir INSTRUCTIONS.md) mais valide s'il est present.
            if "type" in h and h.get("type") not in CQ_HISTORIQUE_TYPE_VALUES:
                errors.add(f"coherenceQualitative.historique[{i}].type invalide : {h.get('type')!r}.")
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


GS_CADENCES = {"quarterly", "annual", "annual_kpi", "none"}
GS_COMPARED_AGAINST = {"guidance", "consensus"}
GS_TIMELINE_TYPES = {"guidance_revision", "vs_consensus", "vs_guidance"}


def validate_guidance_scorecard(d, errors):
    gs = d.get("hypothese", {}).get("guidanceScorecard")
    if gs is None:
        return
    if not isinstance(gs, dict):
        errors.add("hypothese.guidanceScorecard doit etre un objet.")
        return

    if gs.get("cadence") not in GS_CADENCES:
        errors.add(f"guidanceScorecard.cadence={gs.get('cadence')!r} invalide (attendu {sorted(GS_CADENCES)}).")
    if gs.get("comparedAgainst") not in GS_COMPARED_AGAINST:
        errors.add(f"guidanceScorecard.comparedAgainst={gs.get('comparedAgainst')!r} invalide (attendu {sorted(GS_COMPARED_AGAINST)}).")
    if not isinstance(gs.get("basisAligned"), bool):
        errors.add("guidanceScorecard.basisAligned doit etre un booleen.")
    else:
        note = gs.get("basisNote")
        if gs["basisAligned"] and note is not None:
            errors.add("guidanceScorecard.basisNote doit etre null quand basisAligned est true.")
        if not gs["basisAligned"] and not (isinstance(note, str) and note.strip()):
            errors.add("guidanceScorecard.basisNote doit etre une chaine non vide quand basisAligned est false.")

    timeline = gs.get("timeline")
    n_realized = 0
    if not isinstance(timeline, list):
        errors.add("guidanceScorecard.timeline doit etre un tableau.")
        timeline = []
    for i, ev in enumerate(timeline):
        if not isinstance(ev, dict):
            errors.add(f"guidanceScorecard.timeline[{i}] n'est pas un objet.")
            continue
        etype = ev.get("type")
        if etype not in GS_TIMELINE_TYPES:
            errors.add(f"guidanceScorecard.timeline[{i}].type={etype!r} invalide (attendu {sorted(GS_TIMELINE_TYPES)}).")
            continue
        if not isinstance(ev.get("detail"), str) or not ev["detail"].strip():
            errors.add(f"guidanceScorecard.timeline[{i}].detail doit etre une chaine non vide.")
        if etype == "guidance_revision":
            if ev.get("flag") not in (None, "warning"):
                errors.add(f"guidanceScorecard.timeline[{i}].flag={ev.get('flag')!r} invalide (attendu null ou 'warning').")
        else:
            n_realized += 1
            if not isinstance(ev.get("beatPct"), (int, float)):
                errors.add(f"guidanceScorecard.timeline[{i}].beatPct doit etre un nombre pour un type {etype!r}.")
            expected_type = "vs_guidance" if gs.get("comparedAgainst") == "guidance" else "vs_consensus"
            if gs.get("comparedAgainst") in GS_COMPARED_AGAINST and etype != expected_type:
                errors.add(
                    f"guidanceScorecard.timeline[{i}].type={etype!r} incoherent avec "
                    f"comparedAgainst={gs.get('comparedAgainst')!r} (attendu {expected_type!r})."
                )

    pace = gs.get("paceCheckpoint")
    if pace is not None:
        if not isinstance(pace, str) or not pace.strip():
            errors.add("guidanceScorecard.paceCheckpoint doit etre une chaine non vide si present.")
        if gs.get("cadence") == "quarterly":
            errors.add("guidanceScorecard.paceCheckpoint ne doit jamais etre renseigne pour cadence='quarterly' (deja couvert par timeline chaque trimestre).")

    wbp = gs.get("weightedBeatPct")
    if wbp is not None:
        if not isinstance(wbp, (int, float)):
            errors.add("guidanceScorecard.weightedBeatPct doit etre un nombre si present.")
        if n_realized == 0:
            errors.add("guidanceScorecard.weightedBeatPct est renseigne mais timeline ne contient aucune entree vs_consensus/vs_guidance realisee.")

    if not isinstance(gs.get("appliedToProjection"), bool):
        errors.add("guidanceScorecard.appliedToProjection doit etre un booleen.")


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
    validate_guidance_scorecard(d, errors)
    validate_comptes(d, errors)
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
