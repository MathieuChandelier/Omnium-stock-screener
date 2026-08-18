"""
scripts/coherence_checks.py

Batterie d'INVARIANTS sur la chaine schema -> fiches -> historique de prix.
Complementaire de validate_ticker.py, qui verifie la FORME d'un fichier :
ici on verifie la COHERENCE ENTRE fichiers et entre etats successifs.

Principe (demande du 18/08/2026) : beaucoup de regles d'INSTRUCTIONS.md
sont evidentes une fois enoncees - "un refresh sans impact sur les BNA ne
produit pas de nouvelle courbe d'EPS" - mais rien ne les verifiait. Un
invariant evident non teste est un invariant qui derive.

Usage : python scripts/coherence_checks.py      (depuis la racine du depot)
Sortie : une ligne par check, les anomalies detaillees, code de sortie 1
si au moins une anomalie.

Calibrage des seuils : une tolerance purement relative se declenche a tort
sur les BNA proches de zero (SNAP : 0,003$/action d'ecart = 3,8% quand le
BNA vaut -0,09). C4 exige donc un ecart a la fois relatif ET absolu.
"""
import json, glob, os, subprocess, collections

def sh(c): return subprocess.run(c,shell=True,capture_output=True,text=True).stdout
FICHES={}
for f in sorted(glob.glob('data/*.json')):
    b=os.path.basename(f).replace('.json','')
    try: t=json.load(open(f))
    except Exception: continue
    if isinstance(t,dict) and 'hypothese' in t: FICHES[b]=t
PH_RAW=json.load(open('data/priceHistory.json'))
PH=PH_RAW['tickers']

def cy_of(t):
    d=t.get('data') or []
    return (d[-1]['year']+1) if d else None

CHECKS=collections.OrderedDict()
def check(nom):
    def deco(fn): CHECKS[nom]=fn; return fn
    return deco

@check("C1  somme des BNA trimestriels CY == adjEPS[CY]")
def c1():
    bad=[]
    for tk,t in FICHES.items():
        h=t['hypothese']; cy=cy_of(t); qe=h.get('quarterlyEPS') or {}
        arr=qe.get('CY'); tgt=(h.get('adjEPS') or {}).get(str(cy))
        if not arr or not isinstance(tgt,(int,float)): continue
        s=sum(p.get('eps',0) for p in arr)
        if abs(s-tgt)>0.05: bad.append((tk,f'{s:.2f} vs {tgt:.2f} (ecart {s-tgt:+.2f})'))
    return bad

@check("C2  somme des BNA trimestriels NY == adjEPS[CY+1]")
def c2():
    bad=[]
    for tk,t in FICHES.items():
        h=t['hypothese']; cy=cy_of(t); qe=h.get('quarterlyEPS') or {}
        arr=qe.get('NY'); tgt=(h.get('adjEPS') or {}).get(str(cy+1)) if cy else None
        if not arr or not isinstance(tgt,(int,float)): continue
        s=sum(p.get('eps',0) for p in arr)
        if abs(s-tgt)>0.05: bad.append((tk,f'{s:.2f} vs {tgt:.2f} (ecart {s-tgt:+.2f})'))
    return bad

@check("C3  coherenceNoteCY/NY doivent rester null (champs deprecies)")
def c3():
    bad=[]
    for tk,t in FICHES.items():
        qe=t['hypothese'].get('quarterlyEPS') or {}
        for k in ('coherenceNoteCY','coherenceNoteNY'):
            if qe.get(k): bad.append((tk,f'{k} non nul'))
    return bad

@check("C4  adjEPS == adjNet / adjShares (>1% ET >1 cent)")
def c4():
    bad=[]
    for tk,t in FICHES.items():
        h=t['hypothese']; eps=h.get('adjEPS') or {}; net=h.get('adjNet') or {}; sh_=h.get('adjShares') or {}
        for y,v in eps.items():
            n,s=net.get(y),sh_.get(y)
            if not all(isinstance(x,(int,float)) for x in (v,n,s)) or not s: continue
            imp=n/s
            ecart=abs(imp-v)
            if v and ecart>0.01 and ecart/abs(v)>0.01:
                bad.append((tk,f'{y}: eps {v} vs net/actions {imp:.3f} (ecart {ecart:.3f})'))
    return bad

@check("C5  epsConsensus.year == annee en cours")
def c5():
    bad=[]
    for tk,t in FICHES.items():
        c=t.get('epsConsensus') or {}; cy=cy_of(t)
        if c.get('year') and cy and c['year']!=cy: bad.append((tk,f"consensus {c['year']} vs CY {cy}"))
    return bad

@check("C6  guidanceHistory : un seul fyGuided")
def c6():
    bad=[]
    for tk,t in FICHES.items():
        gh=t['hypothese'].get('guidanceHistory') or []
        fys={g.get('fyGuided') for g in gh if isinstance(g,dict)}
        if len(fys)>1: bad.append((tk,f'fyGuided heterogenes : {sorted(fys)}'))
    return bad

@check("C7  derniere capture : epsByYear == adjEPS courant")
def c7():
    bad=[]
    for tk,t in FICHES.items():
        sn=[s for s in (PH.get(tk,{}).get('snapshots') or []) if s.get('price')]
        if not sn: continue
        last=sn[-1]; eps=t['hypothese'].get('adjEPS') or {}
        for y,v in (last.get('epsByYear') or {}).items():
            cur=eps.get(y)
            if isinstance(cur,(int,float)) and abs(cur-v)>0.005:
                bad.append((tk,f'{y}: capture {v} vs fiche {cur}')); break
    return bad

@check("C8  derniere capture : ndCY/shCY == adjND/adjShares[cyYear]")
def c8():
    bad=[]
    for tk,t in FICHES.items():
        sn=[s for s in (PH.get(tk,{}).get('snapshots') or []) if s.get('price')]
        if not sn: continue
        last=sn[-1]; cy=str(last.get('cyYear'))
        nd=(t['hypothese'].get('adjND') or {}).get(cy); shh=(t['hypothese'].get('adjShares') or {}).get(cy)
        if isinstance(nd,(int,float)) and 'ndCY' in last and abs(last['ndCY']-nd)>0.5:
            bad.append((tk,f'ndCY {last["ndCY"]} vs fiche {nd}'))
        elif isinstance(shh,(int,float)) and 'shCY' in last and abs(last['shCY']-shh)>0.5:
            bad.append((tk,f'shCY {last["shCY"]} vs fiche {shh}'))
    return bad

@check("C9  revision d'EPS <=> nouvelle courbe (l'exemple donne)")
def c9():
    bad=[]
    for tk,t in FICHES.items():
        snaps=PH.get(tk,{}).get('snapshots') or []
        if not snaps: continue
        etats=[]
        for s in snaps:
            sig=json.dumps({k:round(float(v),4) for k,v in (s.get('epsByYear') or {}).items()},sort_keys=True)
            if sig!='{}' and (not etats or etats[-1]!=sig): etats.append(sig)
        nb_courbes=len(etats)
        log=[l.split('~') for l in sh(f"git log --format='%H~%ad' --date=short -- data/{tk}.json").strip().splitlines() if '~' in l]
        debut=snaps[0]['date']
        revision_depuis=False
        for h,d in log:
            if d<debut: break
            try: j=json.loads(sh(f"git show {h}:data/{tk}.json"))
            except Exception: continue
            e={k:round(float(v),4) for k,v in ((j.get('hypothese') or {}).get('adjEPS') or {}).items()}
            if e and json.dumps(e,sort_keys=True)!=etats[-1]: revision_depuis=True; break
        if revision_depuis and nb_courbes<2:
            bad.append((tk,'adjEPS revise pendant la fenetre mais 1 seule courbe'))
    return bad

@check("C10 retraitements : jamais sur une majorite de periodes (regle de porte)")
def c10():
    bad=[]
    for tk,t in FICHES.items():
        qe=t['hypothese'].get('quarterlyEPS') or {}
        for k in ('PY','CY','NY'):
            arr=qe.get(k) or []
            if not arr: continue
            n=sum(1 for p in arr if p.get('retraitements'))
            if n>len(arr)/2: bad.append((tk,f'{k}: {n}/{len(arr)} periodes retraitees'))
    return bad

@check("C11 millesime EPS reconstruit : doit montrer une revision reelle")
def c11():
    # Un millesime archive (epsOnly) qui ne differe du suivant que sur des
    # annees DEJA ECOULEES trace une courbe exactement superposee a la
    # courbe vivante : l'utilisateur voit une amorce pale puis une seule
    # ligne, sans l'effet de translation qui justifie l'affichage. Soit le
    # millesime capture le mauvais etat (pris APRES le refresh de resultats
    # au lieu d'avant), soit aucune revision n'a eu lieu et la courbe n'a
    # rien a dire. Dans les deux cas elle ne doit pas etre tracee.
    bad=[]
    for tk,e in PH.items():
        snaps=e.get('snapshots') or []
        for r in [x for x in snaps if x.get('epsOnly')]:
            suite=snaps[snaps.index(r)+1:]
            nx=next((x for x in suite if x.get('epsByYear')),None)
            if not nx: continue
            a,b,cy=r['epsByYear'],nx['epsByYear'],nx.get('cyYear')
            if not cy: continue
            futur=[y for y in set(a)&set(b) if int(y)>=cy]
            revise=[y for y in futur
                    if abs(float(a[y])-float(b[y]))/max(abs(float(b[y])),1e-9)>0.005]
            if futur and not revise:
                bad.append((tk,f"millesime {r['date']} identique a {nx['date']} "
                               f"sur {len(futur)} annees projetees"))
    return bad

@check("C12 scorecard : la tenue de guidance doit etre integree aux projections")
def c12():
    # appliedToProjection n'est pas une option : des lors qu'un
    # weightedBeatPct exploitable existe, il DOIT etre repercute dans
    # adjEPS/adjCA de l'annee en cours (INSTRUCTIONS.md l.717). Un false
    # signale donc une projection qui ignore le comportement observe de
    # l'emetteur - une anomalie a corriger au refresh, pas un etat a
    # afficher sur la fiche.
    bad=[]
    for tk,t in FICHES.items():
        gs=t['hypothese'].get('guidanceScorecard')
        if not isinstance(gs,dict): continue
        if gs.get('weightedBeatPct') is None: continue
        if gs.get('appliedToProjection') is not True:
            bad.append((tk,f"weightedBeatPct={gs['weightedBeatPct']} non repercute "
                           f"(appliedToProjection={gs.get('appliedToProjection')!r})"))
    return bad

@check("C13 revision d'EPS : doit correspondre a un evenement date")
def c13():
    # Une projection ne bouge pas toute seule : elle bouge a des resultats,
    # un CMD, une revision de guidance. La pastille du graphique se pose
    # d'ailleurs sur CET evenement et non sur la capture qui la revele
    # (index.html, buildValoChartSVG). Une revision sans evenement dans
    # l'intervalle est donc soit une date d'evenement manquante dans
    # earningsDates, soit une projection modifiee sans cause tracee -
    # dans les deux cas le graphique ne peut pas la situer.
    ED=PH_RAW.get('earningsDates',{})
    bad=[]
    for tk,e in PH.items():
        snaps=e.get('snapshots') or []
        dates=ED.get(tk,[])
        for i in range(1,len(snaps)):
            a,b=snaps[i-1],snaps[i]
            ea,eb=a.get('epsByYear') or {}, b.get('epsByYear') or {}
            chg=[y for y in set(ea)&set(eb)
                 if abs(float(ea[y])-float(eb[y]))/max(abs(float(eb[y])),1e-9)>0.005]
            if not chg: continue
            # Un millesime reconstruit porte la date du COMMIT : si le refresh
            # de resultats est tombe le meme jour, l'evenement est sur la
            # borne gauche, qu'il faut alors inclure.
            incl=bool(a.get('epsOnly'))
            evs=[d for d in dates
                 if (d>=a['date'] if incl else d>a['date']) and d<=b['date']]
            if not evs:
                bad.append((tk,f"{a['date']} -> {b['date']} : {len(chg)} annee(s) "
                               f"revisee(s), aucun evenement date dans l'intervalle"))
    return bad

@check("C14 libelle 'ex-cash' : interdit sans donnee de dette nette")
def c14():
    # snapExCashPrice retombe sur le cours BRUT quand aucune donnee de dette
    # nette n'existe (cas banque). Le graphique ne doit alors pas s'intituler
    # ex-cash - il afficherait un multiple sur capitalisation sous un nom qui
    # promet l'inverse. index.html teste exactement ndCY, on verifie donc que
    # la fiche et la capture disent la meme chose.
    bad=[]
    for tk,t in FICHES.items():
        sn=[x for x in (PH.get(tk,{}).get('snapshots') or []) if x.get('price')]
        if not sn: continue
        last=sn[-1]
        cy=str(last.get('cyYear'))
        fiche_nd=(t['hypothese'].get('adjND') or {}).get(cy)
        capture_nd='ndCY' in last
        if isinstance(fiche_nd,(int,float)) and not capture_nd:
            bad.append((tk,f"fiche porte adjND[{cy}]={fiche_nd} mais la capture "
                           f"n'a pas ndCY : libelle ex-cash impossible a honorer"))
    return bad

@check("C15 les trois echeances tracees doivent avoir >=2 points archives")
def c16():
    # Le graphique P/E trace CY, CY+1 et CY+2 ensemble. Une echeance dont
    # l'archive ne porte pas deux points exploitables disparait du trace sans
    # que rien ne le signale : la colonne TODAY annonce alors moins de lignes
    # qu'il n'y a d'echeances dans la fiche.
    bad=[]
    for tk,t in FICHES.items():
        cy=cy_of(t)
        if not cy: continue
        sn=[x for x in (PH.get(tk,{}).get('snapshots') or []) if x.get('price')]
        if len(sn)<2: continue
        for k,year in (('CY',cy),('NY',cy+1),('Y2',cy+2)):
            fiche_eps=(t['hypothese'].get('adjEPS') or {}).get(str(year))
            if not isinstance(fiche_eps,(int,float)): continue
            n=sum(1 for x in sn if isinstance((x.get('epsByYear') or {}).get(str(year)),(int,float)))
            if n<2:
                bad.append((tk,f'{k} ({year}) : {n} point(s) archive(s), courbe absente du trace'))
    return bad

def main():
    print(f'{len(FICHES)} fiches auditees\n')
    total=0
    for nom,fn in CHECKS.items():
        bad=fn()
        total+=len(bad)
        etat='OK' if not bad else f'{len(bad)} ANOMALIES'
        print(f'{nom}\n     -> {etat}')
        for tk,det in bad[:6]: print(f'        {tk:<20} {det}')
        if len(bad)>6: print(f'        ... et {len(bad)-6} autres')
    print(f'\nTOTAL : {total} anomalies')
    return 1 if total else 0

if __name__=='__main__':
    import sys; sys.exit(main())
