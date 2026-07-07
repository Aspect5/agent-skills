# Matt Pocock Skill Pack

Pinned subset of `mattpocock/skills`, exported through the adapter seam instead
of merged into `base/skills/`.

## Rules

- `upstream/` is a checked-in snapshot, not hand-edited source.
- Update it with `python3 scripts/external_skills.py sync --pack mattpocock --source-root /path/to/mattpocock-skills`.
- Validate with `python3 scripts/external_skills.py check`.
- Install through `./install.sh`, which exports namespaced skills into
  `.generated/external-skills/` first.

## Approved exports

- `mp-codebase-design`
- `mp-diagnosing-bugs`
- `mp-domain-modeling`
- `mp-grilling`
- `mp-prototype`
- `mp-research`
- `mp-tdd`

## Why the namespace

The stable `mp-` prefix prevents collisions with first-party skills such as
`code-review` and `handoff`, and with future imported packs.
