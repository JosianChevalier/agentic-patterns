---
description: "When every script invocation triggers a permission prompt and you want one allowlist entry to cover all tools."
tags: [permissions, agent-identity]
family: harness-permissions
---

# `tools/` symlink facade for prompt-free allowlisting

Claude Code's Bash allowlist matches the literal command string and `*` doesn't cross `/`. Keep scripts in the layer they serve; expose **flat file symlinks** in `tools/`; one allowlist entry `Bash(tools/*.py *)` covers everything. Invariants: never a directory symlink (re-prompts), every new executable gets symlink + doc row. Deny-list only the git shapes that break concurrency (`git -C`, `git add .`/`-A`, `commit -a`), not git wholesale. Corollary pattern: `CLAUDE_CODE_SESSION_ID` sits in the Bash env but `echo $VAR` isn't cleanly allowlistable → package the read as a 3-line `tools/whoami.py` (fail-loud) that falls under the single entry; one derivation of the session short, three uses (commits, leases, run-id).

## Reference
`reference/harness/permissions-playbook.md`, `reference/harness/settings.json`
