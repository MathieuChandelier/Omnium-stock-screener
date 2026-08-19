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

@check("C1  somme des BNA trimestriels CY == omniumEPS[CY]")
def c1():
    bad=[]
    for tk,t in FICHES.items():
        h=t['hypothese']; cy=cy_of(t); qe=h.get('quarterlyEPS') or {}
        arr=qe.get('CY'); tgt=(h.get('omniumEPS') or {}).get(str(cy))
        if not arr or not isinstance(tgt,(int,float)): continue
        s=sum(p.get('eps',0) for p in arr)
        if abs(s-tgt)>0.05: bad.append((tk,f'{s:.2f} vs {tgt:.2f} (ecart {s-tgt:+.2f})'))
    return bad

@check("C2  somme des BNA trimestriels NY == omniumEPS[CY+1]")
def c2():
    bad=[]
    for tk,t in FICHES.items():
        h=t['hypothese']; cy=cy_of(t); qe=h.get('quarterlyEPS') or {}
        arr=qe.get('NY'); tgt=(h.get('omniumEPS') or {}).get(str(cy+1)) if cy else None
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

@check("C4  omniumEPS == adjNet / adjShares (>1% ET >1 cent)")
def c4():
    bad=[]
    for tk,t in FICHES.items():
        h=t['hypothese']; eps=h.get('omniumEPS') or {}; net=h.get('adjNet') or {}; sh_=h.get('adjShares') or {}
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

@check("C7  derniere capture : epsByYear == omniumEPS courant")
def c7():
    bad=[]
    for tk,t in FICHES.items():
        sn=[s for s in (PH.get(tk,{}).get('snapshots') or []) if s.get('price')]
        if not sn: continue
        last=sn[-1]; eps=t['hypothese'].get('omniumEPS') or {}
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
            e={k:round(float(v),4) for k,v in ((j.get('hypothese') or {}).get('omniumEPS') or {}).items()}
            if e and json.dumps(e,sort_keys=True)!=etats[-1]: revision_depuis=True; break
        if revision_depuis and nb_courbes<2:
            bad.append((tk,'omniumEPS revise pendant la fenetre mais 1 seule courbe'))
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
    # omniumEPS/adjCA de l'annee en cours (INSTRUCTIONS.md l.717). Un false
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
            fiche_eps=(t['hypothese'].get('omniumEPS') or {}).get(str(year))
            if not isinstance(fiche_eps,(int,float)): continue
            n=sum(1 for x in sn if isinstance((x.get('epsByYear') or {}).get(str(year)),(int,float)))
            if n<2:
                bad.append((tk,f'{k} ({year}) : {n} point(s) archive(s), courbe absente du trace'))
    return bad

@check("C16 epsAdj.basis : doit valoir GAAP ou non-GAAP, jamais une phrase")
def c16():
    # Signale par une session parallele, verifie ici : quand ce champ porte
    # une phrase au lieu de l'enum, le traitement defensif cote app le traite
    # comme ABSENT - la fiche perd donc silencieusement son paragraphe
    # "Accounting basis". Aucune casse visible, juste une information qui
    # disparait, ce qu'aucun controle de forme ne voyait.
    ENUM={'GAAP','non-GAAP'}
    bad=[]
    for tk,t in FICHES.items():
        dc=t['hypothese'].get('dernierCall') or {}
        ea=((dc.get('resultatsVsConsensus') or {}).get('epsAdj') or {})
        if 'basis' not in ea: continue
        b=ea['basis']
        if not (isinstance(b,str) and b.strip() in ENUM):
            apercu=(b if isinstance(b,str) else repr(b))[:48].replace('\n',' ')
            bad.append((tk,f'hors enum : "{apercu}..."'))
    return bad

@check("X1  relution projetee : doit etre gagee par une contrainte chiffree")
def x1():
    # Pour un industriel, adjND borne ce qui est finançable : un rachat qui
    # ferait deriver le levier se voit. Pour une banque ce garde-fou est
    # absent, et le modele peut projeter une relution que rien ne gage.
    # Cas BNP : -1,8%/an ferme alors que la fiche ecrit que la distribution
    # de l'exces de CET1 "sera determinee annuellement a partir de 2027,
    # non chiffree a ce stade".
    bad=[]
    for tk,t in FICHES.items():
        it=t.get('issuerType') or 'industrial'
        if it=='industrial': continue
        sh_=t['hypothese'].get('adjShares') or {}
        ys=sorted(y for y in sh_ if isinstance(sh_[y],(int,float)))
        if len(ys)<2: continue
        cagr=((sh_[ys[-1]]/sh_[ys[0]])**(1/(len(ys)-1))-1)*100
        if cagr>-1: continue
        cc=t.get('capitalConstraint') or {}
        if cc.get('fundsBuyback') is not True:
            bad.append((tk,f'actions {cagr:+.1f}%/an mais fundsBuyback='
                           f'{cc.get("fundsBuyback")!r} : relution non gagee'))
    return bad

@check("X2  emetteur non industriel : capitalConstraint obligatoire")
def x2():
    ATTENDU={'bank':'CET1','insurer':'SCR','reit':'NAV'}
    bad=[]
    for tk,t in FICHES.items():
        it=t.get('issuerType') or 'industrial'
        if it=='industrial': continue
        cc=t.get('capitalConstraint')
        if not isinstance(cc,dict):
            bad.append((tk,f"issuerType={it} sans capitalConstraint")); continue
        att=ATTENDU.get(it)
        if att and cc.get('metric')!=att:
            bad.append((tk,f"issuerType={it} attend metric={att}, trouve {cc.get('metric')!r}"))
        for k in ('current','requirement'):
            if not isinstance(cc.get(k),(int,float)):
                bad.append((tk,f"capitalConstraint.{k} non chiffre"))
    return bad

@check("X3  contrainte de capital : le niveau doit couvrir l'exigence")
def x3():
    # En dessous de l'exigence reglementaire, la projection n'est pas
    # seulement optimiste : elle n'est pas finançable.
    bad=[]
    for tk,t in FICHES.items():
        cc=t.get('capitalConstraint')
        if not isinstance(cc,dict): continue
        cur,req=cc.get('current'),cc.get('requirement')
        if not all(isinstance(x,(int,float)) for x in (cur,req)): continue
        if cur<req:
            bad.append((tk,f"{cc.get('metric')} {cur}{cc.get('unit','')} < "
                           f"{cc.get('requirementLabel','exigence')} {req}{cc.get('unit','')}"))
    return bad

@check("C17 horizon adjXXX : les 5 annees affichees doivent etre couvertes")
def c17():
    # yearsFor() affiche CY..CY+4 et l'Expected annual return se calcule
    # jusqu'a LY=CY+4. Toute annee non couverte par omniumEPS est servie par la
    # base CAGR "stupide" (getProj) - back-testee a ~37% d'erreur mediane
    # sur le net a 2 ans. Cas reel : MSFT 2031 absent d'omniumEPS, donc le
    # chiffre de tete de fiche reposait sur l'extrapolation, pas l'analyse.
    bad=[]
    for tk,t in FICHES.items():
        h=t['hypothese']; d=t.get('data') or []
        if not d: continue
        ly=d[-1]['year']
        a=h.get('omniumEPS') or {}
        aN=h.get('adjNet') or {}; aS=h.get('adjShares') or {}
        # getProj derive l'EPS de adjNet/adjShares quand omniumEPS manque :
        # une annee n'est en defaut que si AUCUNE des deux voies n'existe.
        couvert=lambda y:(isinstance(a.get(str(y)),(int,float))
            or (isinstance(aN.get(str(y)),(int,float)) and isinstance(aS.get(str(y)),(int,float))))
        manq=[y for y in range(ly+1,ly+6) if not couvert(y)]
        if manq: bad.append((tk,f'omniumEPS absent pour {manq} : base CAGR servie '
                                f'a l\'affichage (dont le CAGR de tete de fiche '
                                f'si {ly+5} manque)'))
    return bad

# ── AVERTISSEMENTS : files de revue au prochain refresh, PAS des anomalies ──
# (n'affectent pas le code de sortie - un invariant dur doit etre rare et
#  certain ; une derive a expliquer est un travail d'analyste, pas un bug)

@check("W1  ~ derive Net/EBIT >10pts entre historique et derniere projection")
def w1():
    bad=[]
    for tk,t in FICHES.items():
        if (t.get('issuerType') or 'industrial')!='industrial': continue
        h=t['hypothese']; d=t.get('data') or []
        hist=[(r.get('net'),r.get('ebit')) for r in d[-3:]]
        hist=[n/e for n,e in hist if isinstance(n,(int,float)) and isinstance(e,(int,float)) and e>0]
        if len(hist)<2: continue
        rh=sum(hist)/len(hist); ly=d[-1]['year']
        aN=h.get('adjNet') or {}; aE=h.get('adjEBIT') or {}
        ys=[y for y in range(ly+1,ly+6)
            if isinstance(aN.get(str(y)),(int,float)) and isinstance(aE.get(str(y)),(int,float)) and aE[str(y)]>0]
        if not ys: continue
        rp=aN[str(ys[-1])]/aE[str(ys[-1])]
        if abs(rp-rh)*100>10:
            bad.append((tk,f'conversion {rh*100:.0f}% (hist) -> {rp*100:.0f}% ({ys[-1]}) : '
                           f'{(rp-rh)*100:+.0f}pts - verifier ancrage IS/financier (E5-c)'))
    return bad

@check("W2  ~ dernier exercice publie : ratio Net/EBIT aberrant (base CAGR polluee ?)")
def w2():
    # Regle E5 d-bis : un vrai one-off (impot exceptionnel, impairment,
    # windfall) doit etre retraite DANS data, sinon il pollue le moteur de
    # CAGR a chaque refresh futur. Un dernier exercice qui devie fortement
    # de la mediane du titre est un candidat - a trancher au refresh
    # (retraiter, ou documenter que c'est operationnel et non exceptionnel).
    bad=[]
    for tk,t in FICHES.items():
        if (t.get('issuerType') or 'industrial')!='industrial': continue
        rs=[(r['year'],r.get('net'),r.get('ebit')) for r in (t.get('data') or [])]
        rs=[(y,n/e) for y,n,e in rs
            if isinstance(n,(int,float)) and isinstance(e,(int,float)) and e>0]
        if len(rs)<5: continue
        med=sorted(r for _,r in rs)[len(rs)//2]
        yL,rL=rs[-1]
        if abs(rL-med)>0.10:
            bad.append((tk,f'{yL} : Net/EBIT {rL*100:.0f}% vs mediane {med*100:.0f}% '
                           f'- one-off non retraite dans data ? (E5 d-bis)'))
    return bad

@check("W3  ~ dette qui monte, conversion qui ne baisse pas (E5 a-ter)")
def w3():
    bad=[]
    for tk,t in FICHES.items():
        if (t.get('issuerType') or 'industrial')!='industrial': continue
        h=t['hypothese']; d=t.get('data') or []
        if not d: continue
        nd0=d[-1].get('nd')
        if not isinstance(nd0,(int,float)) or nd0<=0: continue
        aND=h.get('adjND') or {}
        ys=sorted(int(y) for y in aND if isinstance(aND[y],(int,float)))
        if not ys or aND[str(ys[-1])]<nd0*1.3: continue
        n0,e0=d[-1].get('net'),d[-1].get('ebit')
        aN=h.get('adjNet') or {}; aE=h.get('adjEBIT') or {}
        k=str(ys[-1])
        if not all(isinstance(x,(int,float)) for x in (n0,e0,aN.get(k),aE.get(k))) or e0<=0 or aE[k]<=0: continue
        if aN[k]/aE[k] >= n0/e0-0.01:
            bad.append((tk,f'adjND {nd0:.0f} -> {aND[k]:.0f} (+{(aND[k]/nd0-1)*100:.0f}%) mais '
                           f'conversion {n0/e0*100:.0f}% -> {aN[k]/aE[k]*100:.0f}% : charge '
                           f'financiere integree ? (ou emetteur a reclasser en financier)'))
    return bad

@check("C18 cle legacy adjEPS interdite (renommee omniumEPS le 18/08/2026)")
def c18():
    # Une session de refresh partie d'une doctrine perimee reintroduirait
    # la cle sous son ancien nom : l'app ne la lirait plus, la fiche
    # basculerait silencieusement sur la base CAGR automatique.
    bad=[]
    for tk,t in FICHES.items():
        if 'adjEPS' in (t.get('hypothese') or {}):
            bad.append((tk,'cle adjEPS presente : ecrire omniumEPS'))
    return bad

def main():
    print(f'{len(FICHES)} fiches auditees\n')
    total=0; warns=0
    for nom,fn in CHECKS.items():
        bad=fn()
        is_warn=nom.startswith('W')
        if is_warn: warns+=len(bad)
        else: total+=len(bad)
        etat='OK' if not bad else (f'{len(bad)} A REVOIR' if is_warn else f'{len(bad)} ANOMALIES')
        print(f'{nom}\n     -> {etat}')
        for tk,det in bad[:6]: print(f'        {tk:<20} {det}')
        if len(bad)>6: print(f'        ... et {len(bad)-6} autres')
    print(f'\nTOTAL : {total} anomalies, {warns} points a revoir au prochain refresh')
    return 1 if total else 0

if __name__=='__main__':
    import sys; sys.exit(main())
