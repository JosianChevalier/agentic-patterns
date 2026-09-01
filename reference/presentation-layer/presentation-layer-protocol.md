# Présentation — le livrable `.pptx` (+ prototype reveal.js)

**Couche 5 « présentation »** du modèle médaillon (cf. CLAUDE.md racine). Rend le contenu markdown de la **couche 4** (`4-contenu/`) en deck présentable.

## ⚠️ À qui s'adresse le PDF qu'on produit *maintenant*

Le PDF rendu en ce moment **ne part pas aux participants** : il part aux **commanditaires** — les gens de CATS qui ont commandé la formation (contacts Audrey Direr, Pauline Balay) — **pour qu'ils valident le contenu**. C'est **eux** le lecteur courant, pas l'apprenant final. Cadre tout ce qui se rend ici comme une **surface de validation pour le commanditaire** (le livrable `.pptx` pour les participants vient ensuite). *(L'audience pédagogique finale P1/P2 reste celle du fond — cf. CLAUDE.md racine §1.)*

## Principe : une source, deux renderers

Le markdown de couche 4 est la **source unique**. Couche 5 = **deux renderers** qui le consomment, jamais l'inverse.

- **reveal.js — boucle de validation.** md → HTML déterministe, **zéro réalignement manuel**. C'est ici qu'on itère le contenu vite. **Déployé pour que CATS voie et valide dessus.** → vit court (jetable après bascule pptx) **mais doit rester fidèle au template** tant qu'il sert de surface de validation.
- **pptx — livrable contractuel.** Le deck remis à CATS, via les templates de slide. Le **réalignement manuel** (mise en forme fine) ne se paie **qu'une fois, à la validation**.

**But** : raccourcir 4→5. Le gain vient de reveal (feedback instantané, pas de mise en forme) ; le coût pptx est différé et payé une seule fois.

## Contrainte maîtresse : congruence des layouts

CATS valide sur reveal → si le pptx final rend différemment, on livre une forme non validée. Donc **les layouts reveal mirrorent les layouts du template pptx**. Bonne nouvelle : le template est minimal (cf. ci-dessous), le mirroring est peu coûteux.

## Contrat d'interface 4↔5 : la grammaire markdown

Une **grammaire markdown unique** nomme le **type** de chaque slide et fixe le **vocabulaire du corps** (bullets, encart définition, placeholder visuel 🎨, exercice 🎲, tableau, lignes-manifeste).

**État : grammaire dérivée des `*.slides.md` existants + implémentée — documentée dans `5.1-reveal/GRAMMAIRE.md`.** Validée sur l'output (le PDF rendu), pas dans l'abstrait. 3 points restent à confirmer par Josian (cf. fin de `GRAMMAIRE.md`).

## Structure : un renderer par cible (`5.1` / `5.2`)

Le découpage suit le principe **« une source, deux renderers »** ci-dessus — par **cible de rendu**, pas par moteur/charte.

- **`5.1-reveal/`** — la **chaîne reveal** (valider + itérer). Tout y vit : moteur (`build.py`, `vendor/reveal/`, decktape via `package.json`/`node_modules/`), contrat de parsing (`GRAMMAIRE.md`), **charte** (`theme/` : `cats.css`, `logo-cats.png`, `CHARTE.md`), sortie buildée (`build/`, gitignoré).
- **`5.2-pptx/`** — le **deck `.pptx`** à la main, livrable contractuel. **Stub** (cf. `5.2-pptx/CLAUDE.md`).

Pas de `5.0` : ce méta-fichier tient lieu de couche d'entrée.

## Charte visuelle

Décisions cosmétiques (template CATS mirroré, couleurs, layouts, mobilier) → **`5.1-reveal/theme/CHARTE.md`**.

## Chaîne reveal → PDF (boucle de validation) — opérationnelle

Outils dans `5.1-reveal/` (Python stdlib + reveal vendoré ; PDF = **decktape**, Chromium **épinglé** par Puppeteer — `npm install` dans `5.1-reveal/`, `node_modules/` gitignoré). **Une commande rend HTML + PDF** — `build.py` enchaîne lui-même l'export (`export_pdf()`), plus d'étape manuelle :
```
tools/build.py <slug> [--date DD/MM/YYYY]   # une section -> build/<slug>.html + .pdf
tools/build-all.py [--date DD/MM/YYYY]      # deck complet -> build/deck.html + .pdf
```
`build/` est gitignoré (régénérable). Sous le capot : decktape capture les slides **une à une** via CDP sur le Chromium épinglé (`--size 1280x720` → MediaBox 960×540 pt paysage) — pas de course « print avant que reveal soit prêt », pas de régression aux màj du Chrome système. decktape absent/échec : HTML écrit quand même, PDF périmé + `!` signalé (non bloquant).

## Chaîne de production (pptx — différé)

Voir `5.2-pptx/CLAUDE.md`. En deux temps : conversion script (md couche 4 → deck via templates) puis **réalignement manuel**, payé une seule fois à la bascule.

## À faire (couche 5)

- [x] Grammaire markdown — dérivée + implémentée (`5.1-reveal/GRAMMAIRE.md`). *3 points à confirmer Josian.*
- [x] Thème reveal.js fidèle au template (`5.1-reveal/theme/cats.css` — 2 couleurs, logo, pied de page).
- [x] Renderer reveal + export PDF (decktape + Chromium épinglé). **Prouvé sur le deck complet (311 slides).**
- [ ] Schémas 🎨 — placeholders pour l'instant ; dessin = chantier dédié. **`build.py` rend le `🎨` nu en cadre d'attente explicite** (icône 🖼 + « Image à venir », pour qu'on lise que c'est un placeholder, pas un visuel manquant) ; la spec vit dans le sidecar `.visuels.md`, jamais à l'écran (forme legacy `*🎨 spec*` encore tolérée — spec résiduelle affichée sous le cadre).
- [ ] Script de conversion pptx (livrable contractuel, `5.2-pptx/`).
- [ ] Convention de versionnement du `.pptx` final (lourd/propriétaire — non versionné ici par défaut).
