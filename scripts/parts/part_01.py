#!/usr/bin/env python3
"""Safe profile-scoped Dreaming helper for Hermes Agent.

This script never asks an LLM to make decisions. It provides deterministic
filesystem operations around an LLM-authored change plan:

- resolve a requested Hermes profile home
- scan only that profile's skills and memories
- create a manifest and rollback snapshot
- validate a structured change plan
- apply only explicitly approved changes
- quarantine instead of deleting
- render a human-readable report
- roll back one applied cycle

Python 3.10+; standard library only.
"""

from __future__ import annotations

import argparse

import contextlib

import datetime as dt

import difflib

import hashlib

import json

import os

from pathlib import Path

import re

import shutil

import sys

import tempfile

import uuid

from typing import Any, Iterable

TOOL_VERSION = "1.0.0"

ALLOWED_ACTIONS = {
    "KEEP",
    "CORRECT",
    "MERGE",
    "INTEGRATE",
    "SPLIT",
    "PRUNE",
    "DEFER",
    "PROMOTE_CANDIDATE",
}

CONFIDENCE_VALUES = {"HIGH", "MEDIUM", "LOW"}

EDITABLE_SUFFIXES = {".md", ".txt", ".yaml", ".yml", ".json", ".toml"}

DEFAULT_MAX_FILE_BYTES = 1_000_000

DEFAULT_MEMORY_LIMIT = 2200

DEFAULT_USER_LIMIT = 1375

class DreamingError(RuntimeError):
    pass

def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

def cycle_id() -> str:
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"

def expand_path(value: str | Path) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(str(value)))).resolve()

def infer_base_home() -> Path:
    configured = os.environ.get("HERMES_BASE_HOME")
    if configured:
        return expand_path(configured)

    current = expand_path(os.environ.get("HERMES_HOME", "~/.hermes"))
    if current.parent.name == "profiles":
        return current.parent.parent
    return current

def resolve_target_home(profile: str | None, home: str | None) -> tuple[Path, str, Path]:
    if profile and home:
        raise DreamingError("Use either --profile or --home, not both.")

    base = infer_base_home()
    if home:
        target = expand_path(home)
        label = target.name or "custom"
        return target, label, base

    if profile:
        normalized = profile.strip()
        if normalized.lower() in {"default", "base"}:
            return base, "default", base
        if not re.fullmatch(r"[A-Za-z0-9._-]+", normalized):
            raise DreamingError(
                "Profile name may contain only letters, numbers, '.', '_' and '-'. "
                "Use --home for a custom path."
            )
        return (base / "profiles" / normalized).resolve(), normalized, base

    current = expand_path(os.environ.get("HERMES_HOME", str(base)))
    if current == base:
        label = "default"
    elif current.parent.name == "profiles":
        label = current.name
    else:
        label = current.name or "custom"
    return current, label, base

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def safe_relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise DreamingError(f"Path escapes target home: {path}") from exc

def normalize_relative(value: str) -> str:
    candidate = Path(value)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise DreamingError(f"Unsafe relative path: {value!r}")
    normalized = candidate.as_posix().lstrip("./")
    if not normalized or normalized == ".":
        raise DreamingError(f"Empty relative path: {value!r}")
    if not (normalized == "skills" or normalized.startswith("skills/") or normalized == "memories" or normalized.startswith("memories/")):
        raise DreamingError(
            f"Path is outside the requested profile's skills/memories scope: {value!r}"
        )
    return normalized

def is_text_candidate(path: Path, max_bytes: int) -> tuple[bool, str | None]:
    if path.is_symlink():
        return False, "symlink"
    try:
        size = path.stat().st_size
    except OSError as exc:
        return False, f"stat-error: {exc}"
    if size > max_bytes:
        return False, f"larger-than-{max_bytes}-bytes"
    if path.suffix.lower() not in EDITABLE_SUFFIXES:
        return False, "non-text-extension"
    try:
        path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return False, f"not-utf8: {exc}"
    return True, None

def discover_protected_skill_dirs(skills_root: Path, self_dir: Path | None) -> set[Path]:
    protected: set[Path] = set()
    if not skills_root.exists():
        return protected

    for marker in skills_root.rglob(".dreaming-protect"):
        if marker.is_file():
            protected.add(marker.parent.resolve())

    if self_dir:
        try:
            self_dir.resolve().relative_to(skills_root.resolve())
        except ValueError:
            pass
        else:
            protected.add(self_dir.resolve())
    return protected

def path_under_any(path: Path, roots: Iterable[Path]) -> bool:
    resolved = path.resolve()
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False

def iter_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        dirs[:] = sorted(
            d for d in dirs if not (current_path / d).is_symlink()
        )
        for name in sorted(files):
            path = current_path / name
            if path.is_file() or path.is_symlink():
                yield path

def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)

def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DreamingError(f"Missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise DreamingError(f"Invalid JSON in {path}: {exc}") from exc

def snapshot_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        destination.symlink_to(os.readlink(source))
    else:
        shutil.copy2(source, destination)

@contextlib.contextmanager
def lock_directory(target_home: Path):
    dreaming_root = target_home / "dreaming"
    dreaming_root.mkdir(parents=True, exist_ok=True)
    lock_dir = dreaming_root / ".lock"
    try:
        lock_dir.mkdir()
    except FileExistsError as exc:
        owner = lock_dir / "owner.json"
        detail = owner.read_text(encoding="utf-8") if owner.exists() else "unknown owner"
        raise DreamingError(f"Another Dreaming operation is active: {detail}") from exc

    write_json(
        lock_dir / "owner.json",
        {"pid": os.getpid(), "started_at": utc_now(), "tool_version": TOOL_VERSION},
    )
    try:
        yield
    finally:
        shutil.rmtree(lock_dir, ignore_errors=True)

def command_resolve(args: argparse.Namespace) -> int:
    target, label, base = resolve_target_home(args.profile, args.home)
    result = {
        "target_home": str(target),
        "target_profile": label,
        "base_home": str(base),
        "skills_root": str(target / "skills"),
        "memories_root": str(target / "memories"),
        "exists": target.exists(),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
