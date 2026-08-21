# Doctrine Omnium — deplacee hors du depot

La source de verite de la methodologie (operations A/B, regles E1-E8,
scorecard, ponts, retraitements) ne vit plus dans ce depot.

## Emplacement unique (depuis le 21/08/2026)

Tous les actifs hors-repo du produit vivent dans le **Drive partage
"Omnium Stock-screener"** du compte **mathieu.chandelier@omnium-capital.com**
— et NULLE PART AILLEURS :

| Actif | Emplacement dans le Drive partage |
|---|---|
| Doctrine (methodologie complete) | `00-DOCTRINE/INSTRUCTIONS.md` (fichier `.md` — jamais de version Google Doc) |
| Archive des transcripts de calls | `transcript/<TITRE>/` (un dossier par titre, un doc par evenement ; id Drive du dossier racine : `1OMBnENmfvCWCtAHUesumoQtvT2_rYqk3`) |
| Zips de migration, versions retirees | `90-ARCHIVE/` |

Acces local (Google Drive for desktop) :
`~/Library/CloudStorage/GoogleDrive-mathieu.chandelier@omnium-capital.com/Drive partagés/Omnium Stock-screener/`

## Regle compte unique — a respecter par toute session LLM

- Lire ET ecrire la doctrine et les archives transcripts UNIQUEMENT dans ce
  Drive partage, via un connecteur/point de montage branche sur le compte
  `mathieu.chandelier@omnium-capital.com`.
- Si le connecteur Google Drive de la session est branche sur un AUTRE
  compte (verifiable via le champ `owner` des resultats de recherche ou le
  parametre `ouid` des URLs retournees) : NE RIEN CREER, le signaler.
- Emplacements OBSOLETES a ne plus alimenter ni consulter :
  l'arborescence `transcript/` du compte personnel `ozdaday@gmail.com`
  (racine historique `1difkU7g9LwDTXNZMyX8nXwRaLtZdvYmo`, migree le
  21/08/2026), l'ancien `~/Mon Drive/OMNIUM-DOCTRINE/` (un pointeur
  `OU-EST-LA-DOCTRINE.txt` y subsiste), et les dossiers legacy du compte
  `investors@omnium-capital.com`.

Toute session qui execute une operation A/B doit lire la doctrine a
l'emplacement ci-dessus. La spec operationnelle autonome
INSTRUCTIONS_CALENDAR.md reste dans le depot : elle decrit une mecanique,
pas la methodologie. (La boucle 13F a ete abandonnee le 19/08/2026 — le
champ ownership des fiches reste de la donnee, sans operation dediee.)
