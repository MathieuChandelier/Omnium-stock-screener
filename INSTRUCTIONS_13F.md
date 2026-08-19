# INSTRUCTIONS_13F - Operation D : balayage 13F groupe (ownership)

Fichier AUTONOME (cree le 18/08/2026) : une session qui execute cette
operation n'a besoin QUE de ce fichier. L'operation met a jour le SEUL champ
racine `ownership` de chaque `data/CODE.json` du portefeuille - elle ne
touche JAMAIS `hypothese`/`omniumXXX`/`data`/`nextEvent` ni aucun autre champ.

## POURQUOI UNE OPERATION DEDIEE

Les depots 13F ont une cadence CALENDAIRE commune a tout le marche : dus ~45
jours apres chaque cloture trimestrielle, soit vers les 14-15 fevrier, mai,
aout et novembre. Cette cadence est deconnectee de celle des refreshes
individuels (cales sur les resultats de chaque societe). Rechercher
`ownership` a chaque refresh produisait du travail redondant (rien de neuf
entre deux depots) ET des donnees perimees (un titre non refreshe pendant
des mois gardait un ownership obsolete alors qu'un 13F recent existait).
Quatre balayages par an couvrant tout le portefeuille remplacent des
centaines de recherches individuelles.

## DECLENCHEMENT

Alerte trimestrielle du dashboard, visible a partir du ~17 fevrier / 17 mai
/ 17 aout / 17 novembre (2-3 jours apres l'echeance de depot), listant les
titres dont `ownership.asOf` est anterieur a la derniere echeance. L'alerte
s'eteint d'elle-meme a mesure que les `asOf` se mettent a jour - elle est
DERIVEE des fiches, jamais stockee. Demande directe possible a tout moment.

## METHODE (par titre du portefeuille)

Reprise de la regle historique d'E2 (deplacee ici le 18/08/2026) :

  `ownership` (voir SCHEMA pour la definition complete, la regle PROXY =
  ANCRAGE DE VERITE, le perimetre 13F assume, et la WATCHLIST GERANTS
  ACTIFS) : `insiderPct` ancre sur le dernier proxy/rapport annuel
  disponible en priorite (agregateur en corroboration ou repli seulement),
  `insiderDesc`/`insiderSource`, et jusqu'a ~6 `notableHolders` filtres sur
  la watchlist de gerants actifs (voir ANNEXE) issus du dernier 13F
  disponible - gerants americains sur titres cotes aux US UNIQUEMENT,
  gerants passifs/quasi-indiciels toujours ecartes meme si plus gros
  detenteurs, `tier`/`movement` renseignes par entree, tableau vide et
  `coverageNote` renseignee si le titre est hors perimetre (aucune
  recherche d'equivalent local hors US). Ecrit dans le meme mouvement le
  snapshot `history` (ajout du point precedent avant remplacement de
  l'etat courant, plafonne a 8 points - voir mecanique dans le SCHEMA). Ne
  bloque jamais l'analyse si une source fiable n'est pas trouvee (`null`/
  tableau vide plutot qu'une estimation).


## LIVRABLE

Pour chaque titre traite : le champ racine `ownership` mis a jour dans son
`data/CODE.json` (y compris le snapshot `history` : pousser l'etat precedent
avant remplacement, plafond 8 points - mecanique detaillee dans le SCHEMA
d'INSTRUCTIONS.md, section ownership). `asOf` = date du jour du balayage.
Si un acces git/GitHub est disponible : UN commit dedie au balayage (tous
les titres traites ensemble), confirmation du hash apres coup. Sinon : le
dire explicitement et fournir les blocs `ownership` prets a coller.
Un titre hors perimetre 13F (cotation non-US) : `notableHolders` vide +
`coverageNote`, JAMAIS d'equivalent local recherche (choix assume).

## ANNEXE - WATCHLIST GERANTS ACTIFS (13F)


Liste FERMEE utilisee pour filtrer `notableHolders` (voir WATCHLIST
GERANTS ACTIFS - CRITERE DE SELECTION dans la definition du champ
`ownership`). Base sur la liste "Superinvestors" de Dataroma, complementee
de quelques gerants growth/tech concentres pour rehausser la couverture
value historiquement dominante de cette base. Liste vivante : a etoffer au
fil des sessions si un gerant actif pertinent et recurrent n'y figure pas
encore - jamais purgee retroactivement sans instruction explicite de
l'utilisateur.

Gerants explicitement HORS watchlist par principe (passifs/quasi-indiciels,
jamais recherches ni affiches dans `notableHolders` meme en cas de detention
importante) : Vanguard Group, BlackRock, State Street, Fidelity
(gamme indicielle), Geode Capital Management, Northern Trust, Principal
Financial Group, Charles Schwab, Invesco (gamme ETF), Capital Group/
American Funds, Norges Bank Investment Management, Wellington Management
(diversifie a grande echelle).

### TIER 1 - gerants a plus forte notoriete/conviction (toujours prioritaires
### dans l'affichage si presents au dernier 13F)
- Warren Buffett - Berkshire Hathaway
- Bill Ackman - Pershing Square Capital Management
- Carl Icahn - Icahn Capital Management
- David Einhorn - Greenlight Capital
- David Tepper - Appaloosa Management
- Daniel Loeb - Third Point
- Seth Klarman - Baupost Group
- Chase Coleman - Tiger Global Management
- Stephen Mandel - Lone Pine Capital
- Nelson Peltz - Trian Fund Management
- Terry Smith - Fundsmith
- Chris Hohn - TCI Fund Management
- Mohnish Pabrai - Pabrai Investments
- Chuck Akre - Akre Capital Management
- Prem Watsa - Fairfax Financial Holdings
- Viking Global Investors
- ValueAct Capital
- Li Lu - Himalaya Capital Management
- Francois Rochon - Giverny Capital
- Bill Nygren - Oakmark Funds
- Mason Hawkins - Southeastern Asset Management
- Leon Cooperman
- Brad Gerstner - Altimeter Capital (ajout - growth/tech concentre)
- Philippe Laffont - Coatue Management (ajout - growth/tech concentre)

### TIER 2 - reste de la watchlist (affiches en complement du Tier 1, ou
### seuls si aucun Tier 1 present au 13F du titre)
- Abrams Bison Investments
- Lee Ainslie - Maverick Capital
- Bruce Berkowitz - Fairholme Capital
- Bill & Melinda Gates Foundation Trust
- Norbert Lou - Punch Card Management
- Henry Ellenbogen - Durable Capital Partners
- Christopher Bloomstran - Semper Augustus
- Glenn Greenberg - Brave Warrior Advisors
- Alex Roepers - Atlantic Investment Management
- David Rolfe - Wedgewood Partners
- Glenn Welling - Engaged Capital
- Clifford Sosin - CAS Investment Partners
- Arnold Van Den Berg - Century Management
- Bryan Lawrence - Oakcliff Capital
- Bill Miller - Miller Value Partners
- Pat Dorsey - Dorsey Asset Management
- AKO Capital
- Hillman Capital Management
- Tom Bancroft - Makaira Partners
- Ruane Cunniff LP
- Greg Alexander - Conifer Management
- John Rogers - Ariel Investments
- David Abrams - Abrams Capital Management
- First Eagle Investment Management
- Dennis Hong - ShawSpring Partners
- Sarah Ketterer - Causeway Capital Management
- Wallace Weitz - Weitz Investment Management
- Dodge & Cox Funds
- Francis Chou - Chou Associates
- Samantha McLemore - Patient Capital Management
- Polen Capital Management
- First Pacific Advisors
- Mairs & Power Funds
- Third Avenue Management
- Thomas Russo - Gardner Russo & Quinn
- Vulcan Value Partners
- Robert Vinall - RV Capital GmbH
- Josh Tarasoff - Greenlea Lane Capital
- Kahn Brothers Group
- Harry Burn - Sound Shore
- William Von Mueffling - Cantillon Capital Management
- Christopher Davis - Davis Advisors
- Tweedy Browne
- Muhlenkamp
- Jensen Investment Management
- Steven Check - Check Capital Management
- Thomas Gayner - Markel Group
- Yacktman Asset Management
- Whale Rock Capital Partners (ajout - growth/tech concentre)
- D1 Capital Partners (ajout - growth/multi-strategie concentre)
- Generation Investment Management (ajout - growth/qualite concentre)

Non retenus a ce stade (AUM/notoriete tres faibles ou frequence de mise a
jour peu fiable) : Triple Frond Partners, AltaRock Partners, Valley Forge
Capital Management, Torray Funds - a reconsiderer au cas par cas si l'un
d'eux devient pertinent sur une valeur specifique du portefeuille (small/
mid cap notamment).

