#!/usr/bin/env python3
"""task.py — dispatcher du flux normal de la pipeline de consolidation.

Mutateur unique de `2-consolide/outils/tasks.csv`. **Tout sous `flock`** (`_store.locked`),
1 commit scopé par transition (`git commit -- <paths>`, jamais `git add .`).
Sessions jetables : **un agent prend une seule tâche, la termine, sort** ;
l'orchestrateur relance à la chaîne (plafond 1 tâche/session, cf. `cli.md`).

Verbes (S5 — flux normal · S6 — gate de fidélité 2/2) :
  claim_next [--type map|reduce|validate]
                             **CLAIME** (réservé aux agents spawnés par l'orchestrateur).
                             map|reduce : sélectionne+claim 1 tâche prenable
                             (ordre type,id ; gating sous flock), imprime `TASK: <type>
                             <id>` + contexte `input:`/`note:`/`session:` (cf. cli.md).
                             validate : prend une passe sur un reduce `to_validate`
                             (garde distinct-agent, `owner=<short>`, status inchangé).
  peek_next [--type map|reduce|validate]
                             **LECTURE SEULE** : imprime le candidat que `claim_next`
                             prendrait (même sélection/gating) SANS muter ni committer.
                             Verbe d'inspection « qu'est-ce qui vient » avant/pendant un run.
  claim <id>                 échappatoire ciblée : même gating/transition sur un id.
  done <id> [--output P]     lance check.py ; échec → refuse (reste claimed).
                             OK map → done ; OK reduce → to_validate (author:<short>).
  approve <id>               append `ok:<short>` ; 2e distinct → done. Garde owner +
                             distinct-agent (≠ author, ≠ ok déjà présent).
  split <id> <child-input>…  parent → split ; append enfants map todo (parent=<id>).
  release <id> [--reason …] [--status todo|blocked|abandon]
                             rend la tâche (claimed→todo) ou la marque blocked/abandon.
  stale [--why]              LECTURE SEULE : liste les reduces done périmés (fragment
                             de leur thème (re)mappé après leur done_at — sémantique Make).
  reopen <reduce:clé>|<map:src>… | --stale
                             reduce done→todo, supprime les enfants validate ; map
                             done→todo (re-run, re-route vers une clé neuve) ; --stale
                             rouvre tous les reduces périmés du scan (cf. specs/stale.md).

Spec : `2-consolide/outils/docs/specs/cli.md`, `modele-donnees.md`, `check.md`, `validate.md`, `scoping.md`.

Usage (cf. common/outils/CLAUDE.md — invocation directe, pas `python3`) :
  2-consolide/outils/task.py peek_next            # inspection read-only (ne claime PAS)
  2-consolide/outils/task.py claim_next           # claime (agents orchestrés)
  2-consolide/outils/task.py claim_next --type map
  2-consolide/outils/task.py done map:foo --output 2-consolide/2.1-fragments/foo.md
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _store  # noqa: E402

CLAIMABLE = "todo"

# Cap de citations par shard de validation (cf. 2-consolide/outils/docs/specs/validate.md
# § cite_buckets). Vise
# ≤ ~12-15 cites/shard, ~60 s sous le cap de 300 s d'un validateur.
MAX_CITES_PER_SHARD = 12


# --- Sélection / gating ---------------------------------------------------

def find_row(rows: "list[dict]", task_id: str) -> "dict | None":
    return next((r for r in rows if r["id"] == task_id), None)


_THEME_HEADING = re.compile(r"^## theme:(\S+)\s*$", re.M)


def present_reduce_themes(root: Path) -> "set[str]":
    """Ensemble des clés `<key>` portées par ≥1 `2-consolide/2.1-fragments/*.md`
    (`## theme:<key>`). **Un seul balayage des fragments** — sert le gating
    reduce de TOUS les candidats d'un `next` (vs un grep par candidat :
    O(fragments) au lieu de O(reduces × fragments) par appel). Reproduit le
    `grep -l "## theme:<clé>"` de cli.md § Gating, en set.
    """
    frag_dir = _store.fragments_dir(root)
    themes: "set[str]" = set()
    if not frag_dir.is_dir():
        return themes
    for frag in frag_dir.glob("*.md"):
        themes.update(_THEME_HEADING.findall(frag.read_text(encoding="utf-8")))
    return themes


# --- Scan stale (read-only — sémantique Make, cf. docs/specs/stale.md) -----

def scan_stale(rows: "list[dict]", root: Path) -> "list[tuple[dict, list[str]]]":
    """Reduces `done` périmés : un fragment portant leur thème a été (re)mappé
    **après** leur `done_at`. Modèle Make (target = `reduce:<clé>`, prereqs =
    fragments `## theme:<clé>`, stale = `max(map.done_at touchant <clé>) > reduce.done_at`).

    **Lecture seule**, un seul balayage des fragments. Retourne `[(reduce_row, [ids
    de maps fautifs])]` trié par id de reduce — la liste des maps fautifs sert le
    `--why` et reste vide si on ne la consulte pas. Le fragment projeté `arbitrages.md`
    n'a **pas** de ligne map → invisible ici tant que la projection ne pose pas de
    `done_at` (cf. stale.md ; gap connu, hors lot soir).
    """
    # clé de thème -> (done_at le plus récent, [ids des maps done qui la portent])
    theme_maps: "dict[str, list[tuple[str, str]]]" = {}
    for m in rows:
        if m["type"] != "map" or m["status"] != "done":
            continue
        output = m["output"] or default_output(m)
        path = root / output
        if not path.exists():
            continue
        for key in set(_THEME_HEADING.findall(path.read_text(encoding="utf-8"))):
            theme_maps.setdefault(key, []).append((m["done_at"], m["id"]))

    stale = []
    for r in rows:
        if r["type"] != "reduce" or r["status"] != "done":
            continue
        contributors = theme_maps.get(r["input"], [])
        culprits = [mid for done_at, mid in contributors if done_at > r["done_at"]]
        if culprits:
            stale.append((r, sorted(culprits)))
    stale.sort(key=lambda pair: pair[0]["id"])
    return stale


def is_takeable(row: "dict", root: Path, present_themes: "set[str] | None" = None) -> bool:
    """Une tâche est prenable si `status=todo` et — pour reduce — le gating
    fragment passe. Les `split`/`claimed`/`to_validate`/`done` sont exclus
    d'office (status ≠ todo). `present_themes` : set pré-calculé des thèmes
    portés par un fragment (cf. `present_reduce_themes`) — passé par `next`
    pour ne scanner qu'une fois ; `None` → scan ponctuel (claim d'un seul id)."""
    if row["status"] != CLAIMABLE:
        return False
    if row["type"] == "map":
        return True
    if row["type"] == "reduce":
        if present_themes is None:
            present_themes = present_reduce_themes(root)
        return row["input"] in present_themes
    return False


# --- Bookkeeping de validation (note d'un reduce en to_validate) ----------
# `note` porte `author:<short>` (posé au done reduce), les approbations
# distinctes `ok:<short>`, et les correcteurs `fix:<short>` (exclus comme
# l'auteur après un `corrigé`), tokens séparés par espace (cf. modele-donnees.md
# § Bookkeeping). C'est ce champ que lit la garde distinct-agent.

def parse_validation_note(note: str) -> "tuple[str | None, list[str], list[str]]":
    """`note` → (author, [ok…], [fix…]) : auteur du reduce, approbations distinctes,
    correcteurs `corrigé` (exclus comme l'auteur). Tokens séparés par espace."""
    author = None
    oks: "list[str]" = []
    fixers: "list[str]" = []
    for tok in note.split():
        if tok.startswith("author:"):
            author = tok[len("author:"):]
        elif tok.startswith("ok:"):
            oks.append(tok[len("ok:"):])
        elif tok.startswith("fix:"):
            fixers.append(tok[len("fix:"):])
    return author, oks, fixers


def format_validation_note(author: "str | None", oks: "list[str]",
                           fixers: "list[str] | None" = None) -> str:
    """(author, [ok…], [fix…]) → `author:A ok:B … fix:C …`."""
    toks = [f"author:{author}"] if author else []
    toks += [f"ok:{o}" for o in oks]
    toks += [f"fix:{f}" for f in (fixers or [])]
    return " ".join(toks)


# --- Lease de correction (token `correcting:<short>` sur le reduce parent) -
# Sérialise les correcteurs concurrents d'un même `2-consolide/2.2-content/<clé>.md` partagé :
# un seul correcteur édite le consolidé à la fois (cf. CORRECT_VALIDATE.md
# § Lease). Token libre dans la note du reduce `split`, distinct des tokens de
# validation (author:/ok:/fix:, ignorés par `parse_validation_note`).

_LEASE = "correcting:"


def parse_lease(note: str) -> "str | None":
    """Short du correcteur tenant la lease `correcting:<short>`, ou `None`."""
    for tok in note.split():
        if tok.startswith(_LEASE):
            return tok[len(_LEASE):]
    return None


def set_lease(note: str, short: str) -> str:
    """Pose `correcting:<short>` sur la note (remplace une lease existante,
    laisse les autres tokens intacts) — idempotent pour le même short."""
    return " ".join([*clear_lease(note).split(), f"{_LEASE}{short}"])


def clear_lease(note: str) -> str:
    """Retire le token `correcting:*` de la note (laisse les autres intacts)."""
    return " ".join(t for t in note.split() if not t.startswith(_LEASE))


def held_lease_parents(rows: "list[dict]") -> "set[str]":
    """Ids des reduce parents qui **tiennent** une lease `correcting:<short>` sur
    leur note. Un shard `validate` dont le `parent` est dans ce set est sous
    correction : son contenu va être reset-all (cf. `_reset_validate_siblings`) — le
    sémaphore de sélection NE doit jamais le rendre (`is_validatable` côté agent,
    `peek_schedule` côté orchestrateur). Un claim ne rend jamais un truc verrouillé.
    Un seul balayage des notes, set partagé par les deux chemins de sélection
    (même pattern que `present_reduce_themes` pour le gating reduce)."""
    return {r["id"] for r in rows if parse_lease(r["note"])}


# --- Sharding du gate validate (buckets de sources) -----------------------
# Au `done` d'un reduce, on éclate le gate 2/2 en lignes-enfants `validate`,
# une par paquet de sources (cf. 2-consolide/outils/docs/specs/validate.md § cite_buckets). Pur :
# parse les refs du consolidé, aucune I/O CSV/git.

# Mirroir du motif `ONE_REF` de check.py — une citation `[src:…]` / `[res:…]` / `[arb:…]`.
_ONE_REF = re.compile(r"\[(?P<kind>src|res|arb):(?P<body>[^\]]+)\]")

# Slug de bucket commun à TOUTES les cites `[arb:NNNN]` : un arbitrage résout contre
# son propre fichier ADR (fait trivialement présent), pas une source brute → on ne veut
# pas 1 shard validate par décision. Toutes les cites arb tombent dans un seul bucket.
_ARB_SLUG = "arbitrages"


def _ref_slug(kind: str, body: str) -> str:
    """Slug groupant d'une citation : `body` sans ancre (`§…`/`#…`), 1er token ;
    pour un `res:`, 1er segment avant `/` (`foo/slide-03.png` → `foo`) ; pour un
    `arb:`, constante `arbitrages` (toutes les décisions = un seul bucket de validation)."""
    if kind == "arb":
        return _ARB_SLUG
    loc = body.split("§", 1)[0].split("#", 1)[0]
    tokens = loc.split()
    if not tokens:
        return ""
    slug = tokens[0]
    if kind == "res":
        slug = slug.split("/", 1)[0]
    return slug


def cite_buckets(consolide_path) -> "list[list[str]]":
    """Découpe les sources d'un consolidé en buckets de citations pour shader
    le gate validate (cf. 2-consolide/outils/docs/specs/validate.md § cite_buckets). Pur : lit le
    consolidé, ne touche ni CSV ni git.

    Compte les citations par slug, puis bucketise glouton sur les slugs triés :
    on empile tant que la somme des comptes `≤ MAX_CITES_PER_SHARD`, au
    dépassement on ferme le bucket et on en ouvre un neuf. Une source seule
    très citée (compte > cap) occupe son propre bucket (atome, jamais coupée) ;
    un consolidé peu cité (total ≤ cap) → 1 seul bucket. Sans aucune ref → `[]`.
    """
    text = Path(consolide_path).read_text(encoding="utf-8")
    counts: "dict[str, int]" = {}
    for m in _ONE_REF.finditer(text):
        slug = _ref_slug(m.group("kind"), m.group("body"))
        if slug:
            counts[slug] = counts.get(slug, 0) + 1

    buckets: "list[list[str]]" = []
    current: "list[str]" = []
    current_sum = 0
    for slug in sorted(counts):  # ordre trié → sortie déterministe
        n = counts[slug]
        if current and current_sum + n > MAX_CITES_PER_SHARD:
            buckets.append(current)
            current, current_sum = [], 0
        current.append(slug)
        current_sum += n
    if current:
        buckets.append(current)
    return buckets


def is_validatable(row: "dict", short: str,
                   locked_parents: "set[str] | None" = None) -> bool:
    """Enfant `validate:<clé>#n` prenable pour une passe de validation :
    `to_validate`, **aucune passe en cours** (`owner` vide), **parent non sous
    correction**, et garde distinct-agent — `short` ≠ auteur, ≠ tout correcteur
    `fix:`, et ≠ tout `ok:` déjà enregistré (per-row, sur la `note` de l'enfant ;
    cf. validate.md § Garde distinct-agent).

    `locked_parents` : set pré-calculé des reduce parents tenant une lease
    `correcting:` (cf. `held_lease_parents`) — passé par `_select_validate` pour
    exclure d'office les shards sous correction (le sémaphore ne rend jamais un truc
    verrouillé : ces shards vont être reset-all). `None` → pas de gating lease
    (vérif d'un seul row hors flux normal — tests).
    Le reduce parent est désormais `split` (non terminal) et n'est jamais prenable."""
    if row["type"] != "validate" or row["status"] != "to_validate":
        return False
    if row["owner"]:                       # passe déjà en cours par un validateur
        return False
    if locked_parents and row["parent"] in locked_parents:
        return False                       # parent sous correction → shard verrouillé
    author, oks, fixers = parse_validation_note(row["note"])
    return short != author and short not in fixers and short not in oks


# --- Sorties (chemins d'artefact par défaut) ------------------------------

def default_output(row: "dict") -> str:
    """Artefact par défaut : map → `2-consolide/2.1-fragments/<slug>.md` ;
    reduce → `2-consolide/2.2-content/<theme>.md`. Surchargé par `--output`."""
    ident = row["id"].split(":", 1)[1]
    if row["type"] == "map":
        return f"2-consolide/2.1-fragments/{ident}.md"
    return f"2-consolide/2.2-content/{row['input']}.md"


def require_owner(row: "dict", short: str) -> None:
    """Garde : on n'agit (done/split) que sur **sa propre** tâche claimée."""
    if row["owner"] != short:
        _store.die(f"{row['id']} claimé par {row['owner']!r} ≠ {short!r} (session courante)")


# --- Transition partagée claim (next / claim) -----------------------------

def _print_task_context(row: "dict", short: str) -> None:
    """Imprime, **sous** la ligne `TASK:`, le contexte de démarrage de la tâche —
    tout ce dont l'agent a besoin pour commencer **sans re-grepper `tasks.csv`**.
    Une paire `clé: valeur` par ligne (valeur vide → `clé:`),
    format stable documenté dans `2-consolide/outils/docs/specs/cli.md` § Sortie de `claim_next` :

      input:   col `input` de la ligne (chemin source d'un map / clé de thème d'un
               reduce/validate ; porte la plage `#L<a>-<b>` d'un sous-lot splitté).
      note:    col `note` (p. ex. `oversize` → c'est une tâche de scoping).
      session: ton short — l'`owner` que ce claim **vient d'écrire** dans le CSV
               (= `map_session` du fragment).
    """
    for key, val in (("input", row["input"]), ("note", row["note"]), ("session", short)):
        print(f"{key}: {val}" if val else f"{key}:")


def _do_claim(root: Path, row: "dict", rows: "list[dict]", short: str, commit: bool) -> None:
    row["status"] = "claimed"
    row["owner"] = short
    row["claimed_at"] = _store.now()
    _store.write_tasks(root, rows)
    # Purge de l'output au claim d'un **reduce** : le consolidé est une fonction pure
    # des fragments, pas une source — l'ancienne version est de la sortie périmée. La
    # supprimer ici (et nulle part en amont : `reopen` la laisse, la KB reste grepable
    # toute la semaine d'arbitrage) force l'agent à un `Write` neuf au lieu d'un `Edit`
    # — qui exigerait un `Read` préalable (friction harnais) et **ancrerait** l'agent
    # sur l'ancien texte au lieu de re-dériver des fragments. Seul le reduce
    # *réellement pris* purge SON fichier, juste avant de le réécrire. `missing_ok` :
    # un reduce jamais réduit (formation-* `todo`) n'a pas de fichier. Sous le flock du
    # claim ; non committée → un crash post-claim laisse une suppression transitoire
    # en working tree (HEAD intact), réécrite au re-claim.
    if row["type"] == "reduce":
        (root / default_output(row)).unlink(missing_ok=True)
    if commit:
        _store.commit(root, [_store.tasks_path(root)], f"Claim {row['id']} ({short})")
    print(f"TASK: {row['type']} {row['id']}")
    _print_task_context(row, short)


# --- Sélection partagée (claim_next / peek_next) --------------------------
# Même logique de sélection des deux côtés ; seul l'effet diffère (claim_next
# mute+commit, peek_next ne fait que lire). Ces deux helpers sont **read-only** —
# ils sont appelés sous le flock par `claim_next` (avant mutation) et hors flock
# par `peek_next` (lecture seule, jamais de mutation).

def _select_production(rows: "list[dict]", root: Path, type_: "str | None") -> "dict | None":
    """1er candidat production prenable (map|reduce), ordre déterministe `(type, id)`,
    ou `None`. `--type map` court-circuite le balayage des fragments (aucun candidat
    reduce). Lecture seule."""
    present = set() if type_ == "map" else present_reduce_themes(root)
    cands = [r for r in rows
             if (type_ is None or r["type"] == type_)
             and is_takeable(r, root, present)]
    if not cands:
        return None
    cands.sort(key=lambda r: (r["type"], r["id"]))  # ordre déterministe : type puis id
    return cands[0]


def _select_validate(rows: "list[dict]", short: str) -> "dict | None":
    """1er enfant `validate:<clé>#n` `to_validate` prenable pour une passe de
    validation (garde distinct-agent **+ parent non sous correction**), ordre
    déterministe `id`, ou `None`. Lecture seule."""
    locked = held_lease_parents(rows)
    cands = [r for r in rows if is_validatable(r, short, locked)]
    if not cands:
        return None
    cands.sort(key=lambda r: r["id"])  # ordre déterministe
    return cands[0]


def cmd_claim_next(root: Path, args, short: str) -> int:
    if args.type == "validate":
        return _claim_next_validate(root, args, short)
    with _store.locked(root):
        rows = _store.read_tasks(root)
        row = _select_production(rows, root, args.type)
        if row is None:
            _store.die("rien à prendre" + (f" (--type {args.type})" if args.type else ""))
        _do_claim(root, row, rows, short, commit=not args.no_commit)
    return 0


def _claim_next_validate(root: Path, args, short: str) -> int:
    """`claim_next --type validate` : prend une passe sur un reduce `to_validate`
    prenable (garde distinct-agent), enregistre le validateur en `owner`
    **sans muter `status`** (reste `to_validate`)."""
    with _store.locked(root):
        rows = _store.read_tasks(root)
        row = _select_validate(rows, short)
        if row is None:
            _store.die("rien à valider")
        row["owner"] = short               # passe en cours ; status inchangé
        _store.write_tasks(root, rows)
        if not args.no_commit:
            _store.commit(root, [_store.tasks_path(root)],
                          f"Take-validate {row['id']} ({short})")
    print(f"TASK: validate {row['id']}")
    _print_task_context(row, short)
    return 0


def cmd_peek_next(root: Path, args, short: str) -> int:
    """`peek_next` : **lecture seule**. Imprime le candidat que `claim_next`
    prendrait (même sélection/gating), SANS muter le CSV ni committer. Verbe
    d'inspection « qu'est-ce qui vient » avant/pendant un run de l'orchestrateur.
    Aucun `write_tasks`, aucun `commit` : pas de flock nécessaire (read-only)."""
    rows = _store.read_tasks(root)
    if args.type == "validate":
        row = _select_validate(rows, short)
        if row is None:
            print("rien à prendre (--type validate)")
            return 0
        print(f"TASK: validate {row['id']}")
        return 0
    row = _select_production(rows, root, args.type)
    if row is None:
        print("rien à prendre" + (f" (--type {args.type})" if args.type else ""))
        return 0
    print(f"TASK: {row['type']} {row['id']}")
    return 0


def cmd_claim(root: Path, args, short: str) -> int:
    with _store.locked(root):
        rows = _store.read_tasks(root)
        row = find_row(rows, args.id) or _store.die(f"id inconnu: {args.id}")
        if not is_takeable(row, root):
            _store.die(f"{args.id} non prenable (status={row['status']}, type={row['type']})")
        _do_claim(root, row, rows, short, commit=not args.no_commit)
    return 0


# --- append partagé : split parent + lignes-enfants -----------------------

def _split_into_children(rows: "list[dict]", parent: "dict",
                         specs: "list[dict]") -> "list[dict]":
    """Pattern d'append commun à `split` et `done`-reduce : crée une ligne-enfant par
    `spec` (kwargs de `_store.new_row`, `id` obligatoire), refuse un id déjà présent,
    passe le parent en `split` (owner lâché) et ajoute les enfants à `rows`.
    `split` n'est pas terminal — claim_next/peek_next l'ignorent, les enfants portent
    l'état. Retourne les enfants créés."""
    existing = {r["id"] for r in rows}
    children = []
    for spec in specs:
        cid = spec["id"]
        if cid in existing:
            _store.die(f"enfant déjà présent: {cid}")
        children.append(_store.new_row(**spec))
    parent["status"] = "split"
    parent["owner"] = ""
    rows.extend(children)
    return children


def _is_validate_shard(row: "dict", parent_id: str) -> bool:
    """Vrai si `row` est un enfant `validate` (frère de shard) du reduce `parent_id`.
    Prédicat partagé par le rollup (approve) et le reset-all (corrige)."""
    return row["parent"] == parent_id and row["type"] == "validate"


def _reset_validate_siblings(rows: "list", parent_id: str, fixer: str) -> None:
    """Reset-all d'un `corrigé` : tous les frères `validate` du reduce `parent_id`
    repartent `to_validate` 0/2 — le contenu qu'ils avaient relu a changé. `author:`
    d'origine + `fix:` antérieurs préservés, `fix:<fixer>` ajouté (correcteur exclu
    des passes suivantes), les `ok:` tombent, owner/done_at vidés. Mutation in-place
    sous le flock CSV de l'appelant."""
    for sib in [r for r in rows if _is_validate_shard(r, parent_id)]:
        author, _oks, fixers = parse_validation_note(sib["note"])
        if fixer not in fixers:
            fixers.append(fixer)
        sib["status"] = "to_validate"
        sib["owner"] = ""
        sib["done_at"] = ""
        sib["note"] = format_validation_note(author, [], fixers)


# --- done -----------------------------------------------------------------

def cmd_done(root: Path, args, short: str) -> int:
    import check  # même dossier — gate de sourçage déterministe (check.md)
    with _store.locked(root):
        rows = _store.read_tasks(root)
        row = find_row(rows, args.id) or _store.die(f"id inconnu: {args.id}")
        if row["status"] != "claimed":
            _store.die(f"{args.id} pas en claimed (status={row['status']})")
        require_owner(row, short)

        output = args.output or default_output(row)
        mode = "fragment" if row["type"] == "map" else "consolide"
        if check.main([mode, output, "--repo-root", str(root)]) != 0:
            _store.die(f"check.py refuse {args.id} (artefact attendu : {output}) — "
                       "corrige le fichier ou passe --output ; reste claimed")

        row["output"] = output
        if row["type"] == "map":
            row["status"] = "done"
            row["done_at"] = _store.now()
            msg = f"Done {args.id} ({short})"
        else:  # reduce : passe le gate déterministe → shard le 2/2 par source
            buckets = cite_buckets(root / output)
            if not buckets:                # RB6 : refuser plutôt qu'un reduce non shardé
                _store.die(f"{args.id} : aucune source résolvable dans {output} — "
                           "rien à valider (le check exige ≥1 cite) ; reste claimed")
            key = args.id.split(":", 1)[1]            # reduce:<clé> → <clé>
            specs = [                                  # un enfant validate par bucket
                dict(id=f"validate:{key}#{n}", type="validate", status="to_validate",
                     parent=args.id, input=f"{output}#sources={','.join(bucket)}",
                     output=output, note=f"author:{short}")
                for n, bucket in enumerate(buckets, 1)
            ]
            children = _split_into_children(rows, row, specs)  # parent → split, owner lâché (S6)
            msg = f"To-validate {args.id} → {len(children)} shard(s) ({short})"
        _store.write_tasks(root, rows)
        if not args.no_commit:
            _store.commit(root, [root / output, _store.tasks_path(root)], msg)
    print(f"{row['status'].upper()}: {row['type']} {args.id}")
    return 0


# --- approve (issue de validation : le `ok`) ------------------------------

def _apply_plus_one(rows: "list", row: dict, short: str) -> int:
    """+1 distinct vers 2/2 — mécanique partagée `approve`/`signale`. Vérifie le
    distinct-agent (≠ author, ≠ oks déjà posés), append `ok:<short>` ; 2e distinct →
    enfant `done` + rollup du reduce `split` (si TOUS les frères validate sont done,
    le parent non terminal roule jusqu'à `done` — même flock, pas de TOCTOU) ; sinon
    1er ok → owner libéré pour le 2e valideur. Renvoie le nombre d'oks (1 ou 2).
    Mutation in-place sous le flock CSV de l'appelant."""
    author, oks, _fixers = parse_validation_note(row["note"])
    if short == author or short in oks:    # garde distinct-agent (défense)
        _store.die(f"{short} déjà engagé sur {row['id']} (author/ok) — distinct requis")
    oks.append(short)
    if len(oks) >= 2:                      # 2e ok distinct → done
        row["status"] = "done"
        row["done_at"] = _store.now()
        row["owner"] = ""
        row["note"] = ""                   # bookkeeping nettoyé
        parent = find_row(rows, row["parent"]) if row["parent"] else None
        if parent and parent["status"] == "split":
            siblings = [r for r in rows if _is_validate_shard(r, parent["id"])]
            if siblings and all(s["status"] == "done" for s in siblings):
                parent["status"] = "done"
                parent["done_at"] = _store.now()
    else:                                  # 1er ok : passe finie, owner libéré
        row["owner"] = ""
        row["note"] = format_validation_note(author, oks)
    return len(oks)


def cmd_approve(root: Path, args, short: str) -> int:
    with _store.locked(root):
        rows = _store.read_tasks(root)
        row = find_row(rows, args.id) or _store.die(f"id inconnu: {args.id}")
        if row["status"] != "to_validate":
            _store.die(f"{args.id} pas en to_validate (status={row['status']})")
        require_owner(row, short)          # on n'approuve que la passe qu'on a prise
        n = _apply_plus_one(rows, row, short)
        _store.write_tasks(root, rows)
        if not args.no_commit:
            _store.commit(root, [_store.tasks_path(root)], f"Validate {args.id}: {n}/2 ({short})")
    print(f"VALIDATE: {args.id} {n}/2" + (" → done" if row["status"] == "done" else ""))
    return 0


# --- corrige (verdict `corrigé` : édition en place du consolidé) ----------

def cmd_corrige(root: Path, args, short: str) -> int:
    """Verdict `corrigé` : le correcteur tient la lease (`claim-correct`) et a édité
    `2-consolide/2.2-content/<clé>.md` — soit corrigé une distorsion en place, soit, si
    l'ambiguïté n'est pas tranchable, **ajouté le flou ouvert à la section `## Points
    flous`** (la fiche reste autoporteuse). Sous flock CSV unique (cf. CORRECT_VALIDATE.md
    § cmd_corrige) : exige la lease (`correcting:<short>` sur le reduce parent, sinon die) ;
    re-lance check.py sur le consolidé (un fix ne peut pas casser le sourçage → **refus +
    garde la lease** si KO, l'agent re-corrige et relance) ; **reset-all** des frères
    `validate` à `to_validate` 0/2 (les `ok:` tombent, `fix:<short>` ajouté, `fix:`
    antérieurs préservés, `author:` d'origine conservé) ; le parent reste `split`, lease
    clearée ; commit scopé unique `[consolidé, tasks.csv]`."""
    import check  # même dossier — re-gate de sourçage déterministe après le fix
    with _store.locked(root):
        rows = _store.read_tasks(root)
        row = find_row(rows, args.id) or _store.die(f"id inconnu: {args.id}")
        parent = find_row(rows, row["parent"]) if row["parent"] else None
        if not parent:
            _store.die(f"{args.id} sans reduce parent — pas de correction en place")
        if parse_lease(parent["note"]) != short:   # la lease est le gate du `corrigé`
            _store.die(f"corrige {args.id} exige la lease de correction "
                       f"(correcting:{short} sur {parent['id']}) — claim-correct d'abord")

        output = parent["output"] or row["output"]
        if check.main(["consolide", output, "--repo-root", str(root)]) != 0:
            _store.die(f"check.py refuse {output} après correction — un fix ne peut pas "
                       "casser le sourçage ; garde la lease, re-corrige et relance")

        # reset-all : tous les frères `validate` repartent `to_validate` 0/2 (le contenu
        # qu'ils avaient relu a changé) ; le correcteur `short` est ajouté aux `fix:`.
        _reset_validate_siblings(rows, parent["id"], short)

        parent["note"] = clear_lease(parent["note"])   # parent reste `split`, lease libérée

        _store.write_tasks(root, rows)
        if not args.no_commit:
            msg = f"Corrige {args.id} ({short})"
            if args.reason:
                msg += f" — {args.reason}"
            _store.commit(root, [root / output, _store.tasks_path(root)], msg)
    print(f"CORRIGE: {args.id} → reset-all des frères, {parent['id']} reste split")
    return 0


# --- claim-correct (lease de correction sur le reduce parent) -------------

def cmd_claim_correct(root: Path, args, short: str) -> int:
    """Pose la lease `correcting:<short>` sur la note du reduce parent `split`
    (sérialise les correcteurs concurrents d'un consolidé partagé, cf.
    CORRECT_VALIDATE.md § Lease) — **refus** si un autre correcteur la tient.
    Sous flock CSV ; l'édition cognitive du consolidé qui suit reste hors flock,
    sérialisée par cette lease durable."""
    with _store.locked(root):
        rows = _store.read_tasks(root)
        row = find_row(rows, args.id) or _store.die(f"id inconnu: {args.id}")
        parent = find_row(rows, row["parent"]) if row["parent"] else None
        if not parent:
            _store.die(f"{args.id} sans reduce parent — pas de lease de correction")
        holder = parse_lease(parent["note"])
        if holder and holder != short:        # lease tenue par un autre correcteur
            _store.die(f"lease de correction tenue par {holder!r} sur {parent['id']} — "
                       f"un seul correcteur par reduce (attends ou prends un autre shard)")
        parent["note"] = set_lease(parent["note"], short)
        _store.write_tasks(root, rows)
        if not args.no_commit:
            _store.commit(root, [_store.tasks_path(root)],
                          f"Claim-correct {args.id} ({short})")
    print(f"CLAIM-CORRECT: {args.id} → correcting:{short} sur {parent['id']}")
    return 0


# --- split ----------------------------------------------------------------

def cmd_split(root: Path, args, short: str) -> int:
    with _store.locked(root):
        rows = _store.read_tasks(root)
        parent = find_row(rows, args.id) or _store.die(f"id inconnu: {args.id}")
        if parent["status"] != "claimed":
            _store.die(f"{args.id} pas en claimed (status={parent['status']})")
        require_owner(parent, short)

        specs = [
            dict(id=f"{args.id}#{k}", type="map", status="todo",
                 parent=args.id, input=child_input)
            for k, child_input in enumerate(args.child_inputs, 1)
        ]
        children = _split_into_children(rows, parent, specs)
        _store.write_tasks(root, rows)
        if not args.no_commit:
            _store.commit(root, [_store.tasks_path(root)],
                          f"Split {args.id} → {len(children)} ({short})")
    print(f"SPLIT: {args.id} → {len(children)} enfant(s)")
    return 0


# --- release --------------------------------------------------------------

def cmd_release(root: Path, args, short: str) -> int:
    if getattr(args, "force_orphan", False):
        return _force_orphan_release(root, args)
    with _store.locked(root):
        rows = _store.read_tasks(root)
        row = find_row(rows, args.id) or _store.die(f"id inconnu: {args.id}")
        if row["status"] != "claimed":
            _store.die(f"{args.id} pas en claimed (status={row['status']})")

        if args.status == "todo":
            row["status"] = "todo"
            row["owner"] = ""
            row["claimed_at"] = ""
            if args.reason:                 # trace optionnelle ; sinon on préserve `oversize`
                row["note"] = args.reason
        else:  # blocked | abandon
            row["status"] = args.status
            row["owner"] = ""
            if args.reason:
                row["note"] = args.reason
        _store.write_tasks(root, rows)
        if not args.no_commit:
            _store.commit(root, [_store.tasks_path(root)], f"Release {args.id} ({short})")
    print(f"RELEASE: {args.id} → {row['status']}")
    return 0


# --- release --force-orphan (chemin admin orchestrateur) ------------------
# Récupère un verrou laissé par un agent **mort** (tué par le cap/sliding/audit,
# crashé, ou sorti sans release) : sans ça, un reduce orphelin `to_validate` gèle
# le gate 2/2 pour tout le run. Calqué sur `release.py --force-abandon-orphan` côté
# `ressources` (watchdog.md §6) : on **bypasse** la garde « tu dois posséder le
# lock » mais on **vérifie que le verrou appartient bien à `<short>`** (le short de
# l'agent tué, R51). Si `owner != <short>` → no-op loggé (l'agent a pu release juste
# avant le kill, ou un autre a reclaim) ; pas de TOCTOU car tout passe sous le flock.

FORCE_ORPHAN_NOOP_RC = 3   # rc dédié du no-op : l'appelant (orchestrateur) distingue
                           # récup réelle (0) / no-op (3) / échec (autre) sans parser stdout


def _force_orphan_release(root: Path, args) -> int:
    """Sous flock : `<id>` est-il `claimed`/`to_validate` avec `owner == <short>`
    (`args.force_orphan`, le short de l'agent tué) ? Si oui :
    - `claimed` (orphelin de production) → reset `status→todo`, vide `owner`/`claimed_at` ;
    - `to_validate` (enfant `validate`, passe abandonnée) → **reset du gate à 0/2** :
      reste `to_validate` (re-prenable ; le repasser `todo` le **gèlerait** — `is_validatable`
      exige `to_validate`), owner vidé, note ramenée à `author:` seul (les `ok:` acquis
      tombent, la garde distinct-agent reste).
    `output` préservé dans les deux cas (et la note `oversize` d'un `claimed`). Sinon
    **no-op** loggé, rc `FORCE_ORPHAN_NOOP_RC` (≠ 0 : une récup réelle et un no-op ne
    doivent pas se confondre côté orchestrateur) — soit pas d'orphelin (owner
    vide / mauvais statut), soit l'owner ne matche pas le short (release juste avant
    le kill / reclaim). Commit scopé `2-consolide/outils/tasks.csv` UNIQUEMENT, **best-effort**
    : log + continue si le commit échoue (R1 : seul `task.py` mute, sous flock)."""
    short = args.force_orphan
    with _store.locked(root):
        rows = _store.read_tasks(root)
        row = find_row(rows, args.id) or _store.die(f"id inconnu: {args.id}")
        if row["status"] not in ("claimed", "to_validate") or not row["owner"]:
            print(f"FORCE-ORPHAN: {args.id} no-op "
                  f"(status={row['status']}, owner={row['owner']!r})")
            return FORCE_ORPHAN_NOOP_RC
        if row["owner"] != short:           # garde owner==short (R51) : sinon no-op
            print(f"FORCE-ORPHAN: {args.id} no-op "
                  f"(owner={row['owner']!r} ≠ short={short!r})")
            return FORCE_ORPHAN_NOOP_RC
        if row["status"] == "to_validate":  # enfant validate orphelin : reset du gate à 0/2
            # passe abandonnée libérée — l'enfant reste `to_validate` (re-prenable),
            # owner vidé, note ramenée à `author:` seul (les `ok:` acquis tombent → 0/2).
            # On NE repasse PAS `todo` : `is_validatable` l'exclurait → enfant gelé.
            row["owner"] = ""
            author, _oks, _fixers = parse_validation_note(row["note"])
            row["note"] = format_validation_note(author, [])
        else:                              # orphelin de production (claimed) → todo
            row["status"] = "todo"
            row["owner"] = ""
            row["claimed_at"] = ""
        # `output` préservé dans les deux cas ; la note `oversize` d'un `claimed` aussi.

        # Orphelin **correcteur** : si le short tient la lease de correction du reduce
        # parent, la clear ET restaure le consolidé committé (la version que les
        # valideurs relisent) — sinon un correcteur mort laisse un working-tree dirty
        # validé 2/2 ≠ committé (cf. CORRECT_VALIDATE.md § Orphelin correcteur).
        parent = find_row(rows, row["parent"]) if row["parent"] else None
        if parent and parse_lease(parent["note"]) == short:
            parent["note"] = clear_lease(parent["note"])
            consolide = parent["output"] or row["output"]
            if consolide and not args.no_commit:   # git checkout best-effort, scopé
                try:
                    _store.checkout(root, [root / consolide])
                except Exception as e:     # noqa: BLE001 — best-effort, on ne plante pas le run
                    print(f"FORCE-ORPHAN: git checkout {consolide} échoué: {e!r} — continue",
                          file=sys.stderr, flush=True)
        _store.write_tasks(root, rows)
        if not args.no_commit:
            try:
                _store.commit(root, [_store.tasks_path(root)], f"Force-orphan {args.id}")
            except Exception as e:         # noqa: BLE001 — best-effort, on ne plante pas le run
                print(f"FORCE-ORPHAN: commit échoué pour {args.id}: {e!r} — continue",
                      file=sys.stderr, flush=True)
    print(f"FORCE-ORPHAN: {args.id} → {row['status']}")
    return 0


# --- clear-lease (chemin admin : lease correcting: orpheline par id) ------
# `release --force-orphan` ne clear une lease que via un **enfant** `owner==<short>`
# (le short de l'agent tué). Quand le short de la lease est un **fantôme** (aucun
# enfant vivant ne le porte), ce chemin est inopérant (no-op, owner enfant vide) et
# la lease parent gèle la validation. Ce verbe cible la lease **par l'id du reduce**
# directement — clear pur, sans toucher aux enfants ni au consolidé (working-tree
# supposé clean ; un orphelin correcteur dirty relève de `--force-orphan`).

def cmd_clear_lease(root: Path, args, short: str) -> int:
    """Chemin admin : retire une lease `correcting:` orpheline d'un reduce `<id>`,
    ciblée par l'id du parent — pour les leases dont le short ne correspond à aucun
    enfant vivant, hors d'atteinte de `release --force-orphan`. Sous flock, réutilise
    `clear_lease`, commit scopé `2-consolide/outils/tasks.csv` uniquement, best-effort. No-op
    loggé si la ligne ne porte pas de lease (R1 : seul `task.py` mute le CSV)."""
    with _store.locked(root):
        rows = _store.read_tasks(root)
        row = find_row(rows, args.id) or _store.die(f"id inconnu: {args.id}")
        held = parse_lease(row["note"])
        if not held:
            print(f"CLEAR-LEASE: {args.id} no-op (pas de lease correcting:)")
            return 0
        row["note"] = clear_lease(row["note"])
        _store.write_tasks(root, rows)
        if not args.no_commit:
            try:
                _store.commit(root, [_store.tasks_path(root)],
                              f"Clear-lease {args.id} (correcting:{held})")
            except Exception as e:         # noqa: BLE001 — best-effort, on ne plante pas
                print(f"CLEAR-LEASE: commit échoué pour {args.id}: {e!r} — continue",
                      file=sys.stderr, flush=True)
    print(f"CLEAR-LEASE: {args.id} → lease correcting:{held} clearée")
    return 0


# --- stale (scan read-only) -----------------------------------------------

def cmd_stale(root: Path, args, short: str) -> int:
    """**Lecture seule** : liste les `reduce:<clé>` périmés (un fragment de leur
    thème a bougé après leur `done_at`). Ne mute ni ne committe rien — sert à
    **décider** quoi rouvrir (Josian dans la boucle). `--why` ajoute les maps
    fautifs. Cf. `docs/specs/stale.md` § 1."""
    stale = scan_stale(_store.read_tasks(root), root)
    if not stale:
        print("STALE: aucun — tous les reduces done sont à jour")
        return 0
    for row, culprits in stale:
        print(f"STALE: {row['id']} (done_at={row['done_at']})")
        if args.why:
            for mid in culprits:
                print(f"  ↳ {mid}")
    print(f"— {len(stale)} reduce(s) périmé(s)")
    return 0


# --- reopen (mutation, flock, 1 commit) -----------------------------------

def _reopen_one(rows: "list[dict]", reduce_id: str) -> "tuple[dict | None, str]":
    """Tente de rouvrir un `reduce:<clé>` **ou** un `map:<src>` done → todo (in-place,
    sous le flock de l'appelant). Garde de statut (cf. stale.md § 2) :
    - `done`  → supprime les enfants `validate:<clé>#*` (option reco : CSV borné),
      reduce `done→todo`, vide `done_at`/`owner`, `note=stale`.
    - `todo`  → no-op (reconstruira déjà).
    - `split` → **refus** (validation 2/2 en vol ; attendre le rollup).
    - autre   → refus (claimed/to_validate : tâche en cours).
    Un **map** n'a ni enfants ni statut `split` : mêmes gardes, re-run pur. Son re-`done`
    porte un `done_at` neuf → les reduces de ses thèmes deviennent périmés au scan `stale`
    (sémantique Make) — c'est le chemin pour re-router une source vers une clé neuve.
    Retourne `(row | None, message)`. `row is None` → rien à committer
    (no-op/refus) ; la mutation des `rows` (suppression d'enfants) est faite in-place.
    Refus durs via `_store.die` (split, id inconnu, mauvais type)."""
    row = find_row(rows, reduce_id) or _store.die(f"id inconnu: {reduce_id}")
    if row["type"] not in ("reduce", "map"):
        _store.die(f"{reduce_id} n'est ni un reduce ni un map (type={row['type']})")
    if row["status"] == "todo":
        return None, f"REOPEN: {reduce_id} no-op (déjà todo)"
    if row["status"] == "split":
        _store.die(f"{reduce_id} en split (validation 2/2 en vol) — attendre le rollup")
    if row["status"] != "done":
        _store.die(f"{reduce_id} non rouvrable (status={row['status']})")
    # done → todo : retire les enfants validate (ils ont validé l'ancien contenu),
    # puis reset du reduce. La suppression de ligne est la seule primitive neuve.
    children = [r["id"] for r in rows if _is_validate_shard(r, reduce_id)]
    rows[:] = [r for r in rows if not _is_validate_shard(r, reduce_id)]
    row["status"] = "todo"
    row["done_at"] = ""
    row["owner"] = ""
    row["note"] = "stale"
    return row, f"REOPEN: {reduce_id} → todo (−{len(children)} validate)"


def cmd_reopen(root: Path, args, short: str) -> int:
    """Rouvre des reduces périmés : `done → todo`, enfants `validate` supprimés
    (cf. `docs/specs/stale.md` § 2). `--stale` rouvre **tous** les périmés du scan
    en un passage. Sous flock, **1 commit scopé** `tasks.csv` pour le lot entier.
    Le reduce redevient un `todo` ordinaire → l'orchestrateur le ramasse, re-grep
    **tous** les fragments (rapports inclus) → re-shard `validate` frais → gate 2/2."""
    with _store.locked(root):
        rows = _store.read_tasks(root)
        ids = list(args.ids)
        if args.stale:
            ids += [row["id"] for row, _ in scan_stale(rows, root)]
        if not ids:
            print("REOPEN: rien à faire (ni id ni --stale stale)")
            return 0
        touched = False
        for reduce_id in dict.fromkeys(ids):       # dédup, ordre stable
            row, msg = _reopen_one(rows, reduce_id)
            touched = touched or row is not None
            print(msg)
        if touched:
            _store.write_tasks(root, rows)
            if not args.no_commit:
                _store.commit(root, [_store.tasks_path(root)],
                              f"Reopen stale ({short})")
    return 0


# --- CLI ------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="task.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--repo-root", help="racine du dépôt (défaut : dérivée du script)")
    common.add_argument("--no-commit", action="store_true",
                        help="mute le CSV mais ne committe pas (tests)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("claim_next", parents=[common],
                       help="sélectionne+CLAIM 1 tâche prenable (agents orchestrés ; "
                            "pour inspecter sans claimer → peek_next)")
    p.add_argument("--type", choices=["map", "reduce", "validate"])
    p.set_defaults(func=cmd_claim_next)

    p = sub.add_parser("peek_next", parents=[common],
                       help="LECTURE SEULE : imprime le candidat que claim_next "
                            "prendrait, sans muter ni committer (inspection)")
    p.add_argument("--type", choices=["map", "reduce", "validate"])
    p.set_defaults(func=cmd_peek_next)

    p = sub.add_parser("claim", parents=[common], help="claim ciblé d'un id")
    p.add_argument("id")
    p.set_defaults(func=cmd_claim)

    p = sub.add_parser("done", parents=[common], help="check.py puis done/to_validate")
    p.add_argument("id")
    p.add_argument("--output", help="artefact (défaut : dérivé du type/id)")
    p.set_defaults(func=cmd_done)

    p = sub.add_parser("approve", parents=[common], help="append ok:<short> ; 2e distinct → done")
    p.add_argument("id")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("corrige", parents=[common],
                       help="verdict corrigé : re-check + reset-all des frères + clear lease")
    p.add_argument("id")
    p.add_argument("--reason", help="résumé court de la correction (message de commit)")
    p.set_defaults(func=cmd_corrige)

    p = sub.add_parser("claim-correct", parents=[common],
                       help="pose la lease correcting:<short> sur le reduce parent (avant un corrigé)")
    p.add_argument("id")
    p.set_defaults(func=cmd_claim_correct)

    p = sub.add_parser("clear-lease", parents=[common],
                       help="admin : clear une lease correcting: orpheline sur un reduce "
                            "<id> (par id parent — hors d'atteinte de --force-orphan)")
    p.add_argument("id")
    p.set_defaults(func=cmd_clear_lease)

    p = sub.add_parser("split", parents=[common], help="parent→split + enfants map todo")
    p.add_argument("id")
    p.add_argument("child_inputs", nargs="+", help="inputs des enfants (plages calées frontières)")
    p.set_defaults(func=cmd_split)

    p = sub.add_parser("release", parents=[common], help="claimed→todo (ou blocked/abandon)")
    p.add_argument("id")
    p.add_argument("--reason", help="trace en note")
    p.add_argument("--status", choices=["todo", "blocked", "abandon"], default="todo")
    p.add_argument("--force-orphan", metavar="SHORT",
                   help="admin (orchestrateur) : récupère un verrou orphelin laissé "
                        "par un agent mort — claimed/to_validate → todo SI owner==SHORT "
                        "(le short de l'agent tué), sinon no-op (cf. watchdog.md §6)")
    p.set_defaults(func=cmd_release)

    p = sub.add_parser("stale", parents=[common],
                       help="LECTURE SEULE : liste les reduces done périmés "
                            "(un fragment de leur thème a bougé après leur done_at)")
    p.add_argument("--why", action="store_true", help="ajoute les maps fautifs sous chaque reduce")
    p.set_defaults(func=cmd_stale)

    p = sub.add_parser("reopen", parents=[common],
                       help="reduce|map done→todo (+ supprime les enfants validate) "
                            "(--stale : tous les reduces périmés du scan)")
    p.add_argument("ids", nargs="*", help="reduce:<clé> ou map:<src> à rouvrir (ou --stale)")
    p.add_argument("--stale", action="store_true", help="rouvre tous les reduces périmés (scan §1)")
    p.set_defaults(func=cmd_reopen)
    return parser


def main(argv: "list[str] | None" = None) -> int:
    args = build_parser().parse_args(argv)
    root = _store.resolve_root(args.repo_root)
    short = _store.short_session()
    return args.func(root, args, short)


if __name__ == "__main__":
    raise SystemExit(main())
