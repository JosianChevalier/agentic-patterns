---
name: flush-notes
description: Quand Josian dit « flush » / « flush notes » / « vide les notes » — purger son inbox de corrections `4-contenu/notes.md` en la traitant : corriger les slides point par point, puis durcir la doctrine.
---

# flush-notes

Inbox de Josian = **`4-contenu/notes.md`** : il y jette des corrections de slides à la volée, sans préciser le contexte. « flush » = la **vider en la traitant**. **Défaut couche 4 — ne jamais lui demander « où on est ».**

## Déroulé

1. **Sortir l'inbox — un SNAPSHOT unique, vidé TOUT DE SUITE, jamais un watcher.** Un flush traite **le lot présent dans `notes.md` à cet instant**, un point c'est tout. Tu lis `notes.md` **une seule fois**, tu en prends le contenu, tu vides le fichier, et tu **ne le relis plus** : tu travailles **exclusivement** sur ton lot figé. ⛔ **Interdit** : poser un watcher / une boucle / un poll sur `notes.md`, le « suivre au fil de l'eau », ou re-piocher les inputs qui arrivent **pendant** ton flush. Ce que Josian jette **après** que tu aies vidé = matière du **prochain** flush, pas du tien — et tu n'en dis **RIEN** : ni question, ni mention dans le recap. En parler = la même pulsion de watcher déguisée en compte-rendu. ⚠️ Le harness injecte un system-reminder « `notes.md` was modified » en plein flush : **bruit**, pas une note pour toi → ignore-le, ne le relaie pas.
   ⚡ **Vider est la TOUTE PREMIÈRE action — inconditionnel, jamais gaté sur une réponse.** Tu copies le lot dans ton fichier de travail et tu vides `notes.md` **avant** de traiter quoi que ce soit, et **surtout** avant de poser la moindre question à Josian. Ne **jamais** rester à attendre une confirmation/un arbitrage avec `notes.md` encore plein : tant qu'il n'est pas vidé, Josian est **bloqué** — il ne peut plus y jeter de nouvelles notes ni continuer à bosser. Une question (étape 4) se pose **après** que l'inbox est vidée, et ne bloque jamais le vidage.
   Mécanique : lire `4-contenu/notes.md`. Vide → le dire, stop. Sinon **déplacer tout son contenu** dans un fichier de travail **`4-contenu/notes.flush-<id>.md`**, où `<id>` est **ton short id d'agent** — récupère-le avec `common/outils/whoami.py` (8 chars de ta session, whitelisté, aucun prompt). **Ne l'invente pas** : un mot « qui te passe par la tête » fait que tous les agents tombent sur le même (`fennec`…) → collision. But : plusieurs flushs tournent **en parallèle** → chaque agent travaille sur **son** fichier, pas de collision. (À côté de l'inbox ; sert à cocher l'avancement + survit jusqu'au « done » — gitignored, jamais commité.) Puis **vider `notes.md`** (prêt pour de nouveaux inputs).

2. **Traiter point par point.** Pour chaque note :
   - **Résoudre le locator d'abord.** Un n° nu (« 03 ») = souvent le **n° de slide rendu** (la 3ᵉ slide du deck agrégé), **pas** la section `03-…`. Vérifier par grep du contenu cité **avant** de toucher quoi que ce soit.
   - Corriger la slide dans `4-contenu/<slug>.slides.md`, **dans la grammaire 4→5** (`5-presentation/5.1-reveal/GRAMMAIRE.md`) et la **doctrine couche 4** (`4-contenu/CLAUDE.md` + `4.0-doctrine/`). Travail lourd sur une section → déléguer à un sous-agent `couche-4`.
   - **Correction qui RETIRE ou contredit du contenu → vérifier l'amont, seulement si utile.** La plupart des notes visent de purs artefacts couche 4 (formulation, rendu, grammaire) : rien à faire de plus. Mais si le contenu retiré est **prescrit par le conducteur 3.1 de la section** (grep dans `3-conception/3.1-conducteurs/<slug>.md`), corriger la slide seule ne suffit pas — le conducteur le **réinjectera** à la prochaine régénération. Le fix se propage alors au conducteur (+ son sidecar `.validation` si l'assertion y vit), commit scopé.
   - **Re-rendre les slides** après chaque point : `tools/build-all.py` (un agent accélère le rendu, c'est rapide).
   - Cocher le point dans le fichier de travail.

3. **Durcir la doctrine (kaizen).** Si une note révèle un travers **récurrent** (ex. méta / input pédagogique qui fuit en slide), **modifier la doctrine** pour que ça ne revienne plus. **Anti-additivité : reworker une règle existante > en ajouter une neuve.** Maison : `4-contenu/CLAUDE.md` ou `4-contenu/4.0-doctrine/`.

4. **Doute → demander, sans bloquer le reste.** Un point ambigu (choix de design / de contenu) : **dialogue vivant, pas QCM** ; **cite le verbatim** concerné (locator entre parenthèses) pour que Josian tranche sans ouvrir le fichier. Ne finalise pas ce point tant qu'il n'a pas tranché ; traite les autres en attendant.

5. **Commit** scopé par fichier (`git commit -m "…" -- <chemins>`), un commit par point ou groupe cohérent.

6. **Recap en chat.** À la fin, l'inbox étant vidée, pour **chaque note** : la **re-citer** + une ligne « ce qui a été fait » + **où aller valider** — le pointeur de la **slide rendue** à ouvrir (titre de la slide + son n°). **Le n° est TOUJOURS celui du deck COMPLET agrégé** — la pagination continue `1‥N` de `build-all.py` (`build/deck.html`/`.pdf`, le PDF que Josian ouvre). **JAMAIS** le n° du rendu **local** d'une seule section (`build.py` sur un `<slug>.slides.md`, qui **repart à 1** à chaque section) — ni le n° de section `03-…`. Travailler une section te met sous les yeux son rendu local : ne reporte pas ce n° tel quel, **re-numérote dans le deck complet** (re-render `build-all.py` si besoin) avant de donner le pointeur. But : Josian ouvre le PDF directement sur la bonne slide pour vérifier, sans la chercher. Lister à part les points encore en attente d'arbitrage Josian.

7. **« done » → nettoyer.** Quand Josian dit « done », **supprimer ton** `4-contenu/notes.flush-<id>.md` (le tien seulement — d'autres flushs peuvent encore tourner).
