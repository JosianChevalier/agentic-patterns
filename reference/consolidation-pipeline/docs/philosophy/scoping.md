# Scoping — doctrine, réalité mesurée, tradeoff idempotence

## Pourquoi le scoping est un mécanisme porteur, pas une rambarde

L'objectif petit-contexte (cf. [map-reduce.md](map-reduce.md)) impose de **ne jamais lire une grosse source d'un bloc**. Découper une source en lots thématiques n'est donc pas un cas de bord pour pièces exceptionnelles : c'est le mécanisme normal qui permet au map de rester sous le seuil de dégradation. On découpe **dès qu'une source risque de saturer** le contexte du map.

## La division du travail : détecter (cheap) vs couper (cognition)

Deux actes, deux acteurs :

- **Détecter** qu'une source est trop grosse = `inventory.py`, sur **métadonnées bon marché** : `wc -l` + nombre de `*.png`. Zéro lecture de contenu. Seuil `lines > 600` OU `imgs > 6`.
- **Couper** = un **agent de scoping**. Où tombent les frontières thématiques est un jugement, pas un calcul. Un script qui couperait tous les 500 lignes trancherait au milieu d'un raisonnement.

**L'objection « l'agent crame son contexte en lisant la source pour décider où couper » ne tient pas** : l'agent ne lit jamais le contenu, seulement l'**outline** — la liste des titres de slides/pages + le nombre de lignes sous chacun. L'outline tient en ~200 lignes même pour un deck de 190 slides. C'est ce qui rend la coupe cognitive *abordable* en contexte : on délègue le jugement sans payer la lecture.

## La doctrine de coupe (façon example mapping)

La cible molle « ~500 lignes » dit *combien* couper ; les 4 règles (cf. `specs/scoping.md`) disent *où*. L'esprit :

- **On suit l'ordre du document.** Deux blocs distants du même thème restent deux chunks — pas de regroupement non-contigu au scoping. Pourquoi : rapprocher les occurrences d'un thème est le travail du **reduce**, en aval, via le grep des fragments. Si le scoping fusionnait déjà, il empièterait sur le reduce et devrait lire le contenu pour juger la parenté thématique — ce qu'on s'interdit.
- **La slide/page est l'atome.** Une frontière de chunk tombe sur une frontière d'unité, jamais au milieu. Le structurel porte le sémantique : l'auteur du deck a déjà fait un découpage en slides, on s'appuie dessus.
- **Exception unité énorme** : une slide unique très dense peut être sous-divisée en plages de lignes nues. La règle structurelle cède quand l'unité elle-même dépasse le budget.

La cible 500 l. est **indicative, pas imposée** : `split` enregistre les plages telles quelles, sans vérifier le budget. On fait confiance au jugement de l'agent plutôt que d'imposer un couperet qui retomberait dans le travers du découpage mécanique.

## Réalité mesurée (mai 2026)

- Les **6 rapports** plafonnent à 316 l. → jamais splittés.
- Parmi les ressources déjà en Validate 2/2, **4 decks franchissent le seuil** (cvp_process1, _10, p2, memo_digiscore : 800-1091 l.).
- Le lot extrait **non encore validé** porte les vraies grosses pièces : `support_formation_participants` (3895 l.) et surtout **`ppt_connaitre_le_si_support_complet` : 10739 l. / 190 slides** (>150k tokens — impensable à lire d'un bloc).

Dès le passage de ces pièces en Validate 2/2, le scoping devient **obligatoire** : sans lui, le map sur ce deck est tout simplement infaisable.

## Tradeoff : idempotence ↔ coupe non déterministe

La coupe est une **décision d'agent (non déterministe)** : deux runs de scoping sur la même source pourraient proposer des lots différents. On **assume** ce tradeoff — on troque le déterminisme de la coupe contre un découpage thématique de meilleure qualité, cohérent avec « les agents possèdent la cognition ».

L'**immutabilité par `id`** tient malgré tout, et c'est elle qui protège l'idempotence du pipeline : une fois le scoping fait, `map:<src>` passe en `status=split` et ses enfants `map:<src>#k` existent. Un re-run d'`inventory` (qui merge par `id`) **voit** ces lignes et **ne réécrit rien** — il ne relance donc jamais un nouveau scoping qui produirait une coupe différente. Le non-déterminisme est confiné au **premier** scoping ; après, l'état est figé par les `id`. L'outline, lui, est régénérable (scratch, gitignored) — le perdre ne coûte rien.

Cas non couvert (différé) : une source qui **grossit** après ré-extraction n'est pas re-splittée — ça relève du marquage `stale`, qu'on n'implémente que si on constate des re-reduce manqués.
