# 1.3-arbitrages/ — faits tranchés hors sources

**Second pilier de la vérité agent**, à côté des consolidés `2-consolide/`. Porte les **faits CATS
absents des couches 1-2** mais nécessaires pour **valider les fiches** de couche 3
(`3-conception/3.1-conducteurs/`, cf. son `CLAUDE.md` § *Validation factuelle des sections*).

**Pourquoi un dossier à part.** `2-consolide/` est peuplé **exclusivement par la pipeline autonome**
depuis les sources greppables. Les arbitrages viennent d'un **jugement humain** (Josian) ou d'un
**feedback CATS hors CR** — pas d'une source greppable. On les **trace ici, à part**.

## Deux provenances

- **`settled`** — **feedback CATS** reçu hors CR (réunion informelle, canal, échange direct).
  Acté : sert de vérité tel quel.
- **`candidat`** — **jugement manuel d'un flou** par Josian (trancher un point ambigu pour ne pas
  bloquer le design). **À confirmer par un expert CATS** ; tant que non confirmé, hypothèse de travail.

**Le cas « personne ne sait ».** Un flou que **ni la KB ni Josian** ne peuvent trancher (typiquement
un *pourquoi CATS fait X*, ou un point explicitement renvoyé à un expert) n'est pas un arbitrage :
c'est une **question pour CATS**. Elle vit dans `QUESTIONS-CATS.md` — une **file d'attente sortante**
(se vide quand *CATS répond*, pas quand on bosse). Batch tiré dans la prépa de chaque contact CATS ;
réponse reçue → mini-ADR `provenance: settled` ici même (boucle fermée). C'est l'**autre issue** d'un
flou que la KB ne tranche pas, le pendant de « Josian tranche → `candidat` ».

## Convention — un mini-ADR par décision

Un arbitrage = **un fait**, dans **son propre fichier**. Un fait transverse peut viser **plusieurs
thèmes** (`theme:` est une liste, cf. frontmatter) : le projecteur émet alors la même puce — même
`[arb: NNNN]` — sous chaque thème listé. Les arbitrages arrivent **par vagues** (un lot validé d'un coup).

- Nom : `NNNN-<slug>.md` — **numéro de séquence monotone** (`0001`, `0002`, …). L'ordre du numéro
  **est** l'ordre chronologique (intra-jour inclus, contrairement à une date) **et** l'**id stable**
  des citations `[arb: NNNN]` (immuable une fois posé → aucune citation cassée). Le prochain numéro =
  `max(existants) + 1`.
- La **date** vit en frontmatter (elle informe, elle n'ordonne pas).

**Le corps EST le fait** — l'énoncé tranché + ses sources (`[src:]`/`[res:]`), prose libre
(multi-lignes OK), **aucun label**. Le **titre est aussi le fait** (énoncé court), pas un sujet.
Le reste du contexte (provenance, confirmation) vit en **frontmatter** ; le projecteur prend le
corps verbatim (aplati en une ligne).

**Pourquoi des faits nus, et pas des plaidoiries** (l'erreur par défaut — l'agent qui *juge un flou*
croit devoir *prouver* son verdict, et déverse son raisonnement dans le fichier). Un arbitrage est
**chargé comme une vérité** par le reduce (couche 2) et le fact-check (couche 3), **en complément de
la 1.2 et écrasant en cas de doute** : le lecteur ne doute pas, il consomme — rien à lui démontrer.
Le **raisonnement qui t'a fait trancher est jetable**, il vit dans ta réflexion, **pas dans le
fichier**. Donc **aucune méta de validation** (« Verdict », « pas de contradiction »), aucun
*pourquoi/comment* de l'arbitrage, aucune réconciliation argumentée des sources. Juste le fait, et
les sources quand il y en a. *(Vaut déjà pour la forme staging `a-valider_<slug>.md` — même format
que le `NNNN` final, renumérotée à la promotion.)*

```markdown
---
date: 2026-06-09
theme: <clé>[, <clé>…]  # une ou plusieurs clés contrôlées de ../../2-consolide/THEMES.md (liste = transverse)
provenance: candidat | settled
note: <feedback CATS (canal/date) | jugement d'un flou (réf fiche/point)>   # d'où vient le fait
confirmed_by: <expert/date>   # optionnel — renseigné à la promotion candidat → settled
---

# 0042 · <le fait, énoncé court>

<le fait, autosuffisant, + sources — 1-2 phrases, peut courir sur plusieurs lignes>.
```

- **Fait faux/périmé** : on corrige le mini-ADR **en place** (l'id `[arb: NNNN]` reste stable,
  aucune citation cassée), puis on relance le projecteur. Skill : `changement-fact`.
- **Promotion `candidat → settled`** : un candidat confirmé par un expert → on bascule
  `provenance: settled` et on renseigne `confirmed_by:` (expert + date).

## Tri des points flous — quoi devient arbitrage, quoi se jette

Un point flou récolté a **trois issues** :

- **Garde** (Josian tranche → `candidat`/`settled`) : **contradiction de concept** ; **frontière
  porteuse de schéma mental** (dont CATS↔CAGIP, qui est un *objectif* de la formation, cf. §1).
- **Tej** (rien à cirer) :
  - **graphie / artefact de transcription** — orthographe d'un sigle ou nom interne mal transcrit ;
  - **attribution en réu** — qui a dit quoi, orthographe des intervenants, désambiguïsation de prénoms ;
  - **détail / bureaucratie CATS** — la **valeur exacte d'un truc interne** (chiffre, nom, date, seuil,
    code) **sans concept derrière**.
  - **Règle anti-perte** : on ne tej que le **pur chiffre/nom**. Si la valeur **porte un concept utile**
    (ex. durée de sprint, gates bloquantes) → **garde**. Mixte → **scinder** : garde le concept, jette
    le chiffre (ex. nombre de caisses = tej, mais seuil privatif/communautaire = garde).
- **Requalifie** (ce n'est pas un flou) :
  - **pédagogie** — c'est du **contenu légitime**, *pas* un flou à jeter. Router selon **qui porte la
    question formation** (les deux cas viennent d'un agent qui lit un rapport — l'ancrage seul ne tranche pas) :
    - la **source elle-même** porte un propos sur la formation — quelqu'un dit « il faut traiter tel
      sujet », « porter tel message », ou « on ne sait pas comment le transmettre en training » → **fait
      sourcé** (quelqu'un l'a dit), garde en **arbitrage ici** ;
    - la source énonce un **fait neutre** et c'est **l'agent** qui se demande de lui-même s'il faut en
      décider quelque chose pour la formation → la question est **la sienne, pas sourcée** → **couche 3
      (conception)**, jamais ici.
  - **méta-KB** — éclatement / hygiène de fiche → **tâche d'investigation** (voir si déjà fait, sinon
    décider drop), pas une décision à arbitrer.

**Kaizen** : les raisons de *tej* agrégées musclent le prompt de reduce (couche 2) — typiquement
« ne pas faire remonter la valeur exacte d'un truc interne sans charge pédagogique » — pour tarir le
bruit à la source aux prochaines récoltes.

## Qui l'alimente / l'utilise

- **Fact-check des fiches** (couche 3, lecture seule) : consulte les arbitrages comme vérité.
  Greppable par thème : `grep -lE "^theme:.*\b<clé>\b" 1-sources/1.3-arbitrages/*.md` (la clé peut
  être une parmi plusieurs).
- **Triage des verdicts** (couche 3) : un ❓ « plausible sans trace » tranché par Josian **entre
  ici** — `candidat` (jugement) ou `settled` (feedback CATS).
- **Pipeline couche 2** : ces faits sont **déjà distillés et taggés par thème** — donc **pas mappés**
  (un arbitrage *est* un fragment). Le **projecteur déterministe** `2-consolide/outils/project_arbitrages.py`
  les plie en un fragment `2-consolide/2.1-fragments/arbitrages.md` (groupé par thème, citations
  `[arb: NNNN]`, provenance `[candidat]`/`[settled]` reportée), consommé par le
  reduce **en tête de hiérarchie** (gagne tout conflit) ; `check.py`/`validate.md` résolvent `[arb:]`
  contre le mini-ADR lui-même. **Lancer le projecteur** après chaque vague d'arbitrages
  (`2-consolide/outils/project_arbitrages.py`). *Le re-trigger stale du reduce relève de `stale.md`
  (spec non encore implémentée).*
