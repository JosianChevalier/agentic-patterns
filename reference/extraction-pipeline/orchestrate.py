#!/usr/bin/env python3
"""Orchestre des sous-agents `claude -p` en parallèle pour drainer la queue
d'extraction `ressources/`.

Chaque sous-agent tourne en headless, picke UNE tâche selon `RESSOURCES_PROTOCOL.md`,
la finit, et sort. L'orchestrateur maintient N slots en parallèle, relance dès
qu'un slot se libère, s'arrête au cap dur ou si la queue est vide (5 sorties
consécutives sans commit).

## Extract hors orchestrateur

L'orchestrateur **ne lance plus** `extract.py`. Toutes les extractions sont
faites à la main par Josian hors orchestrateur (cf. commit fd46534, passe
manuelle des 25 slugs restants). `extract.py` n'est ni dans l'allowlist
sous-agent, ni appelé en pré-flight.

Si une cellule Extract est `—` au démarrage, les étapes suivantes sur ce
slug ne sont pas pickables (`claim.py` exige les prérequis) — les sous-agents
la sautent. Josian la traite à la main : `1-sources/outils/ressources/extract.py <slug>`
+ `claim.py`/`release.py` extract.

Raison historique : `claude -p` peut auto-backgrounder une commande longue
sans `run_in_background: true` explicite, ce qui laissait `extract.py`
orphelin et la cellule verrouillée jusqu'au cap absolu (run 20260527-223339).

## Deux dimensions de cap — `--slots` vs `--max-agents`

Cadrans **orthogonaux** :

- `--slots` (default 3) : **concurrence** — combien d'agents tournent en même
  temps. Largeur du pipeline à t. Limité par CPU, conflits git, rate-limit.
- `--max-agents` (default 10) : **budget total** du run — nombre cumulé d'agents
  lancés avant arrêt, peu importe la concurrence. Garde-fou contre une queue
  qui ne se viderait pas. Une fois atteint : drain puis sortie.

`--slots 3 --max-agents 30` = 3 en parallèle, arrêt après 30 lancements cumulés
(ou avant si queue vide).

## Timeout dynamique à 3 couches (cf. `SPEC_audit_extend_timeout.md` historique)

1. **Sliding watchdog** : kill direct si aucun append au log JSONL depuis
   `--sliding-inactivity` secondes (default 180). Détecte les agents morts /
   bloqués / en attente silencieuse.
2. **Audit-agent intermédiaire** : à partir de `--audit-after` secondes (default
   300), puis toutes les `--audit-interval` (default 60), un `claude -p` (par
   défaut sonnet) reçoit un **digest de la fin du log** (compteurs globaux + N
   derniers events, base64/images retirés — cf. `build_audit_digest`) et juge
   si le pattern ressemble à du progrès, à un blocage ou à un rabbit hole
   hors scope. Verdict binaire kill/continue. En cas d'erreur d'audit →
   continue (safe default). Le digest est injecté inline dans le prompt :
   l'audit ne lit aucun fichier (un log Transcribe brut fait jusqu'à 5 Mo de
   base64 et faisait timeouter l'audit sur les agents les plus longs).
3. **Cap absolu** : `--timeout` (default 600). Kill systématique au-delà,
   peu importe l'activité ou les verdicts précédents.

Dans les trois cas : kill + `force_release_abandon()` du verrou orphelin si
l'agent avait claim une cellule sans la release.

Sortie en fin de run : `1-sources/outils/ressources/runs/<ts>/FLAGS.md` listant :
- cellules `signalé <raison>` (étapes bloquées),
- cellules `corrigé` ou Validate `0/2` (relecture pertinente),
- Verrou non vide (lock potentiellement orphelin),
- mentions « relecture Josian » dans la prose du TODO.

Usage:
  1-sources/outils/ressources/orchestrate.py [--slots N] [--max-agents N] [--model NAME]
                                  [--dry-run]
"""
import argparse
import datetime
import io
import json
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

import _paths

REPO_ROOT = _paths.find_root()
TODO = _paths.ressources_todo(REPO_ROOT)
RUNS_DIR = REPO_ROOT / "1-sources" / "outils" / "ressources" / "runs"

SUBAGENT_PROMPT = """\
Tu es lancé par un orchestrateur (`1-sources/outils/ressources/orchestrate.py`) pour faire
UNE tâche du pipeline d'extraction `ressources/`, puis sortir.

## RÈGLE ABSOLUE n°1 — `run_in_background: false` explicite sur TOUS tes Bash

Tu tournes en `claude -p` headless. **Le harness ne te réveillera PAS quand un
Bash en background termine** : les notifications « background task completion »
n'existent qu'en session interactive, jamais en `-p`. Tu n'as aucun moyen de
les attendre.

Donc **chaque Bash passe `run_in_background: false` EXPLICITEMENT** dans les
paramètres du tool_use — ne te repose pas sur « c'est le défaut » : sur les
commandes longues, `claude -p` peut auto-backgrounder sans que tu le demandes
(run 20260527-223339 : trois `extract.py` orphelins, 10 min de cap absolu).
N'utilise **jamais** `wait`, `pgrep`, `until … sleep` non plus : hors allowlist,
refusés silencieusement.

## RÈGLE ABSOLUE n°2 — 1 claim, pas de re-claim, pas de re-vérification en boucle

**1 agent = 1 claim = 1 lot borné, puis tu SORS.** Jamais de 2ᵉ claim — ni après
un `ok`, ni après un `abandon` (un abandon est définitif : si tu doutes au point
d'abandonner, tu sors, tu ne recommences pas). L'orchestrateur gère le volume
(nombre d'agents), pas ton endurance.

**Plafond par claim** (le piège classique : croire devoir « finir la cellule ») :

- **Triage = 3 slides candidates.** **Transcribe = 1 PNG.** Tu fais ton lot et
  tu releases, **même si la cellule reste en `K/N`** — la suite est pour l'agent
  suivant.
- **Embed / Validate = cellule entière** (pas de plafond par-item).

⚠ L'orchestrateur t'audite en cours de route et **te kill si tu dépasses ton
plafond dans un claim** (verdict déterministe). Dépasser = travail perdu. Reste
dans ton lot.

**Tool results décalés.** En `-p`, la sortie d'un `claim.py`/`release.py` peut
n'apparaître qu'au tour suivant — **ce n'est PAS un échec**. Si le commit
`Claim <step> <slug>` ou `<Step> <slug>: …` est dans `git log`, l'opération a
atterri. Donc :

- **Un seul `git log -1` après un claim/release**, jamais une boucle
  `git log`/`git status`/`grep` pour « confirmer » (run 20260530-154331, agent
  5b8e6222 : ~20 vérifs, 0 slide triée, cellule gelée 8 min).
- **Pas de Bash en parallèle** mêlant claim/release et `git log`/`Read` de
  vérif : si un appel du batch échoue (slug mal tapé), les frères sont annulés
  en cascade et tu perds le fil. Un Bash à la fois, séquentiel.

## Extract n'est pas de ton ressort

Les extractions sont faites à la main par Josian. `extract.py` n'est pas dans
ton allowlist. Une cellule Extract `—` n'est pas pickable, ni les étapes
suivantes du slug : passe ton chemin, prends une autre cellule.

## Procédure

1. Lis `ressources/RESSOURCES_PROTOCOL.md` (protocole complet : choix de
   cellule, étapes, plafonds, critères par étape) puis `RESSOURCES_TODO.md`.
2. Repère **toutes** les cellules prenables, **tires-en une au hasard** (pas
   systématiquement la première : d'autres agents lisent le même tableau en
   parallèle, viser tous la première = collisions ; le hasard vous disperse).
3. `1-sources/outils/ressources/claim.py <step> <slug>` (forme `tools/…` whitelistée).
   Si le claim échoue (race, prérequis, garde ≠ composeur/validateur) : retire
   une autre cellule au hasard. **Max 3 essais**, sinon sors.
4. Fais le boulot selon la section `<step>` du protocole, dans la limite du
   plafond ci-dessus.
5. `1-sources/outils/ressources/release.py <step> <slug> <result>`, puis **sors**.

**Si aucune tâche disponible** (tout en `2/2` ou `signalé`) : sors sans toucher
au repo.

---

## Permissions strictes

Tu tournes en headless avec une **allowlist stricte**. Les seuls outils
autorisés sont :

- `Read`, `Edit`, `Write`, `Glob`, `Grep` (built-in)
- Bash : **uniquement** ces scripts précis du pipeline :
  - `common/outils/whoami.py`
  - `1-sources/outils/ressources/claim.py`
  - `1-sources/outils/ressources/release.py`
  - `1-sources/outils/ressources/check_text_preservation.py`
- Bash git en lecture seule : `git status`, `git diff`, `git log`, `git show`.
- Bash : `1-sources/outils/ressources/crop.py *` (pour les crops PNG ciblés en Transcribe).
- Bash : `cp 1-sources/1.2-nettoyes/ressources/*` (pour l'étape Embed : copier les PNG retenus depuis `_all_pages/` ou `media/` vers la racine du slug).

Tout le reste est refusé silencieusement (`python3`, `curl`, `rm`, `git add`,
`git commit`, etc. — y compris `1-sources/outils/ressources/inventory.py` ou tout autre script non
listé ci-dessus). Si tu as besoin d'autre chose : c'est un signe que tu
sors du périmètre prévu → `signalé`.

## Posture face au doute — IMPORTANT

Tu tournes en mode autonome (pas d'humain à interroger en cours de route).
Le seul canal pour signaler un besoin d'arbitrage est :

```
1-sources/outils/ressources/release.py <step> <slug> "signalé <raison-précise-courte>"
```

Use-le **largement** dès que tu as un doute non trivial. Exemples :

- **Triage** : tu hésites à retain ou skip un visuel (info partiellement
  dans le texte, ambiguïté sur l'apport informatif).
- **Transcribe** : label flou, chiffre illisible même après crop ciblé,
  graphique dont les axes ne sont pas lisibles.
- **Embed** : ancre d'insertion (`insert after: …`) introuvable ou ambiguë
  dans `index.md`.
- **Validate** : divergence inattendue entre `index.md` et la source, suspicion
  d'omission/altération que tu ne peux pas trancher en croisant les sources.
- **N'importe quelle étape** : comportement inattendu d'un script
  (`check_text_preservation.py` qui crashe, claim qui réussit alors qu'il ne
  devrait pas, etc.).

**Vaut mieux 10 signalés à arbitrer qu'1 mauvaise décision dans le pipeline.**
Ne tranche pas tout seul si tu ne serais pas confiant en interactif.

Un `signalé` n'est pas un échec — c'est le canal "humain nécessaire" intégré
au pipeline. La cellule devient non-pickable jusqu'à arbitrage, et tu apparais
dans le `FLAGS.md` du run pour que Josian voie qu'il y a une décision à
prendre.

## Restrictions git

Tu ne fais **aucune** action git directe (`git add`, `git commit`, `git reset`,
etc.). Toute mise à jour du tableau et tout staging de `1-sources/1.2-nettoyes/ressources/<slug>/`
passe **uniquement** par `claim.py` et `release.py` — eux seuls savent stager
les bons fichiers et formater le commit (le pattern attendu par les gardes
"≠ composeur" / "≠ premier validateur" et par l'orchestrateur).
"""


AUDIT_PROMPT_TEMPLATE = """\
Tu es un auditeur d'orchestrateur. Un sous-agent `claude -p` tourne depuis
{elapsed}s sur l'étape **{step}** du pipeline d'extraction `ressources/`, slug
**{slug}**.

Voici un **résumé de la fin de son log** : compteurs globaux d'activité, puis
les derniers events (contenu tronqué, images/base64 retirés). C'est tout ce
dont tu as besoin — tu n'as aucun fichier à lire.

------------------------------------------------------------
{digest}
------------------------------------------------------------

**Ta tâche** : décider si l'agent **progresse**, est **bloqué/en boucle**, ou
parti dans un **rabbit hole hors scope**.

⚠ **Priorité absolue n°1 — sortie de tâche.** Inspecte les `tool_use` des derniers
events. Si l'agent **fabrique des outils ou bricole hors de sa tâche** au lieu
de faire l'extraction, c'est le signal le plus grave → **verdict kill**.
Marqueurs typiques :
- `Write`/`Edit` sur un fichier **hors** du dossier `1-sources/1.2-nettoyes/ressources/{slug}/`
  (surtout un `.py`/`.sh` : il se crée un script).
- `Bash` avec une commande **hors allowlist** (`python3 …`, `chmod`, `cat > …`,
  un script maison) — elle revient en `tool_result ERROR` puisqu'elle est
  refusée, et il la retente.
Exception : si la toute fin du log montre qu'il a abandonné cette piste et
repris le protocole (`crop.py`, Edit de l'`index.md` du slug), laisse `continue`.

⚠ **Priorité absolue n°2 — plafond « 1 livrable / claim ».**
Chaque claim ne couvre qu'un lot borné : **Transcribe = 1 PNG**, **Triage =
3 slides** max (Embed/Validate = cellule entière, pas de plafond par-item).
L'orchestrateur a fait le calcul pour toi — il a comparé la valeur figée dans
la cellule au moment du claim au nombre de livrables présents dans le fichier
en cours. Verdict déterministe, tu n'as rien à recompter :

    PLAFOND: {ceiling_check}

Si cette ligne contient **⚠ DÉPASSEMENT**, l'agent a produit plus de livrables
que son plafond dans un seul claim → **verdict kill, sans débat** : il a perdu
la discipline « 1 slide / agent » et finit par se dégrader (sauts de slide en
slide, abandon, ou `signalé` fabriqué). Si elle dit `ok`, « sans plafond » ou
« non calculable », ce critère ne déclenche rien — passe aux autres signaux.

Autres signaux de patinage :
- `tool_result ERROR` répétés (commande refusée silencieusement par l'allowlist,
  retentée en boucle).
- Même `tool_use` identique répété (boucle d'outil).
- `text`/`thinking` du genre "je n'arrive pas", "le claim a échoué",
  "permission denied", "je vais réessayer".
- Beaucoup de tool_use mais aucun `claim.py` réussi alors qu'on est censé
  travailler sur `{slug}`.
- Activité hors périmètre : lecture/écriture de fichiers sans rapport avec
  `{slug}`, tentative de scripts hors allowlist.

Signaux de progrès :
- Suite cohérente de tool_use correspondant à l'étape `{step}`, **sur UN seul
  livrable** (pour Transcribe : `crop.py` + Read d'images + Edit de l'`index.md`
  du slug — c'est normal et long, mais pour un seul PNG).
- Compteur d'erreurs bas, `claim.py` effectué.

**Sortie** : une seule phrase de justification, puis une ligne EXACTEMENT
au format :

    VERDICT: kill

ou

    VERDICT: continue

Pas de markdown, pas de gras, pas de longue analyse.
"""


def _summarize_event(ev: dict, max_field: int) -> str | None:
    """Render one stream-json event as a compact text block, dropping image /
    base64 payloads and truncating every field to `max_field` chars."""
    t = ev.get("type")
    if t == "system":
        return f"[system {ev.get('subtype', '')}]"
    if t == "result":
        return f"[result {ev.get('subtype', '')}] {str(ev.get('result', ''))[:max_field]}"
    content = (ev.get("message") or {}).get("content")
    if not isinstance(content, list):
        return None
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        it = item.get("type")
        if it == "text":
            txt = (item.get("text") or "").strip()
            if txt:
                parts.append(f"[text] {txt[:max_field]}")
        elif it == "thinking":
            th = (item.get("thinking") or "").strip()
            if th:
                parts.append(f"[thinking] {th[:max_field]}")
        elif it == "tool_use":
            inp = json.dumps(item.get("input") or {}, ensure_ascii=False)
            if len(inp) > max_field:
                inp = inp[:max_field] + "…"
            parts.append(f"[tool_use {item.get('name')}] {inp}")
        elif it == "tool_result":
            err = " ERROR" if item.get("is_error") else ""
            c = item.get("content")
            if isinstance(c, list):
                segs = []
                for b in c:
                    if isinstance(b, dict):
                        segs.append(b.get("text", "") if b.get("type") == "text"
                                    else f"<{b.get('type', '?')}>")
                    else:
                        segs.append(str(b))
                cs = " ".join(segs)
            else:
                cs = str(c)
            parts.append(f"[tool_result{err}] {cs[:max_field]}")
    return "\n".join(parts) if parts else None


def build_audit_digest(log_path: Path, n_events: int = 50,
                       max_field: int = 400) -> str:
    """Compact digest de la FIN du log JSONL d'un sous-agent, pour l'audit.

    Deux blocs : (1) compteurs globaux (total events, tool_use par nom, nb de
    tool_result en erreur) — signal progrès/blocage à coût constant ; (2) les
    `n_events` derniers events résumés, base64/images retirés et champs tronqués.

    La tail suffit pour repérer un agent qui dérive (création de script, Bash
    hors allowlist, sortie de tâche) : ces tool_use apparaissent en clair dans
    les derniers events. C'est à l'audit de les juger (cf. AUDIT_PROMPT_TEMPLATE).

    Découple la taille de l'audit du contenu image : un log Transcribe de 5 Mo
    (blobs base64 des PNG pleine page) produit un digest de quelques Ko. Sans
    ça, l'audit ingérait tout le log et timeoutait précisément sur les agents
    les plus longs — ceux qu'il devait justement surveiller."""
    try:
        lines = log_path.read_text().splitlines()
    except OSError:
        return "(log illisible)"
    events: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if not events:
        return "(log vide — agent pas encore démarré ?)"

    tool_counts: dict[str, int] = {}
    err_count = 0
    for ev in events:
        content = (ev.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "tool_use":
                name = item.get("name", "?")
                tool_counts[name] = tool_counts.get(name, 0) + 1
            elif item.get("type") == "tool_result" and item.get("is_error"):
                err_count += 1
    tool_summary = ", ".join(
        f"{k}×{v}" for k, v in sorted(tool_counts.items(), key=lambda kv: -kv[1])
    ) or "(aucun)"

    tail = events[-n_events:]
    rendered = [s for ev in tail if (s := _summarize_event(ev, max_field))]
    return (
        f"events total: {len(events)}\n"
        f"tool_use: {tool_summary}\n"
        f"tool_result en erreur: {err_count}\n\n"
        f"--- {len(tail)} derniers events ---\n" + "\n".join(rendered)
    )


# Colonnes du tableau TODO (cells = ligne.strip("|").split("|")) et plafond par
# claim de chaque étape. Embed/Validate portent sur la cellule entière → pas de
# plafond par-item, donc absents de PER_CLAIM_CEILING.
STEP_COL = {"extract": 3, "triage": 4, "embed": 5, "transcribe": 6, "validate": 7}
PER_CLAIM_CEILING = {"triage": 3, "transcribe": 1}


def _cell_start_count(step: str, slug: str) -> int:
    """K figé dans la cellule du slug. Tant que l'agent n'a pas release, la
    cellule porte encore le compteur d'AVANT son claim → c'est notre baseline
    « derniers commits ». 0 si vide / `—` / `ok` / illisible."""
    col = STEP_COL.get(step)
    if col is None:
        return 0
    try:
        lines = TODO.read_text().splitlines()
    except OSError:
        return 0
    for line in lines:
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 9 or cells[0] != slug:
            continue
        m = re.match(r"^(\d+)/\d+$", cells[col])
        return int(m.group(1)) if m else 0
    return 0


def compute_ceiling_check(step: str, slug: str) -> str:
    """Ligne verdict prête à injecter dans l'audit : compare la baseline figée
    dans la cellule (= état au claim) au nombre de livrables présents dans le
    fichier en cours, et signale un dépassement du plafond par-claim.

    Déterministe — l'audit n'a rien à recompter, juste à lire le verdict. C'est
    la version fiable du « regarder les derniers commits vs le fichier en cours »
    : on ne fait pas lire de fichier/git à l'audit (les logs Transcribe font
    jusqu'à 5 Mo de base64 et le faisaient timeouter).

    Embed/Validate : pas de plafond par-item (cellule entière) → pas de contrôle.
    """
    ceiling = PER_CLAIM_CEILING.get(step)
    if ceiling is None:
        return "étape sans plafond par-item (embed/validate) — ignore ce critère"
    extracted = _paths.ressources_dir(REPO_ROOT) / slug
    start = _cell_start_count(step, slug)
    try:
        if step == "transcribe":
            current = (extracted / "index.md").read_text().count("<retranscription>")
        else:  # triage : nb de slides/images distinctes tranchées dans triage.md
            t = (extracted / "triage.md").read_text()
            current = len(set(re.findall(r"(?:slide-\d+|image\d+)\.png", t)))
    except OSError:
        return "non calculable (fichier source absent) — juge sur les autres signaux"
    added = current - start
    flag = "⚠ DÉPASSEMENT" if added > ceiling else "ok"
    return (f"plafond={ceiling} livrable(s)/claim ; ajoutés depuis le claim={added} "
            f"→ {flag}")


def heartbeat_path(run_dir: Path, agent_id: int) -> Path:
    """Path du fichier heartbeat d'un agent, sous $TMPDIR (cleanup OS auto).

    Sous $TMPDIR/formation-cats/orchestrate/<run_ts>/ pour rester hors du repo
    et bénéficier du nettoyage automatique au reboot. Cf. commit 989f19d
    pour le pattern $TMPDIR/formation-cats/ projet.
    """
    tmp_root = Path(os.environ.get("TMPDIR", "/tmp")) / "formation-cats" / "orchestrate" / run_dir.name
    tmp_root.mkdir(parents=True, exist_ok=True)
    return tmp_root / f"agent-{agent_id:02d}.heartbeat"


def now_iso() -> str:
    return datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def kill_tree(proc: subprocess.Popen) -> None:
    """SIGKILL le process group entier de `proc` (subagent + ses subprocess
    `crop.py`, `claim.py`, etc.). Suppose que `proc` a été lancé avec
    `start_new_session=True`. Fallback sur `proc.kill()` si le PGID a déjà
    disparu (process déjà mort) ou OS non-posix."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError, AttributeError):
        try:
            proc.kill()
        except OSError:
            pass


def head_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True, cwd=REPO_ROOT, check=True,
    ).stdout.strip()


def commits_since(sha: str) -> list[str]:
    """Subjects of commits added since <sha> (most recent first)."""
    if not sha:
        return []
    out = subprocess.run(
        ["git", "log", f"{sha}..HEAD", "--pretty=format:%s"],
        capture_output=True, text=True, cwd=REPO_ROOT, check=False,
    ).stdout.strip()
    return out.splitlines() if out else []


CLAIM_RE = re.compile(r"^Claim (extract|triage|embed|transcribe|validate) (\S+) \(([0-9a-f]{8})\)$")
RELEASE_RE = re.compile(r"^(Extract|Triage|Embed|Transcribe|Validate) (\S+): .+ \(([0-9a-f]{8})\)$")
COMMIT_SHORT_RE = re.compile(r"\(([0-9a-f]{8})\)$")


def detect_short_sha(log_path: Path) -> str | None:
    """Parse les premières lignes du log stream-json d'un sous-agent pour en
    extraire son `session_id` (premier event `type=system, subtype=init`).
    Retourne les 8 premiers chars, ou None si pas encore trouvable.

    Sert à attribuer correctement les commits à un agent dans un contexte où
    plusieurs sous-agents commitent en parallèle sur le même HEAD."""
    try:
        with log_path.open() as f:
            for _ in range(50):
                line = f.readline()
                if not line:
                    return None
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    continue
                sid = ev.get("session_id")
                if sid:
                    return sid[:8]
    except OSError:
        pass
    return None


def filter_commits(commits: list[str], short: str | None) -> list[str]:
    """Garde uniquement les commits dont le subject finit par `(short)`. Si
    `short is None`, retourne la liste telle quelle (fallback bug-compat)."""
    if short is None:
        return commits
    return [c for c in commits if (m := COMMIT_SHORT_RE.search(c)) and m.group(1) == short]


def detect_orphan_claims(commits: list[str]) -> list[tuple[str, str, str]]:
    """Parse subjects of an agent's commits ; return (step, slug, short) for
    each Claim without a matching release in the same commit list."""
    claims: set[tuple[str, str, str]] = set()
    releases: set[tuple[str, str, str]] = set()
    for subj in commits:
        if m := CLAIM_RE.match(subj):
            claims.add((m.group(1), m.group(2), m.group(3)))
        elif m := RELEASE_RE.match(subj):
            releases.add((m.group(1).lower(), m.group(2), m.group(3)))
    return [k for k in claims if k not in releases]


def current_step_slug(base_sha: str, short: str | None) -> tuple[str, str] | None:
    """Inspect commits since `base_sha` (filtered to commits authored by the
    agent identified by `short`); return (step, slug) of the most recent
    Claim that has no matching Release. None if no active claim yet — agent is
    either pre-claim or already done.

    Si `short is None` (détection pas encore aboutie), on retombe sur la liste
    non filtrée — risque de prendre la step d'un autre agent, log de l'audit
    sera bruité mais le kill reste cohérent (filtre par log_path)."""
    commits = filter_commits(commits_since(base_sha), short)
    # commits_since returns most-recent-first ; reverse for chronological order
    pending: list[tuple[str, str, str]] = []
    releases: set[tuple[str, str, str]] = set()
    for subj in reversed(commits):
        if m := CLAIM_RE.match(subj):
            pending.append((m.group(1), m.group(2), m.group(3)))
        elif m := RELEASE_RE.match(subj):
            releases.add((m.group(1).lower(), m.group(2), m.group(3)))
    for step, slug, short in reversed(pending):
        if (step, slug, short) not in releases:
            return step, slug
    return None


def launch_audit_async(agent_id: int, log_path: Path, step: str, slug: str,
                       elapsed: int, model: str, run_dir: Path,
                       ) -> tuple[subprocess.Popen, Path, io.TextIOBase]:
    """Lance un `claude -p` d'audit non-bloquant. Retourne (proc, audit_log_path,
    audit_file). L'appelant poll `proc.poll()` ; quand terminé, passe le tuple
    à `parse_audit_result()` qui ferme le fichier et lit le verdict.

    Le stdout/stderr du Popen est rangé directement dans audit_log_path —
    pas de PIPE, pas de risque de blocage de buffer."""
    prompt = AUDIT_PROMPT_TEMPLATE.format(
        elapsed=elapsed, step=step, slug=slug,
        digest=build_audit_digest(log_path),
        ceiling_check=compute_ceiling_check(step, slug),
    )
    audit_log = run_dir / f"audit-{agent_id:02d}-{now_iso()}.log"
    # Pas de --allowedTools : tout le contexte (le digest de la tail) est dans
    # le prompt, l'audit n'a aucun fichier à lire. Évite qu'il tente un Read du
    # log brut (5 Mo de base64 sur les Transcribe) et timeoute.
    cmd = [
        "claude", "-p", prompt,
        "--model", model,
        "--output-format", "text",
    ]
    audit_file = open(audit_log, "w")
    audit_file.write(
        f"# audit agent-{agent_id:02d} started at {now_iso()}\n"
        f"# step={step} slug={slug} elapsed={elapsed}s model={model}\n\n"
    )
    audit_file.flush()
    proc = subprocess.Popen(
        cmd, stdout=audit_file, stderr=subprocess.STDOUT, cwd=REPO_ROOT,
        start_new_session=True,
    )
    return proc, audit_log, audit_file


def parse_audit_result(audit_proc: subprocess.Popen, audit_log_path: Path,
                       audit_file: io.TextIOBase, agent_id: int, step: str,
                       slug: str, elapsed: int, log) -> bool:
    """À appeler quand `audit_proc.poll() is not None`. Ferme le fichier de log,
    lit le verdict, retourne True si kill / False sinon (default continue sur
    rc != 0 ou verdict unparseable)."""
    try:
        audit_file.close()
    except OSError:
        pass
    rc = audit_proc.returncode
    try:
        out = audit_log_path.read_text()
    except OSError:
        out = ""
    if rc != 0:
        log(f"  ! audit agent-{agent_id:02d} rc={rc} — default continue")
        return False
    last_verdict = None
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("VERDICT:"):
            last_verdict = s.split(":", 1)[1].strip().lower()
    if last_verdict == "kill":
        log(f"  ! audit agent-{agent_id:02d} verdict=KILL ({step}/{slug} @{elapsed}s)")
        return True
    if last_verdict == "continue":
        log(f"  ✓ audit agent-{agent_id:02d} verdict=continue ({step}/{slug} @{elapsed}s)")
        return False
    log(f"  ! audit agent-{agent_id:02d} verdict unparseable ({last_verdict!r}) — default continue")
    return False


RELEASE_SCRIPT = Path(__file__).resolve().parent / "release.py"


def force_release_abandon(step: str, slug: str, short: str, log) -> None:
    """Clear a stale lock left by a sub-agent that exited without releasing.
    Delegates to `release.py --force-abandon-orphan` which acquires
    `.ressources.lock` (flock) before the read→modify→write — pas de TOCTOU
    avec un claim/release concurrent d'un autre sous-agent.

    Best-effort : on log et on continue si le commit échoue (pre-commit hook,
    lock git transient, etc.). Le verrou orphelin sera nettoyé au run suivant
    ou par `release.py <step> <slug> abandon` manuel."""
    cmd = [
        sys.executable, str(RELEASE_SCRIPT),
        "--repo-root", str(REPO_ROOT),
        "--force-abandon-orphan", short,
        step, slug, "abandon",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                cwd=REPO_ROOT, check=True)
        out = (result.stdout or "").strip()
        if out:
            log(f"  ! {out}")
    except subprocess.CalledProcessError as e:
        err = (e.stderr or e.stdout or "").strip()
        log(f"  ! force_release_abandon failed (rc={e.returncode}): {err}")
    except OSError as e:
        log(f"  ! force_release_abandon exec failed: {e}")


def queue_has_work() -> bool:
    """Quick heuristic: at least one cell in the table is not done / not locked.

    Vrai si une ligne a au moins une cellule pickable (vide ou Validate 0/2|1/2)
    ET aucun Verrou. On ne réplique pas la logique exacte de claim.py (prereqs,
    gardes ≠ composeur, etc.) — si l'orchestrateur croit qu'il reste du boulot
    mais qu'aucun sous-agent ne picke rien, les 5 sorties vides consécutives
    feront stopper proprement.
    """
    content = TODO.read_text().splitlines()
    for line in content:
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 9 or cells[0] in ("Slug", "---"):
            continue
        verrou = cells[8]
        if verrou and verrou != "—":
            continue  # locked, skip
        # Pickable if any step cell is "—" or empty ; Validate in {0/2, 1/2} ;
        # Transcribe en `K/N` avec K<N (batch partiel, reclaimable).
        for i in range(3, 8):
            v = cells[i]
            if not v or v == "—":
                return True
            if i == 7 and v in ("0/2", "1/2"):
                return True
            if i == 6:
                m = re.match(r"^(\d+)/(\d+)$", v)
                if m and int(m.group(1)) < int(m.group(2)):
                    return True
    return False


def launch_subagent(agent_id: int, run_dir: Path, model: str | None,
                    dry_run: bool) -> tuple[subprocess.Popen | None, io.TextIOBase | None]:
    log_path = run_dir / f"agent-{agent_id:02d}.log"
    cmd = [
        "claude", "-p", SUBAGENT_PROMPT,
        # Strict allowlist : pas de bypass, seuls les outils/scripts ci-dessous
        # sont autorisés. Tout le reste est refusé silencieusement (pas de prompt
        # interactif possible en `-p`). Voir SUBAGENT_PROMPT pour la liste
        # synchronisée côté sous-agent. Garder les deux en sync.
        "--allowedTools",
        "Read", "Edit", "Write", "Glob", "Grep",
        "Bash(common/outils/whoami.py)",
        "Bash(1-sources/outils/ressources/claim.py *)",
        "Bash(1-sources/outils/ressources/release.py *)",
        "Bash(1-sources/outils/ressources/check_text_preservation.py *)",
        "Bash(1-sources/outils/ressources/crop.py *)",
        "Bash(git status*)", "Bash(git diff*)",
        "Bash(git log*)", "Bash(git show*)",
        "Bash(cp 1-sources/1.2-nettoyes/ressources/*)",
        # stream-json + verbose : chaque event (tool_use, tool_result, message)
        # est flushé en JSONL dans le log temps réel — sinon `text` ne print
        # que la réponse finale et on est aveugle pendant l'exec.
        "--output-format", "stream-json", "--verbose",
    ]
    if model:
        cmd += ["--model", model]
    if dry_run:
        print(f"[dry-run] agent-{agent_id:02d}: would launch claude -p (log → {log_path})")
        return None, None
    log_file = open(log_path, "w")
    log_file.write(f"# orchestrator: launching agent-{agent_id:02d} at {now_iso()}\n")
    log_file.write(f"# cmd: {' '.join(repr(c) if ' ' in c else c for c in cmd[:4])} <prompt> ...\n\n")
    log_file.flush()
    hb_path = heartbeat_path(run_dir, agent_id)
    proc = subprocess.Popen(
        cmd, stdout=log_file, stderr=subprocess.STDOUT, cwd=REPO_ROOT,
        start_new_session=True,
        env={**os.environ, "ORCHESTRATE_HEARTBEAT": str(hb_path)},
    )
    return proc, log_file


def scan_flags(run_dir: Path) -> str:
    """Build the final FLAGS.md content by scanning the TODO table + prose."""
    lines = TODO.read_text().splitlines()

    signaled: list[str] = []
    corrected: list[str] = []  # Validate 0/2 means dernière passe a corrigé
    locked: list[str] = []
    for line in lines:
        if not line.startswith("| "):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 9 or cells[0] in ("Slug", "---"):
            continue
        slug = cells[0]
        step_names = ("Extract", "Triage", "Embed", "Transcribe", "Validate")
        for i, name in enumerate(step_names, start=3):
            v = cells[i]
            if v.startswith("signalé"):
                signaled.append(f"- `{slug}` — {name} : {v}")
        if cells[7] == "0/2":
            corrected.append(f"- `{slug}` — Validate 0/2 (la dernière passe a corrigé)")
        verrou = cells[8]
        if verrou and verrou != "—":
            locked.append(f"- `{slug}` — Verrou : {verrou}")

    prose_review = []
    raw = TODO.read_text()
    for m in re.finditer(r"^.*relecture Josian.*$", raw, flags=re.MULTILINE | re.IGNORECASE):
        line = m.group(0)
        if line.startswith("| "):
            continue
        text = line.strip().lstrip("-").strip()
        prose_review.append(f"- {text}")

    out: list[str] = []
    out.append(f"# Flags — run {run_dir.name}\n")
    out.append(f"Généré : {datetime.datetime.now().isoformat(timespec='seconds')}\n")

    def section(title: str, items: list[str], hint: str) -> None:
        out.append(f"\n## {title}\n")
        if not items:
            out.append("*(rien)*\n")
            return
        out.append(f"_{hint}_\n\n")
        out.extend(item + "\n" for item in items)

    section("Cellules `signalé`", signaled,
            "Étapes bloquées — arbitrage Josian nécessaire.")
    section("Validate `0/2`", corrected,
            "Une passe a corrigé : à relire si tu veux vérifier la correction "
            "(deux passes propres restent à faire de toute façon).")
    section("Verrous non libérés", locked,
            "Lock potentiellement orphelin (sous-agent crashé ?). "
            "Vérifier l'âge ; si vieux, `release.py <step> <slug> abandon`.")
    section("Mentions « relecture Josian » dans le TODO", prose_review,
            "Lignes en prose (hors tableau).")

    return "".join(out)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--slots", type=int, default=3,
                        help="concurrence : nombre de sous-agents qui tournent "
                             "EN MÊME TEMPS (default: 3). Quand un slot se libère, "
                             "un nouvel agent est relancé pour le remplacer.")
    parser.add_argument("--max-agents", type=int, default=10,
                        help="budget TOTAL du run : nombre cumulé de sous-agents "
                             "que l'orchestrateur lancera avant d'arrêter (default: 10). "
                             "Garde-fou indépendant de --slots. Une fois atteint, "
                             "plus aucun lancement même si des slots sont libres ; "
                             "drain des agents en cours puis sortie.")
    parser.add_argument("--model", default=None,
                        help="forcer un modèle (ex: 'sonnet', 'opus'). Default: hérité.")
    parser.add_argument("--stagger", type=float, default=2.0,
                        help="délai (s) entre les lancements pour laisser les commits se sérialiser")
    parser.add_argument("--timeout", type=int, default=600,
                        help="cap absolu par sous-agent en secondes (default: 600 = 10 min). "
                             "Kill systématique au-delà, peu importe l'activité ou l'audit.")
    parser.add_argument("--sliding-inactivity", type=int, default=180,
                        help="kill si aucun append au log JSONL depuis N secondes "
                             "(default: 180). Détecte les agents morts/silencieux. "
                             "Tolère un long délai entre tool_use sur des reads "
                             "d'images ou monologues de raisonnement.")
    parser.add_argument("--audit-after", type=int, default=300,
                        help="à partir de quand l'audit-agent peut tourner (default: 300s). "
                             "En deçà, on fait confiance au sliding watchdog seul.")
    parser.add_argument("--audit-interval", type=int, default=60,
                        help="intervalle minimum entre deux audits d'un même sous-agent "
                             "(default: 60s).")
    parser.add_argument("--audit-model", default="sonnet",
                        help="modèle pour l'audit-agent (default: sonnet). Tâche courte : "
                             "lire un log JSONL et trancher kill/continue.")
    parser.add_argument("--audit-timeout", type=int, default=90,
                        help="timeout d'un audit-agent en secondes (default: 90). "
                             "Au-delà, l'audit est killé et le verdict par défaut est "
                             "continue. Configurable pour les tests stress.")
    parser.add_argument("--dry-run", action="store_true",
                        help="affiche ce qui serait fait sans lancer claude -p")
    args = parser.parse_args()

    if args.slots < 1 or args.max_agents < 1:
        sys.exit("error: --slots et --max-agents doivent être ≥ 1")

    if not TODO.exists():
        sys.exit(f"error: {TODO} introuvable")

    if os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("error: ANTHROPIC_API_KEY est set — refus de lancer pour éviter "
                 "toute facturation API. Unset la variable et relance.")

    ts = now_iso()
    run_dir = RUNS_DIR / ts
    run_dir.mkdir(parents=True, exist_ok=True)
    orch_log = open(run_dir / "orchestrator.log", "w")

    def log(msg: str) -> None:
        line = f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}"
        print(line, flush=True)
        orch_log.write(line + "\n")
        orch_log.flush()

    log(f"run dir: {run_dir.relative_to(REPO_ROOT)}")
    log(f"slots={args.slots} max_agents={args.max_agents} "
        f"model={args.model or 'default'} dry_run={args.dry_run}")

    rel_run = run_dir.relative_to(REPO_ROOT)
    # Command prêt à coller dans l'outil `Monitor`. Il suit orchestrator.log
    # (le digest de TOUS les events : launch, completion, verdict d'audit, kill
    # watchdog, drain), émet chaque nouvelle ligne, et SORT à la ligne terminale
    # `flags :` — contrairement à `tail -f` qui ne se terminerait jamais. Le
    # `sleep` est ICI, dans le command Monitor (poll background légitime), pas
    # un sleep foreground de l'agent (lui, bloqué par le harness).
    mon_cmd = (
        'L=' + str(rel_run) + '/orchestrator.log; n=0; while :; do '
        't=$(wc -l <"$L" 2>/dev/null||echo 0); '
        '[ "$t" -gt "$n" ] && { sed -n "$((n+1)),${t}p" "$L"; n=$t; }; '
        'tail -n1 "$L" 2>/dev/null | grep -q "flags :" && break; sleep 2; done'
    )
    banner = (
        "\n" + "=" * 60 + "\n"
        "INSTRUCTION À L'AGENT QUI A LANCÉ CE SCRIPT\n"
        + "=" * 60 + "\n"
        "Run en background (plusieurs min). Pour attendre : outil `Monitor`,\n"
        "JAMAIS `sleep`/`until`/`wait` (sleep foreground = bloqué, aveugle).\n"
        "\n"
        "Colle CE command dans l'outil Monitor — chaque ligne émise est un\n"
        "event (launch, completion, audit, kill watchdog, drain) et il sort\n"
        "en fin de run :\n"
        "\n"
        "  " + mon_cmd + "\n"
        "\n"
        "Si le flux se fige plusieurs minutes alors que ça devrait tourner :\n"
        "Ctrl-C l'orchestrateur (kill les sous-agents + libère les verrous).\n"
        + "=" * 60 + "\n"
    )
    print(banner, flush=True)

    if not queue_has_work():
        log("queue vide à l'init — rien à faire.")
        orch_log.close()
        return

    launched = 0
    consecutive_empty = 0
    # (id, proc, base_sha, start, log_file)
    running: list[tuple[int, subprocess.Popen | None, str, float, io.TextIOBase | None]] = []
    last_audit_at: dict[int, float] = {}  # agent_id -> last audit timestamp (= terminé)
    pending_audits: dict[int, tuple[subprocess.Popen, Path, io.TextIOBase, float, str, str]] = {}
    # agent_id -> (audit_proc, audit_log_path, audit_file, audit_start, step, slug)
    agent_short: dict[int, str | None] = {}  # agent_id -> first 8 chars of session_id (None = not yet detected)

    def ensure_short(aid: int) -> str | None:
        """Lazily detect and cache the agent's session_id short SHA from its
        log. Returns None until the init event is visible in the log."""
        cached = agent_short.get(aid)
        if cached is not None:
            return cached
        sh = detect_short_sha(run_dir / f"agent-{aid:02d}.log")
        if sh:
            agent_short[aid] = sh
            log(f"agent-{aid:02d} short_sha={sh}")
        return sh

    def cleanup_pending_audit(aid: int) -> None:
        """Kill et drop l'audit en cours pour `aid`, s'il y en a un.
        Idempotent."""
        if aid not in pending_audits:
            return
        audit_proc, _, audit_file, _, _, _ = pending_audits.pop(aid)
        if audit_proc.poll() is None:
            kill_tree(audit_proc)
        try:
            audit_file.close()
        except OSError:
            pass

    def check_agent_deadline(aid: int, proc: subprocess.Popen, base: str,
                             start: float) -> str | None:
        """Returns None if agent should keep running, else a short reason string
        ('finished' | 'cap' | 'sliding' | 'audit'). Side-effect : kills the
        process when returning a kill reason. Poll aussi l'audit non-bloquant
        de cet agent s'il y en a un, et en lance un nouveau quand la fenêtre
        est ouverte."""
        if proc is None:
            return None
        if proc.poll() is not None:
            cleanup_pending_audit(aid)
            return "finished"
        now = time.time()
        elapsed = now - start

        # 1. Poll l'audit en cours pour cet agent (non-bloquant).
        if aid in pending_audits:
            audit_proc, audit_log_path, audit_file, audit_start, step, slug = pending_audits[aid]
            if audit_proc.poll() is not None:
                verdict_kill = parse_audit_result(
                    audit_proc, audit_log_path, audit_file, aid, step, slug,
                    int(elapsed), log,
                )
                del pending_audits[aid]
                last_audit_at[aid] = time.time()
                if verdict_kill:
                    kill_tree(proc)
                    return "audit"
            elif now - audit_start > args.audit_timeout:
                log(f"  ! audit agent-{aid:02d} timeout ({args.audit_timeout}s) — kill audit, default continue")
                cleanup_pending_audit(aid)
                last_audit_at[aid] = time.time()
            # Sinon : audit toujours en cours, on continue à check les caps
            # ci-dessous (un agent peut être killé par cap/sliding même pendant
            # un audit — on n'attend pas le verdict).

        # 2. Cap absolu — kill l'agent même si un audit tourne.
        if elapsed > args.timeout:
            log(f"agent-{aid:02d} cap absolu ({args.timeout}s) — kill")
            kill_tree(proc)
            cleanup_pending_audit(aid)
            return "cap"

        # 3. Sliding watchdog.
        # On regarde le mtime du log JSONL claude ET du heartbeat (`ORCHESTRATE_HEARTBEAT`).
        # Le heartbeat est désormais dormant — aucun script de l'allowlist sous-agent
        # ne le touche (extract.py, seul consommateur historique, est sorti du périmètre).
        # Conservé pour resservir au cas où un autre script long entrerait dans l'allowlist.
        log_path = run_dir / f"agent-{aid:02d}.log"
        try:
            mtime = log_path.stat().st_mtime
        except FileNotFoundError:
            mtime = start
        try:
            hb_mtime = heartbeat_path(run_dir, aid).stat().st_mtime
        except FileNotFoundError:
            hb_mtime = 0
        inactivity = now - max(mtime, hb_mtime)
        if inactivity > args.sliding_inactivity:
            log(f"agent-{aid:02d} sliding watchdog ({int(inactivity)}s sans append log+heartbeat) — kill")
            kill_tree(proc)
            cleanup_pending_audit(aid)
            return "sliding"

        # 4. Lancer un audit async si pas déjà en cours et fenêtre OK.
        if aid not in pending_audits:
            last_audit = last_audit_at.get(aid, start)
            if elapsed > args.audit_after and now - last_audit > args.audit_interval:
                short = ensure_short(aid)
                if short is None:
                    # Init event pas encore visible dans le log → on ne peut pas
                    # filtrer les commits par agent ni cibler step/slug. Retry
                    # au prochain poll plutôt que d'auditer sur un mauvais slug.
                    return None
                step_slug = current_step_slug(base, short) or ("unknown", "unknown")
                step, slug = step_slug
                log(f"audit agent-{aid:02d} async start "
                    f"(elapsed={int(elapsed)}s, step={step}, slug={slug})")
                audit_proc, audit_log_path, audit_file = launch_audit_async(
                    aid, log_path, step, slug, int(elapsed),
                    args.audit_model, run_dir,
                )
                pending_audits[aid] = (
                    audit_proc, audit_log_path, audit_file, time.time(), step, slug,
                )

        return None

    def harvest(idx: int) -> None:
        """Pop running[idx], log summary, auto-abandon orphan claims, update
        consecutive_empty."""
        nonlocal consecutive_empty
        agent_id, proc, base, start, log_file = running.pop(idx)
        last_audit_at.pop(agent_id, None)
        cleanup_pending_audit(agent_id)  # idempotent ; cas où l'agent termine pendant un audit
        short = ensure_short(agent_id)
        duration = int(time.time() - start)
        if proc is not None and proc.poll() is None:
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        rc = proc.returncode if proc else -1
        all_commits = commits_since(base)
        new_commits = filter_commits(all_commits, short)
        did_work = len(new_commits) > 0
        consecutive_empty = 0 if did_work else consecutive_empty + 1
        log(
            f"agent-{agent_id:02d} exited rc={rc} duration={duration}s "
            f"commits={len(new_commits)} (short={short or '??'}) "
            f"consecutive_empty={consecutive_empty}"
        )
        if short is None and all_commits:
            log(f"  ! short_sha non détecté — filtrage commits désactivé, fallback bug-compat")
        for c in new_commits:
            log(f"  + {c}")
        for step, slug, ag_short in detect_orphan_claims(new_commits):
            force_release_abandon(step, slug, ag_short, log)
        if log_file is not None:
            try:
                log_file.close()
            except OSError:
                pass

    try:
        while launched < args.max_agents and consecutive_empty < 5:
            # Fill slots
            while len(running) < args.slots and launched < args.max_agents:
                agent_id = launched + 1
                base = head_sha() if not args.dry_run else ""
                proc, log_file = launch_subagent(agent_id, run_dir, args.model, args.dry_run)
                launched += 1
                running.append((agent_id, proc, base, time.time(), log_file))
                log(f"launched agent-{agent_id:02d} (running: {len(running)})")
                if args.dry_run:
                    # In dry-run, don't actually wait — just simulate one iteration
                    running.clear()
                    break
                time.sleep(args.stagger)

            if args.dry_run:
                break

            # Wait for any agent to finish (poll)
            time.sleep(2)
            finished_idx = None
            for idx, (aid, proc, base, start, _lf) in enumerate(running):
                reason = check_agent_deadline(aid, proc, base, start)
                if reason is not None:
                    finished_idx = idx
                    break

            if finished_idx is None:
                continue

            harvest(finished_idx)

            if not queue_has_work():
                log("queue détectée vide — arrêt après les sous-agents en cours.")
                break

        # Drain remaining slots — keep applying the 3-layer check until each
        # agent exits (or hits a kill condition).
        log(f"drain : {len(running)} sous-agent(s) en cours")
        while running:
            time.sleep(2)
            finished_idx = None
            for idx, (aid, proc, base, start, _lf) in enumerate(running):
                reason = check_agent_deadline(aid, proc, base, start)
                if reason is not None:
                    finished_idx = idx
                    break
            if finished_idx is None:
                continue
            harvest(finished_idx)

    except KeyboardInterrupt:
        log("KeyboardInterrupt — kill des sous-agents et audits en cours")
        for aid in list(pending_audits):
            cleanup_pending_audit(aid)
        for aid, proc, _, _, log_file in running:
            if proc and proc.poll() is None:
                kill_tree(proc)
            if log_file is not None:
                try:
                    log_file.close()
                except OSError:
                    pass

    flags_md = scan_flags(run_dir)
    flags_path = run_dir / "FLAGS.md"
    flags_path.write_text(flags_md)
    log(f"flags : {flags_path.relative_to(REPO_ROOT)}")
    print("\n" + "=" * 60)
    print(flags_md)
    orch_log.close()


if __name__ == "__main__":
    main()
