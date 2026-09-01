---
description: "When one content source must feed both a fast stakeholder-validation loop and a costly contractual deliverable: a disposable deterministic renderer for iteration, the expensive renderer paid once at sign-off."
tags: [derived-views, human-protocol]
family: kb-conventions
---

# One source, two renderers

The content markdown is the **single source**; the rendering layer holds **two renderers** that consume it — never the other way around:

- **Validation renderer — disposable.** Deterministic md → HTML(+PDF), **zero manual realignment**. This is where content iterates fast; it's what the stakeholder sees and validates on. Short-lived: thrown away after the switch to the contractual renderer — but it must stay faithful to the target template as long as it serves as validation surface.
- **Contractual renderer — the deliverable.** The format actually handed over (e.g. `.pptx` via templates). Manual fine realignment is paid **once, at validation** — deferred until content is frozen.

The gain comes from the cheap renderer (instant feedback, no formatting work); the expensive cost is deferred and paid a single time.

**Master constraint — layout congruence.** The stakeholder validates on the cheap renderer: if the contractual renderer renders differently, you deliver a form nobody validated. So the cheap renderer's layouts **mirror** the contractual template's. A minimal template keeps that mirroring cheap.

**Interface contract between layers = a markdown grammar.** One grammar names each item's **type** and fixes the body vocabulary (bullets, callouts, placeholders, tables…). Derived from existing content and validated on the rendered output, not in the abstract. Type auto-detection by default; an explicit per-item marker **overrides** it.

**Degraded build is non-blocking.** Exporter missing or failing → the HTML is still written, the stale PDF is flagged (`!`) — never a hard failure of the loop.

Directory structure follows the principle: **one directory per render target** (validation chain vs deliverable), not per engine or theme.

## Reference
`reference/presentation-layer/presentation-layer-protocol.md`
`reference/deliverable-layer/deliverable-layer-protocol.md` (§ « Rendu direct — grammaire 4→5 » : marqueur de template explicite vs auto-détection)
