#!/bin/bash
# Hook PostToolUse (matcher Bash) — cf. .claude/settings.json.
# Un agent qui lance orchestrate.py en background ne voit jamais le bandeau
# « À L'AGENT QUI A LANCÉ CE SCRIPT » (stdout → fichier de sortie, jamais lu).
# Ce hook réinjecte l'essentiel du bandeau dans le contexte de l'appelant,
# avec la commande watch.py prête à coller (run_id = session_id[:8], même
# dérivation que orchestrate.py depuis CLAUDE_CODE_SESSION_ID).
jq -c '
  if ((.tool_input.command // "") | test("orchestrate\\.py"))
     and (.tool_input.run_in_background == true)
  then
    (.session_id[0:8]) as $run |
    {hookSpecificOutput: {
      hookEventName: "PostToolUse",
      additionalContext: ("ORCHESTRATEUR LANCÉ EN BACKGROUND (run " + $run + ") — protocole de suivi :\n→ Arme MAINTENANT l'\''outil Monitor avec : 2-consolide/outils/watch.py " + $run + "\n  (émet le log au fil de l'\''eau ; sort au marqueur terminal « flags : »).\n→ Pendant le run : task.py peek_next (LECTURE SEULE), JAMAIS claim_next.\n→ Après le run : lire .orchestrator/" + $run + "/FLAGS.md (agents tués / orphelins).")
    }}
  else empty end'
