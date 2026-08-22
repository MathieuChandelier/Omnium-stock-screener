"""engine/model.py — le moteur, v1.

Fonction PURE : entrees -> projections. Aucun reseau, aucune horloge, aucun
effet de bord. Memes entrees, memes sorties, a l'octet.

Contrainte de conception (regle 9) : CHAQUE calcul de ce module doit pouvoir
s'ecrire comme une formule de cellule. Si un calcul ne s'exprime pas dans une
feuille, il est trop malin et il se cache. C'est ce qui garantit que le miroir
.xlsx est le modele lui-meme, pas une approximation de presentation.

Vocabulaire : un MOTEUR est une hypothese nommee qui pilote une ou plusieurs
cellules. Il porte sa valeur, son RANG de provenance (guidance / implicite /
normatif) et, pour ce qui vient du management, sa PEREMPTION.
"""

ENGINE_VERSION = "1.0.0"

RANGS = ("guidance", "implicite", "normatif")


# ── Base Omnium : publie + vrais one-offs, nets de leur impot ────────────
# On stocke la SOURCE (le publie et les retraitements), on CALCULE le derive.

def _impot_ligne(r, reste, base_prorata):
    """Effet d'impot d'une ligne : le sien s'il est pose, sinon le prorata."""
    if isinstance(r.get("impot"), (int, float)):
        return r["impot"]
    return reste * (r.get("net", 0.0) / base_prorata) if base_prorata else 0.0


def bases(periode):
    """(omnium, ajuste, coin) a chaque etage, depuis une periode de `comptes`."""
    pub = periode["publie"]
    rets = periode.get("retraitements", [])
    imp = periode.get("impotSurRetraitements", 0.0) or 0.0
    poses = [r for r in rets if isinstance(r.get("impot"), (int, float))]
    reste = imp - sum(r["impot"] for r in poses)
    base = sum(r.get("net", 0.0) for r in rets if r not in poses)

    one = [r for r in rets if r.get("classe") == "oneOff"]
    rec = [r for r in rets if r.get("classe") == "recurrent"]
    emet = [r for r in rets if r.get("origine", "emetteur") == "emetteur"]

    omnium, ajuste, coin = {}, {}, {}
    for etage in ("ebitda", "ebit", "net"):
        if not isinstance(pub.get(etage), (int, float)):
            continue
        tax_one = sum(_impot_ligne(r, reste, base) for r in one) if etage == "net" else 0.0
        tax_rec = sum(_impot_ligne(r, reste, base) for r in rec) if etage == "net" else 0.0
        omnium[etage] = pub[etage] + sum(r.get(etage, 0.0) for r in one) + tax_one
        ajuste[etage] = pub[etage] + sum(r.get(etage, 0.0) for r in emet) + (imp if etage == "net" else 0.0)
        coin[etage] = sum(r.get(etage, 0.0) for r in rec) + tax_rec
    return omnium, ajuste, coin


# ── Moteurs : resolution d'une hypothese pour une annee ──────────────────

def moteur(bloc, annee, defaut=None):
    """Valeur d'un moteur pour une annee, avec sa provenance.

    PEREMPTION (regle 6) : une valeur de rang `guidance` ne vaut QUE pour son
    exercice. Au-dela, le moteur refuse de la propager et bascule sur le
    defaut normatif - c'est la regle qui empeche un taux guide de courir
    indefiniment sur tout l'horizon.
    """
    e = (bloc or {}).get(str(annee))
    if e is not None:
        exp = e.get("expire")
        if exp is None or annee <= exp:
            return e["valeur"], e.get("rang", "normatif"), e.get("moteur", "")
    d = (bloc or {}).get("defaut") or defaut
    if d is None:
        raise ValueError("aucun moteur pour %s et aucun defaut : cellule orpheline" % annee)
    return d["valeur"], d.get("rang", "normatif"), d.get("moteur", "")


# ── Dotations : echeancier PPA + amortissement du capex ──────────────────

def da(annee, ca_prec, ppa, capex_ratio, duree, da_hors_ppa_prec):
    """Dotations de l'annee = amortissement du capex recurrent + PPA.

    La jambe PPA suit l'echeancier PUBLIE quand il existe ; elle s'eteint donc
    d'elle-meme. La jambe recurrente croit avec le capex : da_n =
    da_{n-1} + capex_{n-1}/duree, forme la plus simple qui fasse suivre les
    dotations a l'investissement sans modeliser le parc actif par actif.
    """
    ppa_annee = sum((v.get("echeancier") or {}).get(str(annee), 0.0)
                    for k, v in (ppa or {}).items() if not k.startswith("_"))
    hors_ppa = da_hors_ppa_prec + (ca_prec * capex_ratio) / duree
    return -(hors_ppa + ppa_annee), hors_ppa, ppa_annee


# ── Resultat financier : cascade par rang (proposition 2) ────────────────

def fin_net(bilan, params):
    """Retourne (valeur, rang_resolu).

    Rang 1 : detail publie par instrument.  Rang 2 : taux appliques aux postes
    de bilan decomposes.  Rang 3 : spread normatif sur la dette nette.
    La valeur est retournee AVEC le rang auquel elle a ete resolue - c'est la
    Regle C, une valeur et sa provenance.
    """
    rang = params.get("rang", 3)
    if rang == 1:
        return params["valeur"], 1
    if rang == 2:
        return (-(bilan["debtGross"] * params["tauxDetteBrute"])
                + bilan["cash"] * params["tauxPlacementCash"]
                - bilan["leaseDebt"] * params["tauxLease"]), 2
    return -(bilan["debtGross"] - bilan["cash"] + bilan["leaseDebt"]) * params["spreadNormatif"], 3


def override(inp, annee, metrique):
    """Echappatoire DECLAREE (regle 7).

    Le moteur calcule ; si le jugement diverge, il pose ici une valeur avec sa
    justification, et l'override apparait TEL QUEL dans les sorties. Une
    exception declaree remplace un paragraphe de doctrine par cas particulier -
    a la condition stricte qu'elle soit toujours visible. Une valeur sans
    justification est refusee : c'est ce qui empeche l'echappatoire de devenir
    une porte derobee.
    """
    e = ((inp.get("overrides") or {}).get(str(annee)) or {}).get(metrique)
    if e is None:
        return None
    if not str(e.get("justification", "")).strip():
        raise ValueError("override %s %s sans justification" % (annee, metrique))
    return e


def projette(inp):
    """Deroule l'horizon. Retourne une ligne par annee, chaque metrique
    accompagnee du rang du moteur qui l'a produite."""
    h = inp["hypotheses"]
    horizon = h["horizon"]
    hist = sorted(inp["comptes"])[-1]
    pub = inp["comptes"][hist]["publie"]
    an0 = int(hist[:4])

    omn0, _, _ = bases(inp["comptes"][hist])
    bil = dict(inp["bilan"][hist])
    ca = pub["ca"]
    actions = inp["actions"][str(an0)]
    da_hors_ppa = -pub["da"] - sum((v.get("echeancier") or {}).get(str(an0), 0.0)
                                   for k, v in (inp.get("ppa") or {}).items()
                                   if not k.startswith("_"))

    out = []
    for an in horizon:
        g, rang_g, mot_g = moteur(h["croissanceCA"], an,
                                  {"valeur": h["regleTerminale"]["croissanceTerminale"], "rang": "normatif"})
        m, rang_m, mot_m = moteur(h["margeEbitda"], an,
                                  {"valeur": h["regleTerminale"]["margeTerminale"], "rang": "normatif"})
        t, rang_t, mot_t = moteur(h["tauxImpot"], an)

        ca_prec = ca
        ca = ca_prec * (1 + g)
        ebitda = ca * m
        dot, da_hors_ppa, ppa_an = da(an, ca_prec, inp.get("ppa"),
                                      h["capexSurCA"]["valeur"], h["dureeAmortissement"]["valeur"], da_hors_ppa)
        ebit = ebitda + dot
        fn, rang_f = fin_net(bil, h["resultatFinancier"])
        avant = ebit + fn
        impot = -avant * t
        ov = override(inp, an, "impot")
        if ov is not None:
            impot, rang_t = ov["valeur"], "override"
        minos = pub["minoritaires"] / pub["net"] * (avant + impot) if pub.get("net") else 0.0
        net = avant + impot + minos

        actions = actions * (1 - h["actions"]["rachatAnnuelPct"])
        eps = net / actions

        div = net * h["distribution"]["tauxDistribution"]
        # Roulement de tresorerie, forme minimale et lisible : le resultat
        # entre, le dividende sort, le capex est deja porte par les dotations.
        bil = dict(bil, cash=bil["cash"] + net - div - (ca_prec * h["capexSurCA"]["valeur"]) + (-dot))

        out.append({
            "annee": an, "ca": ca, "croissance": g, "rangCroissance": rang_g, "moteurCroissance": mot_g,
            "margeEbitda": m, "rangMarge": rang_m, "moteurMarge": mot_m,
            "ebitda": ebitda, "da": dot, "daHorsPpa": da_hors_ppa, "daPpa": ppa_an,
            "ebit": ebit, "finNet": fn, "rangFinNet": rang_f, "avantImpot": avant,
            "tauxImpot": t, "rangTaux": rang_t, "moteurTaux": mot_t,
            "impot": impot, "minoritaires": minos, "net": net,
            "override": bool(override(inp, an, "impot")),
            "actions": actions, "eps": eps, "dividende": div,
        })
    return out
