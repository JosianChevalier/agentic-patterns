# Stale / re-reduce — invalidation après ajout de fragments

> Statut : **spec proposée** (option 3). Implémente l'invalidation différée de
> `specs/inventory.md` § Idempotence et `specs/orchestrateur.md` § Vues optionnelles.

## Problème

Le reduce **pull** : à l'exécution il fait `grep -l "## theme:<clé>"` sur **tous** les
fragments et **reconstruit le consolidé de zéro** (cf. `outils/prompts/reduce.md`). Donc
l'additivité est supportée **par construction** : un reduce qui re-tourne absorbe les
nouveaux fragments.

Ce qui manque : **l'invalidation**. Un reduce `done` est figé ; `inventory.py`
(idempotent) ne le rouvre pas, l'orchestrateur ne ramasse que les `todo`. Quand un map
postérieur ajoute des `## theme:<clé>` (ex. les 6 rapports mappés après les reduces CATS),
le consolidé reste périmé. Aucun verbe ne le réveille.

## Modèle — sémantique Make

| Make | Pipeline |
|---|---|
| target | `reduce:<clé>` |
| prerequisites | fragments portant `## theme:<clé>` |
| output | `2-consolide/<clé>.md` |
| target stale = prereq plus récent | `max(map.done_at touchant <clé>) > reduce.done_at` |
| rebuild | re-run du reduce `todo` (re-grep + ré-écrit, déjà le comportement) |

On **ne change pas** le flux pull. On ajoute le **prédicat stale** + le **re-trigger**.

## Pourquoi rebuild-from-scratch et pas incrémental

Tentation : « réutiliser l'ancien consolidé, ne l'éditer que pour absorber les nouveaux
fragments » (gain token). Rejeté pour trois raisons :

1. **Projection pure.** Le consolidé est une **fonction pure des fragments courants** : même
   entrée → même sortie. L'incrémental le rend *path-dependent* (dépend de la séquence
   d'édits) → dérive, cruft, vieilles formulations qui traînent. C'est la propreté d'archive
   du modèle (CLAUDE.md §3, inventaire = projection, jamais maquillé).
2. **Le gain réel est sur la validation, pas le reduce — et il est dur à capter.** Le reduce
   lit des sections déjà distillées (léger). Le poste lourd = la **validation 2/2 par shard**
   (résout chaque citation contre la source brute). Ne re-valider que les buckets touchés
   exigerait de prouver que le non-touché reste fidèle → scoping fragile, risque de correctness.
3. **Sémantiquement faux pour les rapports.** Les rapports sont **transcripts+notes = source de
   vérité** (CLAUDE.md, transcripts > notes > ressources). Leur rôle n'est pas d'**ajouter**
   mais de **réviser** ce que les consolidés tiennent depuis les postfiles moins fiables. Le
   prompt reduce applique déjà cette hiérarchie au rebuild (le transcript **écrase** le fait
   ressource en conflit). Un « réutilise l'ancien + ajoute le neuf » **supprimerait exactement
   les corrections voulues**. Le rebuild donne la révision gratuitement.

Coût assumé : re-reduce + re-validate est lourd (validation dominante, ~plusieurs M tokens pour
tout l'axe CATS) mais **one-shot**, **scopable** (reopen sélectif via le scan) et **cappable**
(`--max-agents`). L'incrémental ne se justifierait que si le re-reduce devenait **fréquent** —
et alors via **incrémental + rebuild complet périodique** (compaction de log), pas tout-incrémental.

## Prérequis de schéma — `done_at` en timestamp

`done_at`/`claimed_at` sont **date seule** (`2026-06-08`) → deux tâches du même jour ne
sont pas ordonnables, le prédicat `>` devient ambigu. Passer en **ISO 8601 secondes**
(`2026-06-08T14:03:11`). Changement isolé au write path (`_store.py`) ; comparaison
lexicographique inchangée, les anciennes valeurs date-seule restent comparables.

## 1. Scan stale (read-only)

Commande `task.py stale` (ou sous-commande `inventory.py`). **Aucune mutation.**

```
theme_latest = {}                       # clé -> max done_at sur les maps done
pour chaque map m (status=done) :
    pour chaque "## theme:<clé>" trouvé dans file(m.output) :
        theme_latest[clé] = max(theme_latest[clé], m.done_at)

stale = [ r.id pour r in reduces si r.status == "done"
                                   and theme_latest.get(r.clé, "") > r.done_at ]
```

Sortie : liste des `reduce:<clé>` périmés (option `--why` : + les fragments fautifs).
Un seul passage de grep sur `fragments/`. Sert à **décider** ce qu'on rouvre — Josian
reste dans la boucle.

## 2. `task.py reopen <reduce:clé>|<map:src> [...]` (mutation, flock, 1 commit)

- **Garde** : `status == done` requis.
  - `split` → **refus** (validation en vol ; attendre le rollup).
  - `todo` → no-op (reconstruira déjà).
- **Actions atomiques** (même flock) :
  1. **Supprime** les enfants `validate:<clé>#*` du reduce (ils ont validé l'ancien
     contenu ; les buckets de sources peuvent changer au prochain `done`).
  2. reduce : `done → todo`, vide `done_at` + `owner`, `note=stale`.
- **Variante** `reopen --stale` : scan (§1) + reopen de tous les périmés en un passage.

**Un `map` se rouvre aussi**, mêmes gardes (ni enfants ni statut `split` côté map). C'est le
chemin du **re-map délibéré** — typiquement re-router une source vers une **clé de thème neuve**
ajoutée après coup à `THEMES.md`. L'invalidation en aval est **automatique** : le re-`done` du map
pose un `done_at` neuf → tous les reduces de ses thèmes (l'ancienne clé comme la neuve) tombent
périmés au scan §1 → `reopen --stale` les ramasse. Aucun chaînage explicite à écrire.

Pas de chemin de re-run spécifique : le reduce redevient un `todo` ordinaire →
orchestrateur le ramasse → agent re-grep **tous** les fragments (rapports inclus) →
`done` → re-shard de **frais** `validate:<clé>#1..n` → gate 2/2. Inchangé.

## 3. Orchestrateur / inventory — aucun changement

Reopened = `todo` standard. `inventory.py` merge toujours par `id`, ne touche ni le
`todo` reopené ni les `done` ; idempotence préservée.

## Décision tranchée — enfants `validate` obsolètes (supprimés)

Au re-`done`, le re-shard append `validate:<clé>#1..n`. Si les anciens `#1..n` existent
encore, collision d'`id`. **Tranché (Josian, 2026-06-09) : supprimer** les anciens enfants
au `reopen` — lignes obsolètes, CSV reste borné. Introduit la **seule primitive neuve** :
suppression de ligne sous flock. Implémenté dans `task.py reopen` (`_reopen_one`). Aucune
info réelle perdue : le contenu et l'historique de validation vivent dans git.

*(Alternative écartée : passer les enfants `abandon` et numéroter le re-shard à la suite —
pas de suppression, mais CSV qui croît et numérotation à rendre consciente de l'existant.)*

## Hors scope

- **Détection automatique d'une source *modifiée*** : `inventory.py` reste idempotent, il ne
  re-`todo` pas un map `done` (pas de hash de source). Le re-map est **délibéré** — `reopen
  map:<src>`, cf. §2 (`specs/inventory.md` § Idempotence).
- `corrige` édite le **consolidé** (couche 2), jamais un fragment → ne déclenche **jamais**
  de faux stale. Seul un map `done` bouge un fragment.

## Séquence opérationnelle (migration one-shot)

1. **Scan** (`task.py stale`) → liste des reduces périmés.
2. **Reopen** sélectif (les thèmes à fort apport des rapports), ou `reopen --stale` + cap.
3. **Run orchestrateur** → re-reduce + re-validate 2/2 des thèmes rouverts.
4. **⟵ ÉTAPE — faire le tour de TOUS les Points flous et les arbitrer.** Le re-reduce
   régénère les `## Points flous` des consolidés.
   Avant de clore : Josian tranche **chacun** → un mini-ADR `1-sources/1.3-arbitrages/NNNN-<slug>.md`
   (`candidat` = jugement à confirmer / `settled` = feedback CATS). Cf. `1-sources/1.3-arbitrages/CLAUDE.md`.
   **Pourquoi ici, pas un cul-de-sac** : `1-sources/1.3-arbitrages/` est **source couche 1 (« 1.3 »)**
   (Migration B **livrée**, `a296bc9`) — un arbitrage *est* déjà un fragment, donc **projeté** (pas mappé,
   via `project_arbitrages.py`) puis **réduit en tête de hiérarchie** (gagne tout conflit). Les arbitrages
   **redescendent** en 1→2→3 et sont **consommés par la pipeline** au cycle suivant : re-reduce surface les
   flous → arbitrage → re-entre comme source → re-reduce l'absorbe. La boucle ne se ferme que si l'étape
   est faite. (Reste à coder pour cette spec : le **scan stale** lui-même.)
5. **Re-scan** → stale vide. Migration close.

## Critères d'acceptation

- Scan à froid sur l'état actuel (rapports 06-08, reduces ≤ 06-06) : liste tous les reduces
  CATS dont un rapport touche le thème.
- `reopen reduce:architecture` : enfants `validate:architecture#*` retirés, ligne reduce
  `done → todo`, `done_at` vidé, `note=stale` ; re-run produit un nouveau consolidé + 2/2.
- `reopen` sur un reduce `split` : refusé.
- Scan stable après un run complet (plus aucun stale).
