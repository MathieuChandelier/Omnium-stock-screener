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
c'est le run suivant qui prolongera :
- resultats trimestriels/annuels (la source primaire : page IR, calendrier
  d'earnings officiel) ;
- conferences brokers et fireside chats (agendas des conferences sante/
  tech/conso : Morgan Stanley, JPM, Goldman, Jefferies...) ;
- Capital Markets Days / Investor Days ;
- assemblees generales, journees produit, lancements annonces ;
- tout evenement date publiquement annonce et structurant pour la these.

Chaque evenement porte :
- `id` : stable, `TICKER-YYYY-MM-DD-slug` (le meme evenement retrouve la
  semaine suivante garde le MEME id - c'est ce qui evite les doublons
  cote selections utilisateur) ;
- `ticker`, `date` (YYYY-MM-DD), `label` court en anglais,
  `type` : `earnings` | `conference` | `cmd` | `agm` | `other` ;
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

## LIVRABLES (deux fichiers, un commit)

1. `data/calendarCandidates.json` COMPLET :
   `{"_meta":{"generatedAt":"<ISO UTC de ce run>","window":"1m"},
     "events":[...]}` - le fichier est REGENERE entierement a chaque run
   (les ids stables assurent la continuite des selections).
2. `data/nextEvents.json` mis a jour (l'ancien livrable de l'Operation C,
   toujours consomme par la colonne NEXT EVENT du portefeuille) :
   pour chaque ticker, la PROCHAINE echeance retenue `{label, date}`
   (convention courte, annee sur 2 chiffres, ex. "Q3 26") - fusion avec
   les entrees existantes, jamais de suppression d'un ticker non traite.
   Ajouter `_meta.lastRun` a la date du jour.

Pousser les deux fichiers dans le meme commit ("Calendar refresh - <date>").
Le dashboard bascule alors automatiquement la pastille bleue en pastille
turquoise "Calendar actions" : l'utilisateur trie, coche ce qu'il veut
dans son agenda (bouton + par ligne -> Google Calendar), et ferme.
