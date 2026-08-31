---
description: "When you need one permanent entry point answering \"what's running right now?\" whose rows empty but whose file never moves."
tags: [work-tracking, discovery, human-protocol, doc-hygiene]
family: kb-conventions
---

# Permanent work-stream index whose rows self-empty

One permanent entry point answers "what's running right now?": an index file that is **never deleted** — its *rows* empty. A finished stream's working file disappears and its row is removed (the why lives in the commit message, per `no-pink-elephant`); when nothing runs, the table is empty but the file remains, so the entry point never moves. Table columns force actionability: what it is, state, **next action**, **who decides**. Standing instruction to agents: serve the human *the next action, ready to decide* — never a global status report; if serving it requires the human to carry anything else, the index is missing something → propose the fix, don't hand-compensate (`human-attention-protocol`). Stream files follow `work-plan-sweep` (work-plan frontmatter, step checkboxes); the folder's nature is settled per `three-natures`.

## Reference
`reference/work-index/CLAUDE.md` (folder protocol), `reference/work-index/INDEX.md` (live index — domain rows kept verbatim, they illustrate the format)
