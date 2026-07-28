# Change Plan Schema

`change_plan.json` is an LLM-authored proposal consumed by the deterministic helper.

## Root Object

```json
{
  "schema_version": 1,
  "cycle_id": "20260728-120000-a1b2c3d4",
  "target_profile": "pts-builder",
  "created_at": "2026-07-28T12:10:00+09:00",
  "summary": "Concise cycle summary",
  "candidates": []
}
```

`cycle_id` and `target_profile` must exactly match `manifest.json`.

## Candidate

```json
{
  "candidate_id": "DREAM-001",
  "action": "INTEGRATE",
  "risk_level": 2,
  "confidence": "HIGH",
  "reason": "A repeated recovery procedure exists only in memory.",
  "evidence": [
    "memories/MEMORY.md contains the confirmed recovery sequence",
    "skills/layout/pts-builder/SKILL.md lacks that failure case"
  ],
  "source_paths": [
    "memories/MEMORY.md",
    "skills/layout/pts-builder/SKILL.md"
  ],
  "writes": [
    {
      "path": "skills/layout/pts-builder/SKILL.md",
      "content": "Complete replacement file content, not a patch instruction"
    }
  ],
  "quarantine_paths": [],
  "requires_approval": true,
  "approved": false
}
```

## Rules

- `candidate_id` must be unique within the cycle.
- `action` must be one of the actions defined in `SKILL.md`.
- `risk_level` must be 0–4.
- `confidence` must be `HIGH`, `MEDIUM`, or `LOW`.
- `reason` is required.
- `evidence` must contain concrete, reviewable statements.
- Paths must be relative to the target profile home.
- Paths must start with `skills/` or `memories/`.
- `writes[].content` contains the complete resulting file.
- `PRUNE` uses `quarantine_paths`; it never uses deletion.
- `KEEP`, `DEFER`, and `PROMOTE_CANDIDATE` cannot contain writes or quarantine paths.
- `CORRECT`, `MERGE`, `INTEGRATE`, and `SPLIT` require at least one write.
- Risk Level 2+ requires approval.
- `PRUNE` always requires approval.
- Default `approved` is `false`.

## Promotion Candidate

A promotion candidate is report-only:

```json
{
  "candidate_id": "DREAM-010",
  "action": "PROMOTE_CANDIDATE",
  "risk_level": 4,
  "confidence": "MEDIUM",
  "reason": "The principle repeatedly governs profile behavior.",
  "evidence": ["..."],
  "source_paths": ["memories/MEMORY.md"],
  "writes": [],
  "quarantine_paths": [],
  "requires_approval": true,
  "approved": false,
  "promotion_target": "SOUL.md",
  "promotion_text": "Proposed principle"
}
```

The helper ignores `promotion_target` and `promotion_text` for writes; they are report metadata only.
