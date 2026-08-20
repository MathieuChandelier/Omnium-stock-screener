# -*- coding: utf-8 -*-
# AUDIT DE ROBUSTESSE DU MODELE (20/08/2026)
# ============================================
# Complement de coherence_checks.py : la batterie verifie la COHERENCE
# INTERNE des chiffres ; cet audit cherche les CLASSES D'ECHEC DU MODELE
# constatees en usage (retour utilisateur 20/08 : "sur chaque ticker il y
# a des erreurs") - donnees jamais posees, retraitements jamais captes,
# champs perimes. Chaque classe vient d'un echec REEL observe ; le but
# est qu'un echec repere une fois devienne detectable partout.
# Lecture seule - produit un rapport, ne modifie rien.
import json, glob, re, sys, datetime, collections

TODAY = datetime.date.today()
FICHES = {}
for f in sorted(glob.glob('data/*.json')):
    try:
        d = json.load(open(f))
    except Exception:
        continue
    if isinstance(d, dict) and isinstance(d.get('hypothese'), dict) and d.get('data'):
        FICHES[f.split('/')[-1][:-5]] = d

REPORT = collections.OrderedDict()

def add(cls, tk, msg):
    REPORT.setdefault(cls, []).append((tk, msg))

# Mots-cles d'elements non recurrents : si la PROSE de la fiche en parle
# mais qu'aucun trimestre REALISE ne porte de retraitement, le pont
# published->Omnium a probablement ete oublie (cas AMAZON/Anthropic).
ONEOFF_KW = re.compile(
    r'mark.to.market|\bmtm\b|r[ée][ée]valuation|one.off|non.r[ée]curr|exceptionnel'
    r'|impairment|d[ée]pr[ée]ciation|plus.value|gain de cession|ipr&d|severance'
    r'|charge fiscale unique|tax benefit|restructur', re.I)

def prose_of(d):
    h = d.get('hypothese') or {}
    parts = []
    def walk(x):
        if isinstance(x, str): parts.append(x)
        elif isinstance(x, dict):
            for v in x.values(): walk(v)
        elif isinstance(x, list):
            for v in x: walk(v)
    for key in ('dernierCall', 'coherenceQualitative', 'summary', 'text'):
        walk(h.get(key) or (d.get(key) if key == 'coherenceQualitative' else None))
    walk(d.get('particularites'))
    gs = h.get('guidanceScorecard') or {}
    walk([gs.get('basisNote'), gs.get('applicationNote')])
    return ' '.join(parts)

for tk, d in FICHES.items():
    h = d['hypothese']
    data = d['data']
    cy = data[-1]['year'] + 1
    qe = h.get('quarterlyEPS') or {}

    # ── A2 : prose one-off vs zero retraitement sur trimestres realises ──
    actual_periods = [p for k in ('PY', 'CY') for p in (qe.get(k) or []) if p.get('actual')]
    has_retr = any((p.get('retraitements') or []) for p in actual_periods)
    kw = ONEOFF_KW.search(prose_of(d))
    if actual_periods and kw and not has_retr:
        add('A2 prose one-off sans retraitement (pont published->Omnium oublie ?)', tk,
            f'mot-cle "{kw.group(0)}"')

    # ── A3 : somme PY PUBLIEE vs data (l exercice clos doit se reconcilier) ──
    py = qe.get('PY') or []
    if py and data[-1].get('shares'):
        base_sum = sum(+p.get('eps', 0) for p in py)
        tgt = data[-1]['net'] / data[-1]['shares']
        if abs(base_sum - tgt) > 0.05:
            add('A3 somme PY != data (net/actions) - decomposition fausse', tk,
                f'{base_sum:.2f} vs {tgt:.2f}')

    # ── A4 : consensus absent / perime / incomplet ──
    co = d.get('epsConsensus') or {}
    if not co or not co.get('eps'):
        add('A4 epsConsensus absent', tk, '')
    else:
        try:
            dt = datetime.date.fromisoformat(str(co.get('date', ''))[:10])
            age = (TODAY - dt).days
            if age > 45:
                add('A4 consensus perime (>45 j)', tk, f'{age} j ({co.get("date")})')
        except ValueError:
            add('A4 consensus sans date exploitable', tk, str(co.get('date')))
        if not co.get('epsNY'):
            add('A4 consensus sans epsNY', tk, '')
        if not co.get('epsY2'):
            add('A4 consensus sans epsY2 (standard 3 ans, 20/08)', tk, '')

    # ── A5 : nextEvent passe (calendrier fiche jamais roule) ──
    ne = d.get('nextEvent') or {}
    try:
        ned = datetime.date.fromisoformat(str(ne.get('date', ''))[:10])
        if ned < TODAY:
            add('A5 nextEvent dans le passe', tk, f'{ne.get("date")} ({ne.get("label")})')
    except ValueError:
        add('A5 nextEvent absent/illisible', tk, str(ne.get('date')))

    # ── A7 : valuePct de particularite qui risque le double comptage ──
    for p in (d.get('particularites') or []):
        v = p.get('valuePct')
        if v not in (None, '', 0) and re.search(r'amortiss|ppa|dilut|p[ée]rim[èe]tre|acquisition', (p.get('text') or ''), re.I):
            add('A7 valuePct suspect (effet deja dans la trajectoire EPS ?)', tk, f'{v} %')

    # ── A8 : trous omniumEPS entre CY et l horizon 2030/FY equivalent ──
    oe = h.get('omniumEPS') or {}
    onet, osh = h.get('omniumNet') or {}, h.get('omniumShares') or {}
    def covered(y):
        s = str(y)
        return isinstance(oe.get(s), (int, float)) or (isinstance(onet.get(s), (int, float)) and isinstance(osh.get(s), (int, float)))
    horizon = cy + 4
    holes = [y for y in range(cy, horizon + 1) if not covered(y)]
    if holes:
        add('A8 horizon de projection troue (CY..CY+4)', tk, f'annees {holes}')

    # ── A9 : scorecard - lecture en cours perimee ──
    gs = h.get('guidanceScorecard') or {}
    ip = gs.get('inProgress') or {}
    if ip:
        try:
            ipd = datetime.date.fromisoformat(str(ip.get('asOf', ''))[:10])
            if (TODAY - ipd).days > 120:
                add('A9 scorecard inProgress perime (>120 j)', tk, str(ip.get('asOf')))
        except ValueError:
            add('A9 scorecard inProgress sans asOf', tk, '')

# ── A11 : actual non reconcilie avec le reported du dernier call ──
# Cas SARTORIUSSTEDIM (20/08/2026) : une ESTIMATION marquee "actual" a
# survecu aux resultats (H1 saisi 1.98, reported IFRS 1.86). Quand
# dernierCall porte un epsReported date d'une periode, l'actual de la
# MEME periode dans quarterlyEPS doit lui etre egal (±0.02, base
# publiee : publishedOf = eps - somme des impacts).
for tk in FICHES:
    d = FICHES[tk]
    h = d.get('hypothese') or {}
    rep = ((h.get('dernierCall') or {}).get('resultatsVsConsensus') or {}).get('epsReported') or {}
    per = str(rep.get('period') or '')
    try:
        val = float(rep.get('actual'))
    except (TypeError, ValueError):
        val = None
    if val is None or not per:
        continue
    lab = per.split()[0]
    q = h.get('quarterlyEPS') or {}
    # Le reported du call date de l'exercice EN COURS : le recoupement ne
    # vaut que pour CY (PY porte les memes labels T1..T4, autre annee).
    for k in ('CY',):
        for pr in (q.get(k) or []):
            if not isinstance(pr, dict) or pr.get('label') != lab or not pr.get('actual'):
                continue
            adj = sum(float(r.get('impact') or 0) for r in (pr.get('retraitements') or []))
            pub = float(pr.get('eps') or 0) - adj
            if abs(pub - val) > 0.02:
                add('A11 actual non reconcilie avec le reported du call', tk,
                    f'{k} {lab} publie fiche {pub:.2f} vs reported call {val:.2f}')

# ── A10 : priceHistory manquant ──
try:
    PH = json.load(open('data/priceHistory.json')).get('tickers', {})
    for tk in FICHES:
        if not (PH.get(tk, {}).get('snapshots')):
            add('A10 priceHistory sans snapshot', tk, '')
except Exception:
    pass

total = 0
for cls, items in REPORT.items():
    print(f'\n{cls}  ->  {len(items)}')
    for tk, msg in items[:12]:
        print(f'    {tk:20s} {msg}')
    if len(items) > 12:
        print(f'    ... et {len(items)-12} autres')
    total += len(items)
print(f'\nTOTAL AUDIT : {total} points, {len(REPORT)} classes')
sys.exit(0)
