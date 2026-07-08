# INSTRUCTIONS POUR TOUT ASSISTANT IA (Claude, GPT, Gemini, etc.)
# travaillant sur le portefeuille Omnium Invest

## ARCHITECTURE DU DEPOT

Le portefeuille vit sur GitHub, dans le depot `Omnium-stock-screener`, sous cette forme :

```
index.html              <- le moteur (jamais modifie pour un titre)
Logotype-Omnium.png
data/
  manifest.json          <- la liste des codes de titres a charger
  TICKER1.json            <- un fichier par titre, autonome
  TICKER2.json
  ...
```

- `manifest.json` contient UN SEUL champ : `{"tickers": ["CODE1", "CODE2", ...]}`.
- Chaque `data/CODE.json` est un objet AUTONOME (pas de cle wrapper, pas de
  "tickers": {...} autour) correspondant exactement au schema ci-dessous.
- `index.html` charge `data/manifest.json`, puis chaque `data/CODE.json` en
  parallele. Un fichier de titre en echec (absent, invalide) est IGNORE sans
  bloquer les autres.
- `index.html` n'est JAMAIS retouche pour ajouter/modifier/supprimer un titre.
  Retirer un titre = supprimer son fichier + son code dans manifest.json,
  operation manuelle, ne necessite aucun assistant IA.

## SCHEMA D'UN FICHIER DE TITRE (data/CODE.json)

```json
{
  "name": "Nom affiche",
  "cours": 85.90,
  "yahooSymbol": "VID.MC",
  "dividende": 1.70,
  "data": [
    {"year":2015,"ca":1080,"ebit":173,"net":145.2,"shares":33,"nd":150,"div":1.16},
    ...
  ],
  "epsConsensus": {"year":2026,"eps":0.88,"epsNY":1.15,"date":"2026-07-01","source":"..."},
  "particularites": [
    {"text":"Explication CONCRETE et complete du fait pris en compte (jamais un chiffre seul).","valuePct":5}
  ],
  "hypothese": {
    "date":"2026-07-02",
    "source":"Refresh T2 2026 - Transcript T2 2026",
    "summary":"Resume 2 lignes de la these actuelle.",
    "text":"Voir STANDARD D'ARCHIVAGE ci-dessous.",
    "impact":"positif|negatif|neutre",
    "adjEPS":{"2026":0.70,"2027":...},
    "adjCA":{"2026":3820,...},
    "adjEBIT":{...},
    "adjNet":{...},
    "adjND":{...},
    "adjShares":{...}
  }
}
```

Le CODE (nom de fichier, sans `.json`) est en MAJUSCULES, sans espace ni
accent (ex: `BUREAUVERITAS`, `DELONGHI`). Les cles adjXXX sont indexees par
annee (les 5 annees de projection en cours). Seules les annees/metriques
renseignees ecrasent la base CAGR historique automatique ; le reste continue
a etre extrapole depuis "data" par le moteur.

## LES DEUX SEULES OPERATIONS

Il n'existe que DEUX types de requetes possibles. Identifie laquelle des
deux avant de commencer.

### OPERATION A : AJOUTER UN TITRE (creation)
Declencheurs : "ajoute [Societe] au portefeuille", "cree une position sur [Societe]".

### OPERATION B : REFRESH D'UN TITRE
Declencheurs : "fais un refresh de [Titre]", "actualise [Titre]". L'utilisateur
fournit dans sa requete le fichier JSON existant du titre (colle son contenu).

## QUESTION D'ENTREE UNIQUE (les deux operations)

Avant de derouler la boucle d'analyse, pose TOUJOURS cette question unique
(sauf si la reponse est deja donnee dans la requete) :

> "Avez-vous un ou plusieurs transcripts de resultats recents a fournir, et
> y a-t-il UN OU PLUSIEURS evenements particuliers a prendre en compte
> (structurels ou ponctuels, chiffres ou qualitatifs) ?"

L'utilisateur peut citer PLUSIEURS elements en reponse, de deux natures
differentes qu'il faut distinguer a l'ecriture (E3/E4/E8) :

- **PARTICULARITE STRUCTURELLE** (recurrente, impacte un calcul CHAQUE
  annee de la meme facon) : ex. distribution gratuite d'actions annuelle
  (Vidrala), mecanisme capitalistique atypique. Peut etre chiffree (va dans
  le tableau `particularites`, avec `valuePct` si un calcul de l'app en
  depend - voir particulariteYieldPct()) ou purement qualitative/narrative
  (`valuePct: null`, contexte permanent de lecture, ex: exposition
  geographique atypique d'un titre - voir Moncler). Peut y en avoir
  PLUSIEURS pour un meme titre.
- **EVENEMENT PONCTUEL** (structurel ou conjoncturel, ex: acquisition,
  changement reglementaire, litige, dynamique de business particuliere du
  trimestre) : impacte directement l'annee en cours (ou une annee precise),
  MAIS PAS les annees futures de facon symetrique et automatique - son
  effet se propage aux annees suivantes UNIQUEMENT parce qu'il change la
  BASE dont repartent les taux de croissance/marge projetes (E1/E4), pas
  parce qu'il est reconduit a l'identique chaque annee. Va dans EVENEMENTS
  & INFLEXIONS (E3, classe i/ii/iii), pas dans `particularites`. Peut y en
  avoir PLUSIEURS par refresh/creation.

Reformule TOUJOURS chaque element cite par l'utilisateur dans tes propres
mots pour confirmer le fait ET son mecanisme avant de l'ecrire (jamais un
chiffre ou un mot-cle seul, qu'il s'agisse d'une particularite ou d'un
evenement).

- Si aucun transcript n'est fourni : poursuis en recherche publique seule
  (la detection autonome d'evenements reste obligatoire dans tous les cas,
  voir E3 ci-dessous - ne te repose jamais uniquement sur ce que
  l'utilisateur fournit).
- Si des transcripts sont fournis : ce sont des sources FERMEES et FAISANT
  AUTORITE - enumere TOUS les evenements materiels qu'ils contiennent (voir E3).

## LA BOUCLE D'ANALYSE (E1 -> E8, commune aux deux operations)

Il existe UNE SEULE boucle d'analyse. La CREATION la deroule en entier
depuis une base vierge ; le REFRESH deroule EXACTEMENT la meme boucle, avec
en plus trois entrees fournies par le JSON existant (borne temporelle, base
de reconciliation + verrous a l'interieur de `hypothese.text`, questions
d'agenda a solder) et une etape de reconciliation en sortie. Un refresh
n'est jamais une analyse plus pauvre qu'une creation. Il RECALCULE TOUT A
NEUF (il ne pousse jamais l'ancienne projection d'un cran).

ORDRE : base CAGR (E1) -> guidance (E2) -> evenements & segments (E3) ->
retrofit CA & marge (E4) -> retrofit pont EBIT->Net (E5) -> [refresh
uniquement] reconciliation (E6) -> controle final de vraisemblance (E7) ->
ecriture unique (E8).

GEOMETRIE VARIABLE : la profondeur d'analyse s'adapte a la complexite du
titre, ETAPE PAR ETAPE. Un mono-produit a guidance simple traverse en ligne
droite ; un conglomerat aux divisions divergentes declenche le build-up.
"Sans objet, une ligne" est un resultat valide. But : la justesse au moindre
effort, pas l'exhaustivite systematique. SEULES exceptions jamais "sans
objet" : E4, E5 et E7 s'appliquent toujours (rapides si rien a redresser).

REGLE D'ESCALADE : face a une incoherence MATERIELLE non resolue (segments
incompatibles avec la guidance, sources contradictoires sur un chiffre cle),
ne tranche PAS en silence : pose la question a l'utilisateur en exposant
l'option, avant de figer les adjXXX.

### E1. BASE CAGR (automatique, moteur de l'app)
Le moteur (getProj dans index.html) extrapole deja "data" en double regime :
CAGR court terme (3 derniers exercices) pour les 2 premieres annees, CAGR
long terme (historique complet) au-dela. C'est la base "stupide" de depart ;
les adjXXX l'ecrasent la ou l'analyse le justifie. Recherche l'historique
GAAP/IFRS le plus complet possible (creation) ou, au refresh, les seules
donnees publiees DEPUIS LA DATE DE LA DERNIERE THESE (`hypothese.date` du
JSON fourni = borne temporelle). Si un exercice annuel vient de cloturer,
integre-le des maintenant a "data".

### E2. GUIDANCE & DERNIERS RESULTATS
- Chiffres GAAP/IFRS uniquement, jamais d'estimation non sourcee.
- La guidance du management prime sur toute autre hypothese.
- GUIDANCE QUALITATIVE DIRECTIONNELLE = CONTRAINTE DURE : une guidance non
  chiffree mais directionnelle est TRADUITE en contrainte verifiable. Ex :
  "croissance rentable" -> NI et EPS croissants chaque annee ; "expansion de
  marge" -> marge en hausse ; "desendettement" -> dette nette en baisse. Ces
  contraintes sont VERIFIEES en E7 et PRIMENT sur les prudences : si un
  empilement de prudences viole la direction guidee, on RELACHE la
  prudence, jamais la guidance.
- Coherence interne obligatoire : chaque annee, adjEPS = adjNet/adjShares
  (a ~2% pres). L'app affiche un avertissement sinon.
- Rachats d'actions : tendance historique + programmes annonces. Dividende :
  projete au rythme de la croissance du net.

### E3. EVENEMENTS PARTICULIERS & SEGMENTS
GEOMETRIE VARIABLE : titre simple -> deux mentions "aucun evenement" et
"segments : sans objet", on passe a E4.
a) EXTRACTION EXHAUSTIVE : les transcripts fournis sont une source FERMEE et
   FAISANT AUTORITE. Enumere TOUS les evenements discutes. DETECTION
   AUTONOME OBLIGATOIRE en plus : cherche AUSSI de toi-meme les evenements
   non signales. Trie chacun : (i) deja dans les chiffres - dis ou ; (ii)
   quantifiable - quantifie-le toi-meme si des elements existent, injecte
   dans les adjXXX via E4 ; (iii) optionnalite/risque non quantifiable -
   exclu des adjXXX, affiche comme asymetrie.
b) RECHERCHE EXTERNE bornee au trimestre en cours (0-2 evenements),
   incluant les evenements SUBIS non mis en avant par le management.
c) DECOMPOSITION PAR SEGMENTS - seulement si l'entreprise publie des
   segments aux profils MATERIELLEMENT DIVERGENTS (sinon "sans objet"). Si
   pertinent : build-up bottom-up confronte au total E1-E2.

### E4. RETROFIT n°1 - SCHEMA DE PROJECTION (CA & MARGE), toujours
a) CROISSANCE DU CA annee par annee, rattachee a des moteurs sources.
b) MARGE EN %, confrontee aux trois ancrages : (1) historique (rythme en
   pb/an normalise) ; (2) resultats recents + guidance annee en cours
   (base RECURRENTE, one-offs retraites) ; (3) cibles moyen/long terme
   (expansion au-dela de la cible chiffree = justifiee moteur par moteur,
   sinon plafonnee ; sans cible, expansion graduelle calee sur l'historique).
c) CONTINUITE DE BASE : les adjXXX sont sur la MEME BASE COMPTABLE que
   "data". CONTROLE DE SOUDURE : le sens de variation entre la derniere
   marge PUBLIEE et la 1ere annee projetee ne doit pas contredire la
   guidance de marge.

### E5. RETROFIT n°2 - PONT EBIT -> RESULTAT NET & EXCEPTIONNELS, toujours
a) PONT : Net = (EBIT de E4 + resultat financier + non-operationnel
   normatif) x (1 - IS normatif) - minoritaires.
b) IS NORMATIF : guidance fiscale > taux effectif historique NORMALISE >
   statutaire. Un taux anormal (windfalls, credit) n'est jamais reconduit
   tel quel.
c) RATIO DE CONVERSION Net/EBIT : derive >~2-3pts expliquee par un moteur
   precis, sinon corrigee.
c-bis) SOUDURE ETENDUE au NET et a l'EPS : la 1ere annee projetee ne cree
   pas de fausse marche vs le dernier exercice PUBLIE, IS inclus.
d) INVENTAIRE DES EXCEPTIONNELS (distincts des particularites, qui sont
   structurelles/recurrentes) : one-offs au-dessus comme en-dessous de
   l'EBIT.
e) RETRAITEMENTS "UNDERLYING"/"ADJUSTED" DU MANAGEMENT - regle contre le
   biais de flatterie. NE PAS reprendre l'adjusted du management tel quel.
   VALIDER le lien GAAP/IFRS <-> ajuste : lister chaque poste ajoute, le
   classer VRAI one-off vs. RECURRENT-DEGUISE. Charges systematiquement
   RECURRENTES a REINTEGRER (le management les exclut a tort) :
   - AMORTISSEMENT DES INTANGIBLES D'ACQUISITION chez un acquereur en serie :
     charge permanente, souvent CROISSANTE - la garder, la faire croitre
     avec les deals.
   - STOCK-BASED COMPENSATION : charge reelle et recurrente - la garder.
   - Couts de "transformation"/restructuration RECURRENTS annee apres annee.
   Restent de vrais one-offs a exclure : discrete/deferred tax items lies a
   une reorganisation, plus/moins-values de cession, extinction de dette,
   depreciation isolee. SIGNAL D'ALERTE : si le NI/EPS GAAP publie DEPASSE
   le NI/EPS "ajuste" (inversion anormale), un CREDIT exceptionnel (souvent
   fiscal) gonfle le GAAP - l'exclure. Documente dans `hypothese.text` la
   base retenue et l'ecart chiffre vs. l'adjusted du management. "data"
   reste en GAAP/IFRS PUBLIE ; les adjXXX sont sur cette base normalisee,
   PAS sur l'adjusted flatteur.

### E6. RECONCILIATION (REFRESH UNIQUEMENT ; sans objet en creation)
E4-E5 se font A NEUF (jamais depuis les anciens adjXXX du JSON fourni) ; E6
confronte ENSUITE au passe.
a) TABLEAU D'ECARTS sur les annees communes (l'horizon glisse).
b) MATERIALITE : ~5% sur adjCA/adjEBIT/adjNet, ~1pt de marge, ~2pts de
   ratio de conversion.
c) CLASSEMENT de chaque ecart materiel : (a) information nouvelle sourcee ;
   (b) correction d'erreur de l'ancienne version - dit sans pudeur ; (c)
   changement de jugement - justifie moteur par moteur. SYMETRIE : l'absence
   d'ecart face a un fait nouveau majeur est aussi suspecte qu'un ecart
   inexplique.
d) VERROUS HERITES (dans l'ancien `hypothese.text`, section PARAMETRES &
   POINTS DE SUIVI) : chacun RE-ATTESTE contre les donnees du trimestre -
   reconduit explicitement, ou leve avec justification sourcee. Jamais
   recopie mecaniquement ni ignore.
e) QUESTIONS D'AGENDA HERITEES : chaque question de l'ancienne WATCH-LIST
   DOIT etre soldee ici.
f) GARDE-FOU ANTI-ANCRAGE : l'ancienne projection est une base de
   comparaison, jamais une cible. Un ecart bien classe vaut mieux qu'une
   fausse continuite.

### E7. CONTROLE FINAL DE VRAISEMBLANCE, toujours, juste avant l'ecriture
Relis la serie adjXXX COMPLETE :
a) Contraintes de guidance (E2) respectees ?
b) Pas de fausse marche a la soudure (dernier exercice publie -> 1ere
   annee) sur AUCUNE ligne.
c) Vraisemblance generale : "si je montrais cette trajectoire au CFO, la
   reconnaitrait-il comme une lecture raisonnable ?"
d) Incoherence residuelle -> ESCALADE plutot que figer une trajectoire
   douteuse.

### E8. ECRITURE UNIQUE - STANDARD D'ARCHIVAGE

Ecris `hypothese` (elle REMPLACE entierement l'ancienne). Le champ `text`
est le SEUL document archive du titre : une note compacte, PAS un rapport
narratif. Il ne stocke QUE ce que les champs structures (data, adjXXX,
particularites) ne portent pas et que le modele ne reconstruit pas seul.
Ne jamais re-narrer des chiffres deja presents dans data/adjXXX ni dans le
transcript source. Budget cible ~5000-9000 caracteres. SIX rubriques
majuscules "== RUBRIQUE ==", dans cet ordre :

1. **SYNTHESE DE LA THESE** (~800-1200 car.) : un paragraphe de cadrage qui
   explique le PARI CENTRAL en une lecture continue - pourquoi on detient
   (ou pas) ce titre, sans avoir a deduire l'argument des evenements epars.
   Se concentre sur la THESE elle-meme, jamais sur la description generique
   de l'entreprise (savoir reconstructible).
2. **EVENEMENTS & INFLEXIONS** : issue de E3, hierarchisee par impact,
   chaque evenement avec sa classe (i)/(ii)/(iii). Le risque
   idiosyncratique materiel est loge ICI (pas de rubrique risques a part).
   "Aucun evenement particulier ce trimestre" si c'est le cas.
3. **PARTICULARITES** : binaire. La/les particularite(s) listee(s), ou
   "Aucune".
4. **RESULTATS, SOURCES & GUIDANCE** (fusion) : une ligne de sources
   (primaire = transcript ; secondaires = FY/consensus) + la GUIDANCE
   DIRECTIONNELLE seulement (contraintes dures) - jamais la re-narration
   du detail trimestriel par segment/geographie + la date du prochain
   refresh utile.
5. **PARAMETRES & POINTS DE SUIVI** (fusion pont + agenda) : les seuls
   parametres necessaires pour reconstruire/verifier (base comptable
   ajustee vs publiee, ETR, net financier, ratio de conversion, tendance
   adjShares) en quelques lignes - pas la pedagogie du pont. Puis la
   WATCH-LIST : les questions que le prochain refresh devra solder. C'est
   la matiere la plus utile au refresh suivant.
6. **CATALYSEURS** : une ligne dense (pas une liste longue).

Ce qui est PRESERVE imperativement : toute HYPOTHESE DE MODELISATION non
triviale qui ne vit QUE dans le "text" (ex: "conflit traite comme
circonscrit, recovery Q2 assumee", "CA cale sur le consensus officiel") -
c'est le seul fragment de prose qui porte une decision de modelisation.
Ce standard ne change RIEN a la construction des projections (E1->E8,
adjXXX identiques) : il regit seulement la forme du document archive.

## LIVRABLE FINAL

### Pour une CREATION (Operation A)
1. Confirme explicitement le CODE du nouveau titre tel qu'il doit etre
   ajoute sur GitHub, ex : "Le fichier sera `data/SIEMENS.json`."
2. Fournis le contenu JSON complet du fichier (objet autonome, schema
   ci-dessus).
3. RAPPELLE que deux actions sont necessaires sur GitHub : (a) creer
   `data/SIEMENS.json` avec ce contenu, ET (b) ajouter `"SIEMENS"` dans le
   tableau `tickers` de `data/manifest.json` - sans quoi le titre resterait
   invisible malgre le fichier present.

### Pour un REFRESH (Operation B)
L'utilisateur fournit le JSON existant du titre dans sa requete (source de
la borne temporelle E1 et de la base de reconciliation E6) : pas besoin de
confirmer le nom/code, il est deja connu.
1. Fournis uniquement le contenu JSON MIS A JOUR du fichier (meme schema),
   pret a remplacer le fichier `data/CODE.json` existant sur GitHub tel quel.
