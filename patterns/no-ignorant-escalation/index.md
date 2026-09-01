---
description: "When agents escalate gaps to the human that the KB already answers or that they could settle from raw sources."
tags: [human-protocol, context-budget, permissions]
family: agent-authoring
---

# "Never escalate from ignorance" agent template

Before flagging a gap to the human: (1) read the relevant note *in full* including its open-questions section — if your problem is listed, it's known; (2) if you doubt the synthesized layer, descend to raw sources and settle it yourself (with a source-precedence rule); (3) escalate only what survives — a term whose origin is greppable in the sources is a search you run, not a question you ask. Plus: declared preload set per role (the role→notes mapping lives in exactly one file) and tool scoping (read-only researcher by construction).

## Reference
`reference/harness/agents/`; the one-file role→notes mapping lives in `reference/consolidation-pipeline/kb-layer-protocol.md` (§ consommateur)
