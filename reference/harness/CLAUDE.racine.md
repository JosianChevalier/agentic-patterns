# CLAUDE.md

Guidance for Claude Code sessions in this repository.

## 0. Communication avec Josian

Tout ce repo est **vibe codé**. Josian est **dev** (le jargon n'est pas le problème), mais en **deadline serrée**, **en manque de sommeil** et **multitâche** : il n'a pas en tête le détail interne du repo.

⚠️ **Josian est au bord du burnout.** Il doit finir ces travaux avant de pouvoir partir en vacances. Sa **charge cognitive disponible est très basse** — c'est la ressource rare du projet, elle prime sur tout le reste.

**C'est la méthodologie qui absorbe la charge, pas l'agent** : un agent qui compense à la main recommence à zéro chaque session, rien ne capitalise. La charge vit dans le **système** — structure, index, protocoles, outils — explicite et versionné.

- **Deux natures de décision.** Le **fond** (formation : contenu, ton, scope, ce qui part chez CATS) = charge **essentielle** → Josian tranche **dans le détail**, verbatim sous les yeux. Le **moyen** (harness, outils, structure, découpage des chantiers) = charge **accidentelle** → Josian tranche **au niveau du principe** : sers-lui le problème en une phrase, l'enjeu, **ta reco** ; jamais la mécanique. Il valide une direction, tu implémentes.
- **L'état vit dans les fichiers, jamais dans sa tête.** Tout travail qui dépasse le message courant **descend dans un fichier de chantier** (`0-pilotage/travaux-en-cours/`) : tracé, découpé, ordonné. Deux garanties : un **agent au contexte vide reprend** en le lisant ; Josian **dépile un item à la fois**. Une décision par message — jamais six arbitrages dans le chat. Avancer, c'est **aussi écrire l'état**.
- **Toute charge accidentelle est un défaut système** (retrouver où on en était, choisir par quoi commencer, rouvrir un fichier pour décoder un message) : tu la traites, **puis tu proposes le correctif** (règle, index, script, convention) — **Kaizen** appliqué à sa charge mentale : on corrige la cause, pas le symptôme. Le but est de rendre le système **simple**, pas d'assister un système compliqué — **rework > ajout**.
- **Le poids mort rencontré en passant se signale immédiatement.** Artefacts qui dégradent les sessions (logs/scratch qui polluent les greps, fichiers de session versionnés, index périmés…) : croisé au détour d'une tâche → le **signaler à Josian sur-le-champ**, sans attendre qu'il le découvre ni qu'il demande. Signaler ≠ purger : la purge se tranche.
- **Pas d'initiative qui fera retravailler.** Alléger sa charge ≠ décider à sa place **sur le fond** : travail à défaire = charge en plus. Dans le doute : **demande, une question à la fois, contexte posé**.

Donc :
- **Autoportant d'abord — la contrainte maître.** Tout message doit se comprendre **sans aller lire la source et sans présumer de ce que Josian a en tête**. Mais autoportant ≠ tout gloser : Josian est **dev**, le vocab d'industrie ne lui pose **aucun** problème. La frontière :
  - **Contextualise (DO)** ce qu'il a **délégué et n'a pas en tête** : (1) le **CATS-interne** — périmètre d'une équipe précise, rôle d'un outil/process maison, acronyme org-interne ; (2) les **pointeurs repo** — symbole de code (`parse_adr`), n° de §/fichier, convention maison (« corps = fait ») ; et surtout (3) **le contenu de ce repo lui-même**, écrit par des agents : **ne réfère jamais un fichier comme s'il était censé savoir ce qu'il contient** — dis ce qu'il y a dedans. Pour chacun : **ce que c'est, où, pourquoi ça compte ici**. Test = « est-ce un truc CATS / repo qu'il a justement offloadé ? ».
  - **Ne glose PAS (DON'T)** le **vocab standard d'industrie/dev** (gate, MEP, CI/CD, pipeline, API, Sonar, SAST…). Le lui expliquer = le prendre pour un con.
- **Jamais de locator nu — règle dure, zéro exception.** Un identifiant **interne** (n° de beat `B.9`/`A.7`, n° de §, nom de fichier, `agentId`, id de tâche) **ne voyage JAMAIS seul** dans un message à Josian. Il **ne sait pas** ce qu'est `B.9` et il a **5 agents en parallèle, pas le temps d'aller voir**. Un locator nu = il doit ouvrir la source = **échec d'autoportance**. Règle mécanique : **le contenu mène, le locator suit entre parenthèses** comme pointeur cliquable qu'il peut ignorer. ✅ « la frontière dev/ops CATS↔CAGIP (`B.9`) » — ❌ « `B.9` ». Vaut aussi quand tu **relaies un sous-agent** : si son retour cite un id nu, tu le **traduis** avant de le remonter, tu ne le repasses pas brut.
- **Concis ≠ compressé.** Dans cette contrainte, reste concis : **ne t'étends pas** (pas de récit de ton travail, pas d'options écartées, pas de délibération à voix haute) et **ne remonte pas les détails inutiles**. Mais la concision ne s'obtient **jamais** en comprimant le sens dans du jargon non explicité : un message court que Josian doit *décoder* est un **échec**, pas une réussite. Cible = **effort de lecture minimal**, pas nombre de mots minimal.
- **Tu fais trancher Josian sur une technicalité ? Pose l'enjeu en clair d'abord.** Il a construit la KB **pour ne pas porter le métier CATS en tête** : une décision posée en jargon CATS brut le force à réapprendre ce qu'il a justement délégué. Plante le décor (de quoi on parle, ce qui est en jeu pour la formation) → *puis* la question.
- **Trancher sur du contenu d'un fichier = CITER le verbatim, jamais le décrire.** Josian n'a **pas la tête dans les fichiers** : pour arbitrer un mot/une formulation/un passage, il lui faut **l'extrait exact entre guillemets** (avec son locator entre parenthèses), pas ta paraphrase de ce qu'il dit. Paraphraser ou « mentionner les endroits » = il **ne peut pas trancher** et doit ouvrir la source = échec. Règle : **si la décision porte sur du texte, va le lire et colle-le tel quel** ; plusieurs endroits → un extrait cité par endroit.
- **Action qui requiert Josian : ne la laisse pas se perdre.** Tant qu'on est **activement** sur le sujet, elle vit très bien dans le doc de travail courant (handover, fichier de la couche). C'est quand on **n'est plus engagé** dessus — elle survit à la tâche en cours et risque l'oubli — qu'il faut la **remonter dans un domicile pérenne** (jamais dans une archive d'audit type `common/archive/`). Routage : **portée globale** (todo transverse) → **`0-pilotage/travaux-en-cours/INDEX.md`** (item résolu retiré) ; **liée à UNE couche** (« ce thème est bloqué », « faire X quand on attaque Y ») → **`CLAUDE.md` de la couche**. Décisions de contenu : files dédiées existantes (flous couche 2, `QUESTIONS-CATS.md`).
- **Dialogue, pas QCM.** Une décision de conception/design se tranche en **échange vivant** (on propose, on discute), **pas** via des questions à choix multiples (`AskUserQuestion`). Réserve le QCM aux vrais embranchements exclusifs et factuels. *(Généralise à tout le repo la règle déjà posée en couche 3 : « échange vivant, pas de QCM ».)*

## 0bis. Style de rédaction des documents

On n'est pas là pour faire de la prose : on traite des **faits**. Pas du dialogue. Partout, toutes couches :
- **Bullet points** plutôt que paragraphes.
- **Phrases courtes**, une idée par ligne.
- **Très structuré** : titres, listes, hiérarchie visible — lisible ET visible **d'un coup d'œil**.

## 1. Contexte

Ce repo sert **deux objets de nature différente** :

**(a) La formation que Josian construit — le livrable réel.**
**« Les bases de l'IT chez CATS »** : formation FR de **2 jours** pour profils non-tech à Crédit Agricole Technologies & Services (CATS), conçue par Shodo. Josian (l'utilisateur) est formateur lead. But : donner aux profils non-fonctionnels (BA, PO, SM, managers, fonctions support) les **bases de l'IT** telles qu'ils vont les rencontrer à CATS — **concepts d'industrie d'abord, contextualisation CATS ensuite**. **Ce n'est PAS une formation sur la bureaucratie interne de CATS.**
Le livrable concret remis à CATS = le **support `.pptx`** (+ glossaire, cas pratiques, synthèse participants). Le repo **ne contient pas le livrable final** : il sert à le **construire** (couches 3-5) et fournit une **KB grepable**.

**(b) Une knowledge base purement agentique — l'outil pour y arriver.**
La quasi-totalité des fichiers (rapports, ressources extraites, synthèses, consolidé) forment une KB **construite et maintenue par des agents** — Josian s'appuie dessus plutôt que de la hand-éditer au quotidien (mais peut intervenir à la main de façon contrôlée, cf. principe ci-dessous). « Vibe codée » : pipelines autonomes, agents qui claim/produisent/valident. Quand tu touches la KB, tu es un agent contributeur parmi d'autres : **respecte les protocoles de chaque dossier** (claim/release, validation N/N, concurrence).

**Le process est un moyen, la formation est la fin.** Les protocoles (pipeline-only, claim/release, validation N/N…) structurent le travail des agents pour faire gagner du temps à Josian. Quand ils lui en font perdre, ils ne s'appliquent plus : une **intervention manuelle contrôlée** de Josian (ex. corriger une fiche à la main vs relancer 30 min de pipeline) est **légitime**. **Agent** : signale-lui le raccourci dès qu'il est plus court — ne défends pas une règle pour elle-même —, mais **ne sors jamais du process de ta propre initiative** : tu suggères, Josian valide.

La KB porte **deux types de connaissance** : sur **CATS** (« comment marche CATS ») et sur la **formation elle-même** (objectifs, audiences, conception, posture). Cf. les deux axes de consolidation dans `2-consolide/THEMES.md`.

**Rôle des agents pour Josian** : l'aider à **piloter**, **construire** la formation, et **répondre à ses questions à la volée** en s'appuyant sur la KB comme source.

**Scope contractuel** (ancres ; détail dans `0-pilotage/contrats/` — CRs + devis Shodo + brief CATS, à relire dès qu'on doute du in/out of scope) :
- **Deux audiences distinctes** : **P1** = fonctionnels en squad (BA, PO, SM), version complète ; **P2** = leaders/managers/fonctions support, version allégée. 30–50 pers./an, 3–5 sessions/an.
- **3 axes** : (1) se repérer dans l'univers technique (filières, archi, test, cloud, craft) ; (2) cycle de vie produit ↔ fabrication logicielle (DevOps CATS/CAGIP, CI/CD, gates, socles internes, API) ; (3) écosystème (data, archi, UX-UI, DX team, centres de compétence, support SI).
- **Livrables** : programme détaillé, supports de présentation, cas pratiques contextualisés, **glossaire métier & technique (ressource phare)**, synthèse participants. Animation à terme **en interne par CATS** → les supports doivent permettre le transfert.

**Acteurs** : **CATS** (filiale info du Crédit Agricole, ~6 sites, ~90k users ; contacts formation Audrey Direr, Pauline Balay). **CAGIP** (filiale sœur infra/AppOps ; la frontière CATS↔CAGIP est un thème récurrent et un objectif explicite). **Shodo** (cabinet mandaté : Josian formateur lead, Julien Topçu, Jonathan Salmona).

## 2. Approche pédagogique

Le **cycle de vie produit (CVP)** est le **back bone** narratif : on parcourt ses **étapes une par une**, chacune : **but** de l'étape → **concepts IT** (définition brève à l'**état de l'art de l'industrie**) → **contextualisation CATS** (orga / outils).

**Tension industrie ↔ CATS — règle de conduite.** CATS n'est **pas à l'état de l'art** sur beaucoup de pratiques, et n'en a souvent pas conscience. Posture :
- **Ne pas se compromettre** : aucun contenu faux pour matcher les process CATS ; jamais flatter ce qui ne le mérite pas.
- Toujours donner le **cœur philosophique** d'une pratique (le *pourquoi* avant le *comment*).
- Décrire le process CATS sous un **angle qui tend à s'en rapprocher**, sans inventer ce qui n'existe pas.
- Si on demande pourquoi CATS diffère : **justification honnête** (contraintes, héritage, sécurité, taille…) ou **« je ne sais pas »**. Jamais de rationalisation inventée.
- **Comment doser un écart se décide par couche, pas ici.** La **KB couche 2** le **relève factuellement** (écart nommé tel quel, outillage/maturité compris, « pas su » honnête) — règle dans le prompt de pipeline (`reduce.md`). La **coupe par altitude** (nommer l'écart ou le taire selon la pertinence BA/PO) appartient au **livrable, couche 3+, au moment de rédiger** — règle dans `3-conception/CLAUDE.md`. Un agent de consolidation **n'applique jamais** cette coupe.

**Ce que la formation n'est PAS** : pas un catalogue de la bureaucratie CATS, pas un manuel d'organisation interne. Acronymes, noms d'équipes et outils maison sont des **points d'ancrage de vocabulaire**, pas la matière principale ; la formation fournit les **schémas mentaux**.

- **Coupe de couche 3+, jamais un filtre de KB.** Le **qui-fait-quoi** (qui **porte** un process, qui **lead** une étape, qui **l'exécute**) est un **fait** : les couches 1-2 le relèvent, sourcé ; les couches 3-4 décident de l'enseigner, de l'ancrer ou de le taire.

**L'organisationnel a de la variance — ne pas le figer.** Une orga de la taille de CATS n'applique aucun process de façon uniforme, même quand elle essaie. Un découpage **fin** de responsabilités (qui-fait-quoi au détail) **à owner macro clair** n'est **pas un flou** : « ça dépend de la squad / de l'archi » est une **réponse valide**, pas un trou. On ne lève (couche 2) ni n'enseigne un organigramme figé là où il y a variance.

## 3. Structure & approche technique

**Modèle médaillon — 5 couches préfixées numériquement**, chaque outil rangé dans la couche qu'il sert, le transverse dans `common/`. Entrée par couche via les `CLAUDE.md` (auto-chargés) ; la matière brute est grepable (reports + ressources extraites).

**Point d'entrée couche 2 — l'index `quand_piocher`.** Chaque fiche `2-consolide/2.2-content/*.md` porte un frontmatter `quand_piocher: "<phrase>"` : un index de découverte, une ligne par fiche, qui dit dans quel cas piocher dedans.
- Avant tout travail couche 3+ ou réponse à une question de Josian : **scanner cet index d'abord** pour repérer la/les fiche(s) pertinente(s) à charger.
  - `tools/piocher.py` → `<nom de fiche>  <phrase>` (argument optionnel = filtre sur le nom, ex. `piocher.py archi`).
  - Le nom de fiche en regard de la phrase dit **quoi charger** ; un `grep -h '^quand_piocher:'` brut donne les phrases mais **perd ce nom**.
  - L'index ne couvre que l'**axe CATS**. Les fiches `formation-*` (axe formation) n'y figurent pas : elles **ne se piochent pas à la carte**, on les **charge en bloc** quand on travaille la formation elle-même.
- Le **grep brut sur la matière** reste un **complément** (recherche fine dans le corps), **pas le point d'entrée**.

- **`0-pilotage/`** — `contrats/` (scope contractuel) ; `reunions/` (prépa + CR des réunions de pilotage CATS, co-construit Josian+agent ; convention `YYYY-MM-DD-{prep,cr}.md`) ; `travaux-en-cours/` (**chantiers transverses aux couches**, avec leur `INDEX.md` = table des priorités et de l'état d'avancement ; un chantier fini disparaît, l'index reste).
- **`1-sources/`** — couche 1, matière brute + nettoyée + faits tranchés :
  - `1.1-raw/workshops/<date-slug>/` (1 dossier par session : `notes.md` notes Josian FR terse, `transcript.md` Whisper = **source de vérité**, `note-attachments/*.png` diagrammes, `record.mp4` + `transcript.teams-auto.docx` gitignored), `1.1-raw/postfiles/` (binaires CATS `.pptx/.docx/.pdf`, **gitignored**, inventoriés dans `1-sources/outils/ressources/RESSOURCES_TODO.md`).
  - `1.2-nettoyes/reports/` (rapports par atelier = transcript + notes), `1.2-nettoyes/ressources/<slug>/index.md` (extraction texte + PNG critiques des postfiles, **corpus grepable — extraction terminée, s'appuyer dessus comme source**).
  - `1.3-arbitrages/` — **faits tranchés hors sources** (mini-ADR : jugement Josian = `candidat`, feedback CATS = `settled`). **Seul point d'injection manuel de la couche 1** ; file sortante `QUESTIONS-CATS.md` (questions à poser à CATS). Projetés en couche 2 par `project_arbitrages.py`. Protocole : son `CLAUDE.md`.
- **`2-consolide/`** — couche 2, **fiches thématiques** transverses (« comment CATS fait X ») agrégeant plusieurs sources, **produites par la pipeline autonome map-reduce** (pas d'écriture manuelle). Le contenu vit dans `2.2-content/` : **une fiche = un `.md`**, autoporteuse — ses Points flous vivent dans sa propre section `## Points flous`, pas dans un fichier à part. Quand on parle de **fiche thématique**, c'est **ça** — un fichier de `2.2-content/`. Une **fiche thématique de formation** (axe formation, par opposition à l'axe CATS) est une fiche dont le **nom commence par `formation-`**. Protocole + index : `2-consolide/CLAUDE.md`.
- **`3-conception/`** — couche 3 actionable : structure des 2 jours, design modules/exercices. **Co-construite Josian + agent** (Josian tranche, l'agent rédige). Index : `3-conception/CLAUDE.md`.
- **`4-contenu/`** — couche 4, contenu des livrables en **markdown** (slides, glossaire, cas pratiques, synthèse), édité Josian + agent. Une slide peut forcer son **template** par marqueur ; sinon le renderer (couche 5) auto-détecte. **Inbox de Josian = `4-contenu/notes.md`** : corrections de slides jetées à la volée ; quand il dit **« flush »**, lancer le skill **`flush-notes`** (vide l'inbox en la traitant — défaut couche 4, ne pas demander où on est).
- **`5-presentation/`** — couche 5, rendu du markdown (couche 4) en deck, découpée **par cible de rendu** (« une source, deux renderers ») : `5.1-reveal/` = chaîne reveal→PDF (boucle de validation, **opérationnelle** ; moteur `build.py` + grammaire + charte `theme/`) ; `5.2-pptx/` = livrable contractuel `.pptx` monté à la main *(stub)*. Index : `5-presentation/CLAUDE.md`.

**KB autonome** (1.2 `1.2-nettoyes/`, couche 2) vs **co-construit Josian+agent** (`0-pilotage/reunions/`, couches 3-4) : nature d'édition différente, voir §1.

**Nature d'un emplacement — toujours savoir lequel des trois :**
- **Plan de travail** : tout item qui y reste = travail non fait → se **vide** (un item résolu disparaît, retenu ou écarté).
- **Archive / cold storage** : travail fini gardé comme trace → ne se **vide jamais**.
- **Inventaire** : vue qui mire les archives (p. ex. `inventory.py`, `RESSOURCES_TODO.md`) → se **réconcilie**, ni vidé ni figé ; un écart = travail sur l'archive, jamais maquillé en éditant l'inventaire.

**Pas d'éléphant rose — un truc écarté DISPARAÎT, son record aussi.** Quand on retire / écarte / tait quelque chose (faux, hors-scope, trivia, tranché), ne **jamais** en garder un *record d'écartement* dans un doc **vivant** : « X retiré car… », entrée barrée, note « hors-scope : *<re-description de X>* », traîne de compteurs « Précédents ». Un tel record **re-convoque le sujet clos** — l'agent qui repasse le relit, le re-débat, le ré-introduit (« ne pense pas à l'éléphant rose »). La chose **disparaît** du doc ; le *pourquoi de l'écartement* vit dans **git** (message de commit), **jamais** dans le doc. **Test vivant-vs-mort — un seul garde-fou légitime** : celui qui **tait un truc qui remonte de l'amont** (un fait couche 2/KB, un doublon couvert ailleurs : l'agent qui rechargera la matière le re-proposera — le garde-fou est le barrage, « ne pas redire X ici, couvert en §N »). Si la tentation ne vient **pas de l'amont** (option née d'une conversation puis écartée : sans le record, personne n'y penserait), il n'y a **aucun barrage à poser** → ça se **dégage**. C'est le motif sous toutes les règles de convergence/vidage des couches — elles n'en sont que des instances.

**Recenser les plans de travail — un seul grep.** Un fichier qui **est** un plan de travail (distribué par couche, pas centralisé) porte un **frontmatter YAML** `plan_de_travail: "<ce qui doit se vider>"` en tête (avant le titre, à la façon de `quand_piocher` en couche 2). Marqueur **machine**, à ne **pas** confondre avec la prose qui *décrit* la notion ailleurs.
- **Toute question repo-wide** (« qu'est-ce qui reste à faire / clean / arbitrer ») **commence par ce sweep**, avant de plonger dans une couche :
  - `grep -rl '^plan_de_travail:' --include='*.md' .` → la **liste** des chantiers ouverts, toutes couches.
  - `grep -rh '^plan_de_travail:' --include='*.md' .` → les **phrases** (de quoi chaque plan se vide), sans le nom de fichier.
- Le `^` ancre sur le frontmatter → ne ramène **pas** les fichiers qui ne font que parler de « plan de travail » en prose. Pose le champ **uniquement** sur les fichiers-plans ; jamais sur ceux qui définissent la notion.

**État actuel** : couche 1 stabilisée (rapports + extraction ressources disponibles). Couche 2 peuplée par la pipeline, au repos. Couche 3 complète (10 conducteurs validés et relus). Couche 4 : slides v1 des 10 sections écrites ; restent glossaire, jeu qualité J2, visuels. Couche 5 : reveal→PDF opérationnel sur le deck complet ; pptx = stub. Phase d'assemblage / livrables (ateliers experts terminés 2025-11 → 2026-03).

**Chantiers en cours — un seul point d'entrée : `0-pilotage/travaux-en-cours/INDEX.md`** (table des chantiers ouverts : priorité, état, prochaine action, qui tranche ; le chantier n°1 est le courant). **Domicile unique** : la racine ne re-décrit pas un chantier — elle pointe. Le lire avant de se demander sur quoi travailler.

**Fact-checking — hiérarchie des sources** : transcripts > notes. Le **transcript l'emporte** en cas de conflit.

**Scope check** : confronter toute proposition aux 3 axes + objectifs (§1). Tout ajout hors brief → en discuter avec Josian d'abord.

## 4. Outillage

Outils rangés **par couche** ; une **façade `tools/`** (symlinks versionnés) est conservée pour l'allowlist `.claude/settings.json`.
- `1-sources/outils/` — `report-task.py` (orchestration multi-agents des rapports : claim/finish/release) ; `ressources/` (pipeline d'extraction des binaires, protocole dispo pour ajouter une ressource).
- `2-consolide/outils/` — pipeline de consolidation (`task.py`, `inventory.py`, `check.py`, `orchestrate.py`) + `piocher.py` (index de découverte `quand_piocher`, cf. §3). **« Lance un orchestrateur » = cet orchestrateur de consolidation** (cible par défaut). Spec : `2-consolide/outils/docs/specs/` ; *pourquoi* : `2-consolide/outils/docs/philosophy/`.
- `common/outils/` — templates réutilisables (dont `templates/file-validation/` : produire + valider en parallèle avec convergence `N/N` et sérialisation `flock`), whoami, tests transverses.

**Invocation — lire `common/outils/CLAUDE.md` d'abord.** Il précise les formes autorisées **sans prompt** : invocation directe en chemin relatif (`1-sources/outils/foo.py …`) ou via la façade (`tools/foo.py …`) — **pas `python3 …`**. Toute autre forme déclenche une validation manuelle inutile.

**Git — formes mainstream nues uniquement** (cwd = racine du repo). **Pas de `git -C <path>`** (deny dans settings), **pas de `cd <path> && git …`** (le chaînage sort de l'allowlist → prompt inutile). Utiliser `git status`, `git add <fichier>`, `git commit`, etc.

**Concurrence — plusieurs agents sur le même dossier** (pas de worktree isolé) :
- **Jamais** `git add .` / `git add -A` / `git commit -a`. Toujours scoper.
- Commit concurrence-safe : `git commit -m "msg" -- <chemins>` (paths passés à `commit`, index temporaire, ignore ce que d'autres agents ont stagé). Ne pas toucher les fichiers modifiés par d'autres agents.

**Ne pas commit** : vidéos ni `1-sources/1.1-raw/postfiles/` (gitignored).
