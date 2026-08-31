#!/usr/bin/env python3
"""Imprime le short id de l'agent courant (8 premiers chars de $CLAUDE_CODE_SESSION_ID).

Sert aux agents pour connaître leur identité avant un claim — notamment pour les
gardes "≠ composeur" / "≠ premier validateur" du pipeline ressources.

Whitelisté via `Bash(tools/*.py *)` dans .claude/settings.json : aucun prompt.
"""

import os
import sys

session = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
if not session:
    sys.exit("error: CLAUDE_CODE_SESSION_ID env var is required")
print(session[:8])
