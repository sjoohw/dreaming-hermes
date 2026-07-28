# Profile Path Resolution

## Standard Layout

```text
~/.hermes/                         default profile HERMES_HOME
~/.hermes/skills/                  default profile skills
~/.hermes/memories/                default profile memories
~/.hermes/profiles/<name>/         named profile HERMES_HOME
~/.hermes/profiles/<name>/skills/  named profile skills
~/.hermes/profiles/<name>/memories/ named profile memories
```

A named profile wrapper sets `HERMES_HOME` to its own profile directory.

## Resolution Order

1. Explicit `--home`
2. Explicit `--profile`
3. Active `HERMES_HOME`
4. Default `~/.hermes`

Base home resolution:

1. `HERMES_BASE_HOME`, when set
2. If `HERMES_HOME` ends with `profiles/<name>`, use the parent above `profiles`
3. Otherwise use `HERMES_HOME`
4. Otherwise use `~/.hermes`

## Scope Boundary

For target home `T`, Dreaming may analyze and propose changes only under:

```text
T/skills/
T/memories/
```

The following are outside scope:

```text
T/SOUL.md
T/AGENTS.md
T/config.yaml
T/.env
T/sessions/
T/cron/
T/state.db
<base>/profiles/<other-profile>/
```

## External Skill Directories

A profile's `config.yaml` may expose shared skill directories. They are excluded by default because changing a shared directory may affect multiple profiles. Include them only in a separately designed, report-only shared-skill governance cycle.
