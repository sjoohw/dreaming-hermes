# Hermes Agent Dreaming Skill

A report-first, profile-scoped knowledge curation skill for Hermes Agent.

## Scope

For one explicitly selected profile, Dreaming reviews only:

```text
<TARGET_HERMES_HOME>/skills/
<TARGET_HERMES_HOME>/memories/
```

It does not mix the default profile, another named profile, or external shared skills into the cycle.

Standard Hermes locations:

```text
Default: ~/.hermes
Named:   ~/.hermes/profiles/<name>
```

For installations rooted at `~/hermes`, set `HERMES_BASE_HOME=~/hermes` or provide the exact profile home with `--home`.

## Install

Clone the repository and copy its contents into the target profile's skill directory.

### Named profile

```bash
git clone https://github.com/sjoohw/dreaming-hermes.git
mkdir -p ~/hermes/profiles/pts-builder/skills/maintenance/dreaming
cp -a dreaming-hermes/. ~/hermes/profiles/pts-builder/skills/maintenance/dreaming/
rm -rf ~/hermes/profiles/pts-builder/skills/maintenance/dreaming/.git
chmod +x ~/hermes/profiles/pts-builder/skills/maintenance/dreaming/scripts/dreaming.py
```

### Default profile

```bash
git clone https://github.com/sjoohw/dreaming-hermes.git
mkdir -p ~/.hermes/skills/maintenance/dreaming
cp -a dreaming-hermes/. ~/.hermes/skills/maintenance/dreaming/
rm -rf ~/.hermes/skills/maintenance/dreaming/.git
chmod +x ~/.hermes/skills/maintenance/dreaming/scripts/dreaming.py
```

Start a new Hermes session after installation so the new skill is discovered.

## Use

```text
/dreaming pts-builder profile의 skill과 memory를 검토해줘
```

Default behavior is report-only. The skill creates a manifest, full rollback snapshot, structured change plan, validation result, and report under the selected profile:

```text
<TARGET_HERMES_HOME>/dreaming/
├── runs/<cycle-id>/
├── snapshots/<cycle-id>/
└── quarantine/<cycle-id>/
```

## Manual Helper Commands

```bash
# Resolve
python3 scripts/dreaming.py resolve --profile pts-builder

# Scan and snapshot
python3 scripts/dreaming.py scan --profile pts-builder

# Validate the LLM-authored plan
python3 scripts/dreaming.py validate \
  --profile pts-builder \
  --run-dir ~/hermes/profiles/pts-builder/dreaming/runs/<cycle-id>

# Render report
python3 scripts/dreaming.py render \
  --profile pts-builder \
  --run-dir ~/hermes/profiles/pts-builder/dreaming/runs/<cycle-id>

# Apply candidates whose `approved` field is true
python3 scripts/dreaming.py apply \
  --profile pts-builder \
  --run-dir ~/hermes/profiles/pts-builder/dreaming/runs/<cycle-id>

# Roll back
python3 scripts/dreaming.py rollback \
  --profile pts-builder \
  --run-dir ~/hermes/profiles/pts-builder/dreaming/runs/<cycle-id>
```

When using a nonstandard root, export it first:

```bash
export HERMES_BASE_HOME=~/hermes
```

## Protection

Place an empty marker in a skill directory to prevent Dreaming changes:

```bash
touch ~/hermes/profiles/pts-builder/skills/critical-skill/.dreaming-protect
```

The running Dreaming skill protects itself automatically.

## Test

```bash
python3 tests/test_dreaming.py
```

## Repository Layout

```text
SKILL.md
scripts/dreaming.py
scripts/parts/part_01.py ... part_06.py
references/profile-paths.md
references/dreaming-policy.md
references/change-plan-schema.md
templates/change_plan.example.json
templates/report_template.md
tests/test_dreaming.py
```
