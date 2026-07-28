#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "dreaming.py"


def run(*args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"Command failed ({result.returncode}): {args}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        base = Path(temp) / ".hermes"
        profile = base / "profiles" / "pts-builder"
        skill = profile / "skills" / "layout" / "sample"
        memories = profile / "memories"
        skill.mkdir(parents=True)
        memories.mkdir(parents=True)

        skill_file = skill / "SKILL.md"
        skill_file.write_text(
            "---\nname: sample\ndescription: Sample skill\n---\n\n# Sample\n\nOld procedure.\n",
            encoding="utf-8",
        )
        memory_file = memories / "MEMORY.md"
        memory_file.write_text("Useful fact.\n", encoding="utf-8")
        (memories / "USER.md").write_text("Concise answers.\n", encoding="utf-8")

        env = os.environ.copy()
        env["HERMES_BASE_HOME"] = str(base)
        env.pop("HERMES_HOME", None)

        resolved = json.loads(run("resolve", "--profile", "pts-builder", env=env).stdout)
        assert Path(resolved["target_home"]) == profile.resolve()

        scan = json.loads(run("scan", "--profile", "pts-builder", env=env).stdout)
        run_dir = Path(scan["run_dir"])
        manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["target_profile"] == "pts-builder"
        assert all(
            item["path"].startswith(("skills/", "memories/"))
            for item in manifest["files"]
        )

        new_skill = (
            "---\nname: sample\ndescription: Sample skill\n---\n\n# Sample\n\nImproved procedure.\n"
        )
        plan = {
            "schema_version": 1,
            "cycle_id": manifest["cycle_id"],
            "target_profile": "pts-builder",
            "created_at": "2026-07-28T00:00:00+09:00",
            "summary": "Test plan",
            "candidates": [
                {
                    "candidate_id": "DREAM-001",
                    "action": "CORRECT",
                    "risk_level": 2,
                    "confidence": "HIGH",
                    "reason": "Test correction",
                    "evidence": ["Test evidence"],
                    "source_paths": ["skills/layout/sample/SKILL.md"],
                    "writes": [
                        {
                            "path": "skills/layout/sample/SKILL.md",
                            "content": new_skill,
                        }
                    ],
                    "quarantine_paths": [],
                    "requires_approval": True,
                    "approved": True,
                },
                {
                    "candidate_id": "DREAM-002",
                    "action": "PRUNE",
                    "risk_level": 3,
                    "confidence": "HIGH",
                    "reason": "Test quarantine",
                    "evidence": ["Test evidence"],
                    "source_paths": ["memories/MEMORY.md"],
                    "writes": [],
                    "quarantine_paths": ["memories/MEMORY.md"],
                    "requires_approval": True,
                    "approved": True,
                },
            ],
        }
        (run_dir / "change_plan.json").write_text(
            json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        run("validate", "--profile", "pts-builder", "--run-dir", str(run_dir), env=env)
        run("render", "--profile", "pts-builder", "--run-dir", str(run_dir), env=env)
        assert (run_dir / "report.md").exists()

        run("apply", "--profile", "pts-builder", "--run-dir", str(run_dir), env=env)
        assert skill_file.read_text(encoding="utf-8") == new_skill
        assert not memory_file.exists()
        quarantine = profile / "dreaming" / "quarantine" / manifest["cycle_id"] / "memories" / "MEMORY.md"
        assert quarantine.exists()

        run("rollback", "--profile", "pts-builder", "--run-dir", str(run_dir), env=env)
        assert "Old procedure." in skill_file.read_text(encoding="utf-8")
        assert memory_file.read_text(encoding="utf-8") == "Useful fact.\n"
        assert not quarantine.exists()

        print("All Dreaming helper tests passed.")


if __name__ == "__main__":
    main()
