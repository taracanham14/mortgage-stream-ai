---
name: adding-underwriting-rules
description: Procedure for adding or changing a deterministic underwriting rule, risk-routing condition, or affordability threshold in mortgage_agents/tools.py. Use when the user asks to add, change or tighten an underwriting rule, DTI band, risk flag or FCA citation. Do NOT use for the FastAPI layer, the dashboard, deployment, or the Privacy Shield.
---

# Adding Underwriting Rules Skill

## When to use
Use this skill when changing or adding a threshold, routing condition, or regulatory citation that lives inside `mortgage_agents/tools.py`.

## When NOT to use
Do not use this skill for modifications to the FastAPI dashboard, deployment scripts, Docker files, or the Privacy Shield gateway (`privacy.py`).

## Workflow
1. **Modify tools.py**: Edit the relevant function in [tools.py](file:///c:/Users/chris/agy2-projects/my-first-project/mortgage-stream-ai/mortgage_agents/tools.py). Keep the logic as plain, deterministic Python so the model never performs the arithmetic or applies the rule itself.
2. **Update Tests**: Add or extend a matching case in [test_core.py](file:///c:/Users/chris/agy2-projects/my-first-project/mortgage-stream-ai/tests/test_core.py) so the new behaviour is pinned by a test.
3. **Verify**: Run the verification script [run_rule_tests.sh](file:///c:/Users/chris/agy2-projects/my-first-project/mortgage-stream-ai/.agents/skills/adding-underwriting-rules/scripts/run_rule_tests.sh) and confirm it passes before treating the change as done.
