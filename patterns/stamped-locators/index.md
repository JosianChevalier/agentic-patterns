---
description: "When items in rendered files need stable chat-safe addresses: locators stamped into a render-stripped zone by an idempotent annotate tool, plus a resolver."
tags: [discovery, human-protocol, idempotency, derived-views]
family: kb-conventions
---

# Stamped locators in a render-stripped zone

Every item gets a locator `NN#MM` (file prefix + 1-based block index), **stamped into the item itself** — inside the trailing italic parenthesis of its title, a zone the renderer strips, so the address exists in the source but never on screen (the one sanctioned exception to "no internal ids in displayed titles"; a parenthesis that *belongs* to the displayed title, e.g. an acronym, is never touched — the locator is appended after it). `annotate` is **idempotent**: rerun after any add/remove/move and it renumbers everything (never renumber by hand); an untitled block still consumes a number, because numbering = rendered order, not title count. The same tool **resolves** the other way (`00#44` → title), which is what makes the "never a bare locator" rule cheap to honor: content leads, locator follows in parentheses, and anyone can expand one. Downstream anchors (sidecar items, audit maps) reuse the same locators — a re-annotate that shifts numbers means updating dependents and regenerating derived views, or they desync silently.

## Reference
`reference/deliverable-layer/slides.py`; rules in `reference/deliverable-layer/deliverable-layer-protocol.md` (§ « Locators de slides »)
