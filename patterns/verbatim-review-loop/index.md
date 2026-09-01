---
description: "When a human reviews agent-drafted content one item at a time and the loop must close in the chat: serve verbatim, take feedback, re-serve the full reworked item."
tags: [human-protocol, cognitive-bias]
family: agent-authoring
---

# Verbatim review loop — one item at a time, closed in the chat

Unit of work = **one item** (a slide, an entry); never move to the next until this one is explicitly validated. The loop: (1) serve the item **verbatim in the chat** — the exact text as it is / as it would be, quoted, locator in parentheses; never a paraphrase ("I propose rewording the part about X" is unreviewable); (2) human gives feedback; (3) **re-serve the entire reworked item** — not a diff, not "ok, integrated", not a summary of what moved: the item in its *after* state, re-readable at a glance; (4) repeat until explicit validation; (5) **only then** edit the file + scoped commit, then next item. Two symmetric faults: **apply-and-continue** (take the feedback, edit the file, move on — the human never sees what their feedback produced and loses control of the very content they must own) and **describe-instead-of-show** ("I tightened the intro and dropped the tool mention" cannot be reviewed). Test: after your message, can the human **read the item as it will be** without opening a file? No → the message failed.

## Reference
`reference/deliverable-layer/deliverable-layer-protocol.md` (§ « Revue de slides »)
