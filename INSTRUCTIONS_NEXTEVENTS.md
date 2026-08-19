# INSTRUCTIONS_NEXTEVENTS - Operation C : prochains evenements (nextEvents.json)

Fichier AUTONOME (extrait d'INSTRUCTIONS.md le 18/08/2026) : une session qui
execute cette operation n'a besoin QUE de ce fichier. L'operation ne touche
JAMAIS `hypothese`/`omniumXXX`/`data` ni un `data/CODE.json` individuel.

DECLENCHEMENT : alerte mensuelle du dashboard (visible a partir du 1er du
mois si `_meta.lastRun` du fichier est anterieur au mois en cours), ou
demande directe de l'utilisateur.

Declencheur : "mets a jour les dates de prochains resultats [du portefeuille |
de TICKER1, TICKER2, ...]". L'utilisateur fournit les codes exacts tels
qu'ils figurent dans `data/manifest.json` (ou "le portefeuille" pour tous
les traiter), ET colle le contenu actuel de `data/nextEvents.json` (pour
permettre la fusion du point 2 du LIVRABLE FINAL) - a defaut, si l'ancien
contenu n'est pas fourni, le demander avant de continuer plutot que de
livrer un fichier partiel qui ferait disparaitre les entrees non
redemandees.

Operation LEGERE et INDEPENDANTE de la boucle E1-E8 : ne touche JAMAIS
`hypothese`/`omniumXXX`/`data`, et ne touche JAMAIS un `data/CODE.json`
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


## LIVRABLE

L'utilisateur fournit la liste des codes a traiter (ou "le portefeuille" en
listant tous les codes de `manifest.json`) ET le contenu actuel de
`data/nextEvents.json`.
1. Pour chaque code demande : recherche de la date confirmee, sinon
   deduction du trimestre attendu (voir logique de l'Operation C
   ci-dessus).
2. Livrable : LE FICHIER `data/nextEvents.json` COMPLET, entrees demandees
   mises a jour + entrees existantes non redemandees conservees telles
   quelles. Jamais de `data/CODE.json` individuel touche, jamais de
   reference a `hypothese`/omniumXXX/`data`/`ancrages`/`priorEPS`/`ownership`/
   `compliance`/`coherenceQualitative`. Si un acces `git`/GitHub est
   disponible : POUSSE directement ce fichier en remplacement de l'existant
   sur GitHub, confirme apres coup le commit pousse (lien ou hash). Si cet
   acces est absent : DIS-LE EXPLICITEMENT et fournis le fichier complet
   pret a coller manuellement.


## CHAMP _meta (ajoute le 18/08/2026)

Le fichier livre porte OBLIGATOIREMENT une cle racine `_meta` :
`"_meta": {"lastRun": "AAAA-MM-JJ"}` (date du passage). C'est elle qui
eteint l'alerte mensuelle du dashboard - sans elle, l'alerte reste affichee.
L'app ne lit `nextEvents.json` que par code de titre : `_meta` est invisible
a l'affichage et reserve a ce pilotage.
