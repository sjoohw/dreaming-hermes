---
name: dreaming
description: Review and curate one explicitly selected Hermes profile's own skills and memories through a safe report-first workflow with snapshots, structured change plans, approval gates, quarantine, and rollback.
version: 1.0.0
platforms: [linux, macos]
metadata:
  hermes:
    tags: [hermes-agent, profile, skills, memory, maintenance, governance]
    category: maintenance
    requires_toolsets: [terminal]
---

# Dreaming

## Purpose

Use this skill to review, correct, merge, integrate, split, or quarantine accumulated knowledge for **one requested Hermes profile**.

The scope is always limited to the requested profile's own:

- `<TARGET_HERMES_HOME>/skills/`
- `<TARGET_HERMES_HOME>/memories/`

Do not silently include:

- the default profile when a named profile was requested
- another named profile
- skills from another profile
- shared or external skill directories
- `SOUL.md`, `AGENTS.md`, configuration, sessions, credentials, cron jobs, or state databases

A promotion candidate for `SOUL.md` or `AGENTS.md` may be reported, but Dreaming must never write those files.

## Profile Resolution Contract

Resolve the target before reading any source file.

1. When the user explicitly names a profile, use that profile only.
2. `default` means the default Hermes home.
3. When no profile is named, use the currently active `HERMES_HOME`.
4. When the user gives an explicit home path, use `--home` rather than guessing a profile name.
5. Show the resolved target profile and paths before analysis.
6. If the resolved target does not exist, stop. Do not fall back to another profile.

Current Hermes layout:

```text
Default profile: ~/.hermes
Named profile:   ~/.hermes/profiles/<profile-name>
```

The helper also honors:

- `HERMES_HOME` for the active profile
- `HERMES_BASE_HOME` for a nonstandard base home
- `--home` for an explicit target home

Never hardcode a user's example path when profile resolution can determine it safely.

## Invocation Examples

```text
/dreaming pts-builder profile의 skill과 memory를 검토해줘
/dreaming default profile을 report-only로 정리해줘
/dreaming --home /srv/hermes/team-agent 변경 후보를 만들어줘
```

Interpret the first example as:

```bash
python3 <SKILL_DIR>/scripts/dreaming.py scan --profile pts-builder
```

Interpret an omitted profile as the current active profile:

```bash
python3 <SKILL_DIR>/scripts/dreaming.py scan
```

## Non-Negotiable Safety Rules

1. Start in `REPORT_ONLY` mode.
2. Never edit source files while analyzing them.
3. Create a manifest and snapshot before proposing changes.
4. Never delete directly. `PRUNE` means moving to quarantine after approval.
5. All semantic changes require an explicit structured change plan.
6. Risk Level 2 or higher requires user approval.
7. Every `PRUNE` requires user approval regardless of confidence.
8. Do not change a file that changed after the scan.
9. Do not modify the Dreaming skill itself while it is running.
10. Respect a `.dreaming-protect` marker inside any skill directory.
11. If evidence is insufficient, use `DEFER`; do not guess.
12. Do not treat wording cleanup as a reason to repeatedly rewrite stable knowledge.
13. A memory is not promoted to a skill merely because it is detailed; it must describe a reusable procedure.
14. A skill is not reduced to memory merely because it is short; classify by purpose, not length.
15. Do not mix knowledge from multiple profiles in one cycle.

## Actions

Use exactly one action per candidate:

| Action | Meaning |
|---|---|
| `KEEP` | Keep as-is |
| `CORRECT` | Fix inaccurate, contradictory, or incomplete content |
| `MERGE` | Combine genuinely duplicate knowledge |
| `INTEGRATE` | Add a useful memory fragment into an existing skill |
| `SPLIT` | Divide an overly broad skill into focused skills |
| `PRUNE` | Move an obsolete item to quarantine after approval |
| `DEFER` | Leave unchanged because evidence is insufficient |
| `PROMOTE_CANDIDATE` | Report a possible `SOUL.md` or `AGENTS.md` principle without writing it |

## Risk Classification

| Level | Typical change | Policy |
|---|---|---|
| 0 | Analysis and report only | Automatic |
| 1 | Typo, formatting, exact duplicate cleanup with no semantic change | May be auto-applied only when HIGH confidence and explicitly allowed |
| 2 | Memory consolidation or skill content update | Approval required |
| 3 | Skill merge, split, quarantine, major semantic change | Approval required |
| 4 | Identity, security, authorization, system behavior | Report only; never apply here |

Assess risk and confidence separately.

## Procedure

### 1. Resolve and Confirm the Target

Run:

```bash
python3 <SKILL_DIR>/scripts/dreaming.py resolve --profile <PROFILE>
```

For the active profile:

```bash
python3 <SKILL_DIR>/scripts/dreaming.py resolve
```

State clearly:

```text
Target profile: <name>
Skills: <target-home>/skills
Memories: <target-home>/memories
Other profiles: excluded
External skill directories: excluded
Mode: report only
```

If this differs from the user's request, stop rather than substituting another profile.

### 2. Scan and Snapshot

Run:

```bash
python3 <SKILL_DIR>/scripts/dreaming.py scan --profile <PROFILE>
```

Capture the returned `run_dir`, `manifest`, and `snapshot_dir`.

The scan inventories the selected profile only and protects the running Dreaming skill. It creates:

```text
<TARGET_HERMES_HOME>/dreaming/runs/<cycle-id>/manifest.json
<TARGET_HERMES_HOME>/dreaming/snapshots/<cycle-id>/...
```

### 3. Read the Manifest Before Reading Content

Read `manifest.json` and analyze only entries where:

- `editable` is `true`
- `protected` is `false`
- `path` starts with `skills/` or `memories/`

Non-editable files may be noted as dependencies but must not be changed.

For skills, normally inspect:

- `SKILL.md`
- Markdown/text references used by that skill
- YAML/JSON/TOML knowledge or templates when their meaning is relevant

Do not rewrite executable scripts merely to make the wording cleaner.

For memories, inspect all editable files under the selected profile's `memories/` directory. In a standard Hermes installation these commonly include `MEMORY.md` and `USER.md`.

### 4. Build an Evidence Map

Before proposing changes, record:

- exact source paths
- the conflicting or overlapping statements
- which statement is more authoritative and why
- whether the knowledge is factual memory or reusable procedure
- whether the information is current, stale, ambiguous, or unverifiable
- downstream skills likely affected

Acceptable evidence includes:

- the selected profile's current configuration or workflow
- explicit user correction
- a newer, more specific memory entry
- executable or test results
- an authoritative reference already available to the profile
- an unambiguous internal contradiction

A model's unsupported recollection is not evidence.

### 5. Create `change_plan.json`

Use `references/change-plan-schema.md` and `templates/change_plan.example.json`.

Write the plan to:

```text
<run_dir>/change_plan.json
```

Each candidate must contain:

- stable `candidate_id`
- one action
- risk level and confidence
- reason and evidence
- source paths
- complete proposed file contents in `writes`
- quarantine paths for `PRUNE`
- approval requirement
- `approved: false` by default

Do not use vague instructions such as “clean this up.” The proposed result must be reviewable as an exact diff.

### 6. Validate the Plan

Run:

```bash
python3 <SKILL_DIR>/scripts/dreaming.py validate \
  --profile <PROFILE> \
  --run-dir <RUN_DIR>
```

Fix all validation errors before presenting the report.

Validation enforces:

- profile and cycle match
- path confinement to the selected profile's `skills/` and `memories/`
- protected skill exclusion
- action-specific requirements
- approval requirements
- basic `SKILL.md` frontmatter
- current standard memory size limits for `MEMORY.md` and `USER.md`

If the user's Hermes version or configuration uses different memory limits, pass the correct values explicitly.

### 7. Render the Dreaming Report

Run:

```bash
python3 <SKILL_DIR>/scripts/dreaming.py render \
  --profile <PROFILE> \
  --run-dir <RUN_DIR>
```

Review `<run_dir>/report.md` and present:

- target profile and exact scope
- findings grouped by action
- risk and confidence
- evidence
- proposed diffs
- promotion candidates
- deferred questions
- confirmation that nothing was applied

Do not claim a source file was changed in report-only mode.

### 8. Obtain Approval

Approval must identify candidates, not merely say “apply the report” when the report contains high-risk or destructive proposals.

Update the selected candidates in `change_plan.json`:

```json
"approved": true
```

Keep rejected or undecided candidates as `false`.

### 9. Apply Approved Candidates

Run only after approval:

```bash
python3 <SKILL_DIR>/scripts/dreaming.py apply \
  --profile <PROFILE> \
  --run-dir <RUN_DIR>
```

The helper:

- revalidates the plan
- checks that relevant files have not changed since scan
- applies only approved candidates
- moves prune targets to quarantine
- validates written state
- restores touched files if apply fails
- records `apply_result.json`

`--auto-level1` may be used only when the user has explicitly enabled automatic Level 1 changes.

### 10. Verify After Apply

Verify:

- changed `SKILL.md` files remain discoverable
- no source path outside the requested profile changed
- memory files remain within configured limits
- quarantine contains the expected originals
- `apply_result.json` lists only approved candidates
- the profile starts a fresh Hermes session successfully

Remember that Hermes memory is captured at session start; newly changed memory may not appear in an already-running session.

### 11. Roll Back When Needed

Run:

```bash
python3 <SKILL_DIR>/scripts/dreaming.py rollback \
  --profile <PROFILE> \
  --run-dir <RUN_DIR>
```

The helper refuses rollback when touched files changed after apply. Use `--force` only after explicit user approval because it can overwrite later edits.

## Analysis Heuristics

### Skill vs. Memory

- Put reusable procedures, tool instructions, workflows, checks, and failure recovery in skills.
- Put durable profile-specific facts, preferences, environment details, and concise lessons in memory.
- Integrate a memory into a skill only when it has become a generalized procedure.
- Preserve source provenance when consolidating unique facts.

### Merge

Merge only when the candidates have the same operational responsibility. Do not merge merely because they share keywords.

A good merge:

- has one clear trigger
- has one coherent procedure
- retains unique constraints and failure cases
- removes contradictory duplicate instructions

### Correct

Prefer the smallest change that fixes the issue. When two entries disagree and authority is unclear, use `DEFER`.

### Prune

A low usage count alone is not sufficient. A rarely used recovery procedure may still be critical. Prefer quarantine for:

- knowledge tied to a removed tool or workflow
- superseded duplicates with preserved provenance
- one-off artifacts incorrectly stored as reusable knowledge
- content explicitly invalidated by the user

### Promotion Candidate

Report repeated, durable principles that shape identity or operating behavior. Do not promote task-specific implementation details.

## Failure Handling

Stop without applying when:

- requested profile cannot be resolved
- manifest or snapshot creation fails
- source files change after scan
- plan validation fails
- evidence is insufficient for a semantic correction
- multiple candidates attempt to write the same path
- a protected path is targeted
- post-apply verification fails

Never recover by switching to another profile or broadening scope.

## Output Standard

Conclude every cycle with:

```text
Target profile: <profile>
Cycle ID: <cycle-id>
Mode: REPORT_ONLY | APPLIED | ROLLED_BACK
Skills reviewed: <count>
Memories reviewed: <count>
Applied candidates: <ids or none>
Report: <path>
Rollback snapshot: <path>
```

## Supporting Files

Load only when needed:

- `references/profile-paths.md`
- `references/change-plan-schema.md`
- `references/dreaming-policy.md`
- `templates/change_plan.example.json`
- `scripts/dreaming.py`
