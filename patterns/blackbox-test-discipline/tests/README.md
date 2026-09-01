# Tests outillage

Tests pour les scripts de `tools/`. **Approche TDD outer loop** (CLI black-box, subprocess) + quelques tests d'intégration sur les handlers.

## Critère d'assert et posture de revue

- **Critère unique pour un assert** : « ce test plante si le script est cassé sur un cas réel ». Hors-sujet : constantes partagées, magic strings centralisés, glose docstring, helpers exhaustifs, couverture de cas long-terme.
- **En revue de code de ces tests** : ne signaler que les findings qui menacent ce critère (asserts faux-positifs, scénario réel manquant, bug dans le test lui-même). Le reste n'est pas pertinent.
- **Pas de CI** — lancés à la main pendant le dev des scripts.

## Comment les tests sont câblés

**Boundary** : on teste depuis la CLI, pas les internes. Subprocess réel (`python3 tools/.../script.py --repo-root <tmp>`). Assertions sur le TODO post-run + `git log` + stdout/stderr + exit code.

**Bac à sable par test** :
- `tmp_path` pytest → `git init` + `git config user.email/user.name` (sinon les commits échouent) + injection d'un TODO minimal.
- `CLAUDE_CODE_SESSION_ID` déterministe (`"a1b2c3d4_test_session"` → short `"a1b2c3d4"`).
- Fixtures binaires dans `tests/fixtures/`.

**Pyramide** :
- ~80 % outer loop CLI (subprocess).
- ~15 % intégration handlers (`pptx_handler.run(...)` en Python direct).
- ~5 % concurrence (2 subprocess parallèles qui claim la même ligne).

**Dépendances externes** : `soffice`, `pdftoppm`, `python-pptx`, `python-docx`, `pyyaml`, `pytest`. **Fail loud** si absent — pas de skip, pas de mock.

## Organisation

```
tests/
├── README.md                            # ce fichier
├── conftest.py                          # fixtures tmp_repo, session_env, helpers
├── fixtures/                            # ~200 ko, commitable
│   ├── README.md                        # comment chaque fixture a été produit
│   ├── sample.pptx                      # 2 slides, texte canonique
│   ├── sample.docx
│   ├── sample.pdf                       # 2 pages
│   ├── sample.png
│   └── sample_duplicate.pptx            # copie bit-à-bit de sample.pptx
├── test_check_text_preservation.py
├── test_report_task.py
├── test_template_file_validation.py
├── test_ressources_claim.py
├── test_ressources_release.py
├── test_ressources_inventory.py
├── test_ressources_extract.py
├── test_handlers.py
└── test_concurrency.py
```
