def command_scan(args: argparse.Namespace) -> int:
    target, label, base = resolve_target_home(args.profile, args.home)
    if not target.exists():
        raise DreamingError(f"Requested profile home does not exist: {target}")

    run_id = args.cycle_id or cycle_id()
    run_dir = target / "dreaming" / "runs" / run_id
    snapshot_dir = target / "dreaming" / "snapshots" / run_id
    if run_dir.exists() or snapshot_dir.exists():
        raise DreamingError(f"Cycle already exists: {run_id}")

    skills_root = target / "skills"
    memories_root = target / "memories"
    script_skill_dir = Path(__file__).resolve().parent.parent
    protected_dirs = discover_protected_skill_dirs(skills_root, script_skill_dir)

    with lock_directory(target):
        run_dir.mkdir(parents=True)
        snapshot_dir.mkdir(parents=True)
        files: list[dict[str, Any]] = []
        counts = {
            "skills": 0,
            "memories": 0,
            "editable": 0,
            "protected": 0,
            "skipped": 0,
        }

        for kind, root in (("skill", skills_root), ("memory", memories_root)):
            for path in iter_files(root):
                rel = safe_relative(path, target)
                protected = path_under_any(path, protected_dirs)
                editable, skipped_reason = is_text_candidate(path, args.max_file_bytes)
                if protected:
                    editable = False
                    skipped_reason = "protected-skill"
                entry: dict[str, Any] = {
                    "path": rel,
                    "kind": kind,
                    "size_bytes": path.lstat().st_size,
                    "sha256": None if path.is_symlink() else sha256_file(path),
                    "editable": editable,
                    "protected": protected,
                    "skipped_reason": skipped_reason,
                }
                files.append(entry)
                counts["skills" if kind == "skill" else "memories"] += 1
                if editable:
                    counts["editable"] += 1
                else:
                    counts["skipped"] += 1
                if protected:
                    counts["protected"] += 1
                snapshot_file(path, snapshot_dir / rel)

        manifest = {
            "schema_version": 1,
            "tool_version": TOOL_VERSION,
            "cycle_id": run_id,
            "created_at": utc_now(),
            "target_profile": label,
            "target_home": str(target),
            "base_home": str(base),
            "scope": {
                "include": ["skills/**", "memories/**"],
                "exclude_other_profiles": True,
                "exclude_external_skill_dirs": True,
                "protected_skill_dirs": [
                    safe_relative(path, target) for path in sorted(protected_dirs)
                ],
            },
            "roots": {
                "skills": str(skills_root),
                "memories": str(memories_root),
            },
            "counts": counts,
            "files": files,
        }
        write_json(run_dir / "manifest.json", manifest)
        write_json(
            run_dir / "status.json",
            {
                "cycle_id": run_id,
                "state": "SCANNED",
                "updated_at": utc_now(),
                "mode": "REPORT_ONLY",
            },
        )

        workspace = f"""# Dreaming Analysis Workspace\n\n- Cycle ID: `{run_id}`\n- Target profile: `{label}`\n- Target home: `{target}`\n- Scope: only `{target}/skills` and `{target}/memories`\n- Other profiles: excluded\n- External skill directories: excluded\n- Default mode: report only\n\nCreate `change_plan.json` in this run directory using the bundled schema.\nDo not modify source files during analysis.\n"""
        (run_dir / "WORKSPACE.md").write_text(workspace, encoding="utf-8")

    result = {
        "cycle_id": run_id,
        "target_profile": label,
        "target_home": str(target),
        "run_dir": str(run_dir),
        "snapshot_dir": str(snapshot_dir),
        "manifest": str(run_dir / "manifest.json"),
        "counts": counts,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

def manifest_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["path"]: entry for entry in manifest.get("files", [])}

def validate_skill_frontmatter(path: str, content: str) -> list[str]:
    errors: list[str] = []
    if not path.endswith("/SKILL.md") and path != "skills/SKILL.md":
        return errors
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return [f"{path}: SKILL.md must begin with YAML frontmatter ('---')."]
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return [f"{path}: SKILL.md frontmatter is not closed."]
    frontmatter = "\n".join(lines[1:end])
    if not re.search(r"(?m)^name\s*:\s*\S+", frontmatter):
        errors.append(f"{path}: SKILL.md frontmatter is missing name.")
    if not re.search(r"(?m)^description\s*:\s*\S+", frontmatter):
        errors.append(f"{path}: SKILL.md frontmatter is missing description.")
    return errors
