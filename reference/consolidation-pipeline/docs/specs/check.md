# `check.py` — linter de sourçage déterministe

Gate appelé par `done <id>` sur l'artefact. **Échec → `done` refusé**, la tâche reste `claimed`. (Un reduce qui passe `check.py` part en `to_validate`, pas en `done` — cf. [cli.md](cli.md).)

**Ce qu'il garantit** : tout fait pointe vers une source réelle (anti-extrapolation). **Pas** que le fait soit fidèle à cette source — la fidélité est portée au reduce par le gate 2/2 ([validate.md](validate.md)), pas ici. `check.py` est **inchangé** par l'ajout du gate de fidélité. → *pourquoi cette séparation* : `philosophy/gate-fidelite.md`.

## Sur un fragment

- frontmatter valide (`source`, `source_type` ∈ {`report`, `ressource`, `arbitrage`}, `map_session`). `arbitrage` = fragment **projeté** (`project_arbitrages.py`), pas mappé ;
- **toute puce** sous une section `## theme:` se termine par une **suite d'une ou plusieurs** citations `[src: …]` / `[res: …]` / `[arb: …]` accolées — regex : `(\s*\[(src|res|arb):[^\]]+\])+\s*$`. Une puce sans citation = échec (anti-extrapolation) ;
- **chaque** citation de la suite est **résolvable** (pas seulement la dernière) : extraire *tous* les tokens trailing, valider chacun — slug `src` ∈ rapports connus / chemin `res` existe sous `1-sources/1.2-nettoyes/ressources/` / `arb:NNNN` → mini-ADR `1-sources/1.3-arbitrages/NNNN-*.md` existe. Une ref cassée parmi plusieurs = échec. Le test chemin-vs-slug porte sur le **localisateur** (avant l'ancre `§`/`#`), donc un repère peut contenir un `/` libre (`[src:tdd-atdd §CI/CD/CT]`) sans être pris pour un chemin ;
- clés de thème ∈ `THEMES.md` (ou `_à-créer`).
- une section `## écarté:<slug>` (candidat arbitré-rejeté, cf. [formats.md](formats.md)) est **tolérée** : elle compte comme section présente, mais ses puces sont des faits gelés et **ne sont pas lintées**.

## Sur un consolidé

- **frontmatter « quand_piocher »** : bloc `---` … `---` en tête de fiche (avant le titre) portant un champ `quand_piocher` non vide — en-tête « Quand piocher ici », index de découverte greppable/préchargeable, **exigé sur les deux axes** (présence seule, contenu non contrôlé ; cf. `reduce.md` § Règles communes) ;
- titre `# <clé>` (1re ligne non vide **du corps**, après le frontmatter) ;
- sections présentes au format `2-consolide/CLAUDE.md` (cf. [formats.md](formats.md)) ;
- la section « Matérialisation CATS » porte des citations ;
- ≤ ~300 lignes (au-delà : refus → signal d'éclatement du thème).

### Exception : fiches de l'axe formation (`formation-*`)

Une fiche dont le nom commence par `formation-` (cf. CLAUDE.md §3) ne décrit pas « comment CATS fait X » : la **structure consolidé** (5 sections industrie↔CATS + citation CATS) **ne s'applique pas** et n'est **pas vérifiée**. Restent contrôlés : **frontmatter `quand_piocher`** (les deux axes), titre `# <clé>`, **refs cassées** (toute citation présente doit résoudre), taille ≤ ~300 lignes.
