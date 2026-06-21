---
# Copy to <project>/.agents/profiles/code-review.md and edit. Every field is OPTIONAL —
# the base skill runs unmodified with no profile, and better with one. The base depends
# on this SHAPE, never on your values.
skill: code-review
extends: code-review@1
project: <project-name>

# Command discovery override. Omit any key and the skill auto-detects from
# package.json / pyproject.toml / Makefile / .github/workflows. Never assumed.
commands:
  lint: "<lint command>"
  test: "<test command>"
  ci: "<full gate command>"

severity_floor: should-fix        # blocker | should-fix | nit
focus_paths: []                   # weight findings here higher
ignore_paths: []                  # never flag (e.g. generated code)

# Budget / model knobs — skills self-throttle on these.
model: <your harness model id>   # tier is what matters — cheaper ⇒ lower-freedom, stronger ⇒ more latitude
                                 #   Codex: gpt-5.4 / gpt-5.5 · Claude Code: claude-haiku-4-5 / claude-opus-4-8
budget:
  period: day                    # day | month
  limit_usd: 100
fan_out: ask                     # allowed | ask | never  (gate on multi-agent spend)
---

## ADD
- <project-specific rules appended to the base checklist, e.g. "every new DB query must be tenant-scoped">

## OVERRIDE
- base:migration-reversible → <e.g. migrations use an in-house tool; require its down-stanza, not a SQL rollback>

## SUPPRESS
- base:security-secrets   # <reason this project opts out, e.g. a dedicated gitleaks gate already covers it>
