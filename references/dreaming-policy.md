# Dreaming Policy

## Goal

Improve the selected profile's accumulated knowledge without causing irreversible information loss or cross-profile contamination.

## Protected Content

- The running Dreaming skill package
- Any skill directory containing `.dreaming-protect`
- Identity and operating-policy files outside `skills/` and `memories/`
- Non-text and executable files by default

## Evidence Hierarchy

From strongest to weakest:

1. Explicit user correction or approval
2. Current executable behavior or test evidence
3. Current profile configuration and authoritative local references
4. Newer, specific memory with clear provenance
5. Internal consistency inference
6. Model recollection — insufficient by itself

## Confidence

- `HIGH`: Direct evidence; one clear interpretation
- `MEDIUM`: Strong inference; minor uncertainty
- `LOW`: Multiple plausible interpretations or incomplete context

Low-confidence semantic changes should normally be `DEFER`.

## Information Preservation

When merging:

- retain unique constraints
- retain exceptions and failure recovery
- retain source paths in evidence
- avoid replacing precise details with generic summaries
- do not erase rejected alternatives when their rejection reason remains useful

## Stability

Do not repeatedly rewrite content for style. A candidate must improve correctness, consistency, reuse, or safety—not merely produce different prose.

## Approval

- Risk 0: report only
- Risk 1: optional controlled auto-apply
- Risk 2–3: explicit candidate approval
- Risk 4: report only
- Every prune: explicit approval
