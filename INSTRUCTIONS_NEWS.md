# INSTRUCTIONS_NEWS — boucle News du run hebdomadaire

Fichier AUTONOME (cree le 21/08/2026). Une session qui execute cette
operation n'a besoin QUE de ce fichier — plus INSTRUCTIONS_CALENDAR.md,
car la boucle News s'execute DANS LE MEME RUN hebdomadaire que le Market
Calendar : meme session, meme passe sur les sources IR, meme commit.
L'operation ne touche JAMAIS `hypothese`/`omniumXXX`/`data` ni un
`data/CODE.json` individuel.

Elle REMPLACE l'ancienne boucle Python automatisee (collectors/
communiques.py + web.py + youtube.py, dormante — conservee comme contexte
historique seulement) : la collecte est desormais faite par la session
LLM elle-meme, avec les memes garanties (jamais d'invention, jamais
d'echec silencieux) et la lecon principale de l'ancienne boucle en tete —
elle notifiait PLUSIEURS fois le meme evenement (un item par lien) ; la
regle de dedup par EVENEMENT ci-dessous existe pour ca.

DECLENCHEMENT : celui du calendrier (INSTRUCTIONS_CALENDAR.md) — pastille
bleue "Refresh calendar" du jeudi matin, ou demande directe. Boucle
MANUELLE, aucun token API, aucune automatisation.

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
   whitelist, brokers) et YouTube — puis filtrer selon la typologie
   stricte ci-dessous.
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
   Le protocole de recherche detaille (requetes, chaines, quotas) est
   defini par la spec du moteur YouTube ; la presente typologie et la
   regle de dedup ci-dessous s'imposent a lui.

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

## LIVRABLES

`data/newsFeed.json`, REGENERE entierement a chaque run (memes vertus
que le calendrier : les ids stables assurent la continuite, les items
sortis de la fenetre 7d disparaissent) :

```
{"_meta":{"generatedAt":"<ISO UTC de ce run>","window":"7d"},
 "items":[{"id":"TICKER-YYYYMMDD-slug-evenement",
           "ticker":"...","date":"YYYY-MM-DD",
           "kind":"communique|externe|broker|video",
           "title":"...","summary":"1-2 lignes",
           "source":"...","url":"...","critical":true,
           "corroborations":[{"source":"...","url":"..."}]}]}
```

Livre dans LE MEME COMMIT que `data/calendarCandidates.json` et
`data/nextEvents.json` ("Calendar refresh - <date>") : un run, un commit,
trois fichiers.

ECHEC DE RETRIEVE = NOTIFICATION TYPEE : si le pressroom d'un titre
reste illisible apres les trois strategies (403 persistant, coquille JS)
et que la session ne dispose pas du navigateur, le run INSCRIT le titre
dans `data/sourceGaps.json`, section `news`
(`{"ticker":"...","source":"pressroom","note":"<cause courte>",
"url":"<page pressroom>","blockedBy":"navigateur_indisponible"}`).
La passe qui sert le titre EFFACE son entree. Jamais d'echec silencieux,
jamais de contenu invente pour combler un trou de collecte.
