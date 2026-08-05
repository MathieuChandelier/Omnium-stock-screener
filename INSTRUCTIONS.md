# INSTRUCTIONS POUR TOUT ASSISTANT IA (Claude, GPT, Gemini, etc.)
# travaillant sur le portefeuille Omnium Invest

## ARCHITECTURE DU DEPOT

Le portefeuille vit sur GitHub, dans le depot `Omnium-stock-screener`, sous cette forme :

```
index.html              <- le moteur (jamais modifie pour un titre)
Logotype-Omnium.png
data/
  manifest.json          <- la liste des codes de titres a charger
  nextEvents.json         <- OPTIONNEL, prochains evenements (voir plus bas)
  TICKER1.json            <- un fichier par titre, autonome
  TICKER2.json
  ...
```

- `manifest.json` contient UN SEUL champ : `{"tickers": ["CODE1", "CODE2", ...]}`.
- `nextEvents.json` est un fichier PLAT et OPTIONNEL : `{"CODE1":
  {"label":"...","date":"..."|null}, "CODE2": {...}, ...}`. Il n'est
  ALIMENTE QUE par l'Operation C (mise a jour groupee des prochains
  evenements) - jamais par une creation ou un refresh. Son absence ne
  bloque jamais le chargement de l'app (voir DOUBLE STOCKAGE plus bas).
- Chaque `data/CODE.json` est un objet AUTONOME (pas de cle wrapper, pas de
  "tickers": {...} autour) correspondant exactement au schema ci-dessous.
- `index.html` charge `data/manifest.json`, puis chaque `data/CODE.json` en
  parallele, ainsi que `data/nextEvents.json` (silencieusement ignore s'il
  est absent). Un fichier de titre en echec (absent, invalide) est IGNORE
  sans bloquer les autres.
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
  "fyEndMonth": 7,
  "data": [
    {"year":2015,"ca":1080,"ebit":173,"net":145.2,"shares":33,"nd":150,"div":1.16},
    ...
  ],
  "epsConsensus": {"year":2026,"eps":0.88,"epsNY":1.15,"date":"2026-07-01","source":"...","analystsCount":25,"analystsCountNY":null},
  "particularites": [
    {"text":"Explication CONCRETE et complete du fait pris en compte (jamais un chiffre seul).","valuePct":5}
  ],
  "nextEvent": {"label":"Q3 26","date":null},
  "ownership": {
    "asOf":"2026-07-22",
    "insiderPct":4.1,
    "insiderDesc":"Dirigeants et famille fondatrice (ex: Mendelson) - description courte du bloc de controle.",
    "insiderSource":"Proxy statement/DEF 14A (date), ou agregateur si le proxy n'est pas exploitable - source nommee explicitement.",
    "notableHolders":[
      {"investor":"Bill Ackman - Pershing Square Capital Management","pct":0.9,"tier":1,"movement":"position renforcee vs 13F precedent","asOf":"2026-Q1","source":"13F Q1 2026"},
      {"investor":"Terry Smith - Fundsmith","pct":0.4,"tier":1,"movement":null,"asOf":"2026-Q1","source":"13F Q1 2026"}
    ],
    "coverageNote":"Precision sur la couverture 13F pour ce titre (voir OWNERSHIP ci-dessous) - null si sans objet (titre US couvert normalement).",
    "history":[
      {"asOf":"2026-01-15","insiderPct":4.3},
      {"asOf":"2026-04-10","insiderPct":4.1}
    ]
  },
  "compliance": {
    "asOf":"2026-07-22",
    "items":[
      {"year":2026,"title":"Phrase courte et complete du fait ou de l'allegation.","allegedBy":"SEC, cabinet d'avocats plaignants, ou vendeur a decouvert nomme","date":"2026-07-16","status":"sollicitation|enquete_en_cours|plainte_deposee|reglee|classee_sans_suite|condamnation|non_fondee","outcome":null,"source":"Source nommee + date"}
    ],
    "note":"Synthese courte, ou confirmation explicite qu'aucun element n'a ete trouve."
  },
  "hypothese": {
    "date":"2026-07-02",
    "priorEPS":{"date":"2026-04-10","eps":{"2025":0.62,"2026":0.70}},
    "source":"Refresh T2 2026 - Transcript T2 2026",
    "dernierCall":{
      "quarter":"T2 26",
      "communiqueAnalyse":true,
      "transcriptAnalyse":true,
      "resultatsVsConsensus":{"ca":{"actual":3820,"consensus":3790},"epsAdj":{"actual":0.72,"consensus":0.68,"basis":"non-GAAP"}},
      "guidanceProchainTrimestre":"Phrase courte, chiffres inclus, ou 'Pas de guidance trimestrielle chiffree fournie' si la societe ne guide qu'a l'annee.",
      "guidanceAnnuelle":"Phrase courte, chiffres inclus (CA et marge ou EPS).",
      "pointsCles":["Point 1 du call, une phrase complete.","Point 2.","Point 3.","Point 4 (optionnel)."]
    },
    "guidanceHistory":[
      {"quarter":"T1 26","date":"2026-04-10","fyGuided":2026,"guidanceAnnuelle":"CA +6-8%, marge EBIT ~22%."},
      {"quarter":"T2 26","date":"2026-07-02","fyGuided":2026,"guidanceAnnuelle":"CA +7-9%, marge EBIT ~22.5%."}
    ],
    "guidanceLongTerme":"Objectif CMD mars 2025 : marge EBIT >25% et CA CAGR high-single-digit a horizon 2028, ou null si aucune guidance pluriannuelle formulee.",
    "guidanceLongTermeHistory":[
      {"asOf":"2024-11-05","text":"Objectif CMD nov. 2023 : marge EBIT >22% a horizon 2026."}
    ],
    "quarterlyEPS":{
      "cadence":"trimestriel",
      "historique":[
        {"year":2024,"periods":[
          {"label":"T1","eps":0.10},
          {"label":"T2","eps":0.11},
          {"label":"T3","eps":0.13},
          {"label":"T4","eps":0.12}
        ]}
      ],
      "PY":[
        {"label":"T1","eps":0.14,"actual":true},
        {"label":"T2","eps":0.15,"actual":true},
        {"label":"T3","eps":0.17,"actual":true},
        {"label":"T4","eps":0.15,"actual":true}
      ],
      "CY":[
        {"label":"T1","eps":0.16,"actual":true},
        {"label":"T2","eps":0.18,"actual":true},
        {"label":"T3","eps":0.19,"actual":false},
        {"label":"T4","eps":0.17,"actual":false}
      ],
      "NY":[
        {"label":"T1","eps":0.20,"actual":false},
        {"label":"T2","eps":0.23,"actual":false},
        {"label":"T3","eps":0.25,"actual":false},
        {"label":"T4","eps":0.22,"actual":false}
      ],
      "epsForward12m":0.90,
      "forwardPeriodLabel":"T3 26 -> T2 27",
      "coherenceNoteCY":null,
      "coherenceNoteNY":null
    },
    "summary":"Resume 2 lignes de la these actuelle.",
    "cagrBridge":"OPTIONNEL - phrase courte de pont explicitant les composantes du CAGR EPS quand une decomposition explicite aide le lecteur (ex. '+6% volume +3% prix +2pt marge -1pt dilution = +10% CAGR'), null/absent sinon - voir definition complete plus bas.",
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

LANGUE DES CHAMPS TEXTE (regle distincte du CODE ci-dessus, qui lui reste
TOUJOURS sans accent) : tous les champs texte narratifs du JSON -
`hypothese.text`, `hypothese.summary`, `ancrages[].moteur`,
`hypothese.dernierCall.*`, `hypothese.guidanceHistory[].guidanceAnnuelle`,
`hypothese.guidanceLongTerme`, `particularites[].text`,
`ownership.insiderDesc`/`insiderSource`/`coverageNote`,
`compliance.items[].title`/`note`, etc. - sont REDIGES EN FRANCAIS AVEC LES
ACCENTS CORRECTS (é/è/à/ê/ç/ô/î... complets), JAMAIS en ASCII depouille de
ses accents (interdit, ASCII sans accent : "decceleration", "marche" pour
"marché", "these" pour "thèse" ; correct, accentue : "décélération",
"marché", "thèse").
Eviter les traductions maladroites ou lourdes de termes techniques anglais
consacres dans l'analyse financiere (ex : NE PAS traduire "moat" par
"fosse" - le conserver tel quel "moat"). A l'inverse, des termes anglais
d'usage courant du secteur (guidance, transcript, flagship, DTC, moat,
benchmark, one-off, etc.) peuvent rester en anglais sans etre force-traduits,
mais TOUT le reste de la prose environnante reste en francais correctement
accentue - ce n'est donc pas "tout en anglais" ni "tout traduit de force",
mais du francais accentue avec les quelques termes techniques anglais deja
ancres dans l'usage du secteur conserves tels quels.

Le champ `epsConsensus` porte le consensus sell-side de reference pour `CY`
et `CY+1` (`eps`/`epsNY`), affiche cote app EN LIGNE, juste a cote de la
valeur Consensus dans le bloc EPS CY/NY (`index.html`, `.rb-eps-annualval`)
- CHANGEMENT DE DESIGN : le detail complet de la source n'apparait PLUS a
cet endroit (l'ancien bloc `.rb-eps-src`, directement sous le titre EPS,
cassait la symetrie visuelle avec les autres cadres sequentiels du bloc
"These Omnium"). Seul le NOMBRE D'ANALYSTES apparait desormais a cote de
la valeur, entre parentheses (ex. "Consensus 5,98€ (25 analystes)") ; le
detail complet (fournisseur, base comptable, date) est affiche PLUS BAS,
dans la carte "Dernieres hypotheses", juste apres le bandeau `dernierCall`
- au meme niveau que les autres precisions factuelles sur la construction
de l'EPS, plutot que de casser le rythme visuel du haut de page.
- `analystsCount` : ENTIER, le nombre d'analystes composant le consensus
  pour `CY`. Champ STRUCTURE (pas a extraire d'un texte libre) - c'est lui,
  et lui seul, qui pilote l'affichage "(N analystes)" cote app. `null` si
  le nombre exact n'est pas connu (l'app n'affiche alors simplement rien
  entre parentheses, jamais une estimation approximative a ce niveau).
- `analystsCountNY` : OPTIONNEL, meme principe pour `CY+1` UNIQUEMENT si
  le panel d'analystes couvrant l'annee suivante est CONNU pour differer
  de celui de `CY` (rare - la plupart du temps le meme panel de consensus
  couvre les deux annees). Si absent, l'app retombe automatiquement sur
  `analystsCount` (celui de `CY`) pour l'annee suivante egalement - ne PAS
  dupliquer la meme valeur ici par defaut, laisser le champ absent dans ce
  cas courant.
- `source` : UNE SEULE LIGNE D'ATTRIBUTION - la base comptable (GAAP/non-
  GAAP) + le fournisseur nomme. NE PLUS EMBARQUER LE NOMBRE D'ANALYSTES
  DANS CE TEXTE (desormais porte par `analystsCount`/`analystsCountNY` ci-
  dessus, champ structure - eviter la duplication de la meme information
  sous deux formes differentes dans le meme JSON). RIEN D'AUTRE dans ce
  champ. Ce champ repond a une question unique pour le lecteur - "d'ou
  vient ce chiffre de consensus, et sur quelle base ?" - jamais "pourquoi
  Omnium en differe" (c'est le role d'un `ancrages` explicite, jamais
  duplique ici) ni "que va-t-il se passer au prochain refresh" (une
  speculation sur une revision future n'a pas sa place dans un champ de
  citation ; si c'est un point de suivi reel, il vit dans la WATCH-LIST de
  `hypothese.text`). Exemple correct : `"GAAP - S&P Global Market
  Intelligence/TipRanks via Yahoo Finance/Barchart"` (SANS le nombre
  d'analystes, qui vit desormais dans `analystsCount`).
  MAUVAIS EXEMPLE (a ne plus reproduire) : "Consensus sell-side GAAP (Apple
  ne publie pas d'EPS ajuste separe ; S&P Global Market Intelligence/
  TipRanks via Yahoo Finance/Barchart, ~30 analystes). Date-e de juste
  avant la publication du 30/07 - Apple a bat ce trimestre (2,02$ vs 1,89$
  attendu) donc ce consensus sera probablement revise legerement a la
  hausse au prochain refresh, mais l'essentiel de l'ecart avec l'estimation
  Omnium tient au retraitement du remboursement tarifaire (+0,11$ au T3,
  non recurrent) que le consensus GAAP n'exclut pas." - en plus du nombre
  d'analystes qui n'a plus sa place ici (voir `analystsCount`), la
  justification du choix GAAP, le rappel du beat du trimestre (deja dans
  `dernierCall`, visible plus haut dans la meme carte) et l'explication de
  l'ecart avec Omnium (deja dans `ancrages`) y sont tous re-narres en
  double emploi.
  DEUXIEME MAUVAIS EXEMPLE, AUTRE MODE DE DERIVE (a ne plus reproduire) :
  "Consensus dedui du forward P/E ~17,2x (cours 182$, post-split) ; adj
  EPS - guidance management low-to-mid-teens growth. Targets analystes
  ~214-223$ (Strong Buy). Confirme par le T2 26 : croissance H1 reelle
  +14,9%, quasi identique a l'hypothese." - ici ce n'est PAS le nombre
  d'analystes qui pollue le champ, mais QUATRE informations de nature
  differente qui n'ont chacune pas leur place ICI : (1) la METHODOLOGIE de
  construction du consensus (deduction via un forward P/E) - si elle
  merite d'etre tracee, elle vit dans `ancrages` ou `hypothese.text`,
  jamais dans ce champ d'attribution ; (2) un rappel de guidance - deja
  couvert par `dernierCall.guidanceAnnuelle`, double emploi pur ; (3) des
  OBJECTIFS DE COURS de brokers ("targets analystes ~214-223$, Strong
  Buy") - hors perimetre total du champ `epsConsensus`, qui ne porte QUE
  le consensus d'EPS, jamais des price targets ni des recommandations
  d'achat/vente ; (4) une CONFIRMATION post-publication (croissance H1
  reelle) - un fait de refresh qui appartient a `dernierCall.pointsCles`
  ou a la rubrique EVENEMENTS de `hypothese.text`, jamais ici. Aucun
  nombre d'analystes n'etant identifiable dans ce texte, le champ
  `analystsCount` correspondant doit rester `null` plutot que d'inventer
  un chiffre - l'app n'affiche alors simplement pas la parenthese
  "(N analystes)", comportement normal (voir SCHEMA, absence gracieuse).
- `date` : date du consensus (juste avant la derniere publication de
  resultats, generalement), affichee automatiquement a cote de `source`
  cote app (pas besoin de la repeter dans le texte de `source`).

Le champ `fyEndMonth` est OPTIONNEL, entier de 1 a 12, le mois de cloture de
l'exercice fiscal du titre. ABSENT (pas de cle du tout) pour un exercice
calendaire standard (cloture en decembre) - c'est le cas par defaut, ne
JAMAIS ecrire `"fyEndMonth": 12` explicitement. Renseigne UNIQUEMENT pour un
exercice DECALE (ex. Copart, cloture le 31 juillet -> `"fyEndMonth": 7`) :
declenche cote `index.html` le badge "Exercice decale" et les libelles de
mois dans les colonnes de projection. Les annees du tableau `data` et des
`adjXXX` designent alors des EXERCICES FISCAUX (ex. "2025" = exercice clos
au mois `fyEndMonth` de l'annee civile 2025), jamais des annees civiles au
sens strict. Pilote egalement la convention `"Q<n> FY <AA>"` de `nextEvent.
label` (voir plus bas) et le declenchement conditionnel d'E7 bis (voir
boucle d'analyse plus bas) des qu'un ou plusieurs trimestres de l'exercice
en cours sont deja publies au moment de l'analyse.

Le champ `nextEvent` porte le prochain evenement de resultats (ou, a
defaut, l'evenement alternatif le plus pertinent, ex: Capital Markets Day)
affiche en colonne portefeuille dans index.html ("Next event"). Convention
COURTE et anglo-saxonne (annee sur 2 chiffres, mois abrege anglais quand
une date est affichee - la conversion date -> "Jul 22" etc. est geree par
index.html, jamais stockee telle quelle dans le JSON) :
- `label` : "Q<n> <AA>" (exercice calendaire, ex. "Q2 26"), "H<n> <AA>"
  (semestre, ex. "H1 26"), ou "Q<n> FY <AA>" (exercice decale, coherent
  avec `fyEndMonth` si le titre en a un, ex. "Q2 FY 27") si la date n'est
  pas encore annoncee publiquement ; sinon un libelle court de l'evenement
  lui-meme ("Q2 26", "CMD", "Investor Day", etc.). Annee TOUJOURS sur 2
  chiffres, jamais 4 (ex. "26" pas "2026").
- `date` : date confirmee au format ISO (`"2026-10-23"`) des qu'elle est
  publiquement annoncee, sinon `null`.
Ce champ n'est PAS un objet d'analyse financiere : il ne fait partie ni de
la boucle E1-E8 ni de `hypothese`, et son absence ou son inexactitude
n'affecte aucune projection.

DOUBLE STOCKAGE AVEC PRIORITE (choix delibere) : la meme information peut
vivre a DEUX endroits, avec une regle de priorite fixe cote index.html -
1. **Source prioritaire : `data/nextEvents.json`**, le fichier dedie
   (voir ARCHITECTURE DU DEPOT). Alimente UNIQUEMENT par l'Operation C
   (mise a jour groupee), en un seul fichier remplace d'un coup - donc
   facile a relancer regulierement (ex. toutes les deux semaines) pour
   garder l'ensemble du portefeuille a jour sans toucher aux fichiers de
   titre.
2. **Fallback : le champ `nextEvent` du JSON du titre lui-meme** (ce
   schema). Ecrit/actualise a chaque creation et chaque refresh (voir NOTE
   COMMUNE A/B ci-dessous). N'est affiche par index.html QUE si le ticker
   est absent de `data/nextEvents.json` (typiquement : titre tout juste
   cree, pas encore couvert par un passage de l'Operation C).
Consequence acceptee : entre deux passages de l'Operation C, un refresh
recent peut afficher une date desormais perimee si `data/nextEvents.json`
contient deja une entree pour ce ticker (le fichier dedie l'emporte). C'est
un compromis assume au profit de la simplicite de mise a jour groupee -
la fenetre d'incoherence reste faible si l'Operation C est relancee
regulierement.

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

Le champ `dernierCall` porte un BLOC AUTONOME DE LECTURE RAPIDE sur le
dernier trimestre publie, affiche par l'app JUSTE SOUS la ligne date/source
de `hypothese` (premiere ligne visible du bloc these) - avant meme le
`summary`. Recherche et renseigne a CHAQUE creation et CHAQUE refresh
(Operations A et B uniquement - jamais par l'Operation C, au meme titre que
le reste de `hypothese`), en meme temps que le reste de la recherche de
resultats (E2) et l'extraction du communique/transcript (voir RECHERCHE DU
COMMUNIQUE DE RESULTATS & DU TRANSCRIPT plus haut). SOURCING : `resultatsVs
Consensus` et les deux `guidance*` viennent normalement du COMMUNIQUE DE
RESULTATS (chiffres officiels, tableaux) ; `pointsCles` s'appuie normalement
sur le TRANSCRIPT (Q&A, couleur orale) - si seul le communique a ete trouve,
`pointsCles` peut rester plus court (matiere du communique/lettre aux
actionnaires uniquement) plutot que d'inventer un point non source. SEPARATION
STRICTE avec `hypothese.text` : ce contenu ne doit JAMAIS etre re-narre dans
la these - `text` peut s'y referer ou le reutiliser pour EXPLICITER une
decision de modelisation (ex. "voir dernierCall.pointsCles"), mais ne le
duplique pas.
Sous-champs :
- `quarter` : libelle court du trimestre concerne, meme convention que
  `nextEvent.label` (ex. "T2 26", "Q2 26" selon la langue - rester coherent
  avec le reste du fichier).
- `communiqueAnalyse` / `transcriptAnalyse` : booleens FACTUELS - `true` si
  l'assistant a effectivement pu LIRE le document correspondant pour ce
  refresh (voir RECHERCHE DU COMMUNIQUE DE RESULTATS & DU TRANSCRIPT plus
  haut), `false` sinon (introuvable, payant, pas encore publie au moment du
  refresh, etc.). PILOTE L'AFFICHAGE cote app (`index.html`,
  `renderDernierCall`) : coche turquoise si `true`, croix grise si `false`,
  a cote du libelle "Résultats {quarter}" - c'est la SEULE fonction de ces
  deux champs, ne jamais les renseigner sans avoir reellement tente d'ouvrir
  chaque document (un `true` alors que seul le communique a ete lu, par
  exemple, induit le lecteur en erreur sur la profondeur de la recherche).
  Si `dernierCall` est absent (refresh non lie a un resultat trimestriel),
  ces deux champs n'ont pas lieu d'etre - l'app retombe alors sur l'ancien
  affichage `date · source`.
- `resultatsVsConsensus` : le PUBLIE face au CONSENSUS pour le trimestre qui
  vient de sortir.
  - `ca` : `{actual, consensus}` en millions, MEME BASE COMPTABLE que `data`
    (le chiffre publie, pas un chiffre retraite). `null` si aucun consensus
    de CA n'a ete trouve pour ce trimestre (titres peu couverts).
  - `epsAdj` : `{actual, consensus, basis}` ou `basis` vaut `"GAAP"` ou
    `"non-GAAP"` selon la base sur laquelle le consensus de marche est
    effectivement suivi pour ce titre (majoritairement non-GAAP/ajuste pour
    les valeurs US, souvent plus proche du GAAP pour les valeurs
    europeennes) - a documenter explicitement car cette base N'EST PAS
    necessairement celle d'`adjEPS`/`data` (qui restent toujours en GAAP
    retraite des seuls vrais one-offs, voir E5). `null` si aucun consensus
    d'EPS n'a ete trouve.
- `guidanceProchainTrimestre` : PHRASE COURTE (chiffres inclus quand
  disponibles - CA et marge/EPS guides, confrontes au consensus pre-
  publication si trouve) resumant la guidance du trimestre suivant donnee
  par le management sur CE call. Si la societe ne guide qu'a l'annee (cas
  frequent, ex. medtech europeen) : `"Pas de guidance trimestrielle
  chiffree fournie"` plutot que de forcer un chiffre absent.
- `guidanceAnnuelle` : PHRASE COURTE (chiffres inclus) resumant la guidance
  annuelle en cours (CA et marge OU EPS selon ce que la societe communique),
  telle que reaffirmee/mise a jour sur CE call.
- `pointsCles` : 3 A 4 PHRASES COMPLETES (jamais un mot-cle seul) resumant
  les points les plus importants abordes pendant le call - au choix de
  l'assistant selon ce qui structure le mieux la lecture (ex : dynamique
  commerciale marquante, capital allocation, sujet recurrent des questions
  d'analystes, avertissement ou risque mentionne). Ne doublonne PAS les
  EVENEMENTS deja portes par `hypothese.text` (E3/E8) : ce sont ici des
  points de couleur/contexte du call, pas les evenements structurants de la
  these - une meme information peut apparaitre aux deux endroits si elle est
  a la fois un point marquant du call ET un moteur de projection, mais sa
  formulation complete (le "pourquoi") reste dans `text`/`ancrages`, ici
  seule une phrase de synthese suffit.
Champ factuel et de synthese (comme `priorEPS`) : il ne participe a aucun
raisonnement de E1-E8 et n'influence jamais directement les adjXXX (sauf
si un point qu'il mentionne devient par ailleurs un `ancrages` explicite) -
un repere de lecture rapide pour l'utilisateur avant de lire la these
complete.

Le champ `guidanceHistory` est le SUIVI TRIMESTRIEL, au fil d'un meme
exercice fiscal, de la guidance annuelle telle que communiquee call apres
call - un historique cumulatif, a distinguer de `dernierCall.
guidanceAnnuelle` qui n'en porte que le dernier point (voir mecanique
ci-dessous). Renseigne a CHAQUE creation et CHAQUE refresh (Operations A et
B uniquement - jamais par l'Operation C), en meme temps que `dernierCall`
et a partir des memes sources (COMMUNIQUE DE RESULTATS en priorite pour le
chiffre exact de guidance). Structure : tableau d'objets `{quarter, date,
fyGuided, guidanceAnnuelle}`.
- `quarter` : meme convention que `dernierCall.quarter`.
- `date` : date du call/communique correspondant, format ISO.
- `fyGuided` : ANNEE (entier, 4 chiffres) de l'exercice fiscal auquel la
  `guidanceAnnuelle` de cette ligne se rapporte - PAS necessairement
  l'annee du trimestre qui vient de cloturer. Cas frequent : le call de T4/
  exercice cloture guide deja l'exercice SUIVANT (`fyGuided` = annee N+1
  alors que `quarter` reste "T4 <N>" ou l'exercice annuel N) - c'est ce
  champ, jamais `quarter`, qui pilote le mecanisme de reset ci-dessous.
- `guidanceAnnuelle` : MEME PHRASE (chiffres inclus) que celle ecrite dans
  `dernierCall.guidanceAnnuelle` pour ce call - une seule redaction, copiee
  aux deux endroits, jamais reformulee differemment entre les deux.
MECANIQUE D'ACCUMULATION ET DE RESET (a appliquer a l'ecriture, avant E8) :
- CREATION (Operation A) : `guidanceHistory` demarre avec la seule ligne du
  call couvert par la creation (ou tableau vide si aucune guidance
  annuelle chiffree n'a ete trouvee - pas de ligne forcee).
- REFRESH (Operation B) : reprendre `guidanceHistory` TEL QUEL depuis
  l'ancien JSON fourni (lignes anterieures jamais reecrites ni recalculees,
  meme logique de non-alteration retroactive que `priorEPS`), puis :
  - SI le nouveau call a un `fyGuided` IDENTIQUE au `fyGuided` de la
    DERNIERE ligne existante (meme exercice fiscal suivi depuis plusieurs
    trimestres) : AJOUTER la nouvelle ligne a la suite du tableau existant
    - SAUF SI ce call est en realite le MEME que celui deja porte par la
      derniere ligne (`quarter` identique) : dans ce cas NE RIEN AJOUTER,
      le tableau reste tel quel (voir VERIFICATION DE FRAICHEUR en tete de
      la section REFRESH plus bas, qui doit normalement deja avoir arrete
      le refresh avant d'arriver ici - cette regle est une securite
      redondante, pas le mecanisme principal).
  - SI le nouveau call a un `fyGuided` DIFFERENT (premiere guidance d'un
    nouvel exercice - typiquement le call qui suit la cloture de
    l'exercice precedent) : RESET - le tableau ne contient plus QUE la
    nouvelle ligne, les lignes de l'exercice desormais cloture sont
    abandonnees (leur trace narrative eventuelle, si notable - ex. objectif
    tenu/rate sur l'annee ecoulee - releve de `hypothese.text`, pas de ce
    tableau qui ne suit que l'exercice EN COURS).
  - SI `guidanceHistory` est absent de l'ancien JSON (titre cree avant
    l'introduction de ce champ) : traiter comme une creation (ligne unique)
    plutot que bloquer le refresh.
Champ factuel et cumulatif (mecanique de suivi, pas un jugement) : il ne
participe a aucun raisonnement de E1-E8 - ce n'est pas parce qu'une
guidance a ete relevee deux trimestres de suite que la projection doit
suivre automatiquement (E6-b reste seul juge, ancrage par ancrage). Utile
au refresh suivant pour visualiser en un coup d'oeil la trajectoire de
confiance du management sur l'exercice (relevements/abaissements
successifs, stabilite ou volatilite de la guidance).

Le champ `guidanceLongTerme` est une PHRASE COURTE (chiffres inclus)
portant la guidance PLURIANNUELLE la plus recente formulee par le
management (objectifs de Capital Markets Day/Investor Day, cible
structurelle a 3-5 ans), quand elle existe. C'est un INSTANTANE UNIQUE (la
valeur COURANTE), REMPLACE des qu'une communication plus recente la met a
jour (nouveau CMD, revision explicite). Recherche a chaque creation et
chaque refresh ; si aucune guidance pluriannuelle n'a jamais ete
communiquee par la societe, `null`. Meme statut factuel que
`guidanceHistory` : ne participe a aucun raisonnement E1-E8 par lui-meme
(une cible LT peut neanmoins alimenter un `ancrages` explicite en E4 si
elle est mobilisee comme moteur de projection - dans ce cas le lien vers
l'id de l'ancrage peut etre mentionne ici en une incise courte).

Le champ `guidanceLongTermeHistory` porte SON historique (contrairement a
`guidanceHistory`, qui suit `dernierCall`, celui-ci suit `guidanceLongTerme`
- deux mecaniques de snapshot distinctes, ne pas les confondre) :
- MECANIQUE DE SNAPSHOT (Operation B uniquement) : AVANT de remplacer
  `guidanceLongTerme` par la valeur trouvee ce refresh, COMPARE-la a
  l'ancienne valeur du JSON fourni en entree. Si elle a REELLEMENT change
  (nouveau CMD, cible revisee) : pousse l'ANCIENNE valeur dans
  `guidanceLongTermeHistory` sous la forme `{"asOf": <date du refresh ou
  elle etait encore la valeur courante>, "text": <l'ancienne phrase telle
  quelle>}`, tableau CUMULATIF plafonne aux 5 DERNIERS points (le plus
  ancien tombe silencieusement, comme `ownership.history` mais sur 5 points
  plutot que 8 - une guidance LT change trop rarement pour justifier une
  fenetre plus large). Si elle n'a PAS change (cas de tres loin le plus
  frequent, une guidance LT etant reaffirmee identique refresh apres
  refresh) : NE RIEN AJOUTER a l'historique - un ajout a chaque refresh
  meme sans changement ferait gonfler le tableau de doublons sans aucune
  valeur informative.
- SI `guidanceLongTermeHistory` est absent de l'ancien JSON (titre cree
  avant l'introduction de ce champ) : demarre a tableau VIDE `[]` (pas de
  ligne unique forcee, contrairement a `guidanceHistory` - on ne connait
  pas la valeur qui precedait la version actuelle de `guidanceLongTerme`,
  inutile d'inventer un point de depart).
- CREATION (Operation A) : `guidanceLongTermeHistory` demarre a `[]`
  (aucune valeur anterieure connue).
- Champ factuel et cumulatif, meme statut que `guidanceHistory` : ne
  participe a aucun raisonnement E1-E8, utile au refresh suivant/au
  lecteur pour visualiser la trajectoire d'ambition du management sur le
  temps long (cible relevee, maintenue, ou abaissee d'un CMD au suivant).

Le champ `quarterlyEPS` porte le DETAIL TRIMESTRIEL (ou semestriel) de
l'EPS pour l'annee en cours et l'annee suivante, plus le P/E 12 mois
glissants (forward), affiche par l'app juste sous le bloc EPS CY/NY
existant, dans la meme carte "These Omnium". Construit selon E5 ter (voir
BOUCLE D'ANALYSE) a partir des `adjEPS` deja figes en E4-E5 - jamais un
intrant independant, toujours une DECOMPOSITION du chiffre annuel deja
etabli.

Sous-champs :
- `cadence` : `"trimestriel"` ou `"semestriel"` - pilote uniquement le
  libelle affiche cote app, determine par la cadence de publication reelle
  de la societe (voir E5 ter).
- `historique` : tableau CUMULATIF (contrairement a `PY`/`CY`/`NY`,
  entierement reconstruites a chaque refresh) des annees ANTERIEURES a
  `PY` (donc N-2 et au-dela), affiche par l'app derriere un bouton
  depliant SEPARE ("Historique"), au-dessus du bloc `PY` - repli par
  defaut, jamais affiche en ligne. Chaque entree : `{year, periods}` ou
  `periods` suit EXACTEMENT la meme structure que `PY`/`CY`/`NY` (tableau
  de `{label, eps}` - le champ `actual` est omis ici, une annee historique
  etant par nature entierement publiee, comme `PY`).
  MECANIQUE D'ALIMENTATION (a appliquer UNIQUEMENT au moment de la
  BASCULE TEMPORELLE decrite pour `PY` ci-dessous - jamais a un refresh
  ordinaire a l'interieur du meme exercice fiscal) : au refresh qui fait
  avancer `CY` d'un cran (nouvel exercice cloture dans `data`), AVANT
  d'ecraser `PY` par les valeurs de l'ancien `CY`, pousse l'ANCIEN `PY`
  (celui du JSON fourni en entree, sur le point de devenir obsolete) EN
  TETE de `historique` sous la forme `{"year": <annee de cet ancien PY>,
  "periods": <ses periodes telles quelles>}` - jamais recalcule.
  PLAFOND : conserver au maximum les 5 ANNEES LES PLUS RECENTES dans
  `historique` (au-dela, retirer la plus ancienne en premier) - memes
  choix de taille que `guidanceLongTermeHistory`, pour donner une
  profondeur de lecture utile (jusqu'a ~7 ans en tout avec `PY`/`CY`) sans
  faire grossir le fichier indefiniment au fil des annees.
  SI `historique` est absent de l'ancien JSON (titre cree avant
  l'introduction de ce champ, ou refresh a l'interieur du meme exercice
  qui n'a jamais eu a l'alimenter) : reprendre TEL QUEL (tableau vide `[]`
  si jamais renseigne) plutot que de le reconstruire retroactivement -
  aucune tentative de retrouver des annees anterieures non deja captures
  au fil des bascules passees.
  CREATION (Operation A) : `historique` demarre a `[]` (aucune bascule
  anterieure a l'assistant).
  ABSENCE GRACIEUSE : si `historique` est vide ou absent, l'app n'affiche
  simplement pas le bouton "Historique" - comportement normal, pas une
  erreur (cas de tous les titres tant qu'aucune bascule d'exercice n'a
  encore eu lieu depuis l'introduction de ce champ).
  Champ purement factuel et cumulatif (comme `guidanceLongTermeHistory`),
  jamais un intrant de la boucle E1-E8 - une simple archive de lecture,
  affichee AVEC sa somme (Σ) a titre informatif cote app (a la difference
  de `PY`/`CY`/`NY`, voir ci-dessous), puisqu'aucun enjeu de coherence
  n'existe plus a comparer sur une annee aussi ancienne.
- `PY` (Prior Year) : tableau de meme structure que `CY`, pour l'annee
  PRECEDENTE (`CY-1`) - TOUJOURS `actual:true` sur toute la ligne (annee
  entierement close et publiee). Affiche par l'app EN LIGNE, au meme titre
  que `CY`/`NY` (plus de repli/toggle specifique a cette seule annee -
  seules les annees plus anciennes que `PY`, dans `historique` ci-dessus,
  sont repliees derriere un bouton) - PAS confronte a un `adjEPS` (l'annee
  est deja dans `data`, ce n'est plus une projection), donc pas de
  `coherenceNotePY` correspondant, et pas de somme (Σ) affichee non plus,
  par coherence visuelle avec `CY`/`NY` (voir `coherenceNoteCY`/
  `coherenceNoteNY` ci-dessous pour le detail de ce choix). Absence
  gracieuse : si absent, l'app n'affiche simplement pas ce bloc - migration
  progressive au fil des refresh comme pour `CY`/`NY` a l'introduction du
  champ. TOUJOURS TENTE a chaque creation/refresh au meme titre que `CY`/
  `NY` (voir E5 ter) : c'est une donnee deja publiee et connue (aucun
  cout de recherche supplementaire, contrairement a `CY`/`NY` qui melangent
  actual et estime) - l'absence de `PY` doit rester l'exception, jamais le
  defaut par paresse.
  BASCULE TEMPORELLE (mecanisme a appliquer a chaque refresh) : au refresh
  qui suit la cloture d'un exercice fiscal (`data` vient de recevoir une
  nouvelle annee, `yearsFor()` cote app avance donc `CY` d'un cran), DEUX
  choses se produisent dans le MEME mouvement, avant d'ecrire quoi que ce
  soit :
  1. l'ANCIEN `PY` (celui du JSON fourni en entree, sur le point d'etre
     ecrase) est pousse en tete de `historique` (voir mecanique dediee
     ci-dessus) ;
  2. le bloc `CY` du refresh PRECEDENT (dont toutes les periodes sont
     desormais `actual:true` par construction, l'annee etant close)
     devient le nouveau `PY` - reprends ses valeurs telles quelles
     (eventuellement recalees sur le chiffre definitif publie si different
     de la derniere estimation).
  Puis construis un `CY` entierement neuf pour le nouvel exercice en
  cours. Le libelle affiche (`EPS {CY-1}`) est calcule par l'app a partir
  de `CY`, jamais code en dur cote assistant - aucune action requise cote
  app lors de cette bascule, seule la donnee `historique`/`PY`/`CY`/`NY`
  doit etre rafraichie.
- `CY` : tableau de 4 periodes (trimestres) - ou 2 (semestres) - COUVRANT
  L'INTEGRALITE DE L'ANNEE COURANTE (`adjEPS[CY]`), quel que soit le nombre
  deja publie. Chaque entree `{label, eps, actual}` :
  - `label` : `"T1"`/`"T2"`/`"T3"`/`"T4"` (ou `"H1"`/`"H2"`) SANS l'annee.
    Pour un titre a `fyEndMonth` decale, ce sont des trimestres/semestres
    FISCAUX.
  - `eps` : EPS normalise de la periode, MEME base comptable que `adjEPS`
    (GAAP/IFRS retraite des seuls vrais one-offs, amortissement garde).
  - `actual` : `true` si la periode est deja publiee, `false` si estimee -
    pilote le rendu visuel cote app (pastille pleine vs contour pointille).
- `NY` : meme structure que `CY`, pour l'annee suivante (`adjEPS[CY+1]`) -
  quasi toujours `actual:false` sur toute la ligne.
- `epsForward12m` : somme des 4 PROCHAINS trimestres CHRONOLOGIQUES a
  compter d'aujourd'hui (le premier trimestre non encore publie + les 3
  suivants) - INDEPENDANT du decoupage `CY`/`NY` par annee, qui lui
  affiche toujours l'annee complete. Alimente le P/E 12 mois glissants
  affiche par l'app (calcule cote JS comme `cours / epsForward12m`,
  toujours a jour du cours live).
- `forwardPeriodLabel` : phrase courte identifiant la plage couverte par
  `epsForward12m` (ex. `"T3 26 -> T2 27"`).
- `coherenceNoteCY` / `coherenceNoteNY` : DEPRECIES SOUS LE PROTOCOLE
  ACTUEL (voir E5 ter point 4, revise) - toute divergence entre la somme
  des periodes et l'EPS annuel est desormais ARBITREE INTERACTIVEMENT AVEC
  MATHIEU AVANT LA LIVRAISON DU JSON, jamais documentee a posteriori dans
  ce champ. CONSEQUENCE DIRECTE : ces deux champs restent TOUJOURS `null`
  sur toute creation/refresh mene sous ce protocole - ils ne sont conserves
  dans le schema QUE pour la retro-compatibilite de lecture avec d'anciens
  JSON ecrits avant cette revision (jamais reecrits a neuf, jamais
  utilises pour documenter un ecart desormais resolu en amont de
  l'ecriture). Cote app, ces champs ne pilotent plus aucun affichage pour
  `CY`/`NY` (la somme elle-meme n'est plus affichee pour ces deux blocs -
  voir `historique` et `PY` ci-dessus pour le seul endroit ou une somme
  reste visible, a titre informatif).
  ANCIEN COMPORTEMENT (pour memoire, plus en vigueur) : ces champs
  servaient a documenter un ecart materiel non resolu entre la somme
  trimestrielle et `adjEPS`. Ce mecanisme de documentation a posteriori
  est remplace par l'arbitrage interactif d'E5 ter point 4 - voir cette
  section pour le protocole actuel.

MECANIQUE CREATION vs REFRESH : `PY`/`CY`/`NY` sont un champ FACTUEL ET DE
SYNTHESE reconstruit A NEUF a chaque creation/refresh (comme `dernierCall`),
PAS un registre cumulatif (contrairement a `historique` ci-dessus, ou a
`ownership.history`/`compliance.items`) - la fenetre de periodes glisse a
chaque refresh, aucun sens a en preserver une trace historique au-dela de
ce que `historique` capture deja au moment des bascules. `PY`/`CY`/`NY`
sont donc entierement REMPLACES a chaque ecriture, sans lien avec l'ancien
contenu du JSON fourni en entree (SAUF au moment precis d'une bascule
d'exercice, ou l'ancien `CY` devient le nouveau `PY` - voir BASCULE
TEMPORELLE ci-dessus, seul lien delibere entre deux refresh successifs).

ABSENCE GRACIEUSE : si les donnees disponibles ne permettent pas une
decomposition fiable (voir E5 ter point 5), `quarterlyEPS` reste absent -
l'app n'affiche simplement pas la section, comportement normal, jamais une
erreur. Ne JAMAIS forcer une decomposition approximative juste pour remplir
le champ.

Champ purement factuel et de synthese, comme `dernierCall`/`priorEPS` : ne
participe a aucun raisonnement E1-E8 au-dela de son role de decomposition
(le detail trimestriel ne redefinit jamais `adjEPS` sans passer par le
mecanisme d'arbitrage/escalade d'E5 ter point 4).

Le champ `cagrBridge` porte un PONT NARRATIF OPTIONNEL affiche par l'app
juste sous le bloc "Total Return / EPS CAGR / Div. yield", au-dessus de la
ligne EPS CY/NY (`index.html`, `.rb-bridge-wrap`) - une seule phrase courte
decomposant le CAGR EPS affiche en ses composantes economiques quand cette
decomposition aide reellement le lecteur a juger la these d'un coup d'oeil
(ex. `"+6% volume, +3% prix/mix, +2pt de marge, -1pt de dilution = +10%
CAGR EPS"`). ABSENCE GRACIEUSE PAR DEFAUT : ce champ reste `null`/absent la
plupart du temps - un CAGR simple (un seul moteur dominant, deja explicite
dans `hypothese.text`) n'en a pas besoin, la repetition n'ajoutant rien.
Reserve aux cas ou PLUSIEURS moteurs de nature differente (volume, prix,
marge, dilution, effet de change...) se combinent pour produire le CAGR
final et ou cette combinaison merite d'etre visible sans devoir lire tout
`hypothese.text`. Jamais un calcul independant : les composantes citees
doivent sommer (approximativement) au CAGR EPS deja etabli en E4-E5, jamais
une nouvelle hypothese introduite a cet endroit.

Le champ `ownership` porte un ETAT DES LIEUX FACTUEL ET APPROXIMATIF de
l'actionnariat du titre, affiche par l'app dans le bloc "Dernières
hypothèses" en une petite rubrique dediee, juste apres le texte de these
(`hypothese.text`) et avant le bloc `compliance`.
Recherche et renseigne a CHAQUE creation et CHAQUE refresh (Operations A et
B uniquement - jamais par l'Operation C, au meme titre que le reste de
`hypothese`/`nextEvent`). Ce champ ne fait PAS partie de la boucle E1-E8 :
il ne participe a aucun raisonnement de projection et n'influence jamais
directement les adjXXX. Contrairement a `dernierCall`/`guidanceHistory` il
n'est pas imbrique dans `hypothese` (il vit au niveau racine, comme
`nextEvent`), car il ne depend pas d'un trimestre precis. L'etat COURANT
(`asOf`/`insiderPct`/`insiderDesc`/`insiderSource`/`notableHolders`/
`coverageNote`) est remplace integralement a chaque recherche ; SEUL le
sous-champ `history` est cumulatif (voir mecanique dediee plus bas) - a ne
pas confondre avec `guidanceHistory`, qui suit une logique de reset par
exercice fiscal sans equivalent ici.

PERIMETRE 13F - CHOIX ASSUME, PAS UNE LACUNE : `notableHolders` ne couvre
QUE les gerants americains sur des titres cotes aux US (regime de
declaration Form 13F aupres de la SEC). AUCUNE recherche d'equivalent
europeen (franchissements de seuil AMF/BaFin/Consob etc.) n'est tentee -
ce n'est pas un manque a combler au cas par cas mais une limite de
perimetre deliberee du champ, pour eviter une recherche disparate et peu
fiable titre par titre selon la juridiction. Pour un titre non couvert par
le regime 13F (non cote aux US), `notableHolders` reste simplement `[]` et
`coverageNote` le precise en une phrase (ex: "Titre cote sur Euronext
Varsovie, hors perimetre 13F US - notableHolders non recherche pour ce
titre, choix de perimetre assume du modele").

WATCHLIST GERANTS ACTIFS - CRITERE DE SELECTION DE `notableHolders`
(CHOIX ASSUME, REVISION DU CRITERE INITIAL "TOP PAR % DETENU") : lister
les plus gros detenteurs d'un titre au 13F revient structurellement a
lister les meme quelques mega-gerants passifs/indiciels sur QUASIMENT
TOUTES les valeurs US suivies (Vanguard, BlackRock, State Street, Fidelity
[bras indiciel], Geode Capital, Northern Trust, Principal Financial Group,
Charles Schwab, Invesco, Capital Group/American Funds, Norges Bank) - ces
positions repliquent un indice par construction et ne portent AUCUN
signal de conviction ou de discrimination sur le titre. `notableHolders`
ECARTE SYSTEMATIQUEMENT ces gerants passifs/quasi-indiciels de la liste,
MEME s'ils figurent parmi les plus gros detenteurs au 13F - leur presence
n'est jamais recherchee ni affichee dans ce champ.

A la place, `notableHolders` est filtre sur une WATCHLIST FERMEE de
gerants actifs a gestion concentree et discretionnaire (voir ANNEXE -
WATCHLIST GERANTS ACTIFS en fin de document), organisee en deux niveaux :
- TIER 1 : gerants a forte notoriete/conviction reconnue (Buffett, Ackman,
  Klarman, Icahn, Einhorn, Tepper, etc.) - toujours prioritaires dans
  l'affichage si presents au dernier 13F du titre.
- TIER 2 : reste de la watchlist (value/growth/activiste plus large) -
  affiches en complement du Tier 1, ou seuls si aucun Tier 1 n'est present.
Seuls les gerants de cette watchlist sont recherches et retenus dans
`notableHolders` - PAS une recherche libre de "tout detenteur notable" au
13F, qui retomberait sur les passifs par taille. Si aucun gerant de la
watchlist n'apparait au dernier 13F du titre, `notableHolders` reste `[]`
(cas normal et frequent, pas une anomalie a signaler).

PROXY = ANCRAGE DE VERITE POUR `insiderPct` (regle stricte, pas une simple
priorite parmi d'autres) : le dernier proxy statement/DEF 14A (US) ou
document d'assemblee generale/rapport annuel (Europe) - concretement, son
tableau de detention beneficiaire ("beneficial ownership table" ou
equivalent) - EST la source retenue des qu'il est accessible et lisible,
sans exception. Toute AUTRE source (agregateur, presse financiere) n'est
utilisee QUE pour CORROBORER ce chiffre (verifier qu'il n'y a pas d'ecart
massif ou de mouvement recent non reflete par un proxy potentiellement
ancien), JAMAIS pour le remplacer ou le moyenner avec lui :
- Si l'agregateur CONFIRME l'ordre de grandeur du proxy : `insiderSource`
  cite le proxy en source principale, avec une mention courte de
  corroboration (ex: "DEF 14A depose le 2026-03-15 (corrobore par
  WallStreetZen, ecart <0.5pt)").
- Si l'agregateur DIVERGE materiellement (>5pts) : LE PROXY PRIME toujours
  - ne jamais le remplacer par le chiffre de l'agregateur. Documenter
  l'ecart observe dans `insiderDesc` ou `insiderSource` plutot que de le
  passer sous silence (ex: mouvement d'insider recent post-proxy, base de
  calcul differente de l'agregateur).
- Si AUCUN proxy n'est accessible/lisible pour ce titre (cas rare pour une
  valeur suivie) : replier sur un agregateur reputable, nomme
  explicitement, avec la reserve explicite que le chiffre est un ORDRE DE
  GRANDEUR non ancre sur une source primaire cette fois-ci.
NE JAMAIS presenter ces chiffres avec une fausse precision (decimales
multiples, absence de reserve) dans la reponse a l'utilisateur.

Sous-champs :
- `asOf` : date de la recherche (format ISO), pas necessairement la date
  d'arrete du chiffre sous-jacent (qui peut etre plus ancienne - voir
  `insiderSource`/`notableHolders[].asOf`).
- `insiderPct` : pourcentage APPROXIMATIF du capital detenu par les
  dirigeants/fondateurs/administrateurs (insiders), ancre sur le proxy
  (voir regle ci-dessus). `null` si aucune source exploitable trouvee
  (plutot que d'estimer).
- `insiderDesc` : PHRASE COURTE identifiant QUI compose ce bloc (ex:
  "Famille Mendelson, structure a double classe d'actions" ou "Dirigeants
  et administrateurs, sans famille fondatrice identifiee") - jamais un
  chiffre seul sans ce contexte qualitatif.
- `insiderSource` : source nommee + date de l'arrete, PROXY EN PREMIER
  quand disponible (ex: "DEF 14A depose le 2026-03-15 (corrobore par
  WallStreetZen)" ou, a defaut de proxy exploitable, "WallStreetZen,
  agrege 2026-06 - pas de proxy exploitable trouve").
- `notableHolders` : tableau (0 a ~6 entrees) des gerants ACTIFS de la
  WATCHLIST (voir WATCHLIST GERANTS ACTIFS ci-dessus et ANNEXE en fin de
  document) detectes au DERNIER 13F disponible - GERANTS AMERICAINS
  UNIQUEMENT sur titres cotes aux US (voir PERIMETRE 13F ci-dessus, choix
  assume, aucune recherche alternative hors US). Gerants passifs/
  quasi-indiciels (Vanguard, BlackRock, State Street, etc.) TOUJOURS
  ECARTES meme si plus gros detenteurs nominal - voir WATCHLIST. Chaque
  entree : `{investor, pct, tier, movement, asOf, source}` :
  - `investor` : nom au format "Prenom Nom - Nom du fonds" pour un gerant
    identifie individuellement, ou nom du fonds seul si pas de gerant
    unique nomme dans la watchlist (ex: "ValueAct Capital").
  - `pct` : part du capital de la societe detenue par ce gerant (peut
    etre tres faible pour une large cap face a un book concentre - ce
    champ reste informatif, PAS la mesure de la conviction du gerant, qui
    se lit plutot via le poids de la ligne dans SON PROPRE portefeuille si
    la source le precise, a mentionner dans `source` le cas echeant).
  - `tier` : `1` ou `2` selon la watchlist - determine l'ordre d'affichage
    (Tier 1 toujours en premier).
  - `movement` : PHRASE COURTE optionnelle signalant un changement vs le
    13F precedent SI la comparaison est disponible pour ce refresh
    (ex: "position nouvelle", "renforcee vs 13F precedent", "reduite vs
    13F precedent", "sortie de position" si un gerant present au refresh
    precedent a disparu - a mentionner meme si le gerant sort de la
    liste). `null` si non determinable ou lors d'une creation (Operation
    A, pas de 13F precedent a comparer) - recherche a caractere BEST
    EFFORT, ne bloque jamais le refresh si la comparaison n'est pas
    trouvable.
  `asOf` au format trimestre ("2026-Q1") pour un 13F (qui a
  intrinsequement jusqu'a ~45 jours de delai de depot apres la fin du
  trimestre couvert - a garder en tete comme decalage structurel, jamais
  presente comme temps reel). Tableau vide `[]` si aucun gerant de la
  watchlist detecte ou si le titre est hors perimetre 13F (cas normal et
  frequent, pas une anomalie a signaler).
- `coverageNote` : PHRASE COURTE precisant que `notableHolders` est hors
  perimetre pour CE titre quand pertinent (titre non cote aux US - voir
  PERIMETRE 13F). `null` si le titre est normalement couvert (cas general
  des valeurs US ou des ADR US-listees).
- `history` : tableau CUMULATIF (mecanique dediee ci-dessous) des
  instantanes `{asOf, insiderPct}` successifs, permettant a l'app
  d'afficher l'EVOLUTION du niveau de detention des insiders au fil des
  refresh dans l'annee - PAS les `notableHolders` (fonds 13F, pas suivis
  dans le temps ici, uniquement l'etat courant).

MECANIQUE DE `history` (a appliquer a l'ecriture, avant E8, meme logique
de non-alteration retroactive que `priorEPS`) :
- CREATION (Operation A) : `history` demarre a un tableau VIDE `[]` (aucun
  refresh anterieur a snapshotter).
- REFRESH (Operation B) : AVANT de remplacer l'etat courant, prendre
  `{asOf, insiderPct}` de l'ANCIEN `ownership` fourni en entree (s'il
  existe et si `insiderPct` n'y est pas `null`) et l'AJOUTER a la suite de
  l'ancien tableau `history` (repris tel quel, jamais recalcule) - cette
  copie est un simple horodatage, jamais reinterpretee, SAUF si ce point
  est identique (meme `asOf`) au DERNIER point deja present dans `history`
  (signe que ce refresh est redondant avec le precedent, voir VERIFICATION
  DE FRAICHEUR en tete de la section REFRESH) : dans ce cas NE RIEN
  AJOUTER, securite redondante avec ce garde-fou en amont. Si l'ancien
  `ownership` est absent (titre cree avant l'introduction de ce champ),
  `history` demarre a `[]` comme en creation plutot que de bloquer le
  refresh.
- PLAFOND : conserver au maximum les 8 POINTS LES PLUS RECENTS dans
  `history` (au-dela, retirer les plus anciens en premier) - suffisant
  pour visualiser la tendance sur ~2 ans de refresh sans faire grossir le
  fichier indefiniment.
- Champ mecanique et cumulatif (comme `guidanceHistory`), il ne participe
  a aucun raisonnement de E1-E8 - une hausse ou une baisse du pourcentage
  insiders n'est PAS en soi un signal a traduire en ancrage ; c'est un
  repere de gouvernance affiche a l'utilisateur, qui en tire ses propres
  conclusions.

Champ purement factuel et de synthese, au meme titre que `dernierCall`/
`priorEPS` : il ne participe a aucun calcul et ne doit jamais influencer un
`ancrages` ou un adjXXX (l'actionnariat n'est pas un moteur de projection
financiere dans ce modele - c'est un repere de gouvernance/contexte pour
l'utilisateur, en ligne avec son critere de selection de titres "founder
mode").

Le champ `compliance` porte un ETAT DES LIEUX FACTUEL des fraudes averees
ou allegations de fraude (par des regulateurs, cabinets d'avocats
plaignants, ou analystes/vendeurs a decouvert activistes type Muddy
Waters/Hindenburg/Citron) touchant le titre, affiche par l'app dans le
bloc "Dernières hypothèses" en une petite rubrique dediee, juste apres la
rubrique `ownership`. Recherche et renseigne a CHAQUE creation et CHAQUE
refresh (Operations A et B uniquement - jamais par l'Operation C), au meme
titre que le reste de `hypothese`/`nextEvent`/`ownership`. Vit au niveau
racine du JSON (comme `ownership`), hors `hypothese`. Ce champ ne fait PAS
partie de la boucle E1-E8 : il ne participe a aucun raisonnement de
projection et n'influence jamais directement les adjXXX - un repere de
diligence/gouvernance pour l'utilisateur, pas un intrant de modelisation.

PORTEE DE LA RECHERCHE : uniquement des faits ou allegations de FRAUDE (ou
pratique commerciale gravement trompeuse assimilable) - PAS le contentieux
commercial ou social ordinaire (litiges clients, prud'hommes, conflits de
brevets, class actions "consommateur" courantes type frais/pratiques
tarifaires) qui releve de la marche normale des affaires et n'a pas sa
place ici. La distinction : une plainte pour rupture de contrat ou un
desaccord commercial n'est PAS une allegation de fraude ; une accusation
de manipulation comptable, de tromperie des investisseurs, ou une enquete
de la SEC/DOJ pour fraude en valeurs mobilieres, l'EST. En cas de doute sur
la pertinence d'un element trouve, privilegier l'inclusion avec un statut
et une caracterisation prudente plutot que l'omission silencieuse.
CREATION : recherche etendue a TOUT l'historique public raisonnablement
accessible du titre (depuis l'introduction en bourse si pertinent), pas
seulement le dernier trimestre.

MECANIQUE D'ACCUMULATION (a la difference de `ownership` qui remplace son
etat courant, `compliance.items` est un REGISTRE CUMULATIF, jamais purge -
integrite d'un historique de diligence) :
- CREATION (Operation A) : `items` recense tout ce qui est trouve dans
  l'historique public du titre ; tableau vide `[]` (jamais absent) si rien
  trouve, accompagne d'une `note` le confirmant explicitement (voir
  sous-champs).
- REFRESH (Operation B) : reprendre `items` TEL QUEL depuis l'ancien JSON
  fourni (aucune entree existante supprimee ni recalculee - meme logique
  de non-alteration retroactive que `priorEPS`/`guidanceHistory`), puis :
  - AJOUTER toute nouvelle allegation/procedure detectee depuis le dernier
    `asOf` (recherche ciblee sur la periode ecoulee, pas de re-recherche
    exhaustive de tout l'historique a chaque refresh).
  - METTRE A JOUR le `status`/`outcome` d'une entree EXISTANTE si son issue
    a evolue (ex: enquete classee sans suite, plainte deposee, reglement,
    condamnation) - modification EN PLACE de l'entree, jamais duplication.
  - Aucun plafond de taille (contrairement a `ownership.history`) : un
    registre de diligence ne se purge pas pour des raisons de place.
- Si `compliance` est absent de l'ancien JSON fourni (titre cree avant
  l'introduction de ce champ) : traiter comme une creation (recherche
  etendue a tout l'historique) plutot que bloquer le refresh.

Sous-champs :
- `asOf` : date de la recherche (format ISO).
- `items` : tableau (0 a N entrees, PAS de limite haute) :
  - `year` : annee (entier) du fait ou du debut de l'allegation.
  - `title` : PHRASE COURTE ET COMPLETE decrivant le fait (jamais un mot-cle
    seul) - ex: "Enquete de cabinets d'avocats plaignants US sur une
    possible fraude en valeurs mobilieres, ouverte a la suite de la chute
    du titre consecutive a l'annonce du depart du CEO."
  - `allegedBy` : QUI porte l'accusation/l'enquete - nomme explicitement
    (ex: "SEC", "Pomerantz LLP, Bragar Eagel & Squire (cabinets d'avocats
    plaignants)", "Muddy Waters Research"). Distinguer explicitement dans
    `title`/`allegedBy` un rapport de vendeur a decouvert activiste (biais
    connu : profite de la baisse qu'il provoque) d'une enquete d'un
    regulateur (SEC/DOJ) ou d'une action en justice deposee - la nature de
    la source conditionne le niveau de credibilite a accorder.
  - `date` : date du fait/de l'annonce, format ISO.
  - `status` : un parmi `"sollicitation"` (cabinet d'avocats sollicitant
    des plaignants, stade le plus preliminaire - tres frequent apres toute
    baisse de cours materielle, ne prejuge de rien), `"enquete_en_cours"`
    (enquete reglementaire ouverte), `"plainte_deposee"` (class action ou
    poursuite formellement deposee), `"reglee"` (accord transactionnel),
    `"classee_sans_suite"`, `"condamnation"`, `"non_fondee"` (allegation
    infirmee/demontree fausse).
  - `outcome` : PHRASE COURTE sur l'issue si connue (montant d'accord,
    date de classement, etc.), sinon `null` si encore en cours.
  - `source` : source nommee + date.
- `note` : PHRASE COURTE de synthese globale. Si aucun element trouve :
  confirmer explicitement la recherche plutot que laisser un doute (ex:
  "Aucune fraude averee ni allegation par un analyste/vendeur a decouvert
  activiste identifiee dans l'historique du titre a ce jour (recherche du
  2026-07-22)").

Champ purement factuel, au meme titre que `ownership`/`dernierCall` : il
ne participe a aucun calcul et n'influence jamais un `ancrages` ou un
adjXXX. Une allegation en cours n'est PAS a traduire en decote de
valorisation dans les projections - c'est un repere de diligence affiche
tel quel, l'utilisateur en tire ses propres conclusions.

## LES TROIS OPERATIONS POSSIBLES

Il n'existe que TROIS types de requetes possibles. Identifie laquelle des
trois avant de commencer.

### OPERATION A : AJOUTER UN TITRE (creation)
Declencheurs : "ajoute [Societe] au portefeuille", "cree une position sur [Societe]".

### OPERATION B : REFRESH D'UN TITRE
Declencheurs : "fais un refresh de [Titre]", "actualise [Titre]". L'utilisateur
fournit dans sa requete le fichier JSON existant du titre (colle son contenu).

### OPERATION C : MISE A JOUR DES PROCHAINS EVENEMENTS (nextEvents.json)
Declencheur : "mets a jour les dates de prochains resultats [du portefeuille |
de TICKER1, TICKER2, ...]". L'utilisateur fournit les codes exacts tels
qu'ils figurent dans `data/manifest.json` (ou "le portefeuille" pour tous
les traiter), ET colle le contenu actuel de `data/nextEvents.json` (pour
permettre la fusion du point 2 du LIVRABLE FINAL) - a defaut, si l'ancien
contenu n'est pas fourni, le demander avant de continuer plutot que de
livrer un fichier partiel qui ferait disparaitre les entrees non
redemandees.

Operation LEGERE et INDEPENDANTE de la boucle E1-E8 : ne touche JAMAIS
`hypothese`/`adjXXX`/`data`, et ne touche JAMAIS un `data/CODE.json`
individuel. Ne pose PAS la question d'entree standard (transcript/
evenements). Pour chaque ticker demande :
1. Recherche web de la prochaine date de resultats confirmee (site IR du
   titre, calendrier d'earnings). Si un autre evenement significatif et plus
   proche est publiquement annonce et structurant pour la these (ex. Capital
   Markets Day, Investor Day), il peut se substituer au trimestre comme
   evenement retenu - une ligne suffit pour justifier le choix si non
   trivial.
2. Determine `{label, date}` selon la definition donnee dans le SCHEMA
   ci-dessus (section DOUBLE STOCKAGE) - convention courte, annee sur 2
   chiffres.
3. Si la date n'est publiquement pas encore annoncee, deduire le trimestre
   attendu a partir du dernier exercice publie (`data` du titre) et du
   calendrier de publication habituel (cadence observee sur ses communiques
   passes, ~6-10 semaines apres la cloture de trimestre).

Livrable : LE FICHIER `data/nextEvents.json` COMPLET (tous les tickers
demandes, fusionnes avec les entrees deja presentes pour les tickers NON
demandes cette fois-ci - ne jamais faire disparaitre une entree existante
faute d'avoir ete explicitement redemandee), pret a remplacer tel quel le
fichier existant sur GitHub. Une seule action de deploiement, quel que soit
le nombre de tickers traites.

## RECHERCHE DU COMMUNIQUE DE RESULTATS & DU TRANSCRIPT, QUESTION D'ENTREE (Operations A et B uniquement)

Avant de derouler la boucle d'analyse, RECHERCHE TOI-MEME sur le web DEUX
sources pour le dernier trimestre (ou exercice) publie par la societe - ne
demande JAMAIS a l'utilisateur de les fournir avant d'avoir essaye de les
trouver toutes les deux :
1. **Le COMMUNIQUE DE RESULTATS** (press release, formulaire 8-K, ou lettre
   aux actionnaires selon la societe) : source PRIMAIRE pour les chiffres
   officiels (GAAP/IFRS, guidance chiffree, tableaux actual vs annee/
   trimestre precedent). Generalement disponible sur le site investisseurs
   du groupe ou via SEC EDGAR (8-K) MEME quand le transcript est absent ou
   paywall - a rechercher systematiquement, y compris quand le transcript
   est deja trouve.
2. **Le TRANSCRIPT** du call de resultats : source pour la couleur
   qualitative, les echanges Q&A, et les commentaires du management non
   repris dans le communique.
Les deux sont necessaires pour renseigner correctement `hypothese.
dernierCall` (voir SCHEMA) : les chiffres de `resultatsVsConsensus` et de
guidance viennent normalement du COMMUNIQUE (source la plus fiable pour un
chiffre exact) ; `pointsCles` s'appuie normalement sur le TRANSCRIPT (seule
source des echanges Q&A et de la couleur donnee a l'oral). Meme logique pour
la boucle E1-E8 (E2/E3) : le communique prime pour les chiffres, le
transcript pour l'exhaustivite des evenements discutes. C'est CETTE
recherche qui determine directement `dernierCall.communiqueAnalyse`/
`transcriptAnalyse` (voir SCHEMA) : `true` uniquement si le document a
reellement ete trouve et lu ci-dessous, jamais par defaut.

- SI le communique ET le transcript sont trouves : confirme explicitement a
  l'utilisateur ce que tu as recupere (societe, trimestre/exercice, date de
  publication de chacun) AVANT de continuer, puis pose UNIQUEMENT la
  question sur les evenements particuliers (voir question ci-dessous).
- SI seul le communique est trouve (transcript absent, paywall, societe peu
  couverte) : dis-le explicitement. Le communique reste suffisant pour les
  chiffres de `dernierCall` et pour E2, mais `pointsCles` sera
  necessairement plus pauvre (matiere du communique/lettre aux actionnaires
  uniquement, pas de Q&A) - le signaler dans la reponse plutot que
  d'inventer des points de couleur non sources. Pose la question combinee
  (transcript + evenements) comme si le transcript n'etait pas trouve.
- SI NI l'un NI l'autre n'est trouve (titre tres peu couvert) : dis-le
  explicitement, et pose la question combinee (transcript + evenements)
  comme auparavant.

Pose TOUJOURS, sous la forme adaptee au cas ci-dessus, cette question
(sauf si la reponse est deja donnee dans la requete) :

> [Communique et transcript trouves] "J'ai recupere le communique de
> resultats et le transcript du [T. 2026] (publies le [date]). Y a-t-il UN
> OU PLUSIEURS evenements particuliers a prendre en compte (structurels ou
> ponctuels, chiffres ou qualitatifs) ?"
>
> [Communique trouve, transcript absent] "J'ai recupere le communique de
> resultats du [T. 2026] (publie le [date]), mais pas de transcript public
> du call - en avez-vous un a fournir ? Et y a-t-il UN OU PLUSIEURS
> evenements particuliers a prendre en compte (structurels ou ponctuels,
> chiffres ou qualitatifs) ?"
>
> [Rien trouve] "Je n'ai trouve ni communique de resultats ni transcript
> public pour le dernier trimestre publie - en avez-vous a fournir ? Et y
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
description plus haut. Les champs `ownership` et `compliance` n'entrent
pas non plus dans cette boucle (voir leur description dans le SCHEMA) -
ils sont recherches/ecrits en parallele de la boucle, comme `nextEvent`,
mais jamais utilises comme intrant d'un ancrage ou d'un adjXXX.

ORDRE : base CAGR (E1) -> guidance (E2) -> evenements & segments (E3) ->
retrofit CA & marge (E4) -> retrofit pont EBIT->Net (E5) -> decomposition
trimestrielle de l'EPS (E5 ter) -> [refresh
uniquement] reconciliation en deux temps, projection independante puis
confrontation (E6-a / E6-b) -> controle final de vraisemblance (E7) ->
[titres a `fyEndMonth` avec trimestres de l'exercice en cours deja publies
uniquement] coherence intra-exercice (E7 bis) -> ecriture unique (E8).

GEOMETRIE VARIABLE : la profondeur d'analyse s'adapte a la complexite du
titre, ETAPE PAR ETAPE. Un mono-produit a guidance simple traverse en ligne
droite ; un conglomerat aux divisions divergentes declenche le build-up.
"Sans objet, une ligne" est un resultat valide. But : la justesse au moindre
effort, pas l'exhaustivite systematique. SEULES exceptions jamais "sans
objet" : E4, E5, E5 ter ET E7 s'appliquent toujours (rapides si rien a
redresser ; E5 ter peut se conclure sans ecrire `quarterlyEPS` si la
fiabilite n'est pas au rendez-vous - voir E5 ter point 5 - mais la PASSE
elle-meme, c'est-a-dire la tentative de construction, n'est jamais sautee) ;
en refresh, E6-a s'applique toujours egalement (voir plus bas - c'est le
mecanisme d'independance, il ne se raccourcit pas meme sur un titre simple).
Idem pour la recherche du communique/transcript et le renseignement sincere
de `dernierCall.communiqueAnalyse`/`transcriptAnalyse` (voir SCHEMA et
RECHERCHE DU COMMUNIQUE DE RESULTATS & DU TRANSCRIPT plus haut) : ce sont
des DEFAUTS DE L'OPERATION (creation/refresh), pas des options a la carte.

CE QUI NE REDUIT JAMAIS CE PERIMETRE PAR DEFAUT : quand l'utilisateur
formule sa demande de refresh sur un angle precis ("mets a jour post Q2",
"ajoute le decoupage sequentiel", "refresh avec tel focus"), cette formulation
oriente l'ATTENTION et la PROSE de la reponse (E6-a/E6-b, ancrages mis en
avant) - elle ne dispense JAMAIS des defauts ci-dessus. Une demande de
refresh centree sur un aspect precis reste une Operation B a part entiere :
`dernierCall` (ticks inclus) et `quarterlyEPS` (E5 ter) s'appliquent au meme
titre que si la demande avait ete generique, SAUF si l'etape 0 (verification
de fraicheur) a deja identifie un refresh de pure forme sur le meme call
(auquel cas ces champs, deja corrects, sont repris tels quels plutot que
re-recherches inutilement - voir LIVRABLE FINAL, Operation B). Avant de
livrer le JSON final d'un refresh, verifie explicitement (checklist E8-bis) :
`dernierCall.communiqueAnalyse`/`transcriptAnalyse` sont bien presents et
reflaetent sincerement ce qui a ete lu CE tour-ci (jamais un oubli silencieux
d'un booleen alors que les documents ont ete lus), et `quarterlyEPS` a ete
au moins TENTE (present si les donnees le permettaient, absent avec une
ligne de justification en PARAMETRES & POINTS DE SUIVI sinon).

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
- Recherche egalement, pour `dernierCall` (voir SCHEMA), l'ensemble
  suivant sur le dernier trimestre publie : CA et EPS ajuste ACTUAL face au
  CONSENSUS de marche au moment de la publication ; la guidance chiffree du
  prochain trimestre (si la societe en donne une) et son eventuel consensus
  pre-publication ; la guidance annuelle en cours (CA et marge ou EPS) telle
  que reaffirmee/mise a jour sur ce call ; 3 a 4 points cles du call
  (transcript deja consulte pour E3-a, ou couverture presse de resultats).
  Simple collecte factuelle et de synthese, distincte de la boucle de
  projection - ne bloque jamais l'analyse si un element n'est pas trouve
  (renseigner `null` pour les sous-champs numeriques absents, ou la phrase
  "Pas de guidance trimestrielle chiffree fournie" le cas echeant).
- Ecrit dans le meme mouvement `guidanceHistory` (ajout d'une ligne au
  tableau accumule depuis l'ancien JSON, ou reset si nouvel exercice fiscal
  - voir mecanique dans le SCHEMA) et `guidanceLongTerme` (recherche/mise a
  jour de la derniere guidance pluriannuelle communiquee, `null` a defaut).
- Recherche egalement, en parallele et hors boucle de projection, le champ
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
- Recherche egalement, en parallele et hors boucle de projection, le champ
  `compliance` (voir SCHEMA pour la definition complete, la portee limitee
  aux fraudes/allegations de fraude, et la mecanique de registre cumulatif
  jamais purge) : en CREATION, recherche etendue a tout l'historique
  public du titre ; en REFRESH, recherche ciblee sur la periode ecoulee
  depuis le dernier `asOf`, entrees existantes reprises telles quelles
  (statut mis a jour en place si une issue est connue), jamais supprimees.
  Tableau `items` vide mais `note` renseignee explicitement si rien trouve
  - jamais laisser planer un doute entre "rien cherche" et "rien trouve".

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
   que dans le raisonnement du moment. TITRE A `fyEndMonth` AVEC TRIMESTRES
   DE L'EXERCICE EN COURS DEJA PUBLIES : construis directement la 1ere annee
   projetee bottom-up (cumul publie + reste raisonne), jamais par une
   hypothese de croissance annuelle isolee - voir la mecanique complete en
   E7 bis, a appliquer ICI et pas seulement relue en fin de boucle.
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
a-bis) RESULTAT FINANCIER NORMATIF (non applicable aux valeurs financieres -
   banques, assurances, gestion d'actifs, dont le bilan porte la dette/les
   actifs financiers comme coeur de metier et non comme un agregat "dette
   nette" au sens industriel ; pour ces titres, le resultat financier reste
   une ligne modelisee au cas par cas, hors cadre de cette regle). Pour les
   exercices PUBLIES : le resultat financier retenu est le chiffre publie
   tel quel, jamais retraite sauf vrai one-off identifie en E5-e (ex.
   extinction de dette exceptionnelle). Pour les exercices PROJETES,
   PARAMETRE UNIQUE (meme logique qu'E5bis) :
   - Si un cout ou rendement de financement EXPLICITE a ete communique par
     le management pour une operation identifiee (emission obligataire,
     refinancement, facility-relais), CE TAUX COMMUNIQUE PRIME sur toute
     autre regle ci-dessous.
   - A defaut, si `adjND` projete est POSITIF (dette nette) : charge
     financiere = ND moyen projete de l'annee ((ND debut + ND fin)/2) x
     taux a 10 ans souverain de la devise de reporting + 2 points de
     spread normatif (Bund allemand 10 ans + 2pts pour l'EUR, Treasury 10
     ans + 2pts pour l'USD - le seul Bund/Treasury nu est juge trop
     optimiste, ne reflete ni prime de credit ni prime de terme d'une
     entreprise industrielle), taux recalcule a CHAQUE refresh.
   - A defaut, si `adjND` projete est NEGATIF (cash net) ET que la societe
     mene un programme de rachat d'actions ACTIF et REGULIER (autorisation
     en cours ET rythme observe sur au moins les 2-3 derniers exercices,
     deja documente dans l'`ancrages` qui pilote `adjShares`) : rendement
     retenu sur ce cash net = 0% (le cash est considere comme consomme par
     les rachats en cours d'annee, pas comme un stock place sur l'annee).
   - A defaut (cash net SANS programme de rachat regulier) : produit
     financier = cash net moyen projete x meme taux de reference 10 ans +
     2pts que ci-dessus (sans le spread de credit dans ce cas precis
     serait aussi defendable pour un produit de placement, mais on retient
     le meme taux unique pour la simplicite et la coherence du parametre).
   Taux, devise de reference et cas retenu (positif / negatif-buyback /
   negatif-sans-buyback / taux communique) documentes en `ancrages` (id,
   taux retenu, devise, date de fixing) au meme titre que l'IS normatif,
   jamais recalcules une seconde fois sans confrontation a la valeur
   precedente (E5bis).
a-ter) COHERENCE DETTE/CHARGES FINANCIERES LORS D'UNE M&A OU CESSION : toute
   acquisition ou cession modelisee dans les `ancrages` doit ajuster de
   facon coherente et SIMULTANEE (1) `adjND` du montant NET de l'operation
   (prix net encaisse pour une cession, financement net mobilise pour une
   acquisition) a la date de cloture prevue, en precisant dans le mecanisme
   de l'ancrage l'affectation du produit/cout entre desendettement, retour
   aux actionnaires (dividende/buyback) et reinvestissement/CapEx quand ces
   informations sont connues ; ET (2) les charges financieres nettes
   implicites dans le pont EBIT -> adjNet, RECALCULEES selon la regle E5
   a-bis ci-dessus sur la NOUVELLE trajectoire d'`adjND` qui en resulte -
   jamais laissees figees sur le ratio de conversion Net/EBIT anterieur a
   l'operation. Cas particulier explicite : si l'operation fait basculer
   `adjND` en position de cash net (negatif), la charge financiere doit
   etre remplacee par un produit financier net FAIBLE (voire nul si
   programme de rachat actif, cf. E5 a-bis) plutot que par une charge -
   l'erreur a eviter est de continuer a appliquer le cout de la dette
   d'avant-cession a une societe qui n'a temporairement plus de dette
   nette. Symetriquement, une acquisition financee par dette doit alourdir
   `adjND` ET la charge financiere projetee, pas seulement `adjND` seul.
   Le lien (montant de l'operation -> nouvel `adjND` -> nouvelle charge/
   produit financier -> impact sur `adjNet`) est trace dans un seul
   `ancrages` dedie a l'operation plutot que reparti implicitement, pour
   eviter qu'un des deux effets soit ajuste sans l'autre lors d'un refresh
   futur (cf. E5bis, parametre unique).
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
d-ter) Quand le titre retient une base "AJUSTEE" comme methodologie centrale
   (frequent pour les societes avec des elements discrets GAAP recurrents :
   equity securities, litiges, mark-to-market de dette convertible, discrete
   tax items), `data` du DERNIER exercice publie doit elle-meme etre batie
   sur cette base ajustee - pas laissee en GAAP brut avec une simple mention
   en prose. Rechercher le resultat Adjusted/non-GAAP officiellement publie
   (jamais une estimation) et l'utiliser directement dans `data.net` (et
   `data.ebit` si l'ecart y est significatif) - voir test de coherence en
   E7 point b-bis.
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

### E5 ter. DÉCOMPOSITION TRIMESTRIELLE/SEMESTRIELLE DE L'EPS, toujours
(comme E4/E5/E7 - jamais "sans objet", mais peut se conclure sans ecrire
`quarterlyEPS` si la fiabilite n'est pas au rendez-vous, voir point 5)

Construit `quarterlyEPS` (voir SCHEMA) a partir des adjEPS deja figes en
E4-E5, en quatre passes dans cet ordre - PLUS UNE PASSE 0 systematique :

0. **`PY` (annee precedente) et `historique` (N-2 et au-dela).** Avant meme
   `CY`/`NY`, renseigne `PY` avec les periodes de l'annee CY-1,
   integralement `actual:true` - c'est une donnee deja publiee (resultats
   annuels/trimestriels deja sortis), sans cout de recherche
   supplementaire au-dela de ce qui a deja ete rassemble au point 1
   ci-dessous. En REFRESH uniquement, si ce refresh correspond a une
   BASCULE D'EXERCICE (l'ancien `CY` du JSON fourni en entree vient de se
   cloturer, `data` recoit une nouvelle annee) : AVANT de remplacer `PY`,
   pousse l'ANCIEN `PY` (celui du JSON fourni, sur le point de devenir
   obsolete) en tete de `historique` (voir mecanique complete dans le
   SCHEMA, y compris le plafond de 5 annees), PUIS reprends les valeurs de
   l'ancien `CY` comme nouveau `PY`. En dehors d'une bascule d'exercice
   (refresh ordinaire a l'interieur du meme exercice fiscal), `historique`
   n'est PAS touche - reprends-le tel quel depuis l'ancien JSON.
1. **SAISONNALITE + TRIMESTRES/SEMESTRES DEJA PUBLIES.** Rassemble les
   resultats des periodes deja publiees pour l'exercice en cours et le
   precedent (typiquement 4 a 8 trimestres/semestres selon ce qui est
   disponible), et RETRAITE CHACUN selon la meme discipline que E5
   (amortissement garde, vrais one-offs exclus - un seul trimestre pollue
   par un exceptionnel non retraite fausse le P/E glissant pendant les 4
   trimestres qui suivent). Identifie le patron de saisonnalite propre a ce
   titre (ex. Q4 structurellement plus lourd, S1 traditionnellement plus
   faible). Pour un titre a publication SEMESTRIELLE (pas de trimestres
   publies) : reconstitue une estimation trimestrielle indicative a partir
   du chiffre d'affaires trimestriel (souvent publie meme par un
   semestriel, via un point d'activite) et d'un ratio de marge interpole
   entre la marge du dernier semestre publie et la guidance de marge
   annuelle - marquer ces points `"actual": false` malgre tout (ce sont des
   estimations, pas des publications), et documenter la methode dans le
   texte si le titre bascule ainsi en affichage semestriel plutot que
   trimestriel (voir point 5).
2. **DECOUPAGE VIA LA GUIDANCE.** Applique le patron de saisonnalite
   identifie a la guidance du trimestre suivant (souvent chiffree
   precisement par le management) et a la guidance annuelle en cours, pour
   estimer les trimestres restants de l'exercice en cours et le debut de
   l'exercice suivant.
3. **RECOUPEMENT AVEC LES PROJECTIONS ANNUELLES.** La somme des periodes de
   `CY` doit converger vers `adjEPS[CY]` deja construit en E4-E5 (idem pour
   `NY` vs `adjEPS[CY+1]`) - c'est un VRAI test de coherence interne, pas
   une formalite : calcule explicitement l'ecart en %, POUR CHAQUE ANNEE
   INDEPENDAMMENT (rien n'oblige CY et NY a suivre la meme branche a
   l'etape 4).
4. **ARBITRAGE INTERACTIF (remplace l'ancien mecanisme d'absorption
   silencieuse).** `adjEPS` (issu du protocole complet E1-E8, sources
   multiples, ancrages documentes) reste l'ANCRE DE DEPART, mais DES QU'UN
   ECART EXISTE entre la somme des periodes de `CY` (resp. `NY`) et
   `adjEPS[CY]` (resp. `adjEPS[CY+1]`) - QUELLE QUE SOIT SON AMPLEUR, plus
   de seuil de materialite qui dispenserait d'en parler - PRESENTE L'ECART
   CHIFFRE A MATHIEU AVANT DE FINALISER LE JSON, et demande explicitement
   lequel des deux doit l'emporter :
   - (a) le CUMUL TRIMESTRIEL (`adjEPS[CY]`/`adjEPS[CY+1]` est alors
     ajuste pour coller exactement a la somme des periodes construites en
     etapes 1-2) ; ou
   - (b) l'EPS ANNUEL deja etabli en E1-E5 (les periodes trimestrielles
     sont alors recalees proportionnellement pour boucler exactement sur
     `adjEPS`, EN PRESERVANT LA FORME saisonniere identifiee en etape 1 -
     jamais un recalage uniforme qui aplatirait la saisonnalite).
   Ne JAMAIS trancher seul, ne JAMAIS absorber silencieusement meme un
   ecart minime - CHANGEMENT DE PROTOCOLE : l'ancienne regle qui tolerait
   une absorption automatique sous ~3-4% n'est PLUS EN VIGUEUR. CONSEQUENCE
   DIRECTE : une fois la decision de Mathieu actee, le JSON livre ne
   presente PLUS JAMAIS d'ecart residuel entre la somme trimestrielle et
   `adjEPS` - `coherenceNoteCY`/`coherenceNoteNY` (voir SCHEMA, desormais
   depreciees) restent donc TOUJOURS `null` sur tout JSON ecrit sous ce
   protocole, l'arbitrage ayant deja eu lieu EN AMONT de l'ecriture plutot
   que d'etre documente a posteriori dans le JSON.
5. **GEOMETRIE VARIABLE.** Si les donnees disponibles (trimestres publies,
   guidance) sont trop pauvres pour construire une decomposition
   raisonnablement fiable (titre tres peu couvert, guidance totalement
   absente, societe qui vient d'entrer en bourse sans historique
   trimestriel) : NE PAS ecrire `quarterlyEPS` plutot que de publier une
   decomposition non fiable - une ligne dans `hypothese.text` (rubrique
   PARAMETRES & POINTS DE SUIVI) suffit pour le signaler comme point a
   reprendre au refresh suivant.

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
b-bis) TEST DE BASE COMPTABLE (avant meme de juger le delta plausible) : si
   le titre declare une base ajustee pour ses adjXXX (ex. "BASE = AJUSTEE",
   frequent pour les titres avec des elements discrets GAAP recurrents -
   equity securities, litiges, one-offs fiscaux), verifie que `data` du
   DERNIER exercice publie est construite sur CETTE MEME base, pas en GAAP
   brut. Symptome typique d'un manquement : l'EBIT progresse et le nombre
   d'actions baisse (rachats) d'une annee sur l'autre, mais l'EPS historique
   stagne ou recule - c'est le signe qu'un element discret GAAP (non lie a
   l'exploitation) a pollue `data.net` sans avoir ete retraite, meme si le
   texte le MENTIONNE en commentaire (mentionner en prose ne suffit pas,
   voir E1 point d-bis - `data` doit etre corrigee, pas seulement annotee).
   Dans ce cas, retraite `data` du/des exercice(s) concernes (recherche des
   resultats Adjusted/non-GAAP officiellement publies par la societe,
   jamais une estimation) AVANT de juger la soudure vers la 1ere annee
   projetee - un delta qui parait aberrant (ex. +50-60% sur l'EPS d'une
   annee a l'autre) est souvent le symptome de ce manquement plutot qu'une
   vraie inflexion a expliquer par un ancrage.
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

### E7 bis. COHERENCE INTRA-EXERCICE (titres a `fyEndMonth`, CONDITIONNEL)
S'applique UNIQUEMENT si le titre a un `fyEndMonth` ET qu'au moins un
trimestre de l'exercice fiscal en cours est deja publie au moment de
l'analyse (sinon : sans objet, une ligne, comme les etapes non-obligatoires
de la boucle). Cas vise : l'exercice fiscal en cours n'est PAS encore
cloture, mais un ou plusieurs de ses trimestres sont DEJA publies
(creation ou refresh) - situation frequente pour un titre a `fyEndMonth`
puisque son exercice ne s'aligne pas sur l'annee civile de l'analyse. E7
verifie la soudure entre le dernier exercice CLOS (`data`) et la 1ere annee
PROJETEE (adjXXX) ; il ne verifie PAS que cette 1ere annee projetee est
elle-meme coherente avec les trimestres de CET exercice deja publies. C'est
un angle mort distinct, a couvrir explicitement :
a) Avant d'ecrire le premier adjXXX de l'exercice fiscal en cours,
   additionne les trimestres DEJA PUBLIES de cet exercice (CA, EBIT/resultat
   operationnel, resultat net, actions diluees).
b) Raisonne le ou les trimestres RESTANTS (pas de guidance chiffree chez la
   plupart de ces societes -> extrapolation motivee : rythme des derniers
   trimestres publies, comparable a N-1, elements ponctuels deja identifies
   en E3) plutot que de les ignorer.
c) Le premier adjXXX = somme(trimestres publies) + estimation(trimestres
   restants). JAMAIS une hypothese de croissance annuelle isolee (ex.
   "CA +X% cette annee") deconnectee de ce cumul deja connu.
d) Calcule explicitement l'ecart entre le cumul deja publie (annualise au
   prorata) et l'adjXXX retenu ; si cet ecart implique un dernier trimestre
   dont la croissance s'ecarte fortement (>10 points) du rythme des
   trimestres deja publies sans catalyseur nomme en E3, c'est un signal
   d'incoherence (meme traitement qu'E7-d : documenter le catalyseur ou
   revoir a la baisse, jamais figer tel quel).
e) Consequence mecanique attendue : dans un exercice en cours ou les
   trimestres deja publies sont mitigés/plats, le premier adjXXX doit
   generalement l'etre aussi - un rebond n'est justifie que par un
   catalyseur explicite (E3), jamais par la seule proximite de la fin
   d'exercice.

### E8. ECRITURE UNIQUE - STANDARD D'ARCHIVAGE

Ecris `hypothese` (elle REMPLACE entierement l'ancienne, `ancrages` et
`priorEPS` inclus). Le champ `text` est le SEUL document archive narratif du
titre : une note compacte, PAS un rapport. Il ne stocke QUE ce que les
champs structures (data, adjXXX, particularites, `ancrages`) ne portent pas
et que le modele ne reconstruit pas seul. Ne jamais re-narrer un chiffre
deja present dans data/adjXXX, ni un mecanisme deja porte par une entree
`ancrages` (y referer par id si besoin), ni un fait deja dans le transcript
source. Budget cible ~4500-8500 caracteres. CINQ rubriques majuscules "==
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
4. **PARAMETRES & POINTS DE SUIVI** (fusion pont + agenda) : une mention
   synthetique renvoyant aux `ancrages` structures pour le "pourquoi
   chiffre" (pas de re-narration), plus les seuls parametres qui ne vivent
   pas dans `ancrages` (base comptable ajustee vs publiee, ETR, net
   financier, tendance adjShares) en quelques lignes. Puis la WATCH-LIST :
   les questions que le prochain refresh devra solder, ET la date/l'echeance
   de ce prochain refresh utile (ex. "resultats T4 FY2026, publication
   attendue fin octobre 2026"). C'est la matiere la plus utile au refresh
   suivant, avec `ancrages`.
5. **CATALYSEURS** : une ligne dense (pas une liste longue).

RUBRIQUE SUPPRIMEE - NE PAS REINTRODUIRE : une ancienne rubrique 4
"RESULTATS, SOURCES & GUIDANCE" existait ici (sources lues + guidance
directionnelle re-narrees en prose). Elle est devenue integralement
redondante avec des champs structures qui n'existaient pas au moment de sa
creation : `dernierCall.communiqueAnalyse`/`transcriptAnalyse` (badges
Communique/Transcript coches ou non, cote app) couvrent desormais les
sources lues, et `dernierCall.guidanceProchainTrimestre`/`guidanceAnnuelle`
couvrent la guidance chiffree - re-narrer l'un ou l'autre dans `text` viole
la regle de separation stricte avec `dernierCall` (voir sa definition dans
SCHEMA) exactement comme un chiffre deja present dans `data`/`adjXXX`. Seule
la date du prochain refresh utile n'avait pas d'autre foyer : elle est
desormais dans la WATCH-LIST de la rubrique PARAMETRES & POINTS DE SUIVI
ci-dessus.

Ce qui est PRESERVE imperativement dans le texte : toute HYPOTHESE DE
MODELISATION non triviale qui ne se reduit PAS a un moteur nommable en
`ancrages` (ex: "conflit traite comme circonscrit, recovery Q2 assumee",
"CA cale sur le consensus officiel") - c'est le fragment de prose qui porte
une decision de modelisation, pas un chiffre. Ce standard ne change RIEN a
la construction des projections (E1->E8, adjXXX identiques) : il regit
seulement la forme du document archive et la repartition entre `ancrages`
(mecanismes nommes, verifiables, reutilisables) et `text` (decisions de
lecture non reductibles a un moteur).

E8-bis. VALIDATION STRUCTURELLE AVANT LIVRAISON (obligatoire, Operations A et B)

Avant de livrer le JSON final, EXECUTE ce contrôle sur le fichier ecrit (pas seulement une relecture visuelle - le but est de detecter un defaut de SCHEMA qui peut etre invisible a l'oeil sur un JSON par ailleurs valide et bien redige). Ce controle est distinct d'E7 (qui porte sur la VRAISEMBLANCE des chiffres) : E8-bis porte sur la CONFORMITE STRUCTURELLE au schema attendu par index.html.

Parse JSON strict : le fichier doit etre du JSON valide (accolades/ virgules/guillemets corrects). Une erreur de syntaxe fait echouer le chargement silencieusement cote app (le titre est ignore, voir ARCHITECTURE DU DEPOT).
hypothese.adjXXX = objets plats indexes par annee, jamais un tableau. Verifie explicitement que hypothese.adjCA, adjEBIT, adjNet, adjND, adjShares, adjEPS sont chacun un OBJET de la forme {"2026":valeur,"2027":valeur,...}, directement au niveau racine de hypothese - PAS un tableau [{year:2026,...},...], PAS un champ nomme differemment (ex. projection, forecast). C'est la cause de bug la plus sournoise possible : un JSON parfaitement valide et une these bien redigee, mais l'app retombe silencieusement sur la projection CAGR automatique (E1) sans aucun message d'erreur, produisant un tableau completement different de l'analyse effectuee - ecart qui ne se detecte qu'en comparant visuellement l'app aux chiffres ecrits dans ancrages/text.
Concretement, avant de livrer : pour CHAQUE annee de projection (les 5 annees suivant la derniere annee de data), verifie que hypothese.adjCA[annee] (et les 5 autres champs) existe et est un nombre - pas hypothese.adjCA[0].adjCA ni toute autre imbrication.
Coherence adjEPS = adjNet/adjShares (deja prescrite en E2/E7, re-verifiee ici comme filet de securite final) : recalcule explicitement le ratio pour chaque annee et confirme un ecart <2% vs adjEPS fourni.
Structure de `ancrages` : verifie que CHAQUE entree porte exactement les cles `id`/`moteur`/`applique`/`confiance` (jamais `mechanism`/`scope`/`confidence` ni toute autre variante anglicisee ou renommee), que `applique` est une LISTE de chaines en notation `champ.annee` (ex. `"adjCA.2026"`, jamais `"adjCA 2026"` en texte libre ni une chaine unique), et que `confiance` vaut `haute`, `moyenne` ou `basse`. Une entree qui ne pilote effectivement AUCUN adjXXX (ex. un simple rappel de watch-list) n'a pas sa place dans `ancrages` - voir sa definition en tete de SCHEMA ("moteurs qui justifient les adjXXX") - elle appartient a `hypothese.text` (rubrique PARAMETRES & POINTS DE SUIVI) a la place. Meme risque que pour les adjXXX mal formes : un `ancrages` dont les cles ne correspondent pas exactement au schema peut ne pas s'afficher correctement cote app sans qu'aucune erreur ne soit visible sur le JSON lui-meme.
Aucun champ retire par erreur : confirme que tous les champs du SCHEMA presents dans le JSON fourni en entree (refresh) ou requis en creation sont bien presents en sortie - notamment ownership, compliance, nextEvent, dernierCall, guidanceHistory - un champ silencieusement disparu lors d'une reecriture complete du fichier est aussi difficile a detecter a l'oeil qu'un adjXXX mal forme.
AVANT de verifier la forme, verifie l'OBLIGATION elle-meme (piege identifie en pratique : un refresh signale comme "provisoire" ou "source incomplete" - ex. transcript manquant - n'exempte JAMAIS de tenter E5 ter, ces deux dimensions sont independantes) : si `hypothese.quarterlyEPS` est ABSENT, la reponse doit contenir soit le champ, soit une justification explicite (E5 ter point 5 - donnees insuffisantes/non fiables) dans le texte ou la reponse - jamais une absence silencieuse. Un refresh qui construit un pont H1-actual + H2-estime pour adjEPS (E4-a) mais n'utilise PAS ces memes trimestres actual pour `quarterlyEPS.CY` est incoherent avec lui-meme : les donnees etaient deja rassemblees, ne pas les reutiliser est un oubli, pas un choix.
Si `hypothese.quarterlyEPS` est present, verifie que `PY` (si present), `CY` et `NY` sont chacun un TABLEAU (pas un objet), que chaque entree porte exactement `label`/`eps`/`actual` (`PY` : `actual` toujours `true`), et que la somme des `eps` de `CY` (et de `NY`) COINCIDE EXACTEMENT avec `adjEPS[CY]`/`adjEPS[CY+1]` (a un arrondi d'affichage pres, <0,05 pt) - CE N'EST PLUS UNE TOLERANCE A ~3-4% : sous le protocole actuel (E5 ter point 4), tout ecart devait deja avoir ete arbitre AVEC MATHIEU avant l'ecriture, donc un ecart residuel a ce stade est une INCOHERENCE A CORRIGER avant livraison, pas un cas normal a documenter. `coherenceNoteCY`/`coherenceNoteNY` doivent TOUJOURS rester `null` (voir SCHEMA, champs desormais deprecies) - la presence d'un texte dans l'un ou l'autre de ces deux champs sur un JSON ecrit sous ce protocole est elle-meme une incoherence a corriger. Si `historique` est present, verifie qu'il s'agit d'un TABLEAU (jamais un objet), que chaque entree porte exactement `year`/`periods`, que `periods` suit la structure `{label, eps}` (sans `actual`, toujours implicitement publiee), qu'aucune annee n'y apparait EN DOUBLE, et que le tableau ne depasse pas 5 entrees (plafond - voir SCHEMA).

Si `hypothese.dernierCall` est present (refresh ou creation lie a un resultat), verifie que `communiqueAnalyse` et `transcriptAnalyse` sont BIEN PRESENTS (jamais un champ omis par oubli alors que `dernierCall` lui-meme a ete rempli) et qu'ils reflaetent sincerement la recherche menee CE tour-ci (voir RECHERCHE DU COMMUNIQUE DE RESULTATS & DU TRANSCRIPT) - un `dernierCall` chiffre et detaille alors que ces deux booleens sont absents ou a `false` alors que les documents ont ete lus est une incoherence a corriger avant livraison, au meme titre qu'un adjXXX mal forme (elle affiche une croix grise trompeuse cote app malgre une recherche reellement effectuee).
Verifie `hypothese.guidanceHistory` : TABLEAU (jamais un objet), chaque entree avec exactement `quarter`/`date`/`fyGuided`/`guidanceAnnuelle`, et TOUTES les entrees partagent le MEME `fyGuided` (c'est ce qui borne le tableau a l'exercice fiscal en cours - un `fyGuided` heterogene dans le tableau casse a la fois la mecanique de reset et le badge "Nᵉ point de l'exercice" affiche cote app). Verifie `hypothese.guidanceLongTermeHistory` : TABLEAU (jamais absent si `guidanceLongTerme` a deja change au moins une fois), chaque entree avec exactement `asOf`/`text` - jamais une entree ajoutee pour un refresh ou `guidanceLongTerme` est reste identique (verifie qu'aucune entree consecutive n'a le meme `text`, signe d'un ajout fait a tort).
Si `epsConsensus` est present, verifie que `analystsCount` (si renseigne) est un ENTIER (pas une chaine "~25" ni un texte), et que `source` ne contient PLUS de mention du nombre d'analystes en texte libre (desormais porte exclusivement par `analystsCount`/`analystsCountNY` - voir SCHEMA) - une mention residuelle du type "(~25 analystes)" encore presente dans `source` est une duplication a corriger avant livraison.
Si un ecart est detecte a l'une de ces etapes : CORRIGE avant de livrer, ne livre jamais un fichier dont tu sais qu'il echouera silencieusement au chargement ou a l'affichage des projections. Mentionne explicitement dans la reponse que ce controle a ete effectue et son resultat (ex. "Validation E8-bis : JSON valide, 6/6 champs adjXXX conformes en objets indexes, coherence EPS verifiee a <0,1% pres, N/N ancrages conformes en cles/format, aucun champ manquant.").

## LIVRABLE FINAL

### Pour une CREATION (Operation A)
1. Confirme explicitement le CODE du nouveau titre tel qu'il doit etre
   ajoute sur GitHub, ex : "Le fichier sera `data/SIEMENS.json`."
2. Fournis le contenu JSON complet du fichier (objet autonome, schema
   ci-dessus). `hypothese.priorEPS` est ABSENT en creation (aucun refresh
   anterieur a snapshotter). `nextEvent` renseigne (prochaine publication
   de resultats trouvee, sinon trimestre attendu deduit - voir DOUBLE
   STOCKAGE dans le SCHEMA ci-dessus) : ce nouveau titre n'etant couvert par
   aucun passage anterieur de l'Operation C, ce champ sert de valeur
   affichee jusqu'au prochain passage de C. `hypothese.dernierCall` renseigne
   (resultats vs consensus, guidance prochain trimestre et annuelle, points
   cles du call - voir SCHEMA et E2) - `null`/phrase de repli sur les
   sous-champs sans donnee trouvee, jamais bloquant. `hypothese.
   guidanceHistory` demarre a une ligne unique (ce call) et `hypothese.
   guidanceLongTerme` renseigne si une guidance pluriannuelle existe, sinon
   `null` (voir SCHEMA), `hypothese.guidanceLongTermeHistory` demarre a `[]`.
   `hypothese.quarterlyEPS` renseigne selon E5 ter
   (decomposition trimestrielle/semestrielle de l'EPS, P/E 12 mois
   glissants) - absent uniquement si les donnees disponibles ne permettent
   pas une decomposition fiable (voir E5 ter point 5), jamais publie a
   titre indicatif non fiable ; `historique` demarre a `[]` (aucune bascule
   d'exercice anterieure a l'assistant). `ownership` renseigne (insiders
   ancres sur le dernier proxy en priorite, notableHolders 13F US
   uniquement trouves lors de la recherche E2, `coverageNote` si le titre
   n'est pas couvert par le regime 13F, `history` VIDE `[]` - aucun
   refresh anterieur a snapshotter - voir SCHEMA), sans jamais bloquer la
   creation si une source fiable manque. `compliance` renseigne (recherche
   etendue a tout l'historique public du titre - fraudes averees,
   enquetes, allegations par regulateurs/cabinets d'avocats plaignants/
   vendeurs a decouvert activistes, jamais le contentieux commercial
   ordinaire), `items` vide `[]` avec `note` confirmant explicitement
   l'absence d'element trouve si c'est le cas plutot que de laisser un
   doute.
3. RAPPELLE que deux actions sont necessaires sur GitHub : (a) creer
   `data/SIEMENS.json` avec ce contenu, ET (b) ajouter `"SIEMENS"` dans le
   tableau `tickers` de `data/manifest.json` - sans quoi le titre resterait
   invisible malgre le fichier present.

### Pour un REFRESH (Operation B)
L'utilisateur fournit le JSON existant du titre dans sa requete (source de
la borne temporelle E1 et de la base de reconciliation E6) : pas besoin de
confirmer le nom/code, il est deja connu.
0. VERIFICATION DE FRAICHEUR (avant toute recherche) : compare le trimestre/
   evenement trouve lors de la RECHERCHE DU COMMUNIQUE (plus haut) au
   `hypothese.dernierCall.quarter` DEJA PRESENT dans le JSON fourni en
   entree. SI IDENTIQUE (le refresh porte sur le MEME call que celui deja
   couvert par le fichier - rien de nouveau n'a ete publie depuis) :
   ARRETE-TOI ICI, ne deroule PAS la suite de la boucle, et demande
   explicitement a l'utilisateur s'il souhaite (a) un refresh de pure forme
   ne touchant que des elements independants du trimestre (ex. un
   evenement hors-cycle survenu depuis, un changement d'actionnariat/
   compliance), auquel cas `dernierCall`/`guidanceHistory` sont repris TELS
   QUELS sans nouvelle ligne ni recherche redondante du communique/
   transcript, ou (b) qu'un nouveau trimestre a bien ete publie entre
   temps et qu'il faut regarder plus loin. Ce garde-fou existe parce que
   `guidanceHistory` (AJOUTE une ligne des que `fyGuided` correspond, voir
   SCHEMA) et `ownership.history` (snapshotte l'ancien point a CHAQUE
   refresh, sans condition de changement) n'ont eux-memes aucune protection
   interne contre un doublon si le meme call est traite deux fois - c'est
   cette etape 0, en amont, qui doit l'empecher.
1. Affiche E6-a (projection independante + ancrages) et E6-b (confrontation,
   snapshot priorEPS inclus) comme deux blocs distincts dans la reponse,
   avant le JSON final.
2. `nextEvent` renseigne/actualise (le refresh venant de solder le
   trimestre publie, `nextEvent` doit pointer vers l'echeance suivante) -
   rappelle a l'utilisateur que cette valeur ne s'affichera que si le
   ticker est absent de `data/nextEvents.json`, ou jusqu'au prochain
   passage de l'Operation C qui la supplantera (voir DOUBLE STOCKAGE).
   `hypothese.dernierCall` actualise sur le trimestre venant d'etre solde
   (remplace integralement l'ancien, comme le reste de `hypothese`).
   `hypothese.guidanceHistory` mis a jour selon sa mecanique propre
   (ajout d'une ligne si meme `fyGuided` que la derniere ligne existante,
   reset a une ligne unique si nouvel exercice fiscal - voir SCHEMA) ;
   `hypothese.guidanceLongTerme` reconduit tel quel ou remplace si une
   communication plus recente l'a mise a jour - AVANT tout remplacement,
   snapshotte l'ancienne valeur dans `hypothese.guidanceLongTermeHistory`
   selon sa mecanique propre (voir SCHEMA, uniquement si la valeur a
   reellement change, plafonne a 5 points). `hypothese.quarterlyEPS.PY`/
   `CY`/`NY` entierement RECONSTRUITS selon E5 ter (pas de mecanique
   cumulative comme `priorEPS`/`guidanceHistory` - la fenetre glissante de
   periodes n'a pas de sens a preserver d'un refresh a l'autre) ;
   `hypothese.quarterlyEPS.historique` REPRIS TEL QUEL sauf si ce refresh
   est precisement une BASCULE D'EXERCICE, auquel cas l'ancien `PY` y est
   pousse en tete avant d'etre remplace (voir SCHEMA et E5 ter point 0).
   `ownership` RE-RECHERCHE et REMPLACE integralement son etat courant
   (asOf/insiderPct/insiderDesc/insiderSource/notableHolders/
   coverageNote), MAIS AVANT ce remplacement snapshotte `{asOf,
   insiderPct}` de l'ANCIEN `ownership` dans son propre `history` (tableau
   cumulatif propre a `ownership`, plafonne a 8 points - mecanique dediee,
   distincte de `guidanceHistory` - voir SCHEMA), sans jamais bloquer le
   refresh si une source fiable manque. `compliance` REPREND `items` de
   l'ancien JSON TEL QUEL (rien supprime), AJOUTE toute nouvelle
   allegation/procedure detectee depuis le dernier `asOf`, et MET A JOUR
   en place le `status`/`outcome` des entrees existantes dont l'issue a
   evolue - jamais de reecriture retroactive du contenu d'une ancienne
   entree au-dela de son statut/issue.
3. Fournis ensuite le contenu JSON MIS A JOUR du fichier (meme schema,
   `ancrages`, `priorEPS`, `dernierCall`, `guidanceHistory`,
   `guidanceLongTerme`, `guidanceLongTermeHistory`, `quarterlyEPS` (avec
   son sous-champ `historique`), `ownership`, `compliance` et `nextEvent`
   inclus), pret a remplacer le fichier `data/CODE.json` existant sur
   GitHub tel quel.

### Pour une mise a jour groupee (Operation C)
L'utilisateur fournit la liste des codes a traiter (ou "le portefeuille" en
listant tous les codes de `manifest.json`) ET le contenu actuel de
`data/nextEvents.json`.
1. Pour chaque code demande : recherche de la date confirmee, sinon
   deduction du trimestre attendu (voir logique de l'Operation C
   ci-dessus).
2. Livrable : LE FICHIER `data/nextEvents.json` COMPLET, entrees demandees
   mises a jour + entrees existantes non redemandees conservees telles
   quelles, pret a remplacer le fichier existant sur GitHub. Jamais de
   `data/CODE.json` individuel touche, jamais de reference a
   `hypothese`/adjXXX/`data`/`ancrages`/`priorEPS`/`ownership`/`compliance`.

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
