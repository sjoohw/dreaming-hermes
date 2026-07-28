def command_render(args: argparse.Namespace) -> int:
    run_dir, manifest, target, label = load_run(args)
    plan = read_json(run_dir / "change_plan.json")
    errors = validate_plan_data(plan, manifest, args.memory_limit, args.user_limit)
    validation_status = "PASS" if not errors else "FAIL"
    snapshot_dir = target / "dreaming" / "snapshots" / manifest["cycle_id"]

    grouped: dict[str, list[dict[str, Any]]] = {action: [] for action in sorted(ALLOWED_ACTIONS)}
    for candidate in plan.get("candidates", []):
        grouped.setdefault(candidate.get("action", "UNKNOWN"), []).append(candidate)

    lines: list[str] = [
        f"# Dreaming Report — {manifest['cycle_id']}",
        "",
        "## Execution",
        "",
        f"- Target profile: `{label}`",
        f"- Target home: `{target}`",
        f"- Scope: `{target}/skills`, `{target}/memories` only",
        "- Other profiles: excluded",
        "- External skill directories: excluded",
        f"- Generated at: `{utc_now()}`",
        f"- Plan validation: **{validation_status}**",
        f"- Mode: **REPORT_ONLY** unless separately approved and applied",
        "",
        "## Summary",
        "",
        f"- Scanned skill files: {manifest['counts']['skills']}",
        f"- Scanned memory files: {manifest['counts']['memories']}",
        f"- Editable text files: {manifest['counts']['editable']}",
        f"- Protected files: {manifest['counts']['protected']}",
        f"- Proposed candidates: {len(plan.get('candidates', []))}",
        "",
    ]

    if errors:
        lines.extend(["## Validation Errors", ""])
        lines.extend(f"- {error}" for error in errors)
        lines.append("")

    for action in [
        "CORRECT",
        "MERGE",
        "INTEGRATE",
        "SPLIT",
        "PRUNE",
        "PROMOTE_CANDIDATE",
        "DEFER",
        "KEEP",
    ]:
        candidates = grouped.get(action, [])
        if not candidates:
            continue
        lines.extend([f"## {action}", ""])
        for candidate in candidates:
            cid = candidate.get("candidate_id", "UNKNOWN")
            lines.extend(
                [
                    f"### {cid}",
                    "",
                    f"- Risk: Level {candidate.get('risk_level')}",
                    f"- Confidence: {candidate.get('confidence')}",
                    f"- Requires approval: {candidate.get('requires_approval')}",
                    f"- Approved: {candidate.get('approved', False)}",
                    f"- Reason: {candidate.get('reason', '')}",
                ]
            )
            evidence = candidate.get("evidence", [])
            if evidence:
                lines.append("- Evidence:")
                lines.extend(f"  - {item}" for item in evidence)
            sources = candidate.get("source_paths", [])
            if sources:
                lines.append("- Sources:")
                lines.extend(f"  - `{item}`" for item in sources)
            quarantine = candidate.get("quarantine_paths", [])
            if quarantine:
                lines.append("- Quarantine:")
                lines.extend(f"  - `{item}`" for item in quarantine)

            for write in candidate.get("writes", []):
                rel = write["path"]
                old = read_snapshot_text(snapshot_dir, rel) or ""
                new = write["content"]
                diff = list(
                    difflib.unified_diff(
                        old.splitlines(keepends=True),
                        new.splitlines(keepends=True),
                        fromfile=f"a/{rel}",
                        tofile=f"b/{rel}",
                    )
                )
                lines.extend(["", f"Proposed diff for `{rel}`:", "", "```diff"])
                lines.extend(line.rstrip("\n") for line in truncate_diff(diff))
                lines.extend(["```", ""])
            lines.append("")

    report_path = run_dir / "report.md"
    report_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    result = {
        "cycle_id": manifest["cycle_id"],
        "report": str(report_path),
        "validation": validation_status,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 2

def command_rollback(args: argparse.Namespace) -> int:
    run_dir, manifest, target, label = load_run(args)
    result_path = run_dir / "apply_result.json"
    apply_result = read_json(result_path)
    if apply_result.get("status") not in {"APPLIED", "ROLLED_BACK"}:
        raise DreamingError("Run has no applied state to roll back.")
    if apply_result.get("status") == "ROLLED_BACK":
        raise DreamingError("This cycle was already rolled back.")

    snapshot_dir = target / "dreaming" / "snapshots" / manifest["cycle_id"]
    touched = set(apply_result.get("touched_paths", []))
    post_hashes = apply_result.get("post_hashes", {})

    conflicts: list[str] = []
    for rel in sorted(touched):
        path = target / rel
        expected = post_hashes.get(rel)
        current = sha256_file(path) if path.exists() and path.is_file() else None
        if current != expected:
            conflicts.append(rel)
    if conflicts and not args.force:
        raise DreamingError(
            "Files changed after Dreaming apply; refusing rollback without --force:\n- "
            + "\n- ".join(conflicts)
        )

    with lock_directory(target):
        restore_touched_paths(target, snapshot_dir, manifest, touched)
        quarantine_root = Path(apply_result.get("quarantine_root", target / "dreaming" / "quarantine" / manifest["cycle_id"]))
        cleanup_quarantine_paths(quarantine_root, touched)
        apply_result["status"] = "ROLLED_BACK"
        apply_result["rolled_back_at"] = utc_now()
        apply_result["rollback_forced"] = bool(args.force)
        write_json(result_path, apply_result)
        write_json(
            run_dir / "status.json",
            {
                "cycle_id": manifest["cycle_id"],
                "state": "ROLLED_BACK",
                "updated_at": utc_now(),
                "mode": "ROLLBACK",
            },
        )

    output = {
        "cycle_id": manifest["cycle_id"],
        "target_profile": label,
        "status": "ROLLED_BACK",
        "restored_paths": sorted(touched),
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0

def add_target_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--profile",
        help="Target profile name. Use 'default' for ~/.hermes.",
    )
    group.add_argument(
        "--home",
        help="Explicit target HERMES_HOME path. Overrides profile resolution.",
    )

def add_run_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run-dir", help="Path to a Dreaming run directory.")
    group.add_argument("--cycle-id", help="Cycle ID under the target profile.")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safe profile-scoped Dreaming helper for Hermes Agent."
    )
    parser.add_argument("--version", action="version", version=TOOL_VERSION)
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve = subparsers.add_parser("resolve", help="Resolve a requested profile home.")
    add_target_args(resolve)
    resolve.set_defaults(func=command_resolve)

    scan = subparsers.add_parser(
        "scan", help="Create a profile-scoped manifest and rollback snapshot."
    )
    add_target_args(scan)
    scan.add_argument("--cycle-id", help="Optional explicit cycle ID.")
    scan.add_argument(
        "--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES
    )
    scan.set_defaults(func=command_scan)

    validate = subparsers.add_parser("validate", help="Validate change_plan.json.")
    add_target_args(validate)
    add_run_args(validate)
    validate.add_argument("--memory-limit", type=int, default=DEFAULT_MEMORY_LIMIT)
    validate.add_argument("--user-limit", type=int, default=DEFAULT_USER_LIMIT)
    validate.set_defaults(func=command_validate)

    render = subparsers.add_parser("render", help="Render report.md from the plan.")
    add_target_args(render)
    add_run_args(render)
    render.add_argument("--memory-limit", type=int, default=DEFAULT_MEMORY_LIMIT)
    render.add_argument("--user-limit", type=int, default=DEFAULT_USER_LIMIT)
    render.set_defaults(func=command_render)

    apply = subparsers.add_parser(
        "apply", help="Apply only approved candidates after validation."
    )
    add_target_args(apply)
    add_run_args(apply)
    apply.add_argument(
        "--auto-level1",
        action="store_true",
        help="Also apply eligible HIGH-confidence Level 1 candidates.",
    )
    apply.add_argument("--memory-limit", type=int, default=DEFAULT_MEMORY_LIMIT)
    apply.add_argument("--user-limit", type=int, default=DEFAULT_USER_LIMIT)
    apply.set_defaults(func=command_apply)

    rollback = subparsers.add_parser("rollback", help="Roll back one applied cycle.")
    add_target_args(rollback)
    add_run_args(rollback)
    rollback.add_argument(
        "--force",
        action="store_true",
        help="Overwrite files changed after apply. Use only with explicit user approval.",
    )
    rollback.set_defaults(func=command_rollback)

    return parser
