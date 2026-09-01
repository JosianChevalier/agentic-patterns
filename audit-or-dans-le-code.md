---
plan_de_travail: "candidats de l'audit « or dans le code » — chaque item se vide par arbitrage Josian (retenu → catalogue `patterns/`, sinon disparaît)"
---

# Audit « or dans le code » — candidats pour le catalogue `patterns/`

Lecture ligne à ligne de tous les `.py` + hook + tests de `reference/` (4 lecteurs parallèles, dédupliqué). Verdict proposé par item : **→ pattern `<slug>`** (nouveau pattern ou enrichit ce pattern) ou **écarter**. Josian tranche ; item tranché = retiré d'ici.

Légende : chaque item = trick → mécanique → pourquoi c'est malin → pointeur.

---

## A. Candidats forts — nouvelles entrées proposées


## B. Candidats moyens — enrichissements ponctuels

- **Région générée d'un pipeline = API d'entrée de l'autre** — la consolidation parse le bloc `INVENTORY:BEGIN/END` maintenu par l'inventory d'extraction, filtré `Validate == 2/2`. (`consolidation-pipeline/inventory.py:76-100`) **→ pattern `generated-regions`.**
- **Tests : les 4 lignes non évidentes** — `commit.gpgsign false` dans la fixture (sinon hang pinentry sur machine à signing global) ; `session_env` monkeypatch l'env var et **retourne le short** à grepper ; fixture `git_log` (sujets de commit) comme oracle des transitions ; course réelle non synchronisée + assertion `sorted([rc1,rc2]) == [0, ≠0]` + les **deux** stderr dans le message d'échec. (`patterns/blackbox-test-discipline/tests/conftest.py:37-55,47,143-172` ; `patterns/blackbox-test-discipline/tests/test_concurrency.py:42-66`) **→ pattern `blackbox-test-discipline`.**
- **watch.py : relecture complète + marqueur en dernière ligne** — pas de tail -f ni seek : relit tout, émet `lines[emitted:]` (immune aux truncate) ; exit seulement si le marqueur est la **dernière** ligne ; méta sur stderr, stdout = flux pur. Reprise d'un run : append avec séparateur, jamais d'écrasement ; le marqueur terminal tombe « quoi qu'il arrive » (RUN.md best-effort). (`consolidation-pipeline/watch.py:52-92` ; `orchestrate.py:871-891,1131-1199`) **→ pattern `banner-as-monitor`.**
- **`re.sub` avec lambda en replacement** — le contenu injecté dans une région générée passe par `lambda _m: new_inv` : un `\g<…>` dans le tableau généré ne sera jamais interprété par le moteur regex. Bug classique et silencieux. (`extraction-pipeline/inventory.py:195-204`) **→ pattern `generated-regions`.**

## C. Proposés à écarter (trivia / trop locaux)

- Strip de l'ancre avant la décision chemin-vs-slug (`check.py:84-88`) ; lint appelé in-process via `main(argv)` (`task.py:498`) ; format de contexte à clé nue (`task.py:330-331`) ; `--no-commit` sur parser parent (`task.py:907-910`) ; `dict.fromkeys` dédup ordonnée (`task.py:890`) ; garde module-not-script (`_store.py:266-267`) ; validation d'en-tête CSV (`_store.py:167-168`) ; set pré-calculé partagé pour le gating (`task.py:72-85`) ; `find_root` par `.exists()` compatible worktrees (`_store.py:24-35`) ; clé `_content` transitoire (`inventory.py:149`) ; sentinelle `map_session: projecteur` (`project_arbitrages.py:40`) ; sanitization d'ids + compteur de spawn thread-safe (`orchestrate.py:790-813`) ; dry-run borné par la garde anti-stall elle-même (`orchestrate.py:1266-1269`) ; `signalé [^|]+` — validation dictée par le format de destination (`release.py:69-75`) ; clé de ligne = regex sur nom d'artefact (`report-task.py:62-67`) ; `--stagger 2.0` entre spawns (`extraction-pipeline/orchestrate.py:840`) ; détection de séparateur markdown par `set(...) <= {"-"}` (`inventory.py:86`) ; `sys.executable` + chemin absolu pour le script frère (`extraction-pipeline/orchestrate.py:656-672`) ; callback de log threadé dans les gardes (`orchestrate.py:145-151`) ; fixture `run_script` (`sys.executable`/`check=False`/`cwd=repo`, `patterns/blackbox-test-discipline/tests/conftest.py:143-160`).
