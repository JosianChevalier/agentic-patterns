# Rôle REDUCE — consolider UN thème à partir des fragments

Tu agrèges, pour **un seul thème**, ce qu'en disent les fragments déjà distillés —
**jamais** les sources brutes. Ta sortie passe ensuite le gate de fidélité 2/2.

## Prendre la tâche

- `2-consolide/outils/task.py claim_next --type reduce` → `TASK: reduce <id>`. L'`id` est
  `reduce:<clé>` ; ton thème = `<clé>`. (`claim_next` ne te donne un thème que s'il a
  ≥1 fragment qui le couvre — gating sous flock.)
- Output : `2-consolide/2.2-content/<clé>.md`. **Purgé au claim** (re-reduce inclus) : tu
  pars d'un fichier vide → écris-le **en entier** (`Write`), ne cherche **pas** une version
  antérieure. Le consolidé est une fonction des fragments, pas de l'ancienne sortie.

## Rassembler la matière (contexte minimal)

- `grep -l "## theme:<clé>" 2-consolide/2.1-fragments/*.md` → la liste des fragments qui
  touchent ton thème.
- Lis **uniquement** la section `## theme:<clé>` de chacun. **Pas** les fragments
  entiers, **pas** les sources brutes : tout ce dont tu as besoin est dans ces
  sections distillées (c'est le rôle de la couche fragments).

## Écrire le consolidé `2-consolide/2.2-content/<clé>.md`

**Le gabarit dépend de l'axe de ta clé** (cf. `2-consolide/THEMES.md`) :
- **axe CATS** (clés métier/technique, « comment CATS fait X ») → **gabarit CATS**, les
  5 sections **imposées par `check.py`**.
- **axe formation** (clés `formation-*`, « ce qui est attendu de la formation / comment on
  la conçoit ») → **forme libre, aucun gabarit**. `check.py` n'impose **pas** de sections
  ici : chaque fiche prend la structure que son contenu appelle (cf. § dédié plus bas).

### Gabarit axe CATS (défaut)

(cf. `2-consolide/CLAUDE.md` § Format d'un fichier thématique)

```markdown
---
quand_piocher: "<phrase greppable : dans quel cas un agent ou Josian vient lire cette fiche.>"
---
# <Thème>

<1-3 phrases de cadrage : ce que le fichier couvre / ne couvre pas.>

## Cœur d'industrie
<L'état de l'art, indépendant de CATS. Le *pourquoi* avant le *comment*.>

## Matérialisation CATS
<Comment ça se traduit chez CATS. Faits **cités** `[src: <slug> §N]` / `[res: …]`.>

## Tension industrie ↔ CATS
<Où CATS diffère de l'industrie, et **pourquoi** — **fait factuel** pour la KB (outillage et maturité compris ; pas de filtre d'altitude : l'enrobage/élision pour l'audience se décide en couche 3). Écart non expliqué → « **pas su** » honnête, jamais une rationalisation inventée. Aucun écart réel → `-`.>

## Points flous
<**Plan de travail** : une puce terse par flou **ouvert** (contradiction de concept / frontière porteuse non tranchée). Flou résolu → **retiré**. Aucun flou ouvert → `-` seul, **zéro prose** (pas de « Aucun », pas de « résolu par … »). La fiche est autoporteuse. Gate ci-dessous.>

## Sources
- Rapports : <liste> · Ressources : <liste> · Pré-contrats : <si pertinent>
```

Règles **propres à l'axe CATS** :

- **« Matérialisation CATS » DOIT porter des citations** (`check.py` l'exige).
- **Posture industrie ↔ CATS** (cf. `CLAUDE.md`) : donne d'abord le **cœur
  philosophique** de la pratique d'industrie (le *pourquoi*), puis la matérialisation
  CATS **sans inventer** ce qui n'existe pas. Un écart non expliqué → « je ne sais
  pas » honnête, **jamais** une rationalisation inventée.
- **Tension = le fait factuel de l'écart, pas une redite.** La KB nomme l'écart
  industrie↔CATS sans filtre d'altitude (le tri pédagogique — enrober / éluder selon
  l'audience BA/PO — appartient à la **couche 3**, cf. `CLAUDE.md` §2). Mais la Tension ne
  **redouble pas** les autres sections : le concept d'industrie vit en « Cœur d'industrie »,
  le fait CATS en « Matérialisation CATS » — la vider ne doit jamais faire disparaître la
  définition d'une pratique enseignée (ex. une MR : sa déf est en Cœur d'industrie, pas en
  Tension). Aucun écart réel → `-` (`check.py` n'exige que le titre).
- **Référentiel état de l'art delivery = Accelerate/DORA + flow.** Les approbations externes
  et feux verts de comité aux jalons (type CAB) sont un **écart** — ils dégradent la performance
  de livraison sans améliorer la stabilité ; le shift-left = contrôles automatisés **dans** le
  flux de livraison, jamais un comité. Ne **jamais** qualifier un dispositif d'« aligné sur
  l'état de l'art » pour adoucir : l'écart se nomme platement.
- **Gate « Points flous » — n'émets un flou que si le résoudre change un schéma
  mental.** Si aucune vraie question en suspens : écris juste `-`. Ne te sens **pas
  obligé** de remplir, ne justifie **jamais** une absence. N'émets **PAS** : valeur exacte d'un artefact interne (chiffre/nom/date/
  code/liste/acronyme/outil) sans concept derrière ; statut d'avancement d'un chantier
  ou d'une roadmap interne ; attribution/orthographe d'un intervenant ; graphie d'un
  sigle mal transcrit. Un nombre ne devient un flou que s'il **EST** le concept (durée
  de sprint, nb de gates bloquantes). Pas de flou **fabriqué** : aucune assise au
  transcript / mention non confirmée / `TBD` → on ignore. Ne lève pas non plus un flou
  dont la réponse est **déjà ailleurs dans la 1.2** (recoupement, pas un manque) ; un
  *pourquoi CATS s'écarte de l'industrie* (formalisme, lourdeur) n'est **pas** un flou KB —
  la réponse est un concept que le formateur possède → couche conception ou drop, **jamais**
  une question CATS ; un détail d'**outillage/process trop fin pour un BA/PO** (câblage
  interne que le formateur ne mentionnerait même pas) → calibre la granularité sur l'audience.
  *(Miroir de la règle garde/tej de `1-sources/1.3-arbitrages/CLAUDE.md` § Tri — tarie à la source.)*

### Axe formation (`formation-*`) — forme libre, pas de gabarit

```markdown
---
quand_piocher: "<phrase greppable, façon `description:` d'un skill : dans quel cas un agent ou Josian vient lire cette fiche.>"
---
# <clé>

<1-3 phrases de cadrage : ce que la fiche couvre / ne couvre pas.>

<le corps : la structure que SON contenu appelle — sections, sous-listes ou simple liste.>

## Sources
- CR pilotage : <liste> · Ateliers : <liste> · Brief/devis : <si pertinent>
```

- **Aucune section imposée ni suggérée.** `check.py` ne contrôle que `quand_piocher`,
  le titre, les refs non cassées et la taille. Chaque fiche prend la forme que **son**
  contenu appelle ; n'instancie **pas** le gabarit axe CATS.
- **Que des faits actionnables, cités.** Le ***pourquoi* de conception** se **replie inline**
  dans la décision qu'il justifie — **pas** de section théorie pédagogique générique
  (ex-« Cœur d'industrie »), pas de prose. Bullets, phrases courtes (cf. `CLAUDE.md` §0bis).
- **PAS de section « Points flous / ouverts ».** Une question de conception ouverte **ne vit
  pas dans la fiche** : elle est tranchée via la **mécanique d'arbitrage**
  (`1-sources/1.3-arbitrages/`, `candidat`/`settled`) ou renvoyée à la **conception (couche 3)**.
  N'en émets **aucune** — la fiche ne porte que de l'acté.

### Règles communes aux deux gabarits

- **Frontmatter « quand_piocher »** : **bloc `---` … `---` en tête de fiche, avant le
  titre** (les deux axes), un champ `quand_piocher` portant une phrase **greppable**
  **entre guillemets `"…"`** (façon `description:` d'un skill) disant dans quel cas cette
  fiche répond. Sert d'**index de découverte** entre tous les thèmes — courte, factuelle,
  **entre `"…"`** (la phrase peut contenir `:`, le guillemet la garde YAML-safe).
  C'est le **seul** frontmatter de la fiche. **Imposé par `check.py`** (présence du champ).
- **Citations reprises telles quelles des fragments.** Les refs `[src:…]`/`[res:…]`/`[arb:…]`
  pointent vers les **sources d'origine** : recopie-les verbatim, c'est ce que le validateur
  résoudra. N'en fabrique ni n'en réécris aucune.
- **Acronyme → au moins sa glose.** Tout sigle interne porté dans le consolidé doit
  arriver avec sa définition **au moins une fois** (« CMP (Comité Métier Plénier) »,
  « AFN »…) : la couche 2.2 doit être lisible **sans rouvrir la source**. Si un fragment
  développe le sigle, reprends la glose ; s'il ne le développe nulle part, écris-le
  explicitement (« acronyme non développé dans les sources »). Jamais un sigle nu.
- **Cible 100-300 lignes.** Au-delà de ~300, `check.py` refuse : c'est le signal
  d'**éclater** le thème en sous-clés, **pas** de charcuter le contenu.

## Arbitrages — en tête de hiérarchie, provenance préservée

Le fragment `2-consolide/2.1-fragments/arbitrages.md` (source `arbitrage`) porte des **faits
tranchés à la main / par feedback CATS** (cf. `1-sources/1.3-arbitrages/`), cités `[arb: NNNN]`.
Deux règles **dures** :

- **Priorité absolue** : un fait d'arbitrage **gagne tout conflit** — il prime sur les
  transcripts, les notes, les ressources, **tout**. Si un `[arb: NNNN]` contredit un autre
  fragment, le consolidé retient la version de l'arbitrage (l'autre va en « Points flous » si
  utile). C'est le **sommet** de la hiérarchie de sourçage ci-dessous.
- **Provenance survit jusqu'à la fiche** : chaque puce arb est taggée `[candidat]` (jugement à
  confirmer) ou `[settled]` (feedback CATS acté). **Reporte ce tag** dans le consolidé sur le
  fait correspondant (p. ex. « … *(arbitrage candidat)* [arb: 0042] »). La couche 3 distingue
  **assumé** vs **confirmé** — ne l'efface pas.

## Priorité de sourçage — dépend de l'axe du thème

Quand deux fragments se contredisent (et **qu'aucun n'est un arbitrage** — sinon cf. ci-dessus),
la **source qui l'emporte dépend de l'axe** de ta clé (cf. `2-consolide/THEMES.md`) :

- **Axe CATS** (clés métier/technique) : hiérarchie **transcripts > notes** (cf. `CLAUDE.md`
  § Fact-checking) — le transcript d'atelier l'emporte.
- **Axe formation** (clés `formation-*`, « ce qui est attendu de la formation / comment on
  la conçoit ») : hiérarchie **CR pilotage > ateliers > brief/devis**, et **le plus récent
  peut override** un document antérieur (une décision de pilotage récente prime sur le brief
  initial). Convention **propre à cet axe**, distincte du « transcripts > notes » de l'axe
  CATS. Le `source_type`/la date des fragments dit lequel trancher ; un conflit non
  tranchable de l'axe formation **n'est pas un « Points flous »** (la fiche n'en porte
  pas) → il remonte en **arbitrage** ou en **conception** (cf. § axe formation ci-dessus).

## Finaliser

`2-consolide/outils/task.py done reduce:<clé>` → `check.py` passe **mais** le reduce ne
devient pas `done` : il passe en **`status=split`** (owner lâché), et `done` **append un
enfant `validate` par bucket de sources** (`cite_buckets`, cf. `2-consolide/outils/docs/specs/validate.md`),
chacun naissant en `to_validate`. C'est **normal** : `split` n'est pas terminal, le reduce
ne passera `done` que par rollup quand tous ses enfants le seront (gate 2/2 per-shard).

**Tu sors immédiatement.** N'inspecte ni ta ligne ni le CSV : voir `status=split` après
ton `done` est le comportement attendu, pas une anomalie à investiguer.
