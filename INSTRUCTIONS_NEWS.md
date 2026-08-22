# INSTRUCTIONS_NEWS — boucle News du run hebdomadaire

Fichier AUTONOME (cree le 21/08/2026). Une session qui execute cette
operation n'a besoin QUE de ce fichier — plus INSTRUCTIONS_CALENDAR.md,
car la boucle News s'execute DANS LE MEME RUN hebdomadaire que le Market
Calendar : meme session, meme passe sur les sources IR, meme commit.
L'operation ne touche JAMAIS `hypothese`/`omniumXXX`/`data` ni un
`data/CODE.json` individuel.

Elle REMPLACE l'ancienne boucle Python automatisee (collectors/
communiques.py + web.py, dormants — contexte historique seulement ;
collectors/youtube.py est REACTIVE comme outil de la boucle video
quotidienne, voir plus bas) : la collecte communiques/externe est
desormais faite par la session LLM elle-meme, avec les memes garanties
(jamais d'invention, jamais d'echec silencieux) et la lecon principale
de l'ancienne boucle en tete — elle notifiait PLUSIEURS fois le meme
evenement (un item par lien) ; la regle de dedup par EVENEMENT
ci-dessous existe pour ca.

DEUX CADENCES (decision 21/08/2026) :
- HEBDO : communiques societes + externe critique (kinds `communique`,
  `externe`, `broker`), dans le run du calendrier — declenchement :
  pastille bleue "Refresh calendar" du jeudi matin (INSTRUCTIONS_
  CALENDAR.md), ou demande directe. Boucle MANUELLE. Le run hebdo ne
  fait PLUS de videos.
- DAILY : videos YouTube (kind `video`) via la BOUCLE VIDEO QUOTIDIENNE
  dediee (section ci-dessous), un lot rotatif de tickers par jour —
  c'est elle qui fait s'incrementer quotidiennement les notifications
  du bandeau NEWS.

## PHILOSOPHIE

Screener TRES LARGE, ne retenir que L'ESSENTIEL. La fenetre couvre les
7 JOURS ecoules (du jeudi J-7 au jour du run) et ne regarde que le PASSE
ou l'EN COURS : tout evenement A VENIR appartient au calendrier, pas au
feed. L'ancrage est FORT sur les publications des societes ELLES-MEMES
(pressroom / page communiques du site IR) : c'est la source primaire,
lue pour CHAQUE ticker de `data/manifest.json`, avec les memes methodes
de contournement que le calendrier. Un item qui ne merite pas d'etre lu
par un gerant presse ne rentre pas — le feed vide est un resultat valide.

## OPERATION

Pour CHAQUE ticker du manifest, dans la meme passe que la lecture des
pages "Events" IR du calendrier :

1. Lire la page PRESSROOM / communiques de presse du site IR (souvent
   voisine de la page Events deja visitee). REGLE DES TROIS STRATEGIES
   d'acces : curl nu -> curl avec User-Agent sobre -> navigateur. Les
   flux SEC EDGAR 8-K/6-K de `data/newsSources.json` restent un
   complement utile pour les tickers US (URLs deja validees), jamais un
   substitut a la lecture du pressroom.
2. Screener large les publications EXTERNES de la fenetre (presse
   whitelist, brokers) — puis filtrer selon la typologie stricte
   ci-dessous. Les videos ne sont PAS traitees ici (boucle daily).
3. Ecrire `data/newsFeed.json` (voir LIVRABLES).

## TYPOLOGIE STRICTE DES ITEMS RETENUS

1. COMMUNIQUES DES SOCIETES (`kind:"communique"`) — source primaire,
   pressroom/IR — sur des evenements precis PASSES ou EN COURS :
   acquisition ou cession, profit warning / revision de guidance, depart
   ou arrivee d'un dirigeant important, litige majeur, rappel produit,
   contrat structurant, changement de capital allocation (voir regle
   ci-dessous). EXCLUS : communiques de routine (nominations mineures,
   RSE, prix et distinctions, sponsoring, publications financieres deja
   au calendrier).

   REGLE ROUTINE vs SIGNAL (ajoutee le 21/08/2026, cas d'ecole des
   buybacks) : est retenu ce qui CHANGE l'etat de la these ; est exclu
   ce qui EXECUTE un etat deja connu. Concretement :
   - RETENUS (signal) : annonce d'un NOUVEAU plan de rachat d'actions
     ou d'une nouvelle tranche (montant, autorisation) ; arret,
     suspension ou relevement d'un plan en cours ; REPRISE de rachats
     apres une longue interruption (signal de capital allocation) ;
     coupe ou suspension du dividende, dividende exceptionnel.
   - EXCLUS (routine) : les declarations HEBDOMADAIRES / periodiques
     d'execution des rachats (achats effectifs de la semaine — tres
     courant chez les emetteurs europeens du portefeuille, un communique
     chaque semaine : elles ne ressortent JAMAIS dans le run) ;
     transactions de dirigeants reglementaires de routine ; communiques
     de mise a disposition de documents ; dividende ordinaire au
     calendrier habituel.
   Verifie en reel le 21/08/2026 : "Weekly progress share buyback
   programme - 10 Aug - 14 Aug 2026" (HEINEKEN, 17/08/2026, page
   buyback de theheinekencompany.com) et "Declaration des transactions
   sur actions propres" hebdomadaire de BNP (invest.bnpparibas/document/
   rachat-dactions-...) = EXCLUS ; "Heineken N.V. announces second
   tranche of its EUR 1.5 billion share buyback programme" (12/02/2026)
   = RETENU (nouvel engagement chiffre).

2. EVENEMENTS PUBLIES AILLEURS, UNIQUEMENT SI CRITIQUES
   (`kind:"externe"` ou `kind:"broker"`) :
   - rumeur d'acquisition rapportee par un journal de la WHITELIST :
     Bloomberg, Reuters, Financial Times, Wall Street Journal, Les
     Echos, Handelsblatt, Nikkei, Il Sole 24 Ore, Expansion — extensible
     au cas par cas a un titre de meme calibre, jamais a un agregateur ;
   - rumeur produit ou operationnelle vehiculee par un media serieux
     (meme whitelist) ou un broker ;
   - changement d'opinion broker SEULEMENT s'il s'appuie sur des
     elements precis et importants (these detaillee, channel checks,
     donnees proprietaires). Un changement de target au contenu
     laconique ("PT releve de X a Y") est EXCLU explicitement — c'est
     du bruit, pas de l'information.

3. VIDEOS CRITIQUES (`kind:"video"`, YouTube) : interview d'un CEO, ou
   contenu MATERIEL et SPECIFIQUE au titre (demonstration produit
   structurante, deposition, keynote avec annonce). EXCLUS : analyses
   de chaines generalistes, recaps de resultats, contenu d'opinion.
   Collectees par la BOUCLE VIDEO QUOTIDIENNE (section dediee) ; le
   protocole de recherche detaille (requetes, chaines) est defini par
   la spec du moteur YouTube ; la presente typologie et la regle de
   dedup ci-dessous s'imposent a lui.

## REGLES

- DEDUP PAR EVENEMENT (lecon de l'ancienne boucle) : id stable
  `TICKER-YYYYMMDD-slug-evenement` (date de l'EVENEMENT, slug court en
  anglais). Un meme evenement couvert par un communique + des articles +
  des videos = UN SEUL item ; le lien le plus primaire (communique IR
  s'il existe) porte `source`/`url`, les autres liens vont dans
  `corroborations`. Le meme evenement retrouve la semaine suivante garde
  le MEME id.
- JAMAIS de donnee inventee : chaque item cite sa source REELLE (URL
  effectivement lue pendant le run). Pas de source lisible = pas d'item.
- `summary` : 1-2 lignes factuelles, ce qui s'est passe et pourquoi
  c'est materiel — pas de paraphrase du titre.
- `critical` : true pour tout item retenu (la typologie EST le filtre de
  criticite) ; le champ existe pour permettre un futur niveau "notable".
- SCALABILITE : tout ticker retire de `data/manifest.json` est ignore
  partout — collecte, feed, sourceGaps.

## BOUCLE VIDEO QUOTIDIENNE (kind:"video")

Chaque JOUR, un run Claude Code dedie traite UN LOT rotatif de tickers
du manifest et fusionne ses items `kind:"video"` dans
`data/newsFeed.json` (meme schema, memes regles de typologie et de
dedup — les ids stables font la dedup naturellement), puis commit/push.

DECOUPAGE ET REGLE DE COHERENCE (a ecrire noir sur blanc) :
- Lots calcules depuis `data/manifest.json` : ~12 tickers par lot,
  soit 5 lots pour 59 titres. Le decoupage se recalcule quand le
  manifest change (scalabilite : un ticker retire disparait des lots).
- La rotation complete (nombre de lots, en jours) doit TOUJOURS rester
  inferieure d'au moins 2 jours a la fenetre de recherche : rotation
  5 j / fenetre 7 j aujourd'hui ; si le portefeuille impose 7 lots,
  la fenetre passe a 9 j. C'est ce qui garantit qu'aucune video ne
  tombe entre deux passages d'un meme ticker.

BACKEND :
- VOIE PRINCIPALE : scraping de la recherche youtube.com (ytInitialData,
  le meme moteur que le site) — detection validee aussi bonne ou
  meilleure que l'API (test Tenev, 21/08/2026), sans quota.
- VOIE OPTIONNELLE : l'API YouTube Data v3 si YOUTUBE_API_KEY est
  disponible (secrets GitHub Actions uniquement, jamais en clair) —
  limite de quota journaliere (100 unites par recherche sur un budget
  de 10 000 : la couverture par lots existe aussi pour ca).
- L'outil est `python3 collectors/youtube.py` (le support des lots y
  est ajoute par l'agent moteur YouTube — voir sa spec pour
  l'implementation ; la presente spec n'en fixe que le contrat :
  typologie video, dedup par evenement, schema newsFeed, sourceGaps).

ECHEC DU RUN DAILY = NOTIFICATION TYPEE : scraping bloque, page
inaccessible, resultat illisible -> meme mecanique que le hebdo, entree
dans `data/sourceGaps.json` section `news`
(`{"ticker":"...","source":"youtube","note":"<cause courte>",
"url":"<recherche ou video>","blockedBy":"scraping_bloque"}`), effacee
par la passe qui sert le titre. Jamais de silence.

## LIVRABLES

`data/newsFeed.json`, ecrit par les DEUX cadences (memes vertus que le
calendrier : les ids stables assurent la continuite, les items sortis
de la fenetre disparaissent) :
- le run HEBDO regenere les items `communique`/`externe`/`broker` de la
  fenetre 7d et PRESERVE les items `video` encore en fenetre ;
- le run DAILY fusionne ses items `video` (lot du jour) et purge les
  videos sorties de fenetre, sans toucher aux autres kinds.

```
{"_meta":{"generatedAt":"<ISO UTC de ce run>","window":"7d"},
 "items":[{"id":"TICKER-YYYYMMDD-slug-evenement",
           "ticker":"...","date":"YYYY-MM-DD",
           "kind":"communique|externe|broker|video",
           "title":"...","summary":"1-2 lignes",
           "source":"...","url":"...","critical":true,
           "corroborations":[{"source":"...","url":"..."}]}]}
```

Commits :
- run HEBDO : dans LE MEME COMMIT que `data/calendarCandidates.json` et
  les champs `nextEvent` des fiches ("Calendar refresh - <date>") — un run, un
  commit, trois fichiers ;
- run DAILY : son propre commit/push quotidien ("News video - <date>,
  lot <n>/<total>") — c'est ce push qui incremente les notifications
  du bandeau NEWS chaque jour.

ECHEC DE RETRIEVE = NOTIFICATION TYPEE : si le pressroom d'un titre
reste illisible apres les trois strategies (403 persistant, coquille JS)
et que la session ne dispose pas du navigateur, le run INSCRIT le titre
dans `data/sourceGaps.json`, section `news`
(`{"ticker":"...","source":"pressroom","note":"<cause courte>",
"url":"<page pressroom>","blockedBy":"navigateur_indisponible"}`).
La passe qui sert le titre EFFACE son entree. Jamais d'echec silencieux,
jamais de contenu invente pour combler un trou de collecte.
