def verify_manifest_unchanged(
    target: Path,
    manifest: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> None:
    known = manifest_map(manifest)
    relevant: set[str] = set()
    for candidate in candidates:
        relevant.update(candidate.get("source_paths", []))
        relevant.update(candidate.get("quarantine_paths", []))
        for write in candidate.get("writes", []):
            if write.get("path") in known:
                relevant.add(write["path"])

    errors: list[str] = []
    for raw in sorted(relevant):
        rel = normalize_relative(raw)
        entry = known.get(rel)
        if not entry:
            errors.append(f"Not in manifest: {rel}")
            continue
        path = target / rel
        if not path.exists() and not path.is_symlink():
            errors.append(f"Missing since scan: {rel}")
            continue
        if path.is_symlink():
            errors.append(f"Symlink cannot be modified: {rel}")
            continue
        current = sha256_file(path)
        if current != entry.get("sha256"):
            errors.append(f"Changed since scan: {rel}")
    if errors:
        raise DreamingError("Manifest conflict:\n- " + "\n- ".join(errors))

def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp_name)
        raise

def restore_touched_paths(
    target: Path,
    snapshot_dir: Path,
    original_manifest: dict[str, Any],
    touched: set[str],
) -> None:
    known = manifest_map(original_manifest)
    for rel in sorted(touched, key=lambda value: len(Path(value).parts), reverse=True):
        destination = target / rel
        snapshot = snapshot_dir / rel
        if rel in known:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() or destination.is_symlink():
                if destination.is_dir() and not destination.is_symlink():
                    shutil.rmtree(destination)
                else:
                    destination.unlink()
            snapshot_file(snapshot, destination)
        else:
            if destination.exists() or destination.is_symlink():
                if destination.is_dir() and not destination.is_symlink():
                    shutil.rmtree(destination)
                else:
                    destination.unlink()

def validate_written_state(
    target: Path,
    candidates: list[dict[str, Any]],
    memory_limit: int,
    user_limit: int,
) -> list[str]:
    errors: list[str] = []
    for candidate in candidates:
        cid = candidate["candidate_id"]
        for write in candidate.get("writes", []):
            rel = normalize_relative(write["path"])
            path = target / rel
            if not path.exists():
                errors.append(f"{cid}: write missing after apply: {rel}")
                continue
            try:
                content = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError) as exc:
                errors.append(f"{cid}: cannot read written file {rel}: {exc}")
                continue
            if content != write["content"]:
                errors.append(f"{cid}: written content mismatch: {rel}")
            errors.extend(validate_skill_frontmatter(rel, content))
            if rel == "memories/MEMORY.md" and len(content) > memory_limit:
                errors.append(f"{cid}: MEMORY.md exceeds limit after apply.")
            if rel == "memories/USER.md" and len(content) > user_limit:
                errors.append(f"{cid}: USER.md exceeds limit after apply.")
        for raw in candidate.get("quarantine_paths", []):
            rel = normalize_relative(raw)
            if (target / rel).exists():
                errors.append(f"{cid}: source still exists after quarantine: {rel}")
    return errors

def cleanup_quarantine_paths(quarantine_root: Path, relative_paths: Iterable[str]) -> None:
    for rel in relative_paths:
        path = quarantine_root / rel
        if path.exists() or path.is_symlink():
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
    # Remove empty directories, but keep the cycle root if it still contains data.
    if quarantine_root.exists():
        for current, dirs, files in os.walk(quarantine_root, topdown=False):
            current_path = Path(current)
            if not dirs and not files:
                with contextlib.suppress(OSError):
                    current_path.rmdir()

def command_apply(args: argparse.Namespace) -> int:
    run_dir, manifest, target, label = load_run(args)
    plan = read_json(run_dir / "change_plan.json")
    errors = validate_plan_data(plan, manifest, args.memory_limit, args.user_limit)
    if errors:
        raise DreamingError("Plan validation failed:\n- " + "\n- ".join(errors))

    selected = approved_candidates(plan, args.auto_level1)
    if not selected:
        raise DreamingError(
            "No approved actionable candidates. Set candidate.approved=true, or use "
            "--auto-level1 for eligible Level 1 changes."
        )

    run_id = manifest["cycle_id"]
    snapshot_dir = target / "dreaming" / "snapshots" / run_id
    quarantine_root = target / "dreaming" / "quarantine" / run_id
    if not snapshot_dir.exists():
        raise DreamingError(f"Snapshot missing: {snapshot_dir}")

    touched: set[str] = set()
    applied_candidate_ids: list[str] = []
    created_paths: set[str] = set()

    with lock_directory(target):
        verify_manifest_unchanged(target, manifest, selected)
        try:
            for candidate in selected:
                cid = candidate["candidate_id"]
                for write in candidate.get("writes", []):
                    rel = normalize_relative(write["path"])
                    path = target / rel
                    if rel not in manifest_map(manifest):
                        created_paths.add(rel)
                    atomic_write_text(path, write["content"])
                    touched.add(rel)
                for raw in candidate.get("quarantine_paths", []):
                    rel = normalize_relative(raw)
                    source = target / rel
                    destination = quarantine_root / rel
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if not source.exists():
                        raise DreamingError(f"Cannot quarantine missing path: {rel}")
                    os.replace(source, destination)
                    touched.add(rel)
                applied_candidate_ids.append(cid)

            post_errors = validate_written_state(
                target, selected, args.memory_limit, args.user_limit
            )
            if post_errors:
                raise DreamingError("Post-apply validation failed:\n- " + "\n- ".join(post_errors))
        except Exception:
            restore_touched_paths(target, snapshot_dir, manifest, touched)
            cleanup_quarantine_paths(quarantine_root, touched)
            raise

        post_hashes: dict[str, str | None] = {}
        for rel in sorted(touched):
            path = target / rel
            post_hashes[rel] = sha256_file(path) if path.exists() and path.is_file() else None

        result = {
            "schema_version": 1,
            "cycle_id": run_id,
            "target_profile": label,
            "target_home": str(target),
            "applied_at": utc_now(),
            "candidate_ids": applied_candidate_ids,
            "touched_paths": sorted(touched),
            "created_paths": sorted(created_paths),
            "post_hashes": post_hashes,
            "quarantine_root": str(quarantine_root),
            "status": "APPLIED",
        }
        write_json(run_dir / "apply_result.json", result)
        write_json(
            run_dir / "status.json",
            {
                "cycle_id": run_id,
                "state": "APPLIED",
                "updated_at": utc_now(),
                "mode": "APPROVAL",
            },
        )

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0

def read_snapshot_text(snapshot_dir: Path, rel: str) -> str | None:
    path = snapshot_dir / rel
    if not path.exists() or path.is_symlink():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None

def truncate_diff(lines: list[str], max_lines: int = 120) -> list[str]:
    if len(lines) <= max_lines:
        return lines
    remaining = len(lines) - max_lines
    return lines[:max_lines] + [f"... diff truncated ({remaining} more lines)\n"]
