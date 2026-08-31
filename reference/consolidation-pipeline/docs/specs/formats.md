# Formats — fragment + consolidé

## Fragment : `2-consolide/2.1-fragments/<src-slug>.md`

```markdown
---
source: <src-slug>
source_type: report | ressource
map_session: <short>
---

## theme:<clé>

- <fait distillé, 1-3 lignes> [src: <slug> §N]                              ← une ref (rapport)
- <fait distillé> [res: <slug>/<fichier>]                                    ← une ref (ressource) ; pour un visuel, citer le top-level `<slug>/page-NN.png` (curaté) ; `_all_pages/page-NN.png` seulement s'il n'existe pas top-level
- <fait couvert par plusieurs endroits d'une même source> [res: <slug>/slide-3.png] [res: <slug>/slide-4.png]   ← refs multiples

## theme:<autre-clé>
- ...
```

### Fragment projeté `arbitrages.md` (source `arbitrage`, pas mappé)

`2-consolide/2.1-fragments/arbitrages.md` est produit **déterministement** par `project_arbitrages.py` (pas par un agent map) : il plie les mini-ADR `1-sources/1.3-arbitrages/NNNN-<slug>.md`. Frontmatter `source: arbitrages`, `source_type: arbitrage`, `map_session: projecteur`. Une puce par décision, groupée par `theme:` : `- [candidat|settled] <énoncé> [arb: NNNN]` (l'énoncé = le corps du mini-ADR, aplati en une ligne). La cite `[arb: NNNN]` résout contre le mini-ADR lui-même ; le tag `[candidat]`/`[settled]` porte la **provenance** jusqu'à la fiche (cf. `prompts/reduce.md`). Le reduce le consomme **en tête de hiérarchie** (gagne tout conflit).

Règles :
- Une section `## theme:<clé>` par thème touché. Clés tirées de `THEMES.md` **uniquement**.
- Clé inconnue pertinente → la noter sous `## theme:_à-créer` + 1 ligne d'explication (signalée dans `note` au `done`, arbitrage Josian a posteriori). Ne jamais inventer de clé dans le vocabulaire.
- **Refs multiples** : une puce se termine par **une ou plusieurs** citations accolées (séparées par une espace). Quand un fait s'appuie sur plusieurs slides/§, **citer toutes** les localisations. `check.py` valide chacune mais ne peut pas deviner qu'il en manque une → consigne d'agent.
- On distille des **faits sourcés**, pas des drafts de slides. Pas d'analyse pédagogique.
- Source sans aucun thème : fragment avec frontmatter + `<!-- aucun thème -->`.

### Marqueur `## écarté:<slug>` (candidat `_à-créer` arbitré → rejeté)

Quand un candidat `## theme:_à-créer:<slug>` est arbitré (Josian) et **rejeté** mais qu'on garde sa matière sourcée comme trace, le marqueur quitte la worklist en devenant `## écarté:<slug>`. `<slug>` = l'ancien slug candidat (provenance, retrouvabilité `grep "## écarté"`). Ses puces sont des **faits gelés** : jamais réduites, jamais re-lintées (contenu d'archive). Créé **uniquement** par arbitrage manuel — les agents map ne le produisent jamais (eux parquent en `_à-créer`). Le rejet-avec-suppression reste un simple `delete` de la section.

Contraintes vérifiées par `check.py` : [check.md](check.md).

## Fichier consolidé : `2-consolide/2.2-content/<theme>.md`

Format canonique défini dans `2-consolide/CLAUDE.md` (« Format d'un fichier thématique »). Cible **100-300 lignes** (au-delà : `check.py` refuse → signal d'éclatement du thème en sous-clés). Sections : `Cœur d'industrie`, `Matérialisation CATS` (avec citations), `Tension industrie ↔ CATS`, `Points flous`, `Sources`.

Un thème dont le consolidé dépasserait ~300 lignes → éclater en sous-clés (ajout dans `THEMES.md` + re-inventory).
