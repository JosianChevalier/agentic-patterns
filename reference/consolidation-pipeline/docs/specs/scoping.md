# Scoping / découpe des grosses sources (`split`)

Levier de petit contexte, **pas un cas rare** : on découpe une source dès qu'elle risque de saturer le contexte du map. **Détection = `inventory.py` (cheap) ; coupe = un agent de scoping (cognition).** → *pourquoi, doctrine complète, réalité mesurée, tradeoff idempotence* : `philosophy/scoping.md`.

## Seuil (appliqué par `inventory.py`, sur métadonnées seules)

Sur chaque source map, sans lire le contenu : `lines = wc -l` + `imgs = nb de *.png` du slug (0 pour un rapport).

> **Seuil : `lines > 600` OU `imgs > 6`.**

## Au-dessus du seuil — inventory n'écrit PAS d'enfants

`inventory.py` :
1. génère l'**outline** de la source ;
2. pose **une seule** ligne `map:<src>` en `todo` avec `note=oversize` (`input` = source entière).

Cette tâche n'est pas un map normal : l'agent qui la claim **scope** au lieu de mapper.

### Outline (déterministe, généré par inventory)

Pour chaque frontière `^## (Slide|Page) \d+` de l'`index.md` (délimiteur régulier par type — `## Slide NNN — …` pptx, `## Page NN` pdf), une ligne :

```
<titre> — L<début> (<n> lignes)
```

Calcul cheap (`grep -n` des frontières + soustraction). Tient en ~200 lignes même pour un deck de 190 slides. Régénérable (scratch, gitignored).

## Coupe — l'agent de scoping

Cognition migrée dans [`2-consolide/outils/prompts/scope.md`](../../2-consolide/outils/prompts/scope.md) — source unique cat'ée par l'orchestrateur. En substance : lire **seulement l'outline** (jamais le contenu), regrouper des slides/pages **contiguës** en lots (cible molle ~500 lignes), selon 4 règles (ordre du document / chunk = bloc thématique contigu / sémantique aligné sur le structurel / exception unité énorme sous-divisée), avec fallback ligne-à-ligne sans pagination et re-`split` récursif d'un enfant trop gros. → `README.md` § Prompts, `philosophy/prompts.md`.

Ce que le **système** (CLI) contraint reste ici :

- `split <src> <chemin>#L<a>-<b> …` : plages calées sur les frontières outline (`<a>` = ligne d'un `## Slide/Page`, `<b>` = ligne avant la frontière suivante ; dernier lot → EOF), enregistrées **telles quelles** (aucune vérif de budget). N inputs → N enfants `map:<src>#k` (`todo`, `parent=<src>`), mappés normalement ensuite. Cf. [cli.md](cli.md).
- Un `split` réussi **clôt** la tâche (parent → `split`, `owner` libéré) : **pas** de `release` ensuite (il exige `claimed`, échouerait). `release` = uniquement le chemin d'abandon (on ne découpe pas), qui préserve `note=oversize`.
