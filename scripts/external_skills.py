#!/usr/bin/env python3
"""Sync, validate, and export approved third-party skill packs."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
import re

SUPPORTED_FRONTMATTER_KEYS = {"name", "description", "metadata"}
TOP_LEVEL_KEY_RE = re.compile(r"^([A-Za-z0-9_-]+):(.*)$")


@dataclass(frozen=True)
class SourceInfo:
    repo: str
    commit: str
    license_path: str | None


@dataclass(frozen=True)
class ExportSpec:
    pack_id: str
    pack_dir: Path
    source: SourceInfo
    source_path: str
    target_name: str
    drop_frontmatter_keys: tuple[str, ...]

    @property
    def vendor_source_dir(self) -> Path:
        return self.pack_dir / "upstream" / self.source_path


def repo_root_from_arg(value: str | None) -> Path:
    if value:
        return Path(value).resolve()
    return Path(__file__).resolve().parents[1]


def find_manifest_paths(repo_root: Path) -> list[Path]:
    vendor_root = repo_root / "vendor"
    if not vendor_root.is_dir():
        return []
    return sorted(vendor_root.glob("*/pack.json"))


def load_manifests(repo_root: Path, pack_filter: str | None) -> list[tuple[Path, dict]]:
    manifests: list[tuple[Path, dict]] = []
    for manifest_path in find_manifest_paths(repo_root):
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        pack_id = data.get("id")
        if not pack_id:
            raise ValueError(f"{manifest_path}: missing 'id'")
        if pack_filter and pack_filter != pack_id:
            continue
        manifests.append((manifest_path, data))
    if pack_filter and not manifests:
        raise ValueError(f"no pack.json found for pack '{pack_filter}'")
    return manifests


def collect_export_specs(repo_root: Path, manifests: list[tuple[Path, dict]]) -> list[ExportSpec]:
    base_names = {
        path.name for path in (repo_root / "base" / "skills").iterdir() if path.is_dir()
    }
    seen_targets: dict[str, str] = {}
    specs: list[ExportSpec] = []

    for manifest_path, data in manifests:
        if data.get("schema_version") != 1:
            raise ValueError(f"{manifest_path}: unsupported schema_version {data.get('schema_version')!r}")
        pack_id = data["id"]
        pack_dir = manifest_path.parent
        source_block = data.get("source") or {}
        source = SourceInfo(
            repo=source_block.get("repo", ""),
            commit=source_block.get("commit", ""),
            license_path=source_block.get("license_path"),
        )
        if not source.repo or not source.commit:
            raise ValueError(f"{manifest_path}: source.repo and source.commit are required")
        exports = data.get("exports")
        if not isinstance(exports, list) or not exports:
            raise ValueError(f"{manifest_path}: exports must be a non-empty list")

        for item in exports:
            source_path = item.get("source")
            target_name = item.get("target")
            if not source_path or not target_name:
                raise ValueError(f"{manifest_path}: each export needs source and target")
            if target_name in base_names:
                raise ValueError(
                    f"{manifest_path}: target '{target_name}' collides with base/skills/{target_name}"
                )
            owner = seen_targets.get(target_name)
            if owner:
                raise ValueError(
                    f"{manifest_path}: target '{target_name}' also declared by external pack '{owner}'"
                )
            seen_targets[target_name] = pack_id
            drop_keys = tuple(item.get("drop_frontmatter_keys", []))
            specs.append(
                ExportSpec(
                    pack_id=pack_id,
                    pack_dir=pack_dir,
                    source=source,
                    source_path=source_path,
                    target_name=target_name,
                    drop_frontmatter_keys=drop_keys,
                )
            )
    return specs


def split_frontmatter(text: str, path: Path) -> tuple[str, str]:
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError(f"{path}: unterminated YAML frontmatter")
    frontmatter = text[4:end]
    body = text[end + 5 :]
    return frontmatter, body


def frontmatter_blocks(frontmatter: str, path: Path) -> list[tuple[str, list[str]]]:
    blocks: list[tuple[str, list[str]]] = []
    current_key: str | None = None
    current_lines: list[str] = []

    for line in frontmatter.splitlines():
        match = TOP_LEVEL_KEY_RE.match(line) if line and line[0] not in " \t" else None
        if match:
            if current_key is not None:
                blocks.append((current_key, current_lines))
            current_key = match.group(1)
            current_lines = [line]
            continue
        if current_key is None:
            raise ValueError(f"{path}: unexpected frontmatter content before first key")
        current_lines.append(line)

    if current_key is not None:
        blocks.append((current_key, current_lines))
    return blocks


def rewrite_frontmatter(
    frontmatter: str,
    path: Path,
    target_name: str,
    drop_keys: tuple[str, ...],
) -> tuple[str, list[str]]:
    blocks = frontmatter_blocks(frontmatter, path)
    rendered: list[str] = []
    keys_after_drop: list[str] = []
    dropped = set(drop_keys)

    for key, lines in blocks:
        if key in dropped:
            continue
        keys_after_drop.append(key)
        if key == "name":
            lines = [f"name: {target_name}", *lines[1:]]
        rendered.extend(lines)

    if not rendered:
        raise ValueError(f"{path}: frontmatter is empty after filtering")
    return "\n".join(rendered) + "\n", keys_after_drop


def validate_skill(spec: ExportSpec) -> None:
    skill_dir = spec.vendor_source_dir
    skill_md = skill_dir / "SKILL.md"
    if not skill_dir.is_dir():
        raise ValueError(
            f"[{spec.pack_id}] missing vendored source directory: {skill_dir}"
        )
    if not skill_md.is_file():
        raise ValueError(f"[{spec.pack_id}] missing SKILL.md: {skill_md}")

    frontmatter, _ = split_frontmatter(skill_md.read_text(encoding="utf-8"), skill_md)
    _, keys_after_drop = rewrite_frontmatter(
        frontmatter=frontmatter,
        path=skill_md,
        target_name=spec.target_name,
        drop_keys=spec.drop_frontmatter_keys,
    )

    missing = sorted({"name", "description"} - set(keys_after_drop))
    if missing:
        raise ValueError(
            f"[{spec.pack_id}] {skill_md}: missing required frontmatter keys after filtering: {', '.join(missing)}"
        )

    unsupported = sorted(set(keys_after_drop) - SUPPORTED_FRONTMATTER_KEYS)
    if unsupported:
        raise ValueError(
            f"[{spec.pack_id}] {skill_md}: unsupported top-level frontmatter keys remain: {', '.join(unsupported)}"
        )


def export_skill(spec: ExportSpec, output_dir: Path) -> None:
    source_dir = spec.vendor_source_dir
    target_dir = output_dir / spec.target_name
    if target_dir.exists():
        shutil.rmtree(target_dir)
    shutil.copytree(source_dir, target_dir)

    skill_md = target_dir / "SKILL.md"
    original = skill_md.read_text(encoding="utf-8")
    frontmatter, body = split_frontmatter(original, skill_md)
    rewritten_frontmatter, _ = rewrite_frontmatter(
        frontmatter=frontmatter,
        path=skill_md,
        target_name=spec.target_name,
        drop_keys=spec.drop_frontmatter_keys,
    )
    skill_md.write_text(f"---\n{rewritten_frontmatter}---\n{body}", encoding="utf-8")


def sync_pack(specs: list[ExportSpec], source_root: Path, allow_commit_mismatch: bool) -> None:
    if not source_root.is_dir():
        raise ValueError(f"source_root does not exist: {source_root}")

    expected_commits = {spec.source.commit for spec in specs}
    if len(expected_commits) != 1:
        raise ValueError("selected exports do not agree on a single upstream commit")

    actual_commit = git_head(source_root)
    expected_commit = next(iter(expected_commits))
    if actual_commit and actual_commit != expected_commit and not allow_commit_mismatch:
        raise ValueError(
            f"{source_root}: HEAD is {actual_commit}, but manifest expects {expected_commit}. "
            "Update pack.json first or re-run with --allow-commit-mismatch."
        )

    upstream_root = specs[0].pack_dir / "upstream"
    if upstream_root.exists():
        shutil.rmtree(upstream_root)

    copied_license_targets: set[Path] = set()
    for spec in specs:
        src_dir = source_root / spec.source_path
        if not src_dir.is_dir():
            raise ValueError(f"[{spec.pack_id}] source path not found in clone: {src_dir}")
        dest_dir = spec.vendor_source_dir
        dest_dir.parent.mkdir(parents=True, exist_ok=True)
        if dest_dir.exists():
            shutil.rmtree(dest_dir)
        shutil.copytree(src_dir, dest_dir)

        if spec.source.license_path:
            license_src = source_root / spec.source.license_path
            if license_src.is_file():
                license_dest = spec.pack_dir / "LICENSE.upstream"
                if license_dest not in copied_license_targets:
                    shutil.copy2(license_src, license_dest)
                    copied_license_targets.add(license_dest)


def git_head(path: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def cmd_check(args: argparse.Namespace) -> int:
    repo_root = repo_root_from_arg(args.repo_root)
    manifests = load_manifests(repo_root, args.pack)
    if not manifests:
        print("No external packs configured.")
        return 0
    specs = collect_export_specs(repo_root, manifests)
    for spec in specs:
        validate_skill(spec)
    pack_ids = sorted({spec.pack_id for spec in specs})
    print(f"Validated {len(specs)} exported skill(s) across {len(pack_ids)} pack(s).")
    for pack_id in pack_ids:
        names = sorted(spec.target_name for spec in specs if spec.pack_id == pack_id)
        print(f"- {pack_id}: {', '.join(names)}")
    return 0


def cmd_export(args: argparse.Namespace) -> int:
    repo_root = repo_root_from_arg(args.repo_root)
    output_dir = Path(args.output_dir).resolve() if args.output_dir else repo_root / ".generated" / "external-skills"
    manifests = load_manifests(repo_root, args.pack)
    if not manifests:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        print("No external packs configured.")
        return 0
    specs = collect_export_specs(repo_root, manifests)
    for spec in specs:
        validate_skill(spec)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    for spec in specs:
        export_skill(spec, output_dir)

    print(f"Exported {len(specs)} skill(s) into {output_dir}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    repo_root = repo_root_from_arg(args.repo_root)
    manifests = load_manifests(repo_root, args.pack)
    if not manifests:
        raise ValueError("no external packs configured")
    if len(manifests) > 1 and not args.pack:
        raise ValueError("sync requires --pack when more than one external pack exists")
    specs = collect_export_specs(repo_root, manifests)
    sync_pack(
        specs=specs,
        source_root=Path(args.source_root).resolve(),
        allow_commit_mismatch=args.allow_commit_mismatch,
    )
    print(f"Synced {len(specs)} source skill(s) into vendor snapshots.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage approved third-party skill packs."
    )
    parser.add_argument("--repo-root", help="Path to the agent-skills repo root.")

    subparsers = parser.add_subparsers(dest="command", required=True)

    check_parser = subparsers.add_parser("check", help="Validate configured external packs.")
    check_parser.add_argument("--pack", help="Limit the operation to one pack id.")
    check_parser.set_defaults(func=cmd_check)

    export_parser = subparsers.add_parser(
        "export", help="Materialize approved external skills into a generated directory."
    )
    export_parser.add_argument("--pack", help="Limit the operation to one pack id.")
    export_parser.add_argument(
        "--output-dir",
        help="Directory to populate. Defaults to <repo>/.generated/external-skills.",
    )
    export_parser.set_defaults(func=cmd_export)

    sync_parser = subparsers.add_parser(
        "sync", help="Refresh a checked-in upstream snapshot from a local clone."
    )
    sync_parser.add_argument("--pack", help="Pack id to sync.")
    sync_parser.add_argument("--source-root", required=True, help="Path to a local clone of the upstream repo.")
    sync_parser.add_argument(
        "--allow-commit-mismatch",
        action="store_true",
        help="Allow syncing from a clone whose HEAD differs from the pinned manifest commit.",
    )
    sync_parser.set_defaults(func=cmd_sync)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
