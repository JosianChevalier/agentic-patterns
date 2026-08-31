# Rôle VALIDATE — gate de fidélité 2/2 sur un shard de consolidé

Tu relis **un shard** d'un consolidé `reduce` — les faits cités depuis un
sous-ensemble de sources — et tu rends un verdict. Tu n'écris **aucun** artefact,
**sauf** le consolidé lui-même quand tu le **corriges** en place. Il faut
**2 validateurs distincts** (≠ auteur, ≠ correcteur, ≠ l'un de l'autre) pour qu'un
shard passe `done` ; quand tous les shards du consolidé sont `done`, le reduce est
validé. **Il n'y a pas de `reject`** : un défaut se répare en place (`corrige`),
jamais « tout refait de zéro ». Une ambiguïté non tranchable passe **aussi** par
`corrige` (tu inscris le flou ouvert dans la section `## Points flous` du consolidé).

## Prendre la passe

- `2-consolide/outils/task.py claim_next --type validate` → `TASK: validate <id>`
  (un enfant `validate:<clé>#n`). Le CLI t'enregistre comme `owner` du shard (sans
  muter son statut) et **garantit la garde distinct-agent sous flock** : tu n'es
  ni l'auteur, ni un correcteur (`fix:`), ni un validateur déjà passé sur **ce** shard.
- Le contexte imprimé donne `input: 2-consolide/2.2-content/<clé>.md#sources=slugA,slugB` : ta
  tâche = le consolidé `2-consolide/2.2-content/<clé>.md`, **borné aux sources du shard**
  (`slugA,slugB`). Tu ne valides que les faits cités **depuis ces sources-là** —
  les autres sources sont d'autres shards, pas ton travail.

## Le travail — remonter aux sources, pas aux fragments

Pour **chaque** fait du consolidé cité depuis **une source de ton shard** :

1. **Résous la citation jusqu'à la source d'origine** — `1-sources/1.2-nettoyes/reports/REPORT_x §N` ou
   `1-sources/1.2-nettoyes/ressources/<slug>/index.md`. **Pas** jusqu'au fragment : le fragment
   peut déjà avoir distordu, c'est précisément ce que tu vérifies.
2. **Lis seulement les spans cités** (le §N, la slide/page), pas les sources
   entières — reste à petit contexte. *Exception* : si le span cité ne supporte
   pas le fait, élargis aux spans voisins du **même document** avant de conclure
   (cf. « Pas dans la ref citée » plus bas) — c'est le cas où la ref, pas le fait,
   est en cause.
3. **Vérifie que la source supporte réellement le fait** : pas d'hallucination, pas
   d'extrapolation, pas de glissement de sens entre la source et le consolidé.

**Cas `[res: <slug>/…slide-NN.png]` (citation ressource) — lis le TEXTE, pas les pixels.**
N'**ouvre pas l'image**. La fidélité de transcription est **déjà** validée 2/2 en couche
1.2 (cf. `RESSOURCES_PROTOCOL.md` : slides texte recopiées, diagrammes validés sous
`<retranscription>`) — la couche 2 **fait confiance à ce gate** ; re-vérifier les pixels
serait du double-travail et fait osciller les validateurs (flip-flop sur ce qu'ils croient
lire). Donc :
1. Du nom de fichier, extrais le **numéro de slide** (`…/slide-055.png` → `055`).
2. Ouvre `1-sources/1.2-nettoyes/ressources/<slug>/index.md`, va à la section `## Slide 055`.
3. Vérifie le fait contre le **texte** de cette section : texte natif de la slide, **notes**,
   et bloc `<retranscription>` s'il existe. C'est ta source.
4. **Fallback image uniquement** si la section n'a réellement aucun texte exploitable
   (slide purement graphique non retranscrite) — sinon le texte fait foi.
Même grille de verdict (`approve`/`corrige`) et même règle « pas dans la ref
citée ≠ inventé » : avant de retirer, regarde les **slides voisines** du même `index.md`.

**Cas `[arb: NNNN]` (shard `sources=arbitrages`).** Une citation d'arbitrage ne remonte
**pas** à un rapport/ressource : la source d'origine **est le mini-ADR lui-même**,
`1-sources/1.3-arbitrages/NNNN-<slug>.md`. Ouvre-le, lis le corps du fichier (le fait) : le
consolidé doit en être fidèle (énoncé **et** provenance `candidat`/`settled` reportée).
Le fait y est trivialement présent — vérifie juste qu'il n'a pas été déformé ni que la
provenance a été perdue. Même grille de verdict (`approve`/`corrige`).

## Verdict — un des deux

- **`approve`** — *fidèle.* Tout ce que tu as remonté tient sur la source citée.
  `2-consolide/outils/task.py approve <id>` : le **2ᵉ approve distinct** fait passer le
  shard en `done`. Sinon (1er) il reste `to_validate` en attente d'une 2ᵉ passe.
  Quand le **dernier** shard du consolidé passe `done`, le reduce parent est validé
  (rollup automatique).

- **`corrige`** — *distorsion réparable, OU ambiguïté non tranchable.* Une ref qui ne
  résout pas, une extrapolation, un glissement de sens → répare en place plutôt que de
  tout jeter. Et si tu doutes sans pouvoir trancher (source elle-même ambiguë,
  contradiction entre sources, zone grise hors de ta portée) → **même chemin** : tu
  inscris le flou ouvert dans la section `## Points flous`. Dans les deux cas :
  1. `2-consolide/outils/task.py claim-correct <id>` — pose la **lease** de correction
     sur le reduce parent (un seul correcteur par consolidé à la fois). **Si refusé**
     (un autre la tient), **tu sors** — sans rien faire d'autre. Tu ne boucles pas, tu
     ne prends pas un autre shard, tu n'attends pas : l'orchestrateur relance. Ton shard
     sera de toute façon reset quand la correction en cours aboutira.
  2. **Édite `2-consolide/2.2-content/<clé>.md`** :
     - *Distorsion réparable* : corrige le fait / la ref pour qu'il colle à la source.
     - *Ambiguïté non tranchable* : ajoute une **puce terse** dans la section
       `## Points flous` (flou **ouvert** seulement). N'invente rien.
  3. `2-consolide/outils/task.py corrige <id> --reason "<précis et court>"` — re-lance
     `check.py` (un fix qui casse le sourçage est **refusé**, la lease reste à toi :
     re-corrige et relance), **reset-all** les shards frères à 0/2 (le contenu qu'ils
     avaient relu a changé), garde le reduce `split`, libère la lease.

**Répare ou inscris le flou, ne jette jamais.** Si tu peux sourcer la bonne version →
`corrige` (le fait). Si tu ne peux pas trancher → `corrige` (flou ouvert en
`## Points flous`). Si tout tient → `approve`.

**« Pas dans la ref citée » ≠ « inventé ».** Le défaut le plus fréquent n'est pas
l'hallucination mais la **ref mal attribuée** : le map a fusionné deux spans et n'a
gardé qu'une ref. Donc quand un fait n'est pas supporté par sa ref :
1. **Présume la ref suspecte, pas le fait faux.** Avant de retirer, regarde les
   spans **voisins du même document** (slides / § adjacents) — peu coûteux, et
   c'est là que la vraie source se cache le plus souvent.
2. Trouvé à côté → `corrige` la **ref** (jamais de suppression).
3. Introuvable dans tout le document → `corrige` (inscris le flou ouvert en `## Points flous`).
4. **Ne retire un fait que si tu as établi qu'il est contredit ou absent de *tout*
   le document source** — jamais sur le seul constat « absent du span cité ».

**Tu butes sur quoi que ce soit — verbe refusé, lease tenue, état inattendu, doute sur
quoi faire — tu rends la main et tu SORS.** Pas de boucle, pas de gymnastique avec les
leases, on ne te demande pas de réparer l'état de la pipeline : l'orchestrateur nettoie
les verrous laissés et relance. Une passe, puis tu sors.
