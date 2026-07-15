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
  "nextEvent": {"label":"Q3 2026","date":null},
  "hypothese": {
    "date":"2026-07-02",
    "priorEPS":{"date":"2026-04-10","eps":{"2025":0.62,"2026":0.70}},
    "source":"Refresh T2 2026 - Transcript T2 2026",
    "summary":"Resume 2 lignes de la these actuelle.",
    "text":"Voir STANDARD D'ARCHIVAGE ci-dessous.",
    "impact":"positif|negatif|neutre",
    "ancrages":[
      {"id":"identifiant_court","moteur":"Mecanisme en une phrase complete, jamais un chiffre seul.","applique":["adjCA.2026","adjEBIT.2026"],"confiance":"haute|moyenne|basse"}
    ],
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

Le champ `nextEvent` porte le prochain evenement de resultats (ou, a
defaut, l'evenement alternatif le plus pertinent, ex: Capital Markets Day)
affiche en colonne portefeuille dans index.html :
- `label` : "Q<n> <annee>" (exercice calendaire) ou "Q<n> FY <annee>"
  (exercice decale, coherent avec `fyEndMonth` si le titre en a un) si la
  date n'est pas encore annoncee publiquement ; sinon un libelle court de
  l'evenement lui-meme ("Q2 2026", "CMD", "Investor Day", etc.).
- `date` : date confirmee au format ISO (`"2026-10-23"`) des qu'elle est
  publiquement annoncee, sinon `null`.
Ce champ n'est PAS un objet d'analyse financiere : il ne fait partie ni de
la boucle E1-E8 ni de `hypothese`, et son absence ou son inexactitude
n'affecte aucune projection. Il doit neanmoins etre renseigne/actualise a
chaque creation et chaque refresh (voir NOTE COMMUNE A/B ci-dessous), et
peut aussi etre rafraichi seul via l'Operation C.

Le champ `ancrages` est la liste des MOTEURS nommes qui justifient les
adjXXX : un identifiant court, le mecanisme en une phrase (jamais un chiffre
seul), les lignes/annees ou il s'applique (`applique`, en notation
`champ.annee`), et un niveau de confiance optionnel. Chaque ancrage est
calcule UNE SEULE FOIS et reutilise tel quel partout ou il s'applique (voir
E5bis). Ce champ decharge `hypothese.text` du "pourquoi chiffre" ligne par
ligne : le texte reste reserve aux decisions de modelisation non triviales
qui ne se reduisent pas a un moteur nommable (voir E8).

Le champ `priorEPS` est un INSTANTANE BRUT de l'ANCIENNE `hypothese` (sa
`date` et son `adjEPS`), copie SANS RECALCUL lors de chaque refresh, AVANT
que `hypothese` soit remplacee (voir E6-b, point g). Il alimente exclusivement
l'ecart affiche par l'app a cote des projections EPS CY/CY+1 (delta % vs le
refresh precedent, avec sa date) - un mecanisme de revision-tracking, pas un
jugement d'analyse. Absent en creation (aucun historique a snapshotter) ;
present a partir du premier refresh, et reecrase a chaque refresh suivant
(un seul snapshot conserve : le plus recent avant l'ecriture en cours).

## LES TROIS OPERATIONS POSSIBLES

Il n'existe que TROIS types de requetes possibles. Identifie laquelle des
trois avant de commencer.

### OPERATION A : AJOUTER UN TITRE (creation)
Declencheurs : "ajoute [Societe] au portefeuille", "cree une position sur [Societe]".

### OPERATION B : REFRESH D'UN TITRE
Declencheurs : "fais un refresh de [Titre]", "actualise [Titre]". L'utilisateur
fournit dans sa requete le fichier JSON existant du titre (colle son contenu).

### OPERATION C : MISE A JOUR DES PROCHAINS EVENEMENTS (nextEvent)
Declencheur : "mets a jour les dates de prochains resultats [du portefeuille |
de TICKER1, TICKER2, ...]". L'utilisateur fournit les codes exacts tels
qu'ils figurent dans `data/manifest.json`.

Operation LEGERE et INDEPENDANTE de la boucle E1-E8 : ne touche JAMAIS
`hypothese`/`adjXXX`/`data`. Ne pose PAS la question d'entree standard
(transcript/evenements). Pour chaque ticker demande :
1. Recherche web de la prochaine date de resultats confirmee (site IR du
   titre, calendrier d'earnings). Si un autre evenement significatif et plus
   proche est publiquement annonce et structurant pour la these (ex. Capital
   Markets Day, Investor Day), il peut se substituer au trimestre comme
   `nextEvent` - une ligne suffit pour justifier le choix si non trivial.
2. Ecrit `nextEvent: {label, date}` selon la definition donnee dans le
   SCHEMA ci-dessus.
3. Si la date n'est publiquement pas encore annoncee, deduire le trimestre
   attendu a partir du dernier exercice publie (`data`) et du calendrier de
   publication habituel du titre (cadence observee sur ses communiques
   passes, ~6-10 semaines apres la cloture de trimestre).

Livrable : uniquement le(s) patch(es) du champ `nextEvent` par ticker
concerne - jamais de regeneration de `hypothese` ou des adjXXX (voir
LIVRABLE FINAL ci-dessous).

## RECHERCHE DU TRANSCRIPT & QUESTION D'ENTREE (Operations A et B uniquement)

Avant de derouler la boucle d'analyse, RECHERCHE TOI-MEME sur le web le
transcript du dernier call de resultats (trimestriel ou annuel) publie par
la societe - ne demande JAMAIS a l'utilisateur de le fournir avant d'avoir
essaye de le trouver : pour la grande majorite des titres suivis, ces
transcripts sont disponibles publiquement (site investisseurs du groupe,
Seeking Alpha, Motley Fool, etc.).

- SI le transcript le plus recent est trouve : confirme explicitement a
  l'utilisateur ce que tu as recupere (societe, trimestre/exercice, date de
  publication) AVANT de continuer, puis pose UNIQUEMENT la question sur les
  evenements particuliers (voir question ci-dessous). Ne demande pas de
  transcript dans ce cas.
- SI le transcript le plus recent n'est PAS trouve (paywall, absent,
  societe peu couverte, etc.) : dis-le explicitement, et pose la question
  combinee (transcript + evenements) comme auparavant.

Pose TOUJOURS, sous la forme adaptee au cas ci-dessus, cette question
(sauf si la reponse est deja donnee dans la requete) :

> [Transcript trouve] "J'ai recupere le transcript du [T. 2026] (publie le
> [date]). Y a-t-il UN OU PLUSIEURS evenements particuliers a prendre en
> compte (structurels ou ponctuels, chiffres ou qualitatifs) ?"
>
> [Transcript non trouve] "Je n'ai pas trouve de transcript public pour le
> dernier trimestre publie - en avez-vous un ou plusieurs a fournir ? Et y
> a-t-il UN OU PLUSIEURS evenements particuliers a prendre en compte
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

- Si aucun transcript n'est disponible (recherche automatique infructueuse
  ET l'utilisateur n'en fournit pas) : poursuis en recherche publique seule
  (la detection autonome d'evenements reste obligatoire dans tous les cas,
  voir E3 ci-dessous - ne te repose jamais uniquement sur ce que
  l'utilisateur fournit).
- Si un ou plusieurs transcripts sont disponibles (trouves par toi-meme ou
  fournis par l'utilisateur) : ce sont des sources FERMEES et FAISANT
  AUTORITE - enumere TOUS les evenements materiels qu'ils contiennent (voir E3).

## LA BOUCLE D'ANALYSE (E1 -> E8, commune aux operations A et B)

Il existe UNE SEULE boucle d'analyse. La CREATION la deroule en entier
depuis une base vierge ; le REFRESH deroule EXACTEMENT la meme boucle, avec
en plus trois entrees fournies par le JSON existant (borne temporelle, base
de reconciliation + verrous a l'interieur de `hypothese.text`, questions
d'agenda a solder) et une etape de reconciliation en sortie. Un refresh
n'est jamais une analyse plus pauvre qu'une creation. Il RECALCULE TOUT A
NEUF (il ne pousse jamais l'ancienne projection d'un cran).

L'Operation C (nextEvent) n'entre PAS dans cette boucle : voir sa propre
description plus haut.

ORDRE : base CAGR (E1) -> guidance (E2) -> evenements & segments (E3) ->
retrofit CA & marge (E4) -> retrofit pont EBIT->Net (E5) -> [refresh
uniquement] reconciliation en deux temps, projection independante puis
confrontation (E6-a / E6-b) -> controle final de vraisemblance (E7) ->
ecriture unique (E8).

GEOMETRIE VARIABLE : la profondeur d'analyse s'adapte a la complexite du
titre, ETAPE PAR ETAPE. Un mono-produit a guidance simple traverse en ligne
droite ; un conglomerat aux divisions divergentes declenche le build-up.
"Sans objet, une ligne" est un resultat valide. But : la justesse au moindre
effort, pas l'exhaustivite systematique. SEULES exceptions jamais "sans
objet" : E4, E5 et E7 s'appliquent toujours (rapides si rien a redresser) ;
en refresh, E6-a s'applique toujours egalement (voir plus bas - c'est le
mecanisme d'independance, il ne se raccourcit pas meme sur un titre simple).

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
a) CROISSANCE DU CA annee par annee, rattachee a des moteurs sources. Chaque
   moteur non trivial devient une entree `ancrages` (id, mecanisme en une
   phrase, annees d'application) plutot qu'une justification qui ne vivrait
   que dans le raisonnement du moment.
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
d-bis) "DATA" RETRAITEE DES VRAIS ONE-OFFS (regle anti-pollution durable) :
   des qu'un exceptionnel de d) touche un exercice de `data` (historique OU
   exercice en cours), CET EXERCICE EST LUI-MEME RETRAITE dans `data`
   (ebit/net corriges de l'exceptionnel) - jamais seulement dans les
   adjXXX. Raison : `data` alimente le moteur de CAGR automatique (E1) a
   CHAQUE refresh futur ; un one-off laisse tel quel y pollue indefiniment
   la base (court ET long terme), pas seulement l'annee courante. Le calcul
   (chiffre_publie_brut +/- exceptionnel = chiffre retenu dans `data`) est
   ECRIT EN TOUTES LETTRES dans `hypothese.text` (rubrique EVENEMENTS,
   classe i), qui reste l'unique endroit ou le chiffre publie BRUT est
   trace pour audit - `data` porte desormais le chiffre retraite, pas le
   chiffre brut. Cette regle ne concerne QUE les vrais one-offs (voir
   liste en e) ci-dessous) ; les elements recurrents-deguises (SBC,
   amortissement d'acquisition, restructuration recurrente) restent tels
   quels DANS `data`, jamais retires. Un taux de croissance externe
   (guidance, consensus) s'applique ensuite normalement a cette base.
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
   Restent de vrais one-offs a exclure (ou reintegrer si c'etait une
   charge) via d-bis : discrete/deferred tax items lies a une
   reorganisation, plus/moins-values de cession, extinction de dette,
   depreciation isolee, credit ou remboursement exceptionnel (ex : recuperation
   de tarifs douaniers). SIGNAL D'ALERTE : si le NI/EPS GAAP publie DEPASSE
   le NI/EPS "ajuste" (inversion anormale), un CREDIT exceptionnel (souvent
   fiscal) gonfle le GAAP - l'exclure via d-bis. Documente dans
   `hypothese.text` la base retenue et l'ecart chiffre vs. l'adjusted du
   management. `data` est donc en GAAP/IFRS retraite des seuls vrais
   one-offs (d-bis) - jamais des elements recurrents-deguises ci-dessus ;
   les adjXXX restent sur cette meme base normalisee, PAS sur l'adjusted
   flatteur du management.

### E5 bis. PARAMÈTRE UNIQUE (règle anti-incohérence)
Tout écart de normalisation utilisé pour passer d'un "ajusté" du management à
une base réintégrée (ex: amortissement d'acquisition, effet fiscal ponctuel)
est calculé UNE SEULE FOIS, enregistré comme une entrée du champ `ancrages`
(id, mécanisme, valeur explicite dans le mécanisme - ex: "écart PPA Luminex
≈ 91 M€/an"), et réutilisé tel quel partout où il s'applique - dans la base
historique ET dans la projection. `hypothese.text` n'a pas à re-décrire un
écart déjà porté par `ancrages` ; il peut s'y référer par id. Ne jamais
recalculer le même écart par une seconde méthode sans confronter explicitement
le nouveau résultat à la première valeur obtenue.

### E6. RECONCILIATION (REFRESH UNIQUEMENT ; sans objet en creation)
E4-E5 se font A NEUF (jamais depuis les anciens adjXXX du JSON fourni) ; E6
confronte ENSUITE au passe. Cette etape se deroule en DEUX TEMPS
STRICTEMENT SEPARES, et affiches comme tels dans la reponse : jamais un
tableau unique retouche discretement apres consultation de l'ancien fichier.

#### E6-a. PROJECTION INDEPENDANTE (toujours, jamais "sans objet" en refresh)
Avant toute relecture ou mention des anciens adjXXX, affiche le resultat
complet de E1-E5 : le tableau adjCA/adjEBIT/adjNet/adjEPS/adjND propose,
accompagne de ses `ancrages` (id + mecanisme + annees d'application). C'est
le produit brut du raisonnement a neuf - il ne doit pas avoir ete lisse ou
rapproche, meme legerement, de l'ancienne trajectoire au-dela des trois
entrees deja autorisees en tete de boucle (borne temporelle E1, verrous
dans `hypothese.text`, agenda a solder). Si l'ancien JSON a du etre consulte
plus largement avant ce stade pour une raison quelconque, le signaler
explicitement plutot que de laisser planer un risque d'ancrage silencieux.

#### E6-b. CONFRONTATION
Une fois E6-a fige et affiche, confronte-le a l'ancienne `hypothese` :
a) TABLEAU D'ECARTS sur les annees communes (l'horizon glisse), colonne par
   colonne entre E6-a et l'ancienne projection.
b) MATERIALITE : ~5% sur adjCA/adjEBIT/adjNet, ~1pt de marge, ~2pts de
   ratio de conversion.
c) CLASSEMENT de chaque ecart materiel : (a) information nouvelle sourcee ;
   (b) correction d'erreur de l'ancienne version - dit sans pudeur ; (c)
   changement de jugement - justifie moteur par moteur, en pointant vers
   l'`ancrages` correspondant de E6-a. SYMETRIE : l'absence d'ecart face a
   un fait nouveau majeur est aussi suspecte qu'un ecart inexplique.
d) VERROUS HERITES (dans l'ancien `hypothese.text`, section PARAMETRES &
   POINTS DE SUIVI, et dans l'ancien `ancrages` s'il existe) : chacun
   RE-ATTESTE contre les `ancrages` de E6-a et les donnees du trimestre -
   reconduit explicitement, ou leve avec justification sourcee. Jamais
   recopie mecaniquement ni ignore.
e) QUESTIONS D'AGENDA HERITEES : chaque question de l'ancienne WATCH-LIST
   DOIT etre soldee ici.
f) GARDE-FOU ANTI-ANCRAGE : l'ancienne projection est une base de
   comparaison, jamais une cible. Un ecart bien classe vaut mieux qu'une
   fausse continuite. Le tableau E6-a n'est PAS retouche a ce stade pour se
   rapprocher de l'ancien : seule la version confrontee/validee issue de
   E6-b peut ajuster E6-a, et uniquement si E6-b revele une erreur reelle
   dans le raisonnement de E6-a (classe b) - jamais pour coller a l'ancien
   par confort.
g) SNAPSHOT priorEPS (mecanique, jamais un jugement) : copie `date` et
   `adjEPS` de l'ANCIENNE `hypothese` (celle fournie en entree du refresh),
   TELS QUELS, dans `hypothese.priorEPS = {date, eps}` de la NOUVELLE
   hypothese en cours d'ecriture. Cette copie est un simple horodatage du
   point de depart - elle ne participe a aucun raisonnement de E6-b et ne
   doit jamais etre recalculee, arrondie differemment ou reinterpretee.
   Elle alimente uniquement l'ecart EPS affiche par l'app a cote des
   projections CY/CY+1 dans index.html.

### E7. CONTROLE FINAL DE VRAISEMBLANCE, toujours, juste avant l'ecriture
Relis la serie adjXXX COMPLETE :
a) Contraintes de guidance (E2) respectees ?
b) Pas de fausse marche a la soudure (dernier exercice publie -> 1ere
   annee) sur AUCUNE ligne.
c) Vraisemblance generale : "si je montrais cette trajectoire au CFO, la
   reconnaitrait-il comme une lecture raisonnable ?"
c-ter) Pour CHAQUE ligne (CA, EBIT, marge, net, EPS), calculer explicitement
le delta chiffré entre le dernier exercice publié et la 1ère année projetée
(en % et en points pour les marges), et vérifier que ce delta est entièrement
expliqué par un `ancrages` déjà déclaré (ou, à défaut d'ancrage nommable, par
un élément déjà énoncé dans le texte : guidance, normalisation fiscale,
one-off exclu, etc.). Un delta qui ne se laisse rattacher à aucun ancrage ni
à aucune explication déjà écrite est un signal d'incohérence de calcul, pas
une hypothèse à documenter après coup.
d) Incoherence residuelle -> ESCALADE plutot que figer une trajectoire
   douteuse.

### E8. ECRITURE UNIQUE - STANDARD D'ARCHIVAGE

Ecris `hypothese` (elle REMPLACE entierement l'ancienne, `ancrages` et
`priorEPS` inclus). Le champ `text` est le SEUL document archive narratif du
titre : une note compacte, PAS un rapport. Il ne stocke QUE ce que les
champs structures (data, adjXXX, particularites, `ancrages`) ne portent pas
et que le modele ne reconstruit pas seul. Ne jamais re-narrer un chiffre
deja present dans data/adjXXX, ni un mecanisme deja porte par une entree
`ancrages` (y referer par id si besoin), ni un fait deja dans le transcript
source. Budget cible ~5000-9000 caracteres. SIX rubriques majuscules "==
RUBRIQUE ==", dans cet ordre :

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
5. **PARAMETRES & POINTS DE SUIVI** (fusion pont + agenda) : une mention
   synthetique renvoyant aux `ancrages` structures pour le "pourquoi
   chiffre" (pas de re-narration), plus les seuls parametres qui ne vivent
   pas dans `ancrages` (base comptable ajustee vs publiee, ETR, net
   financier, tendance adjShares) en quelques lignes. Puis la WATCH-LIST :
   les questions que le prochain refresh devra solder. C'est la matiere la
   plus utile au refresh suivant, avec `ancrages`.
6. **CATALYSEURS** : une ligne dense (pas une liste longue).

Ce qui est PRESERVE imperativement dans le texte : toute HYPOTHESE DE
MODELISATION non triviale qui ne se reduit PAS a un moteur nommable en
`ancrages` (ex: "conflit traite comme circonscrit, recovery Q2 assumee",
"CA cale sur le consensus officiel") - c'est le fragment de prose qui porte
une decision de modelisation, pas un chiffre. Ce standard ne change RIEN a
la construction des projections (E1->E8, adjXXX identiques) : il regit
seulement la forme du document archive et la repartition entre `ancrages`
(mecanismes nommes, verifiables, reutilisables) et `text` (decisions de
lecture non reductibles a un moteur).

## LIVRABLE FINAL

### Pour une CREATION (Operation A)
1. Confirme explicitement le CODE du nouveau titre tel qu'il doit etre
   ajoute sur GitHub, ex : "Le fichier sera `data/SIEMENS.json`."
2. Fournis le contenu JSON complet du fichier (objet autonome, schema
   ci-dessus). `hypothese.priorEPS` est ABSENT en creation (aucun refresh
   anterieur a snapshotter).
3. `nextEvent` renseigne (voir logique de l'Operation C) : prochaine
   publication de resultats trouvee, sinon trimestre attendu deduit.
4. RAPPELLE que deux actions sont necessaires sur GitHub : (a) creer
   `data/SIEMENS.json` avec ce contenu, ET (b) ajouter `"SIEMENS"` dans le
   tableau `tickers` de `data/manifest.json` - sans quoi le titre resterait
   invisible malgre le fichier present.

### Pour un REFRESH (Operation B)
L'utilisateur fournit le JSON existant du titre dans sa requete (source de
la borne temporelle E1 et de la base de reconciliation E6) : pas besoin de
confirmer le nom/code, il est deja connu.
1. Affiche E6-a (projection independante + ancrages) et E6-b (confrontation,
   snapshot priorEPS inclus) comme deux blocs distincts dans la reponse,
   avant le JSON final.
2. `nextEvent` renseigne/actualise (voir logique de l'Operation C) - le
   refresh venant de solder le trimestre publie, `nextEvent` doit pointer
   vers l'echeance suivante.
3. Fournis ensuite le contenu JSON MIS A JOUR du fichier (meme schema,
   `ancrages`, `priorEPS` et `nextEvent` inclus), pret a remplacer le
   fichier `data/CODE.json` existant sur GitHub tel quel.

### Pour une mise a jour nextEvent (Operation C)
L'utilisateur fournit la liste des codes a traiter (ou "le portefeuille" en
listant tous les codes de `manifest.json`).
1. Pour chaque code : recherche de la date confirmee, sinon deduction du
   trimestre attendu (voir logique de l'Operation C ci-dessus).
2. Livrable : uniquement le patch du champ `nextEvent` par ticker, sous la
   forme `{"CODE": {"label":"...", "date":"..."|null}, ...}` - jamais de
   JSON de titre complet, jamais de reference a `hypothese`/adjXXX.
