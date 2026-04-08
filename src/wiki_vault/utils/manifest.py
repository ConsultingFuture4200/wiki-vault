"""Manifest writer — SHA-256 hash tracking for incremental compilation."""

import hashlib
import json
from datetime import datetime
from pathlib import Path


def compute_hash(filepath: Path) -> str:
    """Return SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_manifest(vault_path: Path) -> dict:
    manifest_path = vault_path / "_system" / "manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _write_manifest(vault_path: Path, data: dict) -> None:
    manifest_path = vault_path / "_system" / "manifest.json"
    manifest_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def update_manifest(vault_path: Path, source_path: str, word_count: int = 0) -> None:
    """Add or update a source entry in manifest.json with its current hash."""
    data = _read_manifest(vault_path)
    if "sources" not in data:
        data["sources"] = {}

    full_path = vault_path / source_path
    data["sources"][source_path] = {
        "sha256": compute_hash(full_path),
        "last_compiled": None,
        "word_count": word_count,
        "articles_touched": [],
    }
    _write_manifest(vault_path, data)


def mark_source_compiled(vault_path: Path, source_path: str, articles: list[str]) -> None:
    """Update manifest entry after successful compilation."""
    data = _read_manifest(vault_path)
    if source_path in data.get("sources", {}):
        data["sources"][source_path]["last_compiled"] = datetime.now().isoformat()
        data["sources"][source_path]["articles_touched"] = articles
        _write_manifest(vault_path, data)


def get_changed_sources(vault_path: Path) -> list[str]:
    """Return list of source paths whose current hash differs from the manifest."""
    data = _read_manifest(vault_path)
    sources = data.get("sources", {})
    changed = []

    for source_path, entry in sources.items():
        full_path = vault_path / source_path
        if not full_path.exists():
            continue
        current_hash = compute_hash(full_path)
        if current_hash != entry.get("sha256"):
            changed.append(source_path)

    # Also find new files in raw/ not in manifest
    raw_dir = vault_path / "raw"
    if raw_dir.exists():
        for f in raw_dir.rglob("*"):
            if f.is_file():
                rel = f.relative_to(vault_path).as_posix()
                if rel not in sources:
                    changed.append(rel)

    return changed
