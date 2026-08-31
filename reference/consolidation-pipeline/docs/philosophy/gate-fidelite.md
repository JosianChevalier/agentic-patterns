# Le gate de fidélité — pourquoi il remonte aux sources, pas aux fragments

## Deux contrôles de nature différente

Il y a deux choses à garantir, qu'on ne confond pas :

1. **Sourçabilité** — tout fait pointe vers une source réelle (anti-extrapolation). Contrôle **déterministe** : une citation est là ou pas, elle résout ou pas. C'est le métier de `check.py`, et de lui seul. Pas de citation → refus mécanique.
2. **Fidélité** — le fait dit réellement ce que la source dit (anti-hallucination / distorsion). Contrôle **cognitif** : il faut lire le span et juger ; un script ne peut pas le faire. C'est le gate `validate`, agent-based.

`check.py` reste **inchangé** par l'ajout du gate de fidélité : il ne vérifie *jamais* la fidélité, et le gate de fidélité ne refait *jamais* le sourçage. Séparer les deux évite un linter qui prétendrait juger du sens (impossible) et un gate cognitif qui re-ferait du parsing (gâché).

## Pourquoi remonter à la source d'origine, et pas au fragment

Le chemin d'un fait est : `source → fragment (map) → consolidé (reduce)`. Une distorsion peut naître à **chacune** des deux flèches.

Si le validateur du reduce ne remontait qu'au fragment, il ne verrait qu'une des deux flèches : une distorsion née **au map** (fragment infidèle à sa source) serait déjà « actée » dans le fragment et passerait inaperçue. En faisant résoudre chaque citation jusqu'à la **source d'origine** (`1-sources/1.2-nettoyes/ressources/<slug>/index.md` ou `1-sources/1.2-nettoyes/reports/REPORT_x §N`), on collapse les deux transitions en un seul contrôle en bout de chaîne, contre le ground-truth. Une erreur map propagée au reduce est attrapée au même endroit qu'une erreur née au reduce.

Corollaire : les **fragments restent non-validés en fidélité**. On ne met aucune boucle de validation sur les fragments eux-mêmes — juste `check.py` de sourçage. Leurs erreurs éventuelles sont rattrapées en aval, au gate reduce. C'est volontaire : valider les fragments séparément doublerait le coût cognitif pour rattraper, au map, ce que le reduce rattrape déjà.

## Risque résiduel : map vs reduce

- **Au reduce** : le risque de distorsion **disparaît** — couvert par le gate 2/2, deux agents distincts relisant contre la source d'origine, posture « réfute par défaut si doute ».
- **Au map** : un résidu subsiste — un fragment peut distordre sa source sans qu'aucun gate ne le voie *à ce stade* (seul `check.py` tourne, qui ne juge pas la fidélité). Mais ce résidu est **rattrapé en aval** par le gate reduce, qui revérifie contre la source. Le seul cas où un fragment infidèle ne serait jamais attrapé est un fragment qu'aucun reduce ne consomme — sans conséquence, puisqu'il n'atteint jamais la couche 2.

## Pourquoi 2/2 et distinct-agent

Un seul validateur, ou un validateur = l'auteur, ne réfute pas vraiment : biais de confirmation. Deux agents **distincts entre eux et de l'auteur** forcent deux relectures indépendantes ; 2/2 (et non 1/2) parce qu'un seul reject suffit à renvoyer le reduce à `todo` — on préfère un faux négatif (un bon reduce refait) à un faux positif (une distorsion publiée). La garde distinct-agent est vérifiée sous le flock via le bookkeeping `author:`/`ok:` ; c'est le même modèle que le pipeline `1-sources/outils/ressources/`.
