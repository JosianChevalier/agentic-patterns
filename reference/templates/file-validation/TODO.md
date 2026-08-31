# Exemple — TODO.md

Tableau d'état partagé pour la validation multi-agents. À copier/adapter dans votre projet.

## Convention

- Un fichier par ligne, sous `OUTPUT_<slug>.md` (le slug est la clé reconnue par `task.py`).
- État : `todo` → `en cours` → `fait`.
- Verrou : `🔒` occupé, `—` libre.
- Validation : compteur `X/N` ; `N/N ✓` quand convergé (par défaut N=2).
- Toutes les transitions passent par `task.py next | finish | release` (et `claim <slug>` pour un claim ciblé). Pas d'édition manuelle dans le flux normal — seulement pour réparer un verrou orphelin.

## Ordre de priorité — appliqué par `task.py next`

L'agent ne choisit pas : il appelle `task.py next`, qui picke pour lui dans cet ordre (et saute les lignes qu'il a rédigées ou déjà validées) :

1. Ligne `fait` avec `Validation` < `N/N` et `Verrou` libre, la plus proche de `N/N` → passe de validation.
2. Ligne `todo` avec `Verrou` libre → rédaction.

## Tâches

| État | Item | Date | Sources | Fichier | Verrou | Validation |
|---|---|---|---|---|---|---|
| fait | Premier livrable exemple | 2025-01-15 | `sources/a.txt` | `OUTPUT_exemple-un.md` | — | 2/2 ✓ |
| fait | Deuxième livrable | 2025-01-16 | `sources/b.txt` | `OUTPUT_exemple-deux.md` | — | 1/2 |
| en cours | Troisième livrable | 2025-01-17 | `sources/c.txt` | `OUTPUT_exemple-trois.md` | 🔒 | — |
| todo | Quatrième livrable | 2025-01-18 | `sources/d.txt` | `OUTPUT_exemple-quatre.md` | — | — |
