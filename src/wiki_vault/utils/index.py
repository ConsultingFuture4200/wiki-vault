"""Index and glossary management for wiki-vault."""

import re
from pathlib import Path


def update_index(vault_path: Path, title: str, page_type: str, summary: str, rel_path: str) -> None:
    """Add or update an entry in wiki/index.md."""
    index_path = vault_path / "wiki" / "index.md"
    content = index_path.read_text(encoding="utf-8")

    wikilink = f"[[{Path(rel_path).stem}]]"
    new_row = f"| {wikilink} | {page_type} | {summary} |"

    # Check if entry exists (by wikilink in first column)
    escaped = re.escape(wikilink)
    pattern = rf"^\| {escaped} \|.*$"
    if re.search(pattern, content, re.MULTILINE):
        content = re.sub(pattern, new_row, content, flags=re.MULTILINE)
    else:
        content = content.rstrip("\n") + "\n" + new_row + "\n"

    index_path.write_text(content, encoding="utf-8")


def update_glossary(vault_path: Path, term: str, definition: str) -> None:
    """Add a term to wiki/glossary.md if not already present."""
    glossary_path = vault_path / "wiki" / "glossary.md"
    content = glossary_path.read_text(encoding="utf-8")

    # Check if term already exists
    if re.search(rf"^\*\*{re.escape(term)}\*\*", content, re.MULTILINE):
        return

    entry = f"\n**{term}**: {definition}\n"
    content = content.rstrip("\n") + "\n" + entry

    glossary_path.write_text(content, encoding="utf-8")
