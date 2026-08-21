# INSTRUCTIONS_MANAGERS — run trimestriel des positions de gerants

Fichier AUTONOME (cree le 21/08/2026). Une session qui execute cette
operation n'a besoin QUE de ce fichier : la chaine d'acces, le perimetre,
le critere de significativite et la WATCHLIST DES GERANTS SUIVIS y sont
tous inscrits. Rien a lire ailleurs, aucune doctrine a ouvrir.

Cette operation ressuscite la boucle 13F abandonnee le 19/08/2026 sous
une forme differente : plus de collecte continue, plus d'ecriture
automatique dans les fiches. Un run TRIMESTRIEL produit une liste de
mouvements, l'utilisateur les trie dans l'app, et SEULS ceux qu'il
retient entrent plus tard dans `ownership` (voir RETENTION MANUELLE).

L'operation ecrit `data/managerMoves.json` et RIEN D'AUTRE. Elle ne
touche JAMAIS un `data/<CODE>.json`, ni `hypothese`/`omniumXXX`/`data`
d'une fiche. La seule autre ecriture possible est une entree d'echec
dans `data/sourceGaps.json`, section `managers`.

## DECLENCHEMENT

Les 17 FEVRIER, 17 MAI, 17 AOUT et 17 NOVEMBRE, et le run reste DU tant
qu'il n'a pas produit le trimestre attendu (la ligne d'action du
dashboard ne s'eteint que quand `_meta.quarter` vaut le trimestre du
dernier declenchement passe).

Correspondance declenchement -> trimestre couvert :
- 17 fevrier -> Q4 de l'annee PRECEDENTE ;
- 17 mai     -> Q1 de l'annee en cours ;
- 17 aout    -> Q2 ;
- 17 novembre-> Q3.

POURQUOI LE 17. L'echeance legale de depot d'un 13F est de 45 JOURS
apres la cloture du trimestre, soit le 14 ou le 15 du deuxieme mois
suivant. Le 17 laisse TROIS JOURS de marge : les depots de derniere
minute (la norme chez les gros gerants, qui deposent le dernier jour
ouvre) sont tous en ligne, et un decalage de week-end ne fait pas
tourner le run a vide.

Verifie en reel le 21/08/2026 sur Berkshire Hathaway (CIK 0001067983) :
13F-HR du T2 2026 depose le 14/08/2026, T1 2026 le 15/05/2026, T4 2025
le 17/02/2026, T3 2025 le 14/11/2025. Le trimestre est donc toujours
complet a la date de declenchement.

C'est une boucle MANUELLE : l'utilisateur lance la session lui-meme
depuis la ligne d'action "Manager moves — quarterly 13F run" du
dashboard. Aucun token API, aucune automatisation.

## SOURCE : SEC EDGAR, ET RIEN D'AUTRE

Source UNIQUE, gratuite, faisant autorite, sans authentification : les
depots 13F-HR eux-memes sur EDGAR. Jamais un agregateur (whalewisdom,
dataroma, stockcircle...), jamais la presse, jamais un ecran de
consensus : le depot, ou rien.

UN USER-AGENT IDENTIFIANT EST OBLIGATOIRE sur TOUTES les requetes SEC —
sans lui la SEC repond une erreur, pas les donnees :

    User-Agent: Omnium Capital Research mathieu.chandelier@omnium-capital.com

Cadence : rester en dessous de 10 requetes/seconde (une pause de 0,1 a
0,2 s entre appels suffit largement pour 34 gerants).

CHAINE VALIDEE EN REEL LE 21/08/2026, quatre etapes :

1. LISTE DES DEPOTS D'UN GERANT
   `https://data.sec.gov/submissions/CIK##########.json`
   (CIK sur 10 chiffres, zeros a gauche). Dans `filings.recent`, les
   tableaux `form`, `reportDate`, `filingDate`, `accessionNumber` sont
   PARALLELES : filtrer les indices dont `form` commence par `13F-HR`,
   puis retenir celui dont `reportDate` est le trimestre vise (ex.
   `2026-06-30` pour 2026-Q2) et, separement, celui du trimestre
   PRECEDENT (`2026-03-31`) — c'est la comparaison des deux qui produit
   les mouvements.

2. DOSSIER DU DEPOT
   `https://www.sec.gov/Archives/edgar/data/`
   puis `<cik-sans-zeros>/<accessionSansTirets>/`.
   Ex. : accession `0001193125-26-352200`, CIK 1067983 ->
   `.../edgar/data/1067983/000119312526352200/`.

3. TABLE DES POSITIONS
   Le dossier contient un XML d'`<infoTable>` — celui qui n'est PAS
   `primary_doc.xml` (son nom est un numero arbitraire, ex. `56757.xml`,
   `53405.xml` : ne jamais le coder en dur, le lire dans la liste du
   dossier). Chaque `<infoTable>` porte :
   `nameOfIssuer`, `titleOfClass`, `cusip`, `value`, et sous
   `shrsOrPrnAmt` : `sshPrnamt` (nombre de titres) et `sshPrnamtType`.

4. LIEN A PUBLIER dans le champ `url` du mouvement — la page d'index du
   depot, verifiee 200 le 21/08/2026 :
   le dossier de l'etape 2, suivi de
   `<accession-avec-tirets>-index.htm`. Soit, pour l'exemple :
   `https://www.sec.gov/Archives/edgar/data/1067983/`
   `000119312526352200/0001193125-26-352200-index.htm`
   (les deux fragments se concatenent sans separateur ; coupes ici pour
   tenir dans la colonne).

## PIEGES VERIFIES SUR LE DEPOT BERKSHIRE T2 2026

Six pieges, tous constates en reel sur le fichier
`.../000119312526352200/56757.xml` (89 lignes brutes) et son homologue
du T1 2026 (`.../000119312526226661/53405.xml`, 90 lignes).

1. UN EMETTEUR APPARAIT PLUSIEURS FOIS DANS LE MEME DEPOT. Les
   sous-gestionnaires (`<otherManager>`) declarent chacun leur part :
   Berkshire T2 2026 = 89 lignes pour seulement 29 CUSIP distincts —
   APPLE sur 12 lignes, BANK OF AMERICA sur 8, ALPHABET classe A sur 4.
   AGREGER PAR CUSIP (somme de `value` et de `sshPrnamt`) AVANT tout
   calcul de delta. Sans cette agregation, un mouvement est invente a
   chaque fois qu'un sous-gestionnaire change de perimetre.

2. UN EMETTEUR PEUT PORTER PLUSIEURS CUSIP (classes d'actions).
   ALPHABET figure sous 02079K305 (CAP STK CL A) et 02079K107 (CAP STK
   CL C). La fiche du portefeuille est UNE fiche par emetteur : apres
   l'agregation par CUSIP, AGREGER LES CUSIP D'UN MEME EMETTEUR sous le
   ticker du manifest. Verifie : Berkshire detenait 78 791 167 A +
   27 188 433 C = 105 979 600 actions Alphabet au T2 2026, contre
   54 249 798 + 3 585 215 = 57 835 013 au T1, soit +48 144 587 titres
   (+83,2 %). Traiter les classes separement aurait produit DEUX
   mouvements, tous deux faux.

3. `value` EST EN DOLLARS ENTIERS, PAS EN MILLIERS. C'est le point le
   plus dangereux du format, parce qu'une erreur d'unite passe les
   controles sans rien casser : elle deplace `valueAfterUsd` et le seuil
   de significativite d'un facteur 1000. Depuis la refonte du formulaire
   13F (2023), `value` est libelle en dollars entiers. Verifie
   arithmetiquement : Berkshire declare 227 917 808 actions Apple pour
   value 65 950 300 000 environ, soit ~289 $/action — le cours reel ;
   et la somme des `value` du depot vaut 299 253 556 246, soit 299 Md$,
   la taille reelle du portefeuille. Lues en milliers, ces memes lignes
   donneraient 66 000 Md$ et 299 000 Md$ : absurdes.
   CONTROLE DE PLAUSIBILITE OBLIGATOIRE avant d'ecrire quoi que ce soit :
   la somme des `value` d'un depot doit tomber entre ~1 et ~500 Md$. En
   dehors, l'unite est mal lue — ne pas ecrire le fichier.
   (Les depots ANTERIEURS a 2023 sont, eux, en milliers. Le run ne
   compare que deux trimestres consecutifs recents, donc homogenes ; la
   regle est rappelee pour le jour ou une comparaison longue serait
   demandee.)

4. `sshPrnamtType` VAUT `SH` OU `PRN`. `SH` = actions, `PRN` = montant
   principal d'un titre de dette convertible. IGNORER TOUTES LES LIGNES
   `PRN` : leur `sshPrnamt` n'est pas un nombre d'actions et les melanger
   fabrique des deltas monstrueux.

5. LES AMENDEMENTS `13F-HR/A` EXISTENT ET COMPTENT. Prendre pour un
   trimestre le depot le PLUS RECENT le concernant. Dans `primary_doc.xml`
   d'un amendement, `<amendmentType>` distingue deux cas :
   - `RESTATEMENT` : la table remplace INTEGRALEMENT celle du depot
     initial — utiliser la table amendee seule ;
   - `NEW HOLDINGS` : l'amendement AJOUTE des lignes qui etaient sous
     traitement confidentiel — fusionner avec la table initiale.
   Verifie en reel : Berkshire a amende son T1 2025 le 14/08/2025 en
   `NEW HOLDINGS`, motif `Confidential Treatment Expired`. Un gerant qui
   demande le secret sur une position en construction la revele ainsi
   plusieurs mois plus tard.

6. `13F-NT` N'EST PAS UN `13F-HR`. Le formulaire `13F-NT` (notice)
   declare que les titres sont reportes par un AUTRE gerant : il ne
   contient aucune position. Le filtre `form` commence par `13F-HR` les
   ecarte naturellement — ne pas l'assouplir.

## PERIMETRE, ET SA LIMITE, NOIR SUR BLANC

UN 13F NE DECLARE QUE LES TITRES COTES AUX ETATS-UNIS (section 13(f)
securities : actions cotees NYSE/Nasdaq/NYSE American et assimiles). Un
gerant peut detenir 8 % d'Hermes sans qu'aucun 13F ne le montre.

Sur les 59 lignes de `data/manifest.json` : 34 ELIGIBLES, 25 HORS
PERIMETRE.

ELIGIBLES (34) : AAPL, ABNB, ABT, ALPHABET, AMAZON, ARGENX,
ARISTANETWORKS, AVGO, BOOKING, BOSTONSCIENTIFIC, COCACOLA, CPRT,
DANAHER, DEXCOM, EDWARDSLIFESCIENCES, IBKR, INSULET, INTUIT,
INTUITIVESURGICAL, LILLY, MERCADOLIBRE, META, MICROSOFT, NETFLIX, NIKE,
NUBANK, NVIDIA, REPLIGEN, ROBINHOOD, SFM, SHARKNINJA, SNAP, SPOTIFY,
THERMOFISHER.

HORS PERIMETRE (25) : AMADEUS, BIOMERIEUX, BNP, BREMBO, BUREAUVERITAS,
CAMPARI, DELONGHI, DIASORIN, ESSILORLUXOTTICA, FUCHS, HEINEKEN, HERMES,
JCDECAUX, KERING, LONZA, LVMH, MONCLER, NEMETSCHEK, RATIONAL,
SARTORIUSSTEDIM, SCHNEIDER, SEB, STRAUMANN, UCB, VIDRALA.

Un ADR de gre a gre (HEINY, ESLOY...) ne fait pas entrer un titre dans
le perimetre : ces lignes ne figurent pas sur la liste officielle des
13(f) securities et ne sont pas declarees. La regle reste : cote sur un
marche US, ou hors perimetre.

LA NOTIFICATION DOIT LE RAPPELER. `_meta.note` porte la phrase, et
`_meta.tickersEligible` / `_meta.tickersTotal` portent les nombres. Sans
cela, l'absence de LVMH dans la liste se lirait comme une absence de
MOUVEMENT sur LVMH — c'est-a-dire comme une information, alors que c'est
un angle mort de la source. Ces deux lectures sont exactement inverses ;
c'est la raison d'etre du rappel.

SCALABILITE : le manifest fait autorite. Un ticker ajoute entre dans le
perimetre au run suivant (a condition d'etre cote aux US), un ticker
retire disparait — le fichier etant integralement regenere a chaque run,
et l'app filtrant deja mouvements et retentions par le manifest, aucune
purge specifique n'est necessaire. Recompter `tickersEligible` et
`tickersTotal` A CHAQUE RUN plutot que reprendre 34/59 : ce sont des
constats, pas des constantes.

## OPERATION

Pour CHAQUE gerant de la WATCHLIST (section dediee plus bas) :

1. Lire `submissions/CIK##########.json`, isoler le 13F-HR du trimestre
   vise (N) et celui du trimestre precedent (N-1), amendements pris en
   compte (piege 5).
2. Telecharger les deux tables `<infoTable>` et, pour chacune :
   ecarter les lignes `PRN`, agreger par CUSIP, puis agreger les CUSIP
   d'un meme emetteur (pieges 1, 2, 4).
3. Calculer le TOTAL du depot N (somme des `value` de toutes les lignes,
   perimetre entier et pas seulement les titres suivis) — c'est le
   denominateur de `weightInManagerPct`. Passer le controle de
   plausibilite du piege 3.
4. Ne retenir que les emetteurs correspondant a un TICKER ELIGIBLE du
   manifest. Le rapprochement se fait sur `nameOfIssuer` normalise
   (majuscules, ponctuation et suffixes `INC`/`CORP`/`CO`/`PLC`/`LTD`/
   `NV`/`SA` retires), puis se CONFIRME sur le CUSIP : une fois le CUSIP
   identifie pour un titre, c'est lui qui sert a joindre N et N-1, jamais
   le nom (les gerants n'orthographient pas l'emetteur de la meme facon —
   Berkshire ecrit "BANK OF AMER CORP" au T2 et "BANK AMERICA CORP" au
   T1 pour le meme CUSIP 060505104).
5. Comparer N et N-1 emetteur par emetteur et produire les mouvements.

ACTIONS :
- `new`      : absent en N-1, present en N ;
- `exit`     : present en N-1, absent en N ;
- `increase` : `sharesAfter` > `sharesBefore` ;
- `decrease` : `sharesAfter` < `sharesBefore`.

CHAMPS CALCULES :
- `sharesBefore` / `sharesAfter` : nombres de titres AGREGES (0 pour
  l'absent d'un `new` ou d'un `exit` — jamais `null`, la difference
  doit rester calculable) ;
- `deltaShares` = `sharesAfter` - `sharesBefore`, signe ;
- `deltaPct` = `deltaShares` / `sharesBefore` x 100, UNE decimale.
  Pour un `new`, le denominateur est nul : ecrire `null`, jamais une
  valeur symbolique. Pour un `exit`, c'est -100.0 ;
- `valueAfterUsd` : `value` agrege du trimestre N, en DOLLARS ENTIERS
  (piege 3). Pour un `exit`, 0 ;
- `weightInManagerPct` : `valueAfterUsd` / total du depot N x 100, UNE
  decimale. Pour un `exit`, 0.0 — et le poids qui compte pour le tri est
  alors celui de la ligne en N-1 (voir SIGNIFICATIVITE) ;
- `filedAt` : `filingDate` du depot N, `YYYY-MM-DD` ;
- `quarter` : `YYYY-Qn` du trimestre vise.

JAMAIS DE DONNEE INVENTEE. Un chiffre qui ne sort pas des deux depots
lus pendant le run n'entre pas dans le fichier. Un gerant dont un seul
des deux trimestres est lisible ne produit AUCUN mouvement (on ne
compare pas a une position supposee) : il part en `sourceGaps`.

## SIGNIFICATIVITE : SEUIL DE BRUIT, PUIS PLAFOND DE 50

Deux filtres distincts, dans cet ordre. Le premier definit ce qu'est un
MOUVEMENT ; le second choisit lesquels tiennent dans la notification.

### 1. SEUIL DE BRUIT (definition du mouvement)

Un `increase` ou un `decrease` n'est un mouvement que s'il franchit AU
MOINS UN des deux seuils :
- variation d'au moins 5 % de la position en N-1 (`|deltaPct| >= 5`) ;
- OU variation d'au moins 10 M USD en valeur absolue, estimee au cours
  du trimestre (`|deltaShares| x valueAfterUsd / sharesAfter`).

Un `new` ou un `exit` n'est un mouvement que si la ligne pese au moins
10 M USD au trimestre ou elle existe (`valueAfterUsd` pour un `new`,
valeur en N-1 pour un `exit`).

ARGUMENTAIRE. Un fonds ouvert achete et vend en permanence pour des
raisons qui n'ont rien a voir avec sa these : souscriptions, rachats,
rebalancement, gestion de cash. Ces flux deplacent couramment 1 a 3 %
d'une ligne d'un trimestre a l'autre. Les lire comme un signal, c'est
notifier le plombier du fonds, pas son gerant. Le seuil de 5 % passe
franchement au-dessus de cette derive.
La disjonction (5 % OU 10 M USD) existe parce qu'aucun des deux seuils
ne suffit seul, et qu'ils rattrapent des cas opposes : un gerant de
50 Md$ qui bouge 3 % d'une ligne de 2 Md$ engage 60 M USD — decision
majeure invisible au seuil relatif ; un gerant de 800 M$ qui double une
ligne de 4 M$ n'engage que 4 M USD — decision d'entree pleine et entiere,
invisible au seuil absolu. Le OU garde les deux.
Le plancher de 10 M USD sur les `new`/`exit` est necessaire parce qu'une
entree est structurellement +infini en pourcentage : sans lui, une
position de sondage a 300 k$ chez Tiger Global remonterait devant une
coupe de 400 M USD chez Fundsmith.

Ce qui n'atteint pas ces seuils N'EST PAS un mouvement et n'est donc PAS
compte : `_meta.movesFound` denombre les mouvements SIGNIFICATIFS
detectes, bruit exclu. C'est ce qui rend l'ecart
`movesFound - movesKept` lisible dans l'app : il ne dit qu'une chose,
"tant de vrais mouvements n'ont pas tenu sous le plafond".

### 2. PLAFOND DE 50, ET SON ORDRE DE TRI

Au maximum 50 mouvements sont LISTES. Au-dela, tri par les quatre cles
suivantes, dans cet ordre strict :

1. NATURE : `new` et `exit` d'abord, avant tout `increase`/`decrease`.
   Une entree ou une sortie complete est un changement d'etat binaire :
   le gerant n'avait pas d'avis, il en a un — ou l'inverse. C'est la
   seule information du lot qu'aucun renforcement, si gros soit-il, ne
   peut produire.
2. VARIATION EN VALEUR ABSOLUE USD (decroissante). C'est l'argent
   REELLEMENT engage ou libere. Deuxieme et pas premiere, parce qu'elle
   favorise mecaniquement les tres gros fonds ; mais c'est la mesure la
   moins manipulable de l'intensite d'une decision.
3. POIDS DE LA LIGNE CHEZ LE GERANT (`weightInManagerPct`
   decroissant ; pour un `exit`, le poids en N-1). Correctif du critere
   precedent : 500 M USD chez un gerant de 60 Md$ est une ligne de
   remplissage, 500 M USD chez un gerant de 3 Md$ est le coeur du fonds.
4. VARIATION EN POURCENTAGE (`|deltaPct|` decroissant). En DERNIER, et
   volontairement : le pourcentage est degenere sur petite base — une
   ligne de 900 titres portee a 2 700 fait +200 % et ne dit rien. Il ne
   sert donc que de departage.

Le plafond ne modifie jamais `_meta.movesFound` : les mouvements ecartes
sont COMPTES et non listes.

## LIVRABLE : `data/managerMoves.json`

Un seul fichier, integralement regenere a chaque run.

```
{"_meta":{"generatedAt":"<ISO UTC>","quarter":"2026-Q2","managersCovered":N,
  "tickersEligible":34,"tickersTotal":59,"movesFound":N,"movesKept":N,
  "note":"13F = US-listed only, 25 non-US holdings out of scope"},
 "moves":[{"id":"<TICKER>-<2026Q2>-<manager-slug>","ticker":"ALPHABET",
   "manager":"Berkshire Hathaway","managerCik":"0001067983",
   "action":"new|exit|increase|decrease","sharesBefore":N,"sharesAfter":N,
   "deltaShares":N,"deltaPct":213.4,"valueAfterUsd":N,
   "weightInManagerPct":6.1,"quarter":"2026-Q2","filedAt":"2026-08-14",
   "url":"<lien EDGAR du depot>","summary":"<une phrase en anglais>"}]}
```

CONTRAINTES DE FORME, toutes portantes :
- `_meta.quarter` s'ecrit EXACTEMENT `YYYY-Qn`. C'est ce champ, et lui
  seul, qui eteint la ligne d'action "quarterly run due" du dashboard :
  une faute de format laisse le run marque comme non fait.
- `id` : `<TICKER>-<AAAAQn>-<manager-slug>` — le TICKER EN PREMIER, le
  trimestre SANS TIRET (`2026Q2`), le slug du gerant en minuscules ascii
  avec des tirets (`berkshire-hathaway`, `fundsmith`, `tci-fund-
  management`). L'app deduit le ticker d'un mouvement en coupant l'id au
  PREMIER tiret : un id qui ne commence pas par le ticker exact du
  manifest rend le mouvement infiltrable et non purgeable. Le slug d'un
  gerant est STABLE d'un trimestre a l'autre.
- `managerCik` : les 10 chiffres, zeros a gauche, en CHAINE.
- `ticker` : le code du manifest, tel quel.
- `summary` : UNE phrase FACTUELLE EN ANGLAIS, dans le style
  "Berkshire more than triples its Alphabet stake to 65.8m shares
  (6.1% of the portfolio)". Elle porte la nature du mouvement,
  l'ampleur, la position d'arrivee et le poids. JAMAIS d'interpretation,
  jamais de causalite supposee, jamais de projection : pas de "signalant
  sa confiance dans", pas de "avant les resultats", pas de "pari sur
  l'IA". Le gerant a achete ou vendu ; ce qu'il en pensait n'est pas
  dans le depot.

Commit unique ("Manager moves 13F — <trimestre>"), push sur `main`.

## ECHEC = NOTIFICATION TYPEE

Jamais d'echec silencieux, jamais de chiffre invente pour combler un
trou. Un gerant dont le depot est introuvable, incomplet ou illisible
(dossier sans XML d'`infoTable`, XML tronque, trimestre N-1 absent,
requete refusee) est INSCRIT dans `data/sourceGaps.json`, section
`managers` — a CREER si elle n'existe pas :

```
{"ticker":"<TICKER du manifest>","manager":"<nom>","cik":"<10 chiffres>",
 "status":"a_recollecter","note":"<cause courte>","url":"<lien EDGAR>"}
```

`ticker` EST OBLIGATOIRE : le panneau Actions du dashboard est indexe
par titre et ignore toute entree dont le ticker n'est pas au manifest.
Une entree sans ticker est ecrite dans un fichier que rien n'affiche —
c'est-a-dire un echec silencieux avec plus d'etapes.

REGLE D'AFFECTATION, pour ne pas noyer le panneau. Un gerant illisible
ne genere PAS 34 entrees :
- inscrire une entree par couple (ticker, gerant) pour les SEULS tickers
  eligibles que ce gerant detenait au trimestre PRECEDENT (donnee deja
  connue du run precedent, typiquement zero a quatre titres) — ce sont
  les seuls dont le suivi devient aveugle ;
- si le gerant n'a jamais ete lu et qu'aucun ticker ne peut lui etre
  rattache, aucune entree n'est possible : le nommer alors dans
  `_meta.note` de `managerMoves.json` et NE PAS le compter dans
  `managersCovered`. L'ecart entre `managersCovered` et la taille de la
  watchlist est alors la notification.

L'entree est EFFACEE par la passe qui reussit a lire le gerant (la
ligne d'action du dashboard fournit le prompt de reprise). Une entree
dont le ticker quitte le manifest est ignoree par l'app.

## RETENTION MANUELLE ET ENTREE DANS `ownership`

CE RUN N'ECRIT JAMAIS DANS UNE FICHE. Il ne fait que proposer.

Le parcours complet, dont ce run n'est que la premiere moitie :
1. le run publie `data/managerMoves.json` ;
2. l'app affiche les mouvements dans la carte NEWS, famille "Manager
   moves — 13F positions". Chaque ligne porte DEUX boutons : la croix
   (traite, sans suite) et l'epingle (JE LE RETIENS) ;
3. les mouvements retenus s'empilent dans une file cote serveur
   (`server/managers.php`) et une ligne d'action "N retained to apply"
   apparait ;
4. une SESSION D'APPLICATION distincte, lancee par l'utilisateur depuis
   cette ligne, ecrit ces mouvements — CEUX-LA ET AUCUN AUTRE — dans les
   fiches, puis vide la file (`action=applied`).

CE QUE LE RUN D'APPLICATION ECRIT, dans `ownership.notableHolders` de la
fiche concernee, au format EXACT deja en place (aller lire
`data/ALPHABET.json` AVANT d'ecrire) — un objet
`{investor, pct, tier, movement, asOf, source}` :
- `investor` : `"<Gerant principal> - <Societe de gestion>"` quand le
  principal est connu (ex. `"Warren Buffett - Berkshire Hathaway"`),
  sinon la seule societe de gestion ;
- `pct` : part du CAPITAL de la societe detenue apres le mouvement
  (`sharesAfter` rapporte aux actions en circulation, en %). CE N'EST
  PAS `weightInManagerPct`, qui est le poids de la ligne dans le
  portefeuille du GERANT — les deux nombres n'ont ni le meme
  denominateur ni le meme sens. Faute de source solide : `null`, jamais
  une valeur inventee, jamais le poids portefeuille a la place ;
- `tier` : reprendre la convention DEJA utilisee dans la fiche
  concernee (1/2 chez certaines, "T1"/"T2" chez d'autres) — ne pas
  l'harmoniser au passage ;
- `movement` : une phrase factuelle EN ANGLAIS — nature du mouvement,
  ampleur, nombre d'actions apres, rang dans le portefeuille du gerant
  s'il est connu. Les entrees deja presentes dans les fiches sont en
  francais (heritage d'avant ce run) : ne pas les retraduire au passage,
  la regle vaut pour ce qui s'ecrit a partir de maintenant ;
- `asOf` : le trimestre, `"2026-Q2"` ;
- `source` : le lien EDGAR du depot.
Mettre `ownership.asOf` a jour s'il est plus ancien, valider chaque
fiche modifiee avec `python3 scripts/validate_ticker.py
data/<TICKER>.json`, et ne toucher a RIEN d'autre.

REGLE D'OR — `ownership` NE CONTIENT QUE DU MATERIEL. Deux natures, pas
une de plus :
1. LES FONDATEURS ET DIRIGEANTS AU-DESSUS DE 1 % (`insiderPct`,
   `insiderDesc`, `insiderSource`), rafraichis a CHAQUE refresh du
   titre, independamment de ce run — le run trimestriel n'y touche
   jamais ;
2. LES SEULS MOUVEMENTS DE GERANTS EXPLICITEMENT RETENUS par
   l'utilisateur dans l'app.
Aucun remplissage automatique, aucun gerant ajoute pour faire nombre,
aucune position non retenue — meme si elle parait interessante en
passant. Un `notableHolders` qui grossit tout seul redevient un tableau
de detention, c'est-a-dire du bruit ; ce champ existe pour dire qui
compte, pas qui detient.

## WATCHLIST DES GERANTS SUIVIS

34 gerants. Cette liste EST le perimetre du run : elle remplace
l'"ANNEXE WATCHLIST GERANTS ACTIFS" citee par la doctrine principale et
qui n'a jamais existe.

CRITERES D'ADMISSION : gestion ACTIVE et CONCENTREE, historique de
conviction (lignes tenues des annees, pas des trimestres), pertinence
pour un portefeuille de QUALITE / CROISSANCE INTERNATIONALE.

EXCLUS PAR PRINCIPE, quelle que soit leur taille : Vanguard, BlackRock,
State Street, Principal, Geode, Northern Trust, et tout gestionnaire
passif ou indiciel. Leurs 13F sont mecaniques — ils suivent un indice.
Un "renforcement" de 4 % chez Vanguard signifie qu'un investisseur final
a souscrit, pas qu'un gerant a pense quelque chose. Les y chercher, ce
serait notifier des flux en les prenant pour des avis. Meme raison pour
les grands multi-strategies quantitatifs (Renaissance, Two Sigma,
Millennium, Citadel) : des milliers de lignes a rotation rapide, ou
aucune position n'est une conviction.

TOUS LES CIK CI-DESSOUS ONT ETE VERIFIES EN REEL SUR EDGAR LE
21/08/2026 : entite existante, et 13F-HR de `reportDate` 2026-06-30
effectivement depose. Aucun n'est incertain.

### QUALITE / CROISSANCE INTERNATIONALE (14)

Fundsmith LLP                                       CIK 0001569205
  Terry Smith. ~25 lignes, rotation quasi nulle, doctrine qualite
  explicite ; l'un des rares a detenir a la fois les compounders US et
  les grandes marques europeennes du portefeuille.

Lindsell Train Ltd                                  CIK 0001484150
  Nick Train. Portefeuille de marques et de franchises tenu sur des
  decennies ; une vente y est un evenement rare et donc informatif.

Comgest Global Investors S.A.S.                     CIK 0001574947
  Maison francaise "quality growth", horizon long, concentration forte.
  Depose bien un 13F sur son perimetre US (verifie, depot du 24/07/2026).

Veritas Asset Management LLP                        CIK 0001541448
  Global quality, ~30 lignes, discipline de valorisation stricte.

AKO Capital LLP                                     CIK 0001376879
  Nicolai Tangen puis equipe. Qualite europeenne et US, concentre.

Egerton Capital (UK) LLP                            CIK 0001581811
  Long biais fort, lignes tres larges sur un petit nombre de titres.

Findlay Park Partners LLP                           CIK 0001351950
  Fonds americain gere de Londres, qualite/croissance, faible rotation.

Baillie Gifford & Co                                CIK 0001088875
  Croissance seculaire, tolerance a la volatilite, positions tenues
  longtemps. La reference sur les titres de croissance internationale.

Harding Loevner LP                                  CIK 0000928196
  Qualite/croissance internationale, processus tres codifie.

WCM Investment Management, LLC                      CIK 0001061186
  Qualite/croissance globale centree sur l'avantage concurrentiel et la
  culture d'entreprise ; forte exposition aux titres du portefeuille.

Polen Capital Management LLC                        CIK 0001034524
  ~25 lignes, criteres de qualite chiffres et publics, faible rotation.

Sands Capital Management, LLC                       CIK 0001020066
  Croissance seculaire concentree, horizon annonce de 5 ans et plus.

Cantillon Capital Management LLC                    CIK 0001279936
  Qualite globale, portefeuille resserre, tres peu de communication —
  le 13F est la seule fenetre.

Generation Investment Management LLP                CIK 0001375534
  Croissance durable, ~40 lignes, rotation faible, convictions assumees.

### ECOLE DES COMPOUNDERS (7)

Berkshire Hathaway Inc                              CIK 0001067983
  29 emetteurs pour 299 Md$ au T2 2026, detentions en decennies : tout
  mouvement y est une decision, jamais un flux.

Akre Capital Management LLC                         CIK 0001112520
  Doctrine des "compounding machines", une vingtaine de lignes, l'une
  des plus faibles rotations du secteur.

Gardner Russo & Quinn LLC                           CIK 0000860643
  Tom Russo. Specialiste des marques mondiales de consommation et de la
  "capacity to suffer" — le gerant le plus proche du biais europeen du
  portefeuille parmi ceux qui deposent un 13F.

Ruane, Cunniff & Goldfarb L.P.                      CIK 0001720792
  Maison du Sequoia Fund, concentration historique et duree.
  ATTENTION : le 13F vit sous l'entite L.P. ; l'entite INC
  (CIK 0000728014) n'a plus depose depuis 2018.

Giverny Capital Inc.                                CIK 0001641864
  Francois Rochon. Portefeuille de qualite tres concentre, lettre
  annuelle detaillee, rotation minimale.

Broad Run Investment Management, LLC                CIK 0001568621
  ~15 lignes, "focused, low-turnover", forte conviction par ligne.

Select Equity Group, L.P.                           CIK 0001592643
  Recherche fondamentale proprietaire, qualite, horizon long.

### CROISSANCE CONCENTREE (7)

Tiger Global Management LLC                         CIK 0001167483
  Croissance mondiale, positions publiques concentrees ; deja present
  dans l'ownership de plusieurs fiches du portefeuille.

Lone Pine Capital LLC                               CIK 0001061165
  Ecole Tiger, portefeuille resserre sur des franchises de croissance.

Viking Global Investors LP                          CIK 0001103804
  Recherche fondamentale profonde, lignes de taille significative.

Coatue Management LLC                               CIK 0001135730
  Technologie et plateformes, convictions larges assumees.

Durable Capital Partners LP                         CIK 0001798849
  Henry Ellenbogen. Croissance de qualite, horizon long revendique.

Altimeter Capital Management, LP                    CIK 0001541617
  Brad Gerstner. Tres concentre, mouvements souvent brutaux et donc
  lisibles.

Dragoneer Investment Group, LLC                     CIK 0001602189
  Croissance de qualite, peu de lignes cotees, tenues longtemps.

### ACTIVISTES ET CONVICTIONS CONCENTREES (4)

Pershing Square Inc.                                CIK 0002026053
  Bill Ackman. 8 a 12 lignes, chaque mouvement documente publiquement.
  ATTENTION, MIGRATION D'ENTITE EN COURS : le depot du T2 2026
  (14/08/2026) est sous cette entite ; l'historique est sous Pershing
  Square Capital Management, L.P. (CIK 0001336528), dont le dernier
  depot est le T1 2026. Pour un trimestre a cheval, lire LES DEUX et
  agreger avant comparaison.

TCI Fund Management Ltd                             CIK 0001647251
  Chris Hohn. Une dizaine de lignes, tenues des annees, activisme cible.

ValueAct Holdings, L.P.                             CIK 0001418814
  Une dizaine de lignes, engagement long au conseil des societes.

Trian Fund Management, L.P.                         CIK 0001345471
  Nelson Peltz. Consommation et industrie, positions tres concentrees.

### VEHICULES PATRIMONIAUX CONCENTRES (2)

Gates Foundation Trust                              CIK 0001166559
  Portefeuille etroit et stable ; les arbitrages y sont rares et donc
  significatifs.

Duquesne Family Office LLC                          CIK 0001536411
  Stanley Druckenmiller. Rotation elevee mais concentration forte : le
  13F donne un instantane d'allocation lisible.

### CIK PERIMES — PIEGE A NE PAS REPRODUIRE

Un CIK faux ou perime ne provoque AUCUNE erreur visible : la requete
reussit, le gerant n'a simplement plus de depot recent, et il devient
invisible. Ces sept entites ont ete ecartees pour cette raison exacte,
apres verification le 21/08/2026 — ne pas les reintroduire :

- RUANE, CUNNIFF & GOLDFARB INC        0000728014 — dernier 13F 2018-Q1
  (l'entite vivante est la L.P., 0001720792, retenue ci-dessus)
- APPALOOSA MANAGEMENT LP              0001006438 — dernier 13F 2015-Q4
  (l'entite vivante est Appaloosa LP, 0001656456)
- Cantillon Capital Management LLP     0001352269 — dernier 13F 2013-Q1
  (l'entite vivante est la LLC, 0001279936, retenue ci-dessus)
- BAILLIE GIFFORD OVERSEAS LTD         0001085972 — dernier 13F 2001
  (l'entite deposante est Baillie Gifford & Co, 0001088875)
- Pershing Square Capital Management   0001336528 — dernier 13F 2026-Q1
  (migration vers 0002026053, voir ci-dessus)
- Bares Capital Management, Inc.       0001340807 — dernier 13F 2025-Q3
- Ensemble Capital Management, LLC     0001387366 — dernier 13F 2024-Q3

CONTROLE A FAIRE A CHAQUE RUN, avant toute collecte : pour chaque gerant
de la watchlist, verifier qu'un 13F-HR de `reportDate` egal au trimestre
vise existe. Ceux qui n'en ont pas ne sont PAS "sans mouvement" — ils
sont NON LUS, et relevent de la section ECHEC ci-dessus. Un gerant qui
cesse durablement de deposer (fonds ferme, actifs sous le seuil des
100 M USD, changement d'entite) doit etre remplace dans cette watchlist,
pas laisse a pourrir.
