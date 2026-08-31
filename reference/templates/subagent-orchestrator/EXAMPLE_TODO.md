# Exemple — `TODO.md` du domaine (format attendu par l'orchestrateur)

L'orchestrateur lit ce tableau pour décider si la queue a encore du travail
(`queue_has_work()`) et pour produire `FLAGS.md` en fin de run (`scan_flags()`).
Le format **doit** matcher les indices que tu paramètres dans `orchestrate.py`
(`NUM_COLS`, `STEP_COL_RANGE`, `VERROU_COL`, etc.).

C'est le `claim.py` / `release.py` du domaine (cf. skill `file-validation/`)
qui écrit dans ce tableau ; l'orchestrateur ne fait que le **lire**.

## Exemple de tableau

```markdown
| Slug              | Source         | Type | Step1     | Step2 | Step3 | Verrou |
|-------------------|----------------|------|-----------|-------|-------|--------|
| article-2025-01   | corpus/raw/    | doc  | done a1b2 | ok    | 1/2   | —      |
| article-2025-02   | corpus/raw/    | doc  | done c3d4 | —     | —     | f7e8 — 2026-05-27 |
| article-2025-03   | corpus/raw/    | doc  | —         | —     | —     | —      |
```

## Conventions repérées par l'orchestrateur

| Cellule | Sens (côté orchestrateur) |
|---|---|
| `—` ou vide | étape **pickable** → contribue à `queue_has_work() = True` |
| `done <sha>`, `ok`, `skip` | étape **terminée** (selon allow-list du release.py) |
| `1/2` (counter step) | étape encore **reclaimable** (passe restante) |
| `2/2` | étape terminée |
| `signalé <raison>` | étape **bloquée**, listée dans FLAGS.md |
| Verrou `—` | ligne **libre** |
| Verrou `<short> — <date>` | ligne **claimée** par l'agent `<short>` |

## Ce que l'orchestrateur ne fait pas

- Il ne tient pas compte des **prérequis inter-étapes** (`step2` ne peut commencer
  que si `step1 = done`, etc.). C'est au `claim.py` du domaine de bloquer un
  claim invalide — l'orchestrateur considère naïvement qu'une cellule vide est
  pickable. Si deux sorties d'agent consécutives ne produisent aucun commit,
  l'orchestrateur stoppe (= queue épuisée, ou bloquée par prereqs non remplis).

- Il ne distingue pas `signalé` de `done` côté `queue_has_work()` — une étape
  `signalé` est juste "pas vide", donc elle n'est plus pickable de toute façon.
  Elle apparaît seulement dans `FLAGS.md` à la fin du run.

## Format des commits produits par claim/release

Indispensable pour que l'orchestrateur sache **qui a fait quoi** (filtrage par
session id). Format minimum (cf. `CLAIM_RE` / `RELEASE_RE` dans `orchestrate.py`) :

```
Claim <step> <slug> (<short>)
<Step> <slug>: <result> (<short>)
```

où `<short>` = `$CLAUDE_CODE_SESSION_ID[:8]`. Sans ce suffixe, plusieurs agents
qui commitent en parallèle deviennent indistinguables et l'orchestrateur
attribuera mal les commits.

Voir le skill `file-validation/` (variantes "résultats typés" + "auto-abandon
orphelin") pour le claim/release qui écrit ce format.
