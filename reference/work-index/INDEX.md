---
plan_de_travail: "les chantiers transverses ouverts + les priorités entre eux — une ligne se retire quand le chantier est fini (le fichier INDEX.md, lui, reste, table vide)"
---

# Travaux en cours — index des chantiers

**Le seul endroit où regarder « qu'est-ce qui tourne en ce moment ? ».**
Un chantier fini **disparaît** de la table (son pourquoi vit dans git). Plus rien en cours → la table est vide, ce fichier reste.

⚠️ **Ces chantiers sont ce qui sépare Josian de ses vacances, et il est au bord du burnout.** Cet index **est** le dispositif qui lui évite de porter les chantiers en tête : il en dépile **un à la fois**. Agent : sers-lui **la prochaine action, prête à trancher** — pas un état des lieux global. Si tu dois lui faire porter autre chose, c'est que l'index (ou le fichier de chantier) manque de quelque chose : **propose-lui de le corriger**, ne compense pas à la main (cf. charge essentielle vs accidentelle, `CLAUDE.md` racine § « Communication avec Josian »).

## La séquence (pourquoi cet ordre)

**On part du retour CATS.** En l'appliquant, on **embarque au passage** ce qu'il exige : les visuels qu'il réclame. On ne bloque pas sur l'exhaustivité.
**Puis on ré-itère** en une passe dédiée, pour **polir et faire le tour** des visuels non ramassés en chemin.

Conséquence : le chantier 2 est **partiellement consommé par le 1**. Ne pas l'attaquer de front avant lui — son périmètre aura rétréci.

## Chantiers ouverts

| # | Chantier | Ce que c'est | État | Prochaine action | Qui |
|---|----------|--------------|------|------------------|-----|
| 1 | [Retour CATS sur le support v1](chantier-retour-v1/00-INDEX.md) | Dépiler le retour écrit du relecteur CATS sur la v1 du support : rééquilibrer agile↓/tech↑, sommaire minuté, illustrer la tech, étoffer cyber + data, ouverture perspectives | ⚠️ **« tranché » = décision prête, PAS construit dans la v2.** Réellement bâties dans le deck : la **cyber** (section « La sécurité, du cadrage au run ») et la **data** (section « Piloter par la donnée », J2) — écrites, slidées, relues. **Corrections factuelles** appliquées sauf 1 point en attente de réponse du relecteur (rattachement des DBA). Restent **13 décisions** réparties sur 5 fichiers de travail (détail dans l'index du chantier). Puis l'exécution : appliquer les décisions au deck + **dessiner les 108 visuels (0 dessiné)** | Trancher l'**ouverture perspectives** : la forme d'un mini-bloc « Perspectives » (IA / technos d'avenir) entre la fin de vie et la clôture, son budget minutes, son nom au sommaire (fichier `06`) — puis l'ordre conseillé dans l'index du chantier | **Josian tranche**, puis agent applique |
| 2 | **Produire les visuels du support** (couche 4) | Les **108 visuels** des slides sont **spécifiés** (une spec par schéma, avec sa source) mais **aucun n'est dessiné** — c'est la cause directe du « trop abstrait » de CATS : le PDF v1 relu rendait des cadres vides | Specs complètes, production à zéro. Vue de routage : **23** à sourcer sur le web (schémas d'autorité à retrouver), **58** générables maison, **27** ne sortent pas vers le web | **Après le chantier 1** : produire le reste. Vue d'ensemble régénérable par `tools/visuels.py` (`4-contenu/visuels-a-sourcer.md`) ; les specs vivent dans les 10 sidecars `4-contenu/*.visuels.md` (domicile unique) | Agent produit, **Josian valide** |

## Autres plans de travail ouverts (hors chantiers transverses)

Ils vivent **dans leur couche**, pas ici. Recensés par le sweep `grep -rl '^plan_de_travail:' --include='*.md' .`

- **Les 45 commentaires slide-par-slide** du relecteur CATS (todo à cocher, 2/45 cochés) — `0-pilotage/reunions/2026-07-02-retour-cats-support-v1-commentaires.md`. **Matière première du chantier 1** : ses fichiers de travail sur les illustrations tech, les corrections factuelles et le triage se les répartissent intégralement.
- **Les 10 plans de visuels par section** — `4-contenu/*.visuels.md`. Ce sont les **specs du chantier 2**, une ligne par visuel ; un visuel dessiné → sa ligne se retire.

**Coupes et duplication du support** (le support v1 fait 300 slides réelles — plusieurs plans attaquent le surnombre, ils se croisent) :
- **4 gisements de coupe des conducteurs**, à trancher au fil avec Josian — `3-conception/coupes-conducteurs.md` (le détail vit là, y compris le recoupement avec le chantier 1).
- **Carte des idées de la couche 3** puis audit des doublons — `3-conception/3.0-design/carte-idees.md`. Vue « une ligne = une idée qui occupe une slide », extraite du contenu réel des conducteurs, pour diagnostiquer le surnombre.
- **Audit de duplication des slides réelles** (couche 4) — `4-contenu/audit-slides/audit-duplication.md`. Merge des 10 cartes de sections ; chaque suspect à trancher : redite accidentelle (fusionner/couper) ou arc délibéré (garder). Verdicts proposés par l'agent, **Josian tranche**.
