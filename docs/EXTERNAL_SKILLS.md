# External Skills

`agent-skills` keeps first-party process in `base/skills/` and third-party packs
behind an adapter seam in `vendor/<pack>/`.

## Policy

- Do not copy third-party skills into `base/skills/`.
- Do not edit `vendor/<pack>/upstream/` by hand.
- Export third-party skills under a stable namespace prefix so they cannot
  collide with first-party or future imported skills.
- Keep only the approved subset checked in. Exclude deprecated, in-progress,
  setup-heavy, or Codex-incompatible skills until the adapter can handle them
  deliberately.

## Current pack

`vendor/mattpocock/` pins a subset of `mattpocock/skills` at commit
`16a2a5cd00b4416f673f4ff38c7971a04dd708e7`.

Approved exports:

- `mp-codebase-design`
- `mp-diagnosing-bugs`
- `mp-domain-modeling`
- `mp-grilling`
- `mp-prototype`
- `mp-research`
- `mp-tdd`

Excluded for now:

- `code-review`, `handoff`: name collisions with first-party skills.
- `grill-me`, `grill-with-docs`, `setup-matt-pocock-skills`, `triage`,
  `to-prd`, `to-issues`, `implement`, `teach`, and similar user-invoked flows:
  they rely on unsupported top-level frontmatter or repo-level setup that should
  be wrapped deliberately instead of imported raw.
- `deprecated/`, `in-progress/`, `personal/`, and repo-specific `misc/` skills:
  not part of the stable shared workflow.

## Commands

Validate the configured packs:

```bash
python3 scripts/external_skills.py check
```

Export the approved skills into `.generated/external-skills/`:

```bash
python3 scripts/external_skills.py export
```

Refresh a pinned upstream snapshot from a local clone:

```bash
python3 scripts/external_skills.py sync --pack mattpocock --source-root /path/to/mattpocock-skills
python3 scripts/external_skills.py check
```

Install everything into Codex:

```bash
./install.sh
```

Skip third-party exports when needed:

```bash
./install.sh --no-external
```
