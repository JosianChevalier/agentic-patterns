# Contenu des livrables (markdown) — "Les bases de l'IT chez CATS"

**Couche 4 « contenu »** du modèle médaillon (cf. `CLAUDE.md` racine). On y rédige le **contenu réel des livrables** en markdown : c'est la **source de vérité éditée** par Josian + agent — slides, glossaire, cas pratiques, synthèse participants.

**Nature** — co-construit Josian + agent, comme la couche 3 (`3-conception/`), et **à la différence** de la KB autonome (`2-consolide/`, `1-sources/1.2-nettoyes/`). Josian tranche, l'agent rédige.

> 📐 **Doctrine de contenu : `4.0-doctrine/DOCTRINE.md`** — densité (« une idée par slide, exhaustif, découper pas comprimer ») + distinction **repère / à ancrer**. À lire avant de rédiger des slides. *(Syntaxe + visuel = couche 5, hors de cette doctrine.)*

## ⛔ Jamais de tiret cadratin `—` au fil d'une phrase *(règle dure)*

Le `—` ne sert **jamais** de ponctuation de prose (incise, pause, « X — explication ») : on remplace par une **virgule**, un **deux-points**, des **parenthèses**, ou on **coupe** la phrase — selon le sens, jamais mécaniquement. Vaut **aussi dans les titres** (rendus verbatim). Motif : ça sonne **écrit par une IA**, perçu comme **amateur** dans un livrable vendu à une banque.
- ❌ `Le PO priorise le backlog — et décide de s'arrêter.`
- ✅ `Le PO priorise le backlog, et décide de s'arrêter.`

**Le `—` reste légitime** dans 3 cas structurels (il sépare un libellé en gras de sa glose) : encart définition `> **terme** — …` ; puce glossaire `- **terme** — glose` ; libellé composé, `—` **dans** le gras `**1re voie — le flux**`.

> 🧭 **Routage sous-agent.** Quand tu **délègues** du travail de contenu à un sous-agent, prends **`couche-4`** (pas le générique). Pour une **recherche de fait** dans la KB → **`chercheur-kb`** (lecture seule, rend une conclusion sourcée).

## ⛔ Une slide = ce qui est PROJETÉ. Zéro méta. *(règle dure, zéro exception)*

Un `<slug>.slides.md` est le **contenu montré aux participants à l'écran**. Rien d'autre n'y entre. Il contient **uniquement** :
- le **titre** de la slide ;
- le **contenu affiché** : bullets, définition, chiffre, citation, question projetée ;
- un **renvoi visuel nu** : `🎨` seul (must-have, aucune description — la spec vit dans le sidecar, cf. § Visuels) ou `*🎲 …*` (exercice sur table, pas de slide). *(Le `🎨` est un repère de fabrication pour la couche 5, pas un message au participant ; la **description** du schéma, elle, ne s'écrit jamais ici.)*

**INTERDIT dans une slide — ça n'y entre JAMAIS :**
- les **messages d'intention / de narration** (« ici on dira ça », « pour comprendre X il faut d'abord… », « on vient de prouver que… », « avant d'investir, on trie ») ;
- l'**input pédagogique** : l'**objectif d'apprentissage** du bloc (« Objectif du bloc : passer de *subir* à *comprendre* », « le but ici est de… ») **et** tout **diagnostic / jugement sur le participant** (« vous *subissez* l'agilité, appliquée sans le *pourquoi* », « vous appliquez sans comprendre »). C'est la **matière du formateur** (couche 3 / dit à l'oral), **jamais** projetée. On **montre le concept** ; on ne dit pas au participant ce qu'il est censé en retirer, ni ce qu'il ferait de travers ;
- le **tempo / la mise en scène** (« on laisse respirer », « question seule plein cadre », « cold-open », « on révèle le verdict ») ;
- les **transitions** et **rappels d'autres slides** formulés comme du discours d'animateur ;
- **TOUT renvoi à une autre slide** (« *(slide 7)* », « voir slide X », « on l'a vu plus haut ») — **zéro exception**. Personne ne se souvient de « la slide 7 » ; si tu veux relier deux idées, c'est le formateur qui le **dit à l'oral**. Une slide ne se cite jamais elle-même ni une autre.
- les **rappels narratifs temporels** (« rappel du matin », « comme vu ce matin », « on y reviendra ») — le rappel se **fait à l'oral**, il ne s'**écrit** pas à l'écran.
- l'**état de la KB** — le **degré de confiance** ou la **provenance** d'un fait (« candidat », « à confirmer par CATS », « non sourcé », renvoi à un flou, id de source). La slide énonce des **faits** ; elle n'expose **jamais l'état de notre enquête** sur ces faits. Un fait pas assez solide pour être **énoncé nu** ne monte pas sur la slide : il se tranche **avant** (KB, `1-sources/1.3-arbitrages/`, `QUESTIONS-CATS.md`), jamais devant CATS. C'est la salle qu'on a en face, pas la KB : projeter notre incertitude à des participants qui viennent apprendre, c'est saborder le livrable.
- toute phrase qui **parle de la slide** au lieu d'**être** la slide.

**Pourquoi c'est non négociable** : ces slides sont le livrable d'une formation **vendue à un grand groupe bancaire**. Une slide pro montre le **concept**, pas la tuyauterie de l'animation. Le moindre « (slide 7) » ou « rappel du matin » à l'écran = amateur.

**Test unique** : si la phrase **décrit ce qu'on va faire ou dire**, ou **ce qu'on sait ou ne sait pas**, elle n'est pas une slide → elle sort. Si le participant la **lit telle quelle à l'écran**, c'est une slide → elle reste. Dans le doute, ça sort.

## 🔂 Revue de slides — une slide à la fois, la boucle se ferme dans le chat

Quand Josian revoit des slides, l'unité de travail est **une slide**, et on **ne passe pas à la suivante** tant qu'elle n'est pas validée.

**La boucle, à chaque itération :**
1. **Servir la slide dans le chat, verbatim** — le texte exact tel qu'il est / tel qu'il serait, entre guillemets, avec son locator entre parenthèses. **Jamais une paraphrase**, jamais « je propose de reformuler la partie sur X » : Josian n'a pas la tête dans les fichiers, il ne peut trancher que sur du texte sous les yeux *(c'est la règle racine §0 — elle se perd systématiquement ici)*.
2. Josian donne son retour.
3. **Re-servir la slide entière, retravaillée** — pas un diff, pas « ok j'ai intégré », pas un résumé de ce qui a bougé : **la slide dans son état d'après**, à relire d'un coup d'œil.
4. Répéter jusqu'à validation explicite.
5. **Seulement alors** : `Edit` sur le fichier + commit scopé, puis slide suivante.

**Les deux fautes, symétriques :**
- ❌ **Appliquer et enchaîner.** Prendre le retour, éditer le fichier, passer à la slide suivante. Josian ne voit jamais ce qu'a donné son feedback → il a perdu le contrôle du contenu, qui est précisément la charge qu'il **doit** porter (§0 racine : le fond, il tranche dans le détail).
- ❌ **Décrire au lieu de montrer.** « J'ai resserré l'intro et sorti la mention de l'outil » ne se relit pas. On montre la slide.

**Test** : après ton message, Josian peut-il **lire la slide telle qu'elle sera** sans ouvrir un fichier ? Non → le message est raté.

## 🔁 Rendu direct — ce que tu écris EST la slide *(grammaire 4→5)*

Ton `<slug>.slides.md` est **transformé mécaniquement en slide** par le renderer (`5-presentation/5.1-reveal/build.py`, la chaîne reveal→PDF que CATS valide). **Aucun filtre, aucune relecture, aucune réécriture** entre ton markdown et l'écran : la seule transformation est **appliquer le template**. Le markdown **EST** la slide.

**Conséquences directes — non négociables :**
- **Le titre part tel quel.** La ligne `## …` **est** le titre affiché, **verbatim**. Donc **aucun locator interne dans le titre** — pas de `S01.3`, pas de n° de beat, pas de renvoi conducteur 3.1 : il s'afficherait **littéralement** à l'écran. Le titre = ce que le participant lit, rien d'autre.
- **Pas de numéro dans les titres.** La ligne `## Titre` part **verbatim** ; la pagination est **automatique** (gérée par le renderer). **Aucun préfixe `N · `** : il est **interdit** (un résidu serait strippé par sécurité, mais ne l'écris pas). Tout autre préfixe (`S01.3 — …`, `7. …`, `7 — …`) **n'est PAS reconnu → il reste visible dans le titre.**
- **Template = commentaire HTML** `<!-- gabarit: nom -->` en tête de bloc. **PAS** `` `template: nom` `` (non lu → rendu comme une ligne de code parasite dans le corps). Le `nom` doit appartenir au **catalogue des gabarits** ; hors catalogue → retombe sur `contenu`. Sans marqueur, le renderer **auto-détecte** (couverture / séparateur / contenu).
- **Séparateur de chapitre = un bloc autonome** `## Chapitre · Titre` (**sans numéro**, seul entre deux `---`). **Ne jamais** plier un `# Titre` (H1) dans le bloc d'une slide : un `# ` dans un corps de slide est rendu en **gros texte-manifeste**, pas en séparateur — le chapitre disparaît et déborde sur la slide suivante.
  - **Un chapitre = un fil conducteur du programme, pas une respiration narrative.** Une carte `## Chapitre ·` marque **l'entrée dans une section** (= une entrée du sommaire `00`, un fichier `<slug>.slides.md` = un conducteur 3.1). **Une section = exactement une carte chapitre**, en tête. **Interdit** : poser une carte chapitre au **milieu** d'une section pour un sous-mouvement / une transition / une montée d'enjeu (« Le flux », « Le retournement », « Atterrissage », « Récap … »). Ces respirations se jouent **à l'oral** et par les **titres de slides**, jamais par une carte chapitre. Test : si le titre du chapitre n'est **pas** une entrée du sommaire, ce n'est pas un chapitre → ça dégage.

**Contrat complet = `5-presentation/5.1-reveal/GRAMMAIRE.md`** : découpage des slides, **catalogue des gabarits** (noms autorisés), vocabulaire du corps (puces, encart définition `> **terme** —`, renvoi visuel `🎨`, exercice `🎲`, tableaux). **À lire avant de rédiger des slides** — c'est l'interface qui décide ce qui s'affiche.

## Sources amont

- `3-conception/` — structure des 2 jours, design des modules et exercices : dit **quoi** mettre où.
- `2-consolide/` + `1-sources/1.2-nettoyes/` — matière factuelle (KB grepable) pour le fond.
- Fiches `2-consolide/2.2-content/formation-*.md` — **ne pas charger les 13 en bloc**. Charger le **set A4** du mapping consommateur→fiches de `2-consolide/CLAUDE.md` (§ « Charger les fiches `formation-*` par consommateur »). `formation-glossaire` se charge **à part**, uniquement quand on travaille le glossaire.

## Structure par section *(décidée 2026-06-14)*

Une fois lancée, la couche 4 se structure **par section numérotée** (alignée sur `3-conception/3.1-conducteurs/`). Chaque section = **deux fichiers** :
- `<slug>.slides.md` — la **liste + le contenu** des slides.
- `<slug>.visuels.md` — **sidecar des visuels à produire** : la spec de chaque schéma/image, hors des slides (cf. § Visuels). Jamais rendu → **invisible côté CATS**.

*(Le déroulé **macro** — scénario, enchaînement, messages — reste en couche 3.1 ; ici on descend au contenu final des slides.)*

## Registre & audience *(décidé 2026-06-15)* — override du global

Le `CLAUDE.md` racine (§2) et `2-consolide/2.2-content/formation-posture-editoriale.md` disent
« vulgariser » / « vulgariser dur ». **En couche 4, ne pas lire ça comme « simplifier ».**

Public **débutant, mais pas idiot**. On peut leur expliquer des choses **complexes** avec des **mots précis** — il faut juste le faire **correctement** et **partir de la base**. En pratique :
- **Définitions d'industrie précises**, pas une version allégée « noob ».
- **Traverser tous les concepts**, leur donner une **définition** et expliciter leurs **implications**.
- Slides **relativement légères, mais pas anémiques** : la légèreté vient de la clarté et de la construction depuis la base, **pas** du retrait de matière.
- Registre **précis + démystifiant**, jamais condescendant. « Vulgariser » ici = **rendre le technique accessible avec des mots justes**, pas alléger ni infantiliser.
- Test d'une définition : est-ce qu'elle **démystifie** le concept, ou juste un gloss générique ? Un gloss vague (« un serveur = une machine ») nomme sans éclairer → insuffisant.

## Vigilance — écart CATS↔industrie *(hérité de la dépollution couche 3)*

L'écart CATS↔état-de-l'art **n'est jamais** un sujet/angle/posture (règle `3-conception/CLAUDE.md`). La couche 3 a été purgée des rubriques « Tension » et jugements de maturité. **Deux passages restent "zone-limite"** : encadrés par des gardes anti-biais aujourd'hui, ils **dérivent vers le jugement de maturité si repris tels quels en slide** — à surveiller au moment de les rédiger :
- **`08-10`** : « analytics non démontré / hypothèse décorative », « SLA acquis par vagues d'amélioration ».
- **`11`** : « trajectoire / pas retard caché » — OK tant que « pas retard caché » tient.

Seule porte d'un écart nommé en slide : **décision explicite de Josian**, jamais une initiative d'agent.

## Visuels — règle *(toutes sections)*

- **Tout visuel travaille — jamais de décoration.** Sobre, cohérent, lisible en projection, **sans texte EN incrusté**. Pas de stock-photo littérale, pas de « gens qui sourient », pas d'image « banque » posée pour meubler.
- **Quatre types** (portés par le champ `type` de chaque item du sidecar) :
  - **`canonique`** — le **schéma faisant autorité** de la discipline (le diagramme de référence que le domaine utilise pour ce concept), **redessiné en style maison**. Nommer sa source (« d'après … ») et **dessiner d'après l'original**, jamais de mémoire.
  - **`cats`** — image/diagramme **propre à CATS** (frise, org, capture d'un outil maison) → **asset à sourcer** dans une ressource CATS avant de redessiner.
  - **`custom`** — diagramme **sans source unique**, généré maison (comparatif, courbe, frise) — souvent **dynamisable** (animation qui fait bouger l'idée).
  - **`illustration`** *(parcimonie)* — **métaphore qui FAIT TRAVAILLER l'idée** (décharge une abstraction, p. ex. le pétrole pour coût de transaction ⊥ coût d'inventaire). Schéma **stylisé**, jamais une photo littérale ni un cliché décoratif. Si la métaphore n'ajoute pas de compréhension → elle dégage.
- **La spec d'un visuel ne vit JAMAIS dans `.slides.md`** (elle s'y afficherait dans le PDF que CATS valide). Elle vit dans le **sidecar `<slug>.visuels.md`** :
  - **Plan de travail** : un item par visuel (ancré à sa slide), tête de fichier portant le frontmatter `plan_de_travail: "visuels à produire pour <slug>"`. Item = `must-have | nice-to-have` + la spec (schéma, source « d'après … »). **Visuel posé → on retire la ligne** : le sidecar se vide (cf. « éléphant rose », CLAUDE.md racine §3). → c'est la **liste greppable** des images à chercher (`cat 4-contenu/*.visuels.md`), ou **groupée par type** dans **`visuels-a-sourcer.md`** (vue générée par `tools/visuels.py`, read-only, sidecars = domicile unique ; **étape ouverte** = sourcer/produire les visuels, surtout les `canonique` via web-search — régénérer après évolution, ne pas hand-éditer).
  - **Ancrage des items = locator `NN#MM`** (cf. § Locators), entre parenthèses en fin de titre d'item, même format que dans les `.slides.md`. **Réflexe — toute coupe / renommage / déplacement de slide** (y c. le re-annotate qui décale les numéros des slides suivantes) : **mettre à jour le sidecar de la section** (locators + titres), puis **régénérer la vue** `tools/visuels.py > 4-contenu/visuels-a-sourcer.md`. Sans ça la vue désynchronise **en silence**.
  - **must-have** *(extrême minorité)* = la slide **EST l'affichage de ce visuel précis** : son sujet même est de le montrer, le texte ne peut pas s'y substituer (p. ex. afficher le **CVP** quand on parle du CVP). Test dur : **un cadre vide « visuel à venir » serait-il MOINS bizarre côté CATS que rien du tout ?** Oui → must-have. Sur la slide : un **renvoi `🎨` nu** (aucune description), rendu en cadre vide discret côté CATS.
    - ⚠️ « la slide serait mieux avec un schéma » n'est **PAS** must-have. On parle de goulots, de plateformes, de CI/CD **sans les montrer** : le texte porte le concept, le visuel n'enrichit que plus tard. Tout ça → **nice-to-have**.
  - **nice-to-have** *(le cas par défaut — dans le doute, ici)* = la slide est **complète en texte seul**, le visuel l'enrichira plus tard → **sidecar uniquement, ZÉRO trace sur la slide** (pas de cadre, pas de `🎨`).
- **Notation** : `🎨` = renvoi nu vers un visuel must-have ; `🎲` = pas de slide (exercice sur table).

## Locators de slides `NN#MM` — annotés dans les titres

- Notation : `NN` = n° du fichier de section **sans tirets** (`0102` pour `01-02-…`), `MM` = index de la slide (blocs `---`, 1-based). Utilisée notamment dans `audit-slides/*.map.md`.
- **Un bloc sans titre compte** (carte encart pleine page) : il consomme un numéro — la numérotation = l'ordre des pages rendues. Non annotable, il se résout en `(sans titre) <première ligne>` ; seul un bloc vide ne compte pas.
- **Chaque titre porte son locator** dans la parenthèse **italique** finale : `## Titre *(7.1 · 07#03)*`, ou `*(07#03)*` sans n° de sous-beat. C'est l'**exception sanctionnée** à « aucun locator dans le titre » : la parenthèse finale est strippée au rendu (`build.py`), rien ne s'affiche à l'écran. Une parenthèse de **sigle** `(CVP)` fait partie du titre affiché : le locator ne s'y insère jamais, il s'ajoute après → `## Titre (CVP) *(00#34)*`.
- **Après ajout / retrait / déplacement de slides : relancer `tools/slides.py annotate`** (idempotent, renumérote tout). Ne jamais renuméroter à la main.
- `tools/slides.py 00#44 07#12` résout des locators en titres ; `tools/slides.py 04` liste une section.
- **Jamais de locator nu vers Josian** (règle racine §0) : titre en tête, locator entre parenthèses. ✅ « la slide *Lead time* (`00#10`) ».

## Fichiers

- `glossaire-a-construire.md` — graine du **glossaire** (livrable phare) : termes-graines + entrées décidées à matière mince. Une passe dédiée sur toute la KB reste à faire.

## À concevoir *(hérité couche 3 — dilution)*

- **Jeu qualité J2** — exercice sur *vitesse ⊥ qualité* (gros batch = ennemi de la qualité). Placé en **5.7** (module fabrication). ⬜ de dilution encaissé ici, à concevoir à la prod de la section.

## État

- **Première version complète des slides générée** pour les 10 sections (`00` → `12`), depuis le conducteur 3.1 — `.slides.md` + sidecars `.visuels.md`.
- **v1 = on envoie tout le contenu candidat, exhaustif.** La **coupe de volume est une passe ultérieure**, pas maintenant : on fait d'abord valider le **fond** (Josian / CATS), on ajuste le volume après. → ne pas traiter la taille d'une section (ex. `03-cadrage`, 52 slides) comme un blocage à ce stade ; la revue-coupe « avant de figer le volume » (cf. § « Estimer le temps d'une section » de la doctrine) vient **après** la validation du fond.
- Restent : graine glossaire (`glossaire-a-construire.md`), jeu qualité J2 (cf. § À concevoir), **sourcer & produire les visuels** (`visuels-a-sourcer.md`, vue par type — les `canonique` d'abord).
