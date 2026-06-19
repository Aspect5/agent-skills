# Safe-deletion bar (`base:safe-deletion-bar`)

Deletion is the highest-value simplification AND the easiest way to cause a silent outage.
Before removing **any** symbol, file, route, flag, or dependency, clear **all four gates**.
If **any** gate is unmet, downgrade the item to an advisory finding ("likely dead, needs
human confirmation") — do not delete it.

Only load this file when you are about to delete something (SKILL.md Step 6).

## Gate 1 — No live callers, including non-static entry

- grep the **whole repo** (not just the current module) for the symbol/name and confirm
  zero live references. Capture the grep as evidence.
- Rule out **non-static** reachability — the trap LLMs miss:
  - **Dynamic / reflection**: `getattr`, `globals()[name]`, `importlib`, `__getattr__`,
    `eval`, Python entry-points, decorators that register by name.
  - **String-keyed dispatch**: route tables, command registries, event-name maps, plugin
    registries, serializer/`type`-field switches, DI containers keyed by string.
  - **Config-/data-driven**: a class/function named in YAML/JSON/env/DB that a loader
    resolves at runtime.
  - **Framework magic**: ORM hooks, signal handlers, test fixtures auto-collected by name,
    serialization that reflects over fields, public package re-exports (`__init__.py`,
    `index.ts`) that external code may import.
  - **Cross-language / cross-process**: a backend route hit only by a separate frontend
    build or an external client; an event consumed by another service. grep the consuming
    surface too, or mark it "needs investigation".

## Gate 2 — Both sides of every contract accounted for

- If the thing participates in a contract (an event it emits, a key in a persisted blob, a
  field a serializer writes, a response a client reads), confirm the **other side** is gone
  or migrated too. Deleting a producer while a consumer still reads the format is a silent
  break. This is `base:both-sides-of-contract` applied to deletion.

## Gate 3 — Behavior anchor green

- The characterization/golden-master/integration anchor from SKILL.md Step 3 must be green
  **before** the deletion and **after** it. If nothing exercises the code you're deleting,
  that is *weaker* evidence of deadness, not stronger — add a quick reachability probe or
  downgrade to advisory.

## Gate 4 — Not reachable via deploy / runtime config

- Confirm the code is not wired in only under a flag, environment, deploy manifest, feature
  toggle, or cron/scheduler that your local grep doesn't see. Check `.env*` examples,
  deploy YAML, IaC, and scheduler/cron definitions. "Unused on the happy path" ≠ "unused".

## Evidence template (attach to every deletion)

```
DELETE: <path-or-symbol>
- Gate 1 callers:   grep '<name>' across repo → 0 hits; no dynamic/string/config/framework entry (checked: <which>)
- Gate 2 contract: <none | producer+consumer both removed/migrated: …>
- Gate 3 anchor:   <test/cmd> green before & after
- Gate 4 runtime:  not referenced in env/deploy/cron (checked: <which>)
```

## If you cannot clear a gate

Report it as advisory, e.g.:

> `LegacyFooService` — **likely dead** (0 static callers) but reachable via the string-keyed
> handler registry in `dispatch.py:88`; needs human confirmation before deletion.

A confident "needs human confirmation" beats a wrong deletion. Removing reachable code is
exactly the regression this skill exists to prevent.
