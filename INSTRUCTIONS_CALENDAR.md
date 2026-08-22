# INSTRUCTIONS_CALENDAR — boucle hebdomadaire du Market Calendar

Fichier AUTONOME (remplace INSTRUCTIONS_NEXTEVENTS.md le 19/08/2026 - il
absorbe l'Operation C mensuelle dans une boucle HEBDOMADAIRE unique).
Une session qui execute cette operation n'a besoin QUE de ce fichier.
L'operation ne touche JAMAIS `hypothese`/`omniumXXX`/`data` ni un
`data/CODE.json` individuel.

DECLENCHEMENT : pastille bleue "Refresh calendar" du dashboard, visible
chaque JEUDI matin des que `data/calendarCandidates.json:_meta.generatedAt`
est anterieur au jeudi de la semaine courante - ou demande directe.
C'est une boucle MANUELLE : l'utilisateur lance la session lui-meme
(aucun token API, aucune automatisation).

## OPERATION

Pour CHAQUE ticker de `data/manifest.json`, rechercher les evenements
publics a venir sur une fenetre d'UN MOIS : du jeudi du run a J+31
inclus, pas plus - le calendrier ne couvre que le proche horizon,
c'est le run suivant qui prolongera.

SOURCE PRIMAIRE OBLIGATOIRE (renforcee le 21/08/2026) : la page
"Events & Presentations" / "Financial calendar" du site IR de CHAQUE
societe. C'est LA que vivent les evenements critiques a ne pas rater -
en particulier les PRESENTATIONS INVESTISSEURS et les CONFERENCES
BROKERS des que la societe les affiche. Appliquer la REGLE DES TROIS
STRATEGIES d'acces de la doctrine (curl nu -> curl UA sobre ->
navigateur) avant de conclure qu'une page est inaccessible - verifie en
reel le 21/08/2026 : investors.bostonscientific.com repond en curl NU
(y figurait "Boston Scientific at Wells Fargo's 21st Annual Healthcare
Conference", 10 sept 08:00 ET, avec lien webcast) ; investor.
mercadolibre.com exige le NAVIGATEUR (403 curl ; y figurait "Goldman
Sachs Conference in San Francisco", 8 sept) ; se.com passe en curl,
investor.lilly.com et ir.aboutamazon.com exigent le navigateur. Une
passe navigateur couvre tout le portefeuille.

Types d'evenements a capter :
- resultats trimestriels/annuels (calendrier d'earnings officiel) ;
- PRESENTATIONS INVESTISSEURS et conferences brokers / fireside chats
  listees par l'IR (Morgan Stanley, JPM, Goldman, Wells Fargo,
  Jefferies...) - completees au besoin par les agendas des conferences
  elles-memes ;
- Capital Markets Days / Investor Days ;
- assemblees generales, journees produit, lancements annonces ;
- tout evenement date publiquement annonce et structurant pour la these.

Chaque evenement porte :
- `id` : stable, `TICKER-YYYY-MM-DD-slug` (le meme evenement retrouve la
  semaine suivante garde le MEME id - c'est ce qui evite les doublons
  cote selections utilisateur) ;
- `ticker`, `date` (YYYY-MM-DD), `label` court en anglais,
- `time` (HH:MM, Europe/Paris) QUAND la source la donne - l'heure
  n'apparait PAS dans le dashboard mais part dans le Google Calendar
  (decision 20/08/2026). A defaut d'heure connue, calendar.php applique
  lui-meme 22:00 aux EARNINGS (cloture de bourse US, le standard) et
  laisse les autres types en journee entiere - ne jamais inventer une
  heure cote collecte,
  `type` : `earnings` | `conference` | `cmd` | `agm` | `other` ;
- `url` (21/08/2026) : le LIEN PRECIS de l'evenement - page evenement
  IR, lien webcast ou page d'inscription - des que la source en affiche
  un. OBLIGATOIRE quand il existe, absent sinon (jamais un lien
  generique vers la home IR). C'est CE lien qui atterrit dans le
  Google Calendar de l'utilisateur quand il accepte l'evenement au tri
  (calendar.php l'emet en propriete URL et en tete de DESCRIPTION du
  VEVENT) ;
- `source` : ou la date a ete lue (IR page, agenda de conference,
  communique...) ;
- `status` : `confirmed` (date publiee par la societe ou l'organisateur)
  ou `estimated` (deduite de la cadence historique - a re-verifier) ;
- `note` optionnelle (une ligne max).

REGLES :
- JAMAIS de date inventee : `estimated` exige une logique de deduction
  citee dans `note` (cadence des communiques passes).
- Les evenements passes sortent du fichier ; les selections utilisateur
  vivent cote serveur (calendar.php), PAS ici. Le run n'a PAS a connaitre
  les selections : il regenere toute la fenetre, et c'est l'app qui
  masque du tri les evenements deja TRANCHES - acceptes OU refuses
  ("vu = tranche" : a la cloture du tri, les lignes non cochees sont
  marquees refusees et ne reviennent jamais). Dedup par `id` stable -
  d'ou l'importance de la convention d'id.
- Compacite : `label` <= 60 caracteres, `note` une ligne.
- SEMANTIQUE ABREGEE DES LABELS (21/08/2026) : la colonne Agenda du
  portefeuille affiche le label tel quel sur un espace etroit (mobile).
  Le run ecrit donc des labels NORMALISES, clairs mais resumes,
  <= 14 caracteres hors date :
  - earnings : `Q3 26`, `Q4 FY 26`, `H1 26`, `FY 26` (jamais "Q3 2026
    earnings call") ;
  - conference broker : `Conf <Broker abrege>` - GS (Goldman Sachs),
    MS (Morgan Stanley), JPM, BofA, WF (Wells Fargo), DB, UBS, Citi,
    Barclays, Jefferies, Bernstein... Ex : `Conf GS`, `Conf WF` ;
  - capital markets day : `CMD` ; investor day : `Inv Day` ;
    assemblee generale : `AGM` ; autre : forme courte du meme esprit.
  Le detail complet (nom entier de la conference, lieu) va dans `note`
  et/ou est porte par `url`. L'app applique un filet de securite
  (abbrevEventLabel dans index.html, meme table d'abreviations) aux
  labels herites non conformes.

## LIVRABLES (deux fichiers, un commit)

1. `data/calendarCandidates.json` COMPLET :
   `{"_meta":{"generatedAt":"<ISO UTC de ce run>","window":"1m"},
     "events":[...]}` - le fichier est REGENERE entierement a chaque run
   (les ids stables assurent la continuite des selections).
2. Le champ `nextEvent` de CHAQUE fiche `data/<TICKER>.json`, mis a jour
   DIRECTEMENT PAR CE RUN (rappel
   21/08/2026 : l'Operation C n'existe PLUS comme procedure separee -
   ce run hebdomadaire en est l'UNIQUE mainteneur ; le fichier global
   data/nextEvents.json a ete SUPPRIME le 21/08/2026 - il doublonnait le
   champ de la fiche et les deux divergeaient sur 42 titres sur 59,
   toujours consomme par la colonne NEXT EVENT du portefeuille) :
   pour chaque ticker, la PROCHAINE echeance retenue `{label, date}`
   (convention courte, annee sur 2 chiffres, ex. "Q3 26") - fusion avec
   les entrees existantes, jamais de suppression d'un ticker du manifest
   non traite (une page IR illisible ne doit pas effacer l'echeance
   connue). Ajouter `_meta.lastRun` a la date du jour.

SCALABILITE - LE PORTEFEUILLE FAIT AUTORITE (21/08/2026). Le manifest est
la seule liste qui compte, dans les deux sens :
- ticker AJOUTE : il entre dans le perimetre des le run suivant, sans
  aucune declaration ailleurs - le run itere `data/manifest.json`, point ;
- ticker RETIRE : sa fiche disparait avec lui, il n'y a donc plus rien a
  purger cote echeance (et
  il disparait de `calendarCandidates.json`, integralement regenere).
  Sans cette purge, une echeance fantome survivrait au titre.
Cote app, la symetrie est deja assuree : evenements du tri, tuile du
Market Calendar, selections deja acceptees, entrees de `sourceGaps` et
items de `newsFeed` sont tous filtres par le manifest, et les selections
d'un titre retire sont revoquees cote serveur (calPruneRemovedTickers)
- donc aussi retirees du Google Calendar.

ECHEC DE RETRIEVE = NOTIFICATION TYPEE (21/08/2026) : si la page IR d'un
titre reste illisible apres les trois strategies d'acces (403 persistant,
coquille JS) et que la session ne dispose pas du navigateur, le run
INSCRIT le titre dans `data/sourceGaps.json`, section `calendar`
(`{"ticker":"...","status":"a_recollecter","note":"<cause courte>",
"url":"<page IR>"}`). Le panneau Actions du dashboard affiche alors
l'action dediee "passe navigateur Claude in Chrome" avec le prompt exact
pour ce(s) titre(s) ; la passe qui sert le titre EFFACE son entree.
Jamais d'echec silencieux.

Pousser les deux fichiers dans le meme commit ("Calendar refresh - <date>").
Le dashboard bascule alors automatiquement la pastille bleue en pastille
turquoise "Calendar actions" : l'utilisateur trie, coche ce qu'il veut
dans son agenda (bouton + par ligne -> Google Calendar), et ferme.

## BOUCLE NEWS (meme run)

Depuis le 21/08/2026, le run hebdomadaire execute AUSSI la boucle News
specifiee dans INSTRUCTIONS_NEWS.md : meme session, meme passe sur les
sites IR (la page pressroom se lit dans la foulee de la page Events,
avec les memes trois strategies d'acces), fenetre retrospective de 7
jours (les evenements A VENIR restent ici, au calendrier). Son livrable
`data/newsFeed.json` part dans LE MEME COMMIT que calendarCandidates.json
et les champs `nextEvent` des fiches ; ses echecs de retrieve vont dans
`data/sourceGaps.json`, section `news`.

## SYNCHRONISATION GOOGLE CALENDAR (directe, 21/08/2026)

L'abonnement ICS ("From URL") est REMPLACE. Il restait tributaire du
rafraichissement de Google, soit 8 a 24 h de latence entre l'acceptation
d'un evenement au tri et son apparition dans l'agenda.

Desormais `server/calendar.php` ecrit DIRECTEMENT dans un agenda Google
dedie, via un COMPTE DE SERVICE (Google Calendar API v3) : l'acceptation
d'un evenement l'y cree dans la seconde, son retrait l'en supprime aussi
vite. Le flux `.ics` reste servi par le meme script pour compatibilite,
mais ne doit plus etre l'outil de reference.

Configuration, a cote de `calendar.php` sur model.omnium-capital.com :
- `gcal_key.json` : cle privee du compte de service
  `omnium-calendar@omnium-news-collector.iam.gserviceaccount.com` ;
- `gcal_config.json` : `{"calendarId":"<agenda dedie>"}` - l'agenda est
  CREE PAR le compte de service puis partage a l'utilisateur (et non
  l'inverse : la politique Workspace interdit le partage sortant
  modifiable) ;
- `gcal_token_cache.json` : jeton OAuth mis en cache ~1 h, regenere seul.
Ces trois fichiers sont INTERDITS d'acces web (bloc `<FilesMatch>` du
`.htaccess`). Sans eux, la sync est silencieusement sautee et le store
continue de fonctionner - aucune rupture.

CONSEQUENCE POUR LE RUN : rien ne change cote collecte. Le champ `url`
d'un evenement part dans le Google Calendar (propriete `source` + tete de
la description), et l'heure suit la regle ci-dessus. Un titre RETIRE du
manifest voit ses evenements deja acceptes revoques cote serveur, donc
retires de l'agenda Google (cf. SCALABILITE).
