# `inventory.py` — peuplement du CSV

Peuple `2-consolide/outils/tasks.csv` à partir des sources prêtes et du vocabulaire de thèmes. **Idempotent : merge par `id`**, ne réécrit **jamais** une ligne existante (≠ `1-sources/outils/ressources/inventory.py` qui écrase). → *pourquoi l'idempotence et son interaction avec la coupe* : `philosophy/scoping.md`.

## Ce qu'il append

- **Lignes reduce** : une par clé de `THEMES.md` (`reduce:<theme-clé>`, `todo`). Granularité = H2 + quelques H3 (~30 clés), dérivée du sommaire du seed CATS (ex-synthèse de 1re passe, supprimée).
- **Lignes map** :
  - les 6 rapports `1-sources/1.2-nettoyes/reports/REPORT_*.md` ;
  - les slugs ressources en **Validate `2/2`** lus dans `1-sources/outils/ressources/RESSOURCES_TODO.md` (uniquement ceux-là).

## Seuil + branche oversize

Sur chaque source map, applique le **seuil** ([scoping.md](scoping.md)) sur métadonnées cheap (`wc -l`, nb `*.png`) :

- **Sous le seuil** : pose `map:<src>` `todo` (map normal).
- **Au-dessus** : ne pose **pas** d'enfants. Génère l'**outline** (titres `^## (Slide|Page) \d+` + nb de lignes sous chacun) et pose `map:<src>` `todo` avec `note=oversize`. Le découpage est fait par un agent de scoping qui appellera `split`.

## Idempotence

Re-run après extraction : ajoute les nouveaux slugs sans perdre l'état existant. Une `map:<src>` passée en `status=split` (après scoping) + ses enfants → re-run **ne réécrit rien** (merge par `id`). Une source qui grossit après ré-extraction n'est **pas** re-splittée (relève du `stale`, différé).

## Critères d'acceptation

- Run à vide : peuple reduce depuis THEMES + map avec les 6 rapports (aucun ne dépasse le seuil → 6 lignes simples).
- Re-run après extraction : ajoute les slugs sans perdre l'état.
- Un slug au-dessus du seuil : produit `map:<src>` `note=oversize` + son outline (et **non** des enfants).
