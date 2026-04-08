"""wiki-vault compile command — turn raw sources into wiki pages.

Two-phase pipeline:
  Phase 1: Read pending sources, extract a unified concept manifest
  Phase 2: Generate/update wiki pages from the manifest

The LLM reasoning happens through the Claude Code session. This module:
  - Determines which sources need compilation (incremental detection)
  - Reads source content and constructs prompts
  - Parses structured output into wiki pages
  - Updates index, glossary, catalog, manifest, and log
"""

import json
from pathlib import Path

import click

from wiki_vault.utils.catalog import get_pending_sources, mark_compiled
from wiki_vault.utils.git import git_commit
from wiki_vault.utils.index import update_glossary, update_index
from wiki_vault.utils.log import append_log
from wiki_vault.utils.manifest import get_changed_sources, mark_source_compiled, update_manifest
from wiki_vault.utils.wiki import create_wiki_page, find_existing_page, update_wiki_page


def _find_vault_root() -> Path:
    """Walk up from cwd to find vault root."""
    p = Path.cwd()
    for d in [p, *p.parents]:
        if (d / "_system" / "config.yaml").exists():
            return d
    raise click.ClickException("Not inside a wiki vault.")


def _get_sources_to_compile(vault_path: Path) -> list[str]:
    """Return unified list of sources needing compilation (pending + changed hash)."""
    pending = set(get_pending_sources(vault_path))
    changed = set(get_changed_sources(vault_path))
    return sorted(pending | changed)


def _read_source(vault_path: Path, source_path: str) -> str:
    """Read a source file and return its content."""
    full = vault_path / source_path
    return full.read_text(encoding="utf-8")


def _build_extraction_prompt(sources: dict[str, str]) -> str:
    """Build the Phase 1 concept extraction prompt."""
    prompt = """# Concept Extraction

Analyze the following source documents and extract a structured manifest of all concepts, entities, and topics mentioned.

For each item, provide:
- **name**: A clear, descriptive title
- **type**: One of: concept, topic, entity
- **sources**: Which source file(s) mention this item
- **description**: One-sentence description
- **tags**: 2-5 relevant tags (lowercase, hyphenated)

## Type Definitions
- **concept**: An idea, technique, pattern, or abstract principle (e.g., "two-phase compilation", "hash-based change detection")
- **topic**: A broad subject area or domain (e.g., "Obsidian plugin ecosystem", "CLI tool design")
- **entity**: A specific named thing — a tool, library, person, organization (e.g., "Templater", "Click", "Karpathy")

## Output Format

Respond with a JSON block (```json ... ```) containing:
```json
{
  "concepts": [
    {"name": "...", "type": "concept", "sources": ["raw/..."], "description": "...", "tags": ["..."]}
  ],
  "entities": [
    {"name": "...", "type": "entity", "sources": ["raw/..."], "description": "...", "tags": ["..."]}
  ],
  "topics": [
    {"name": "...", "type": "topic", "sources": ["raw/..."], "description": "...", "tags": ["..."]}
  ]
}
```

## Sources

"""
    for path, content in sources.items():
        prompt += f"### Source: `{path}`\n\n{content}\n\n---\n\n"

    return prompt


def _build_article_prompt(item: dict, source_contents: dict[str, str], existing_page: str | None) -> str:
    """Build the Phase 2 article generation prompt for a single concept/entity/topic."""
    prompt = f"""# Write Wiki Article: {item['name']}

**Type:** {item['type']}
**Description:** {item['description']}
**Tags:** {', '.join(item.get('tags', []))}
**Sources:** {', '.join(item['sources'])}

## Instructions

Write a wiki article about "{item['name']}" based on the source material below.

### Required Sections
1. **Overview** — 2-3 sentence summary
2. **Details** — Main content with subheadings as needed
3. **Sources** — Cite which raw sources inform this article

### Formatting Rules
- Use `[[wikilink]]` format for cross-references to other concepts
- Keep the article between 200-3000 words
- Use concrete details from the sources, not generic descriptions
- If sources conflict, use a CONFLICT callout:
  > [!warning] CONFLICT
  > Source A claims X. Source B claims Y.

"""

    if existing_page:
        prompt += f"### Existing Content\nThis article already exists. Integrate new information without losing existing content:\n\n{existing_page}\n\n"

    prompt += "### Source Material\n\n"
    for src_path in item["sources"]:
        if src_path in source_contents:
            prompt += f"#### `{src_path}`\n\n{source_contents[src_path]}\n\n---\n\n"

    prompt += """### Output Format

Respond with ONLY the article body (no frontmatter — that's handled programmatically). Start directly with the ## Overview heading.
"""
    return prompt


def _parse_json_block(text: str) -> dict:
    """Extract and parse a JSON block from LLM output."""
    import re
    match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    # Try parsing the whole text as JSON
    return json.loads(text)


def _write_extraction_prompt(vault_path: Path, prompt: str) -> None:
    """Write the extraction prompt to _system/prompts/compile.md for reference."""
    dest = vault_path / "_system" / "prompts" / "compile.md"
    dest.write_text(prompt, encoding="utf-8")


def run_compile(batch: bool = False) -> None:
    """Compile pending sources into wiki pages."""
    vault_path = _find_vault_root()
    sources_to_compile = _get_sources_to_compile(vault_path)

    if not sources_to_compile:
        click.echo("Nothing to compile. All sources are up to date.")
        return

    click.echo(f"Found {len(sources_to_compile)} source(s) to compile:")
    for s in sources_to_compile:
        click.echo(f"  - {s}")

    # Read all source content
    source_contents = {}
    for src in sources_to_compile:
        try:
            source_contents[src] = _read_source(vault_path, src)
        except Exception as e:
            click.echo(f"  Warning: Could not read {src}: {e}", err=True)

    if not source_contents:
        click.echo("No readable sources. Aborting.")
        return

    # === Phase 1: Concept Extraction ===
    click.echo("\n--- Phase 1: Concept Extraction ---")
    extraction_prompt = _build_extraction_prompt(source_contents)
    _write_extraction_prompt(vault_path, extraction_prompt)

    manifest_path = vault_path / "_system" / "pending-manifest.json"

    # Check for existing manifest (resume support)
    if manifest_path.exists():
        click.echo("Found existing pending-manifest.json from previous run.")
        if not batch:
            use_existing = click.confirm("Use existing manifest?", default=True)
            if use_existing:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                click.echo(f"Resuming with {_count_items(manifest)} items from manifest.")
            else:
                manifest = _run_extraction(vault_path, extraction_prompt, manifest_path, batch)
        else:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    else:
        manifest = _run_extraction(vault_path, extraction_prompt, manifest_path, batch)

    if not manifest:
        click.echo("No concepts extracted. Aborting.")
        return

    # === Phase 2: Wiki Page Generation ===
    click.echo("\n--- Phase 2: Wiki Page Generation ---")
    all_items = []
    for category in ["concepts", "entities", "topics"]:
        all_items.extend(manifest.get(category, []))

    articles_created = 0
    articles_updated = 0
    all_article_paths = []

    for item in all_items:
        title = item["name"]
        existing = find_existing_page(vault_path, title)

        if existing:
            # Read existing page content for context
            existing_content = _read_source(vault_path, existing)
        else:
            existing_content = None

        article_prompt = _build_article_prompt(item, source_contents, existing_content)

        click.echo(f"\n  Writing: {title} ({item['type']})")

        if not batch:
            # Interactive: show the prompt and let the user/LLM generate content
            click.echo(f"  Prompt written. In interactive mode, the LLM generates content.")
            click.echo(f"  For now, generating a structured article from source material...")

        # Generate article body from source material
        body = _generate_article_body(item, source_contents)

        if existing:
            update_wiki_page(
                vault_path,
                existing,
                new_sources=item["sources"],
                new_content=body,
                new_related=[i["name"] for i in all_items if i["name"] != title],
            )
            articles_updated += 1
            all_article_paths.append(existing)
            click.echo(f"  Updated: {existing}")
        else:
            rel_path = create_wiki_page(
                vault_path,
                title=title,
                page_type=item["type"],
                sources=item["sources"],
                tags=item.get("tags", []),
                summary=item["description"],
                body=body,
                related=[i["name"] for i in all_items if i["name"] != title],
            )
            articles_created += 1
            all_article_paths.append(rel_path)
            click.echo(f"  Created: {rel_path}")

        # Update index
        update_index(vault_path, title, item["type"], item["description"], all_article_paths[-1])

    # Update glossary with entity/concept terms
    for item in all_items:
        if item["type"] in ("concept", "entity"):
            update_glossary(vault_path, item["name"], item["description"])

    # Update catalog and manifest for each compiled source
    for src in sources_to_compile:
        mark_compiled(vault_path, src)
        mark_source_compiled(vault_path, src, all_article_paths)
        # Re-hash in case source was already in manifest with old hash
        update_manifest(vault_path, src)

    # Clean up pending manifest
    if manifest_path.exists():
        manifest_path.unlink()

    # Log and commit
    append_log(vault_path, "compile", f"{len(sources_to_compile)} sources", {
        "Sources": ", ".join(sources_to_compile),
        "Articles created": str(articles_created),
        "Articles updated": str(articles_updated),
        "Total articles": str(len(all_article_paths)),
    })

    git_commit(
        vault_path,
        f"wiki-vault: compile | {len(sources_to_compile)} sources, {articles_created + articles_updated} articles",
    )

    click.echo(f"\nCompile complete:")
    click.echo(f"  {articles_created} articles created")
    click.echo(f"  {articles_updated} articles updated")
    click.echo(f"  {len(sources_to_compile)} sources marked as compiled")


def _count_items(manifest: dict) -> int:
    return sum(len(manifest.get(k, [])) for k in ["concepts", "entities", "topics"])


def _run_extraction(vault_path: Path, prompt: str, manifest_path: Path, batch: bool) -> dict | None:
    """Run concept extraction — parse source content into a structured manifest.

    This is a deterministic extraction (no LLM call). It reads frontmatter,
    headings, and key terms from each source to build the manifest.
    """
    import re
    import frontmatter as fm

    click.echo("Extracting concepts from sources...")

    concepts = []
    entities = []
    topics = []
    seen_names = set()

    # Extract source paths from the prompt, then read actual files for reliable parsing
    source_paths = re.findall(r"### Source: `([^`]+)`", prompt)

    for src_path in source_paths:
        full_path = vault_path / src_path
        content = full_path.read_text(encoding="utf-8")
        # Try to parse frontmatter
        try:
            post = fm.loads(content)
            meta = post.metadata
            body = post.content
        except Exception:
            meta = {}
            body = content

        # Extract title from frontmatter or first heading
        title = meta.get("title") or meta.get("name", "")
        if not title:
            heading_match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
            title = heading_match.group(1) if heading_match else Path(src_path).stem.replace("-", " ").title()

        # Build description from frontmatter or first paragraph
        description = meta.get("description", "")
        if not description:
            # Try first non-heading paragraph
            for para in body.split("\n\n"):
                stripped = para.strip()
                if stripped and not stripped.startswith("#") and not stripped.startswith("<") and not stripped.startswith("---"):
                    description = stripped[:200].replace("\n", " ")
                    break
        if not description:
            description = f"Documentation from {Path(src_path).name}."

        # The source itself becomes an entity or topic based on its type
        doc_type = meta.get("type", "")
        known_entity_types = {"agent", "skill", "plugin", "mcp-server", "workflow", "prompt", "config"}
        if doc_type in known_entity_types:
            if title not in seen_names:
                entities.append({
                    "name": title,
                    "type": "entity",
                    "sources": [src_path],
                    "description": description,
                    "tags": _extract_tags(meta, doc_type),
                })
                seen_names.add(title)
        else:
            if title not in seen_names:
                topics.append({
                    "name": title,
                    "type": "topic",
                    "sources": [src_path],
                    "description": description,
                    "tags": _extract_tags(meta, "topic"),
                })
                seen_names.add(title)

        # Extract wikilinked references as potential related entities
        wikilinks = re.findall(r"\[\[([^\]]+)\]\]", body)
        for link in wikilinks:
            if link not in seen_names and len(link) > 2:
                entities.append({
                    "name": link,
                    "type": "entity",
                    "sources": [src_path],
                    "description": f"Referenced in {title}.",
                    "tags": ["reference"],
                })
                seen_names.add(link)

        # Extract key headings as potential concepts
        headings = re.findall(r"^##\s+(.+)$", body, re.MULTILINE)
        for heading in headings:
            clean = heading.strip()
            # Skip generic headings
            if clean.lower() in ("overview", "details", "sources", "related", "configuration", "usage", "setup", "installation"):
                continue
            if clean not in seen_names and len(clean) > 3:
                concepts.append({
                    "name": clean,
                    "type": "concept",
                    "sources": [src_path],
                    "description": f"Concept from {title}: {clean}.",
                    "tags": _extract_tags(meta, "concept"),
                })
                seen_names.add(clean)

    manifest = {"concepts": concepts, "entities": entities, "topics": topics}

    # Write the manifest
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    click.echo(f"Extracted: {len(concepts)} concepts, {len(entities)} entities, {len(topics)} topics")

    if not batch:
        click.echo("\nConcept manifest:")
        for category in ["concepts", "entities", "topics"]:
            items = manifest.get(category, [])
            if items:
                click.echo(f"\n  {category.title()} ({len(items)}):")
                for item in items[:10]:
                    click.echo(f"    - {item['name']}: {item['description'][:80]}")
                if len(items) > 10:
                    click.echo(f"    ... and {len(items) - 10} more")

        proceed = click.confirm("\nProceed to wiki generation?", default=True)
        if not proceed:
            click.echo("Manifest saved. Re-run compile to resume.")
            return None

    return manifest


def _extract_tags(meta: dict, fallback_type: str) -> list[str]:
    """Extract tags from frontmatter metadata."""
    tags = meta.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",")]
    if not tags:
        tags = [fallback_type]
    return [t.lower().replace(" ", "-") for t in tags if t]


def _generate_article_body(item: dict, source_contents: dict[str, str]) -> str:
    """Generate a structured article body from source material.

    This is a deterministic generator — extracts and reorganizes content
    from the sources rather than using an LLM.
    """
    sections = []
    sections.append(f"## Overview\n\n{item['description']}\n")

    # Collect relevant content from each source
    details_parts = []
    source_citations = []

    for src_path in item["sources"]:
        if src_path not in source_contents:
            continue
        content = source_contents[src_path]

        # Try to extract the section most relevant to this item
        excerpt = _extract_relevant_section(content, item["name"])
        if excerpt:
            details_parts.append(excerpt)

        source_citations.append(f"- `{src_path}`")

    if details_parts:
        sections.append("## Details\n\n" + "\n\n".join(details_parts))
    else:
        sections.append(f"## Details\n\n_Content pending — extracted from sources but needs LLM enrichment._\n")

    sections.append("## Sources\n\n" + "\n".join(source_citations))

    return "\n\n".join(sections)


def _extract_relevant_section(content: str, name: str) -> str:
    """Extract the section of content most relevant to the given name."""
    import re

    # Look for a heading that matches the name
    pattern = rf"^(##?\s+{re.escape(name)}.*?)(?=^##?\s|\Z)"
    match = re.search(pattern, content, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1).strip()
        # Limit to ~500 words
        words = text.split()
        if len(words) > 500:
            text = " ".join(words[:500]) + "..."
        return text

    # Look for paragraphs mentioning the name
    paragraphs = content.split("\n\n")
    relevant = [p.strip() for p in paragraphs if name.lower() in p.lower()]
    if relevant:
        text = "\n\n".join(relevant[:3])
        words = text.split()
        if len(words) > 500:
            text = " ".join(words[:500]) + "..."
        return text

    return ""
