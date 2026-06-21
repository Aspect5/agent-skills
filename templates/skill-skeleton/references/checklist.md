# <skill-name> checklist (stable `base:<id>` checks)

Each check has a stable id so a project profile (`.agents/profiles/<skill-name>.md`) can
`OVERRIDE base:<id>` (rebind a default) or `SUPPRESS base:<id>` (turn it off). The base
ships these ids; the project rebinds them — neither side ever forks the body.

Only load this file when you need the full check list or are applying a profile.

## <Group>

- **base:<some-check>** — <what it asserts, in one line>.
- **base:<another-check>** — <...>.
