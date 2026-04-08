"""Wiki page creation and update helpers."""

import re
from datetime import date
from pathlib import Path

import frontmatter


def slug_from_title(title: str) -> str:
    """Convert a title to a filesystem-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug[:80] or "untitled"


def create_wiki_page(
    vault_path: Path,
    title: str,
    page_type: str,
    sources: list[str],
    tags: list[str],
    summary: str,
    body: str,
    related: list[str] | None = None,
) -> str:
    """Create a new wiki page. Returns the relative path."""
    type_dirs = {"concept": "concepts", "topic": "topics", "entity": "entities"}
    subdir = type_dirs.get(page_type, "concepts")
    slug = slug_from_title(title)

    dest_dir = vault_path / "wiki" / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{slug}.md"

    today = date.today().isoformat()
    fm = {
        "title": title,
        "created": today,
        "updated": today,
        "type": page_type,
        "sources": sources,
        "tags": tags,
        "related": [f"[[{r}]]" for r in (related or [])],
        "summary": summary,
        "source_count": len(sources),
    }

    post = frontmatter.Post(body, **fm)
    dest.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")

    return dest.relative_to(vault_path).as_posix()


def update_wiki_page(
    vault_path: Path,
    page_path: str,
    new_sources: list[str],
    new_content: str,
    new_related: list[str] | None = None,
) -> None:
    """Update an existing wiki page with new information from additional sources."""
    full_path = vault_path / page_path
    post = frontmatter.load(str(full_path))

    # Add new sources
    existing_sources = post.metadata.get("sources", [])
    for s in new_sources:
        if s not in existing_sources:
            existing_sources.append(s)
    post.metadata["sources"] = existing_sources
    post.metadata["source_count"] = len(existing_sources)
    post.metadata["updated"] = date.today().isoformat()

    # Add new related links
    if new_related:
        existing_related = post.metadata.get("related", [])
        for r in new_related:
            link = f"[[{r}]]"
            if link not in existing_related:
                existing_related.append(link)
        post.metadata["related"] = existing_related

    # Append new content
    if new_content:
        post.content = post.content.rstrip() + "\n\n---\n\n" + new_content

    full_path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")


def find_existing_page(vault_path: Path, title: str) -> str | None:
    """Find an existing wiki page by title slug. Returns relative path or None."""
    slug = slug_from_title(title)
    wiki_dir = vault_path / "wiki"
    for subdir in ["concepts", "topics", "entities"]:
        candidate = wiki_dir / subdir / f"{slug}.md"
        if candidate.exists():
            return candidate.relative_to(vault_path).as_posix()
    return None
