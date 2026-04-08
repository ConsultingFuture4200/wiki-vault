"""CLAUDE.md generator for wiki-vault."""


def generate_claude_md(name: str) -> str:
    """Return the full text of CLAUDE.md for a new vault."""
    return f"""# {name} — Wiki Vault

## Architecture

This vault follows a three-layer architecture:

### raw/ — Immutable Source Layer
- **Owner:** Human (via ingest)
- **Rule:** The LLM NEVER modifies files in raw/. Sources are copied in via `wiki-vault ingest` and treated as read-only ground truth.
- **Subdirectories:** articles/, papers/, repos/, datasets/, images/

### wiki/ — LLM-Owned Knowledge Layer
- **Owner:** LLM (via compile)
- **Rule:** The LLM generates and updates all files here during `wiki-vault compile`. Humans may edit but should expect LLM overwrites on recompile.
- **Subdirectories:** concepts/, topics/, entities/
- **Special files:** index.md (master index), glossary.md (term definitions)

### output/ — Rendered Artifacts
- **Owner:** LLM (via render, query)
- **Subdirectories:** reports/, slides/, charts/

## Article Template

Every wiki page in wiki/ MUST follow this frontmatter schema:

```yaml
---
title: "Article Title"
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: concept | topic | entity | glossary
sources:
  - raw/articles/source-name.md
tags: [tag1, tag2]
related:
  - "[[Related Article 1]]"
summary: "One-sentence summary."
source_count: 2
---
```

### Required Sections

1. **Overview** — 2-3 sentence summary of the concept
2. **Details** — Main content, organized with subheadings as needed
3. **Sources** — List of raw sources this article draws from, with specific citations
4. **Related** — Wikilinks to related articles (must match the `related` frontmatter field)

## Compilation Workflow

When compiling a source, follow this sequence:

1. Read the raw source file
2. In interactive mode: discuss key concepts with the user before writing
3. Write or update wiki articles (one per concept/entity/topic)
4. Update wiki/index.md with one-line summary for each new/updated article
5. Update wiki/glossary.md with new terms
6. Update related fields to maintain bidirectional wikilinks
7. Log the operation to _system/log.md

## Wikilink Conventions

- Use `[[article-name]]` format for all cross-references
- Links must be bidirectional: if A links to B, B's `related` field must include A
- Use the article's filename (without extension) as the link target
- Prefer specific links over general ones

## Conflict Handling

When new information contradicts existing claims in a wiki article:

> [!warning] CONFLICT
> **Source A** claims X. **Source B** claims Y.
> Both claims preserved pending resolution.

Never silently overwrite existing claims. Always preserve both sides with attribution.

## Quality Standards

- Minimum article length: 200 words
- Every article must cite at least one raw source
- Every article must have a complete frontmatter block
- Summaries must be one sentence, under 150 characters
- Tags should use lowercase, hyphenated format (e.g., `machine-learning`)

## Log Format

All operations are logged in `_system/log.md` with this format:

```markdown
## [YYYY-MM-DD] <operation> | <title>
- Source: <path>
- Status: <status>
- Details: <any additional info>
```

Operations: `init`, `ingest`, `compile`, `lint`, `query`

## Domain Conventions

_This section evolves during use. As patterns emerge in your wiki's content, document domain-specific conventions here — naming standards, taxonomy rules, preferred terminology, etc._
"""
