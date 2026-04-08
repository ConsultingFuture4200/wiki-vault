"""Catalog writer — manages _system/catalog.md source entries."""

import re
from datetime import date
from pathlib import Path


def update_catalog(vault_path: Path, source_path: str, title: str, word_count: int) -> None:
    """Add or update a source entry in _system/catalog.md.

    Idempotent: updates existing entry if source already cataloged.
    """
    catalog_path = vault_path / "_system" / "catalog.md"
    content = catalog_path.read_text(encoding="utf-8")

    today = date.today().isoformat()
    new_row = f"| {source_path} | {title} | {today} | pending-compile | {word_count} |"

    # Check if source already has an entry (match on source path in first column)
    escaped = re.escape(source_path)
    pattern = rf"^\| {escaped} \|.*$"
    if re.search(pattern, content, re.MULTILINE):
        content = re.sub(pattern, new_row, content, flags=re.MULTILINE)
    else:
        content = content.rstrip("\n") + "\n" + new_row + "\n"

    catalog_path.write_text(content, encoding="utf-8")


def mark_compiled(vault_path: Path, source_path: str) -> None:
    """Update a catalog entry's status from pending-compile to compiled."""
    catalog_path = vault_path / "_system" / "catalog.md"
    content = catalog_path.read_text(encoding="utf-8")

    escaped = re.escape(source_path)
    pattern = rf"^(\| {escaped} \|[^|]*\|[^|]*\|) pending-compile (\|.*)$"
    content = re.sub(pattern, r"\1 compiled \2", content, flags=re.MULTILINE)

    catalog_path.write_text(content, encoding="utf-8")


def get_pending_sources(vault_path: Path) -> list[str]:
    """Return list of source paths with status pending-compile."""
    catalog_path = vault_path / "_system" / "catalog.md"
    content = catalog_path.read_text(encoding="utf-8")

    sources = []
    for match in re.finditer(r"^\| ([^ |]+) \|[^|]*\|[^|]*\| pending-compile \|", content, re.MULTILINE):
        sources.append(match.group(1))
    return sources
