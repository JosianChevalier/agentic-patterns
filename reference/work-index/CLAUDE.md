# 0-pilotage/travaux-en-cours/ — chantiers transverses en cours

Un **chantier** = un gros morceau de travail **transverse aux couches**, qui vit plus longtemps qu'une session et traverse plusieurs couches du repo (typiquement : couche 1 → 2 → 3 → 4).
Il a besoin d'un **domicile** parce qu'aucune couche ne le contient à elle seule.

Point d'entrée : **`INDEX.md`** — la table des chantiers ouverts, avec priorités et prochaine action.

**À distinguer des deux autres dossiers de la couche 0 :**
- `0-pilotage/contrats/` — le **scope contractuel** (devis Shodo, brief CATS, CR d'avant-contrat). Figé, archive.
- `0-pilotage/reunions/` — prépa + CR des **réunions client** avec CATS. Trace d'échanges, s'accumule.

Ici = **du travail en train de se faire**. Ni figé, ni accumulé.

## Nature : plan de travail (ça se vide)

Chaque fichier de chantier est un **plan de travail** : ce qui y reste = travail non fait.
Un chantier **terminé disparaît** — son fichier est supprimé, sa ligne retirée de `INDEX.md`. Le **pourquoi** de ce qui a été fait ou écarté vit dans **git** (message de commit), jamais dans un doc vivant : pas d'entrée barrée, pas de « X retiré car… ».

⚠️ **`INDEX.md` lui-même ne se supprime jamais.** C'est le **point d'entrée permanent** — l'endroit unique où Josian regarde « qu'est-ce qui tourne en ce moment ? ». Quand plus rien n'est en cours, l'index reste, sa table est simplement **vide**. Ce sont les **lignes** qui se vident, pas le fichier.

## Conventions

- Un chantier = un fichier `chantier-<slug>.md`, ou un **dossier** `chantier-<slug>/` avec son propre `00-INDEX.md` s'il se subdivise en plusieurs fichiers de travail.
- Frontmatter obligatoire en tête (avant le titre) :
  ```yaml
  ---
  plan_de_travail: "<ce qui doit se vider — et à quelle condition c'est vide>"
  ---
  ```
  C'est le marqueur **machine** du sweep repo-wide : `grep -rl '^plan_de_travail:' --include='*.md' .`
- Un chantier porte un **suivi d'étape** visible d'un coup d'œil (cases à cocher + marqueur ➡️ sur l'étape courante), pour qu'une session fraîche sache où reprendre sans relire tout le fichier.
- Rédaction : bullets, phrases courtes, FR. Autoportant pour Josian — **jamais de locator nu** (le contenu mène, le pointeur suit entre parenthèses).
