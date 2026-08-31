# Messages de commit — commit conventionnel, préfixe de scope par couche

Format **commit conventionnel** :
- **Titre court** (une ligne, ~72 caractères max) : `(scope) Description de ce qui a été fait`
- **Corps** (optionnel, séparé par une ligne vide) : le détail en bullets — ce qui a changé et pourquoi, **pas le contenu du diff** (il vit dans les fichiers).
- Un **squash** ne concatène jamais les messages repliés : titre neuf + corps synthétique.

Le `scope` liste les couches touchées, notation compacte :
- couche seule → `(3)`
- intervalle → `(2-5)` = couches 2 à 5
- liste → `(0,2,4-5)` = couches 0, 2, 4 et 5

Transverse (`common/`, racine, `tools/`) ou sans couche identifiable → pas de préfixe.
