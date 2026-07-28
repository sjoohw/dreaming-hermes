#!/usr/bin/env python3
"""Entry point for the profile-scoped Hermes Dreaming helper."""
from pathlib import Path

_PARTS = Path(__file__).resolve().parent / "parts"
for _part in sorted(_PARTS.glob("part_*.py")):
    _source = _part.read_text(encoding="utf-8")
    exec(compile(_source, str(_part), "exec"), globals(), globals())

if __name__ == "__main__":
    raise SystemExit(main())
