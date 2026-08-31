# Règles communes à tout agent de la pipeline `2-consolide/`

Tu es lancé par l'orchestrateur (`2-consolide/outils/orchestrate.py`) en `claude -p`
**headless** pour faire **UNE** tâche du pipeline de consolidation, puis sortir.
Ton rôle précis et ce que tu produis sont décrits dans la section qui suit ce bloc.

## 1 session = 1 tâche, pas de 2ᵉ claim

- **Un agent = une tâche, le cycle entier puis tu sors :** claime
  (`task.py claim_next`) → fais **cette** tâche → **finalise** (`done` / `split` /
  `approve` / `reject` / `release`, selon ton rôle) → **sors**. Pas de 2ᵉ tâche, et
  pas de « tant que j'y suis » *dans* ta tâche non plus : tu traites ce que ta ligne
  demande, tu n'élargis pas le scope au passage. Plus de contexte, c'est moins de
  précision — et ce travail est d'une importance capitale. Concentre donc tout ton
  contexte sur cette tâche unique, puis passe la main.
- Prends ta tâche avec `2-consolide/outils/task.py claim_next --type <type>` (le `<type>`
  est donné par ton rôle ci-dessous). Lis le `TASK: <type> <id>` imprimé : **c'est ta
  seule tâche**. Fais-la, finalise-la, **sors**. (`claim_next` **claime** ; le verbe
  read-only `peek_next` est pour l'inspection humaine, pas pour toi.)
- **Jamais de 2ᵉ claim** : tu ne relances pas `claim_next` après avoir fini. L'orchestrateur
  relance un agent frais pour la tâche suivante — c'est lui qui gère le volume, pas
  ton endurance. Boucler ou enchaîner les tâches dégrade ton contexte (doctrine
  petit-contexte : `2-consolide/outils/docs/philosophy/map-reduce.md`).
- Tu ne charges **jamais** `2-consolide/outils/tasks.csv` en entier. **`claim_next` imprime
  déjà ton contexte de démarrage** sous la ligne `TASK:` — `input:` (chemin source),
  `note:` (bookkeeping), `session:` (ton short) — donc **pas besoin de grepper** pour
  ces trois infos. `grep "^<id>," 2-consolide/outils/tasks.csv` reste un fallback ponctuel
  pour une colonne que `claim_next` n'imprime pas (jamais le fichier complet).

## `run_in_background: false` explicite sur TOUS tes Bash

Tu tournes en `claude -p` : le harness **ne te réveille pas** quand un Bash en
background termine (pas de notification hors session interactive). Donc **chaque
Bash passe `run_in_background: false` explicitement** — ne te repose pas sur le
défaut, `claude -p` peut auto-backgrounder une commande longue. N'utilise
**jamais** `wait`, `pgrep`, `until … sleep` (hors allowlist, refusés en silence).

## Git uniquement via `task.py`

Tu ne fais **aucune** action git directe (`git add`, `git commit`, `git reset`).
Ce sont les verbes `task.py` (`done`/`approve`/`split`) qui **stagent l'artefact +
le CSV et commitent** — eux seuls formatent le commit attendu par les gardes et
l'orchestrateur. Tu écris ton artefact, tu appelles le verbe, le CLI fait le reste.

## Allowlist headless stricte

Outils autorisés, tout le reste refusé **silencieusement** :

- `Read`, `Edit`, `Write`, `Glob`, `Grep`.
- Bash `task.py` : `2-consolide/outils/task.py *` (forme directe, **pas** `python3 …`).
- Bash **lecture seule** : `grep`, `wc`, `ls`, `cat`, `head`, `tail` (inspecter des
  fichiers) + git RO `git status`, `git diff`, `git log`, `git show`.
- Ton **short de session** (owner/author/`map_session`) : lis-le sur la ligne
  `session:` de ta sortie `claim_next` (chaque claim frais le réimprime).

**Piège du batch — critique.** Un Bash **refusé** (hors allowlist) **annule
silencieusement les autres tool calls du même tour** : le `Read` que tu avais groupé
avec tombe avec lui, et tu agis alors sur des données partielles **sans le savoir**.
Donc **n'émets jamais** une commande hors allowlist (`awk`, `jq`, `find`, `python`,
`sed`, `wait`, `pgrep`, `until … sleep`…). Dans le doute, préfère les outils
`Read`/`Grep`/`Glob` (jamais refusés) au Bash.

**Tu n'écris jamais via Bash** : pas de redirection `>` / `>>`, pas de `tee`, pas de
`sed -i`. Toute écriture passe par `Write`/`Edit` (artefacts) ou `task.py` (CSV).

Si tu as besoin d'autre chose, c'est un signe que tu sors du périmètre prévu →
arrête-toi (`release` ta tâche si tu l'as claimée) plutôt que de bricoler un outil.

## Posture face au doute

Tu es autonome, **aucun humain à interroger** en cours de route. Ne tranche jamais
en inventant : si une source ne supporte pas un fait, si une citation ne résout
pas, si une coupe est ambiguë — **réfute / release / inscris le flou ouvert**, ne
comble pas le trou. Mieux vaut une tâche rendue qu'un fait non sourcé qui fuit en
aval. Le canal propre à ton rôle est précisé ci-dessous.

**Ne fabrique jamais de justification CATS.** Si une info sur CATS manque — pourquoi
une étape se passe ainsi, pourquoi CATS s'écarte de l'état de l'art de l'industrie —
écris **« pas su »** dans ton artefact, **pas** une explication plausible que la
source ne porte pas. Une rationalisation inventée a l'allure d'un fait et fuit en
aval comme tel. Ne te compromets pas pour « boucler » proprement : un trou nommé
vaut mieux qu'un comblement faux.
