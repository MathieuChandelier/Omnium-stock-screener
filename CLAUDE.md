# Omnium Stock Screener — reperes pour les sessions LLM

App single-file (`index.html`) + fiches `data/<CODE>.json`, servie par
GitHub Pages sur https://screener.omnium-capital.com (tout push sur `main`
deploie la production, cache CDN ~10 min).

## Ou vivent les actifs hors-repo (REGLE COMPTE UNIQUE, 21/08/2026)

La doctrine methodologique et l'archive des transcripts vivent dans le
**Drive partage "Omnium Stock-screener"** du compte
**mathieu.chandelier@omnium-capital.com** — et nulle part ailleurs :

- Doctrine : `00-DOCTRINE/INSTRUCTIONS.md` (fichier `.md` ; ne jamais
  editer une version Google Doc).
- Transcripts : `transcript/<TITRE>/` — id Drive du dossier racine :
  `1difkU7g9LwDTXNZMyX8nXwRaLtZdvYmo` (Google Docs natifs, id historique
  conserve lors de la migration).
- Acces local : `~/Library/CloudStorage/GoogleDrive-mathieu.chandelier@omnium-capital.com/Drive partagés/Omnium Stock-screener/`

AVANT toute creation/lecture de fichier Drive : verifier que le connecteur
est branche sur `mathieu.chandelier@omnium-capital.com` (champ `owner` des
resultats, ou `ouid` des URLs). Si c'est un autre compte : ne rien creer,
le signaler. Il ne reste rien chez `ozdaday@gmail.com` (arborescence deplacee le
21/08/2026) ; les dossiers legacy `investors@omnium-capital.com`,
`~/Mon Drive/OMNIUM-DOCTRINE/` et la copie .docx dans
`90-ARCHIVE/transcript-copie-docx-migration-zip-20260821` sont OBSOLETES. Voir `INSTRUCTIONS.md` (stub de pointage) pour le detail.

## Garde-fous repo

- Ne jamais pousser une modification d'`index.html` sans verification
  console navigateur (un SyntaxError = production blanche).
- Avant tout commit touchant `data/<CODE>.json` : `python3
  scripts/validate_ticker.py data/<CODE>.json` doit etre vert (le workflow
  CI "Valider les fichiers de titres" bloque sinon — regle "propre a
  partir de maintenant") et `python3 scripts/coherence_checks.py` doit
  afficher 0 anomalie.
- Commits selectifs par fichier (jamais `git add -A`) quand plusieurs
  sessions/agents editent le repo en parallele.
