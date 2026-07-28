def validate_plan_data(
    plan: dict[str, Any],
    manifest: dict[str, Any],
    memory_limit: int,
    user_limit: int,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(plan, dict):
        return ["Plan root must be a JSON object."]
    if plan.get("cycle_id") != manifest.get("cycle_id"):
        errors.append("Plan cycle_id does not match manifest cycle_id.")
    if plan.get("target_profile") != manifest.get("target_profile"):
        errors.append("Plan target_profile does not match manifest target_profile.")

    candidates = plan.get("candidates")
    if not isinstance(candidates, list):
        return errors + ["Plan candidates must be a list."]

    known = manifest_map(manifest)
    seen_ids: set[str] = set()
    touched: dict[str, str] = {}

    for index, candidate in enumerate(candidates):
        prefix = f"candidates[{index}]"
        if not isinstance(candidate, dict):
            errors.append(f"{prefix} must be an object.")
            continue

        cid = candidate.get("candidate_id")
        if not isinstance(cid, str) or not cid.strip():
            errors.append(f"{prefix}.candidate_id must be a non-empty string.")
            cid = prefix
        elif cid in seen_ids:
            errors.append(f"Duplicate candidate_id: {cid}")
        else:
            seen_ids.add(cid)

        action = candidate.get("action")
        if action not in ALLOWED_ACTIONS:
            errors.append(f"{cid}: invalid action {action!r}.")

        risk = candidate.get("risk_level")
        if not isinstance(risk, int) or not 0 <= risk <= 4:
            errors.append(f"{cid}: risk_level must be an integer from 0 to 4.")

        confidence = candidate.get("confidence")
        if confidence not in CONFIDENCE_VALUES:
            errors.append(f"{cid}: confidence must be HIGH, MEDIUM or LOW.")

        reason = candidate.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{cid}: reason is required.")

        evidence = candidate.get("evidence", [])
        if not isinstance(evidence, list) or not all(isinstance(x, str) for x in evidence):
            errors.append(f"{cid}: evidence must be a list of strings.")

        source_paths = candidate.get("source_paths", [])
        if not isinstance(source_paths, list) or not all(isinstance(x, str) for x in source_paths):
            errors.append(f"{cid}: source_paths must be a list of strings.")
            source_paths = []
        normalized_sources: list[str] = []
        for raw in source_paths:
            try:
                rel = normalize_relative(raw)
                normalized_sources.append(rel)
            except DreamingError as exc:
                errors.append(f"{cid}: {exc}")
                continue
            if rel not in known:
                errors.append(f"{cid}: source path is not in manifest: {rel}")

        writes = candidate.get("writes", [])
        if not isinstance(writes, list):
            errors.append(f"{cid}: writes must be a list.")
            writes = []
        normalized_writes: list[str] = []
        for w_index, write in enumerate(writes):
            if not isinstance(write, dict):
                errors.append(f"{cid}: writes[{w_index}] must be an object.")
                continue
            raw_path = write.get("path")
            content = write.get("content")
            if not isinstance(raw_path, str):
                errors.append(f"{cid}: writes[{w_index}].path must be a string.")
                continue
            try:
                rel = normalize_relative(raw_path)
            except DreamingError as exc:
                errors.append(f"{cid}: {exc}")
                continue
            normalized_writes.append(rel)
            if not isinstance(content, str):
                errors.append(f"{cid}: writes[{w_index}].content must be a string.")
                continue
            if rel in known and known[rel].get("protected"):
                errors.append(f"{cid}: cannot write protected path: {rel}")
            if rel in touched:
                errors.append(f"{cid}: path is targeted more than once (also by {touched[rel]}): {rel}")
            touched[rel] = str(cid)
            errors.extend(validate_skill_frontmatter(rel, content))
            if rel == "memories/MEMORY.md" and len(content) > memory_limit:
                errors.append(
                    f"{cid}: memories/MEMORY.md exceeds {memory_limit} characters ({len(content)})."
                )
            if rel == "memories/USER.md" and len(content) > user_limit:
                errors.append(
                    f"{cid}: memories/USER.md exceeds {user_limit} characters ({len(content)})."
                )

        quarantine_paths = candidate.get("quarantine_paths", [])
        if not isinstance(quarantine_paths, list) or not all(
            isinstance(x, str) for x in quarantine_paths
        ):
            errors.append(f"{cid}: quarantine_paths must be a list of strings.")
            quarantine_paths = []
        normalized_quarantine: list[str] = []
        for raw in quarantine_paths:
            try:
                rel = normalize_relative(raw)
            except DreamingError as exc:
                errors.append(f"{cid}: {exc}")
                continue
            normalized_quarantine.append(rel)
            if rel not in known:
                errors.append(f"{cid}: quarantine path is not in manifest: {rel}")
            elif known[rel].get("protected"):
                errors.append(f"{cid}: cannot quarantine protected path: {rel}")
            if rel in touched:
                errors.append(f"{cid}: path is targeted more than once (also by {touched[rel]}): {rel}")
            touched[rel] = str(cid)

        requires_approval = candidate.get("requires_approval")
        if not isinstance(requires_approval, bool):
            errors.append(f"{cid}: requires_approval must be boolean.")
        if isinstance(risk, int) and risk >= 2 and requires_approval is not True:
            errors.append(f"{cid}: risk level {risk} requires approval.")
        if action == "PRUNE" and requires_approval is not True:
            errors.append(f"{cid}: PRUNE always requires approval.")

        if action in {"KEEP", "DEFER", "PROMOTE_CANDIDATE"} and (
            normalized_writes or normalized_quarantine
        ):
            errors.append(f"{cid}: {action} must not write or quarantine files.")
        if action == "PRUNE" and not normalized_quarantine:
            errors.append(f"{cid}: PRUNE requires quarantine_paths.")
        if action in {"CORRECT", "MERGE", "INTEGRATE", "SPLIT"} and not normalized_writes:
            errors.append(f"{cid}: {action} requires at least one write.")

    return errors

def load_run(args: argparse.Namespace) -> tuple[Path, dict[str, Any], Path, str]:
    target, label, _base = resolve_target_home(args.profile, args.home)
    if getattr(args, "run_dir", None):
        run_dir = expand_path(args.run_dir)
    elif getattr(args, "cycle_id", None):
        run_dir = target / "dreaming" / "runs" / args.cycle_id
    else:
        raise DreamingError("Provide --run-dir or --cycle-id.")
    manifest = read_json(run_dir / "manifest.json")
    manifest_home = expand_path(manifest["target_home"])
    if manifest_home != target:
        raise DreamingError(
            f"Run targets {manifest_home}, but current selection resolves to {target}."
        )
    if manifest.get("target_profile") != label:
        raise DreamingError(
            f"Run targets profile {manifest.get('target_profile')!r}, not {label!r}."
        )
    return run_dir, manifest, target, label

def command_validate(args: argparse.Namespace) -> int:
    run_dir, manifest, _target, _label = load_run(args)
    plan_path = run_dir / "change_plan.json"
    plan = read_json(plan_path)
    errors = validate_plan_data(plan, manifest, args.memory_limit, args.user_limit)
    result = {
        "valid": not errors,
        "cycle_id": manifest["cycle_id"],
        "plan": str(plan_path),
        "errors": errors,
    }
    write_json(run_dir / "validation.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 2

def approved_candidates(plan: dict[str, Any], auto_level1: bool) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for candidate in plan.get("candidates", []):
        action = candidate.get("action")
        if action in {"KEEP", "DEFER", "PROMOTE_CANDIDATE"}:
            continue
        approved = candidate.get("approved") is True
        if (
            auto_level1
            and candidate.get("risk_level") == 1
            and candidate.get("confidence") == "HIGH"
            and candidate.get("requires_approval") is False
        ):
            approved = True
        if approved:
            selected.append(candidate)
    return selected
