"""wiki-vault ingest command — register sources into the vault."""

import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

import click

from wiki_vault.utils.catalog import update_catalog
from wiki_vault.utils.git import git_commit
from wiki_vault.utils.log import append_log
from wiki_vault.utils.manifest import update_manifest

# Extension to raw/ subdirectory mapping
EXT_MAP = {
    ".md": "raw/articles",
    ".txt": "raw/articles",
    ".pdf": "raw/papers",
    ".csv": "raw/datasets",
    ".json": "raw/datasets",
    ".tsv": "raw/datasets",
    ".png": "raw/images",
    ".jpg": "raw/images",
    ".jpeg": "raw/images",
    ".gif": "raw/images",
    ".svg": "raw/images",
}
DEFAULT_SUBDIR = "raw/articles"


def _find_vault_root(start: Path = None) -> Path:
    """Walk up from start to find a directory containing _system/config.yaml."""
    p = start or Path.cwd()
    for d in [p, *p.parents]:
        if (d / "_system" / "config.yaml").exists():
            return d
    raise click.ClickException("Not inside a wiki vault (no _system/config.yaml found). Run `wiki-vault init` first.")


def _word_count(filepath: Path) -> int:
    """Count words in a text file. Returns 0 for binary files."""
    try:
        text = filepath.read_text(encoding="utf-8")
        return len(text.split())
    except (UnicodeDecodeError, ValueError):
        return 0


def _title_from_path(filepath: Path) -> str:
    """Extract a human-readable title from a file path."""
    return filepath.stem.replace("-", " ").replace("_", " ").title()


def _ingest_local_file(vault_path: Path, source: Path) -> dict:
    """Copy a local file into the correct raw/ subdirectory. Returns metadata."""
    ext = source.suffix.lower()
    subdir = EXT_MAP.get(ext, DEFAULT_SUBDIR)
    dest_dir = vault_path / subdir
    dest_dir.mkdir(parents=True, exist_ok=True)

    # Disambiguate common filenames (SKILL.md, README.md, etc.) by prefixing parent dir
    dest_name = source.name
    dest = dest_dir / dest_name
    if dest.exists() or dest_name.upper() == dest_name:
        # Use parent folder name as prefix for disambiguation
        parent_name = source.parent.name
        if parent_name and parent_name not in (".", "/"):
            dest_name = f"{parent_name}-{source.name}"
            dest = dest_dir / dest_name

    shutil.copy2(source, dest)

    rel_path = dest.relative_to(vault_path).as_posix()
    words = _word_count(dest)
    # Use parent folder for title when filename is generic
    if source.stem.upper() == source.stem and source.parent.name:
        title = _title_from_path(Path(source.parent.name))
    else:
        title = _title_from_path(source)

    return {
        "source": str(source),
        "dest": rel_path,
        "title": title,
        "word_count": words,
    }


def _ingest_url(vault_path: Path, url: str) -> dict:
    """Fetch a URL, extract content as markdown, download images. Returns metadata."""
    import requests
    from readability import Document
    from markdownify import markdownify as md

    resp = requests.get(url, timeout=30, headers={"User-Agent": "wiki-vault/0.1"})
    resp.raise_for_status()

    doc = Document(resp.text)
    title = doc.title()
    html_content = doc.summary()

    # Convert HTML to markdown
    markdown_content = md(html_content, heading_style="ATX", strip=["img"])

    # Download images from the HTML
    img_dir = vault_path / "raw" / "images"
    img_dir.mkdir(parents=True, exist_ok=True)

    from lxml import html as lxml_html
    tree = lxml_html.fromstring(html_content)
    for img in tree.xpath("//img[@src]"):
        img_url = img.get("src")
        if not img_url or img_url.startswith("data:"):
            continue
        # Make absolute URL
        if img_url.startswith("//"):
            img_url = "https:" + img_url
        elif img_url.startswith("/"):
            parsed = urlparse(url)
            img_url = f"{parsed.scheme}://{parsed.netloc}{img_url}"
        try:
            img_resp = requests.get(img_url, timeout=15)
            img_resp.raise_for_status()
            img_name = Path(urlparse(img_url).path).name or "image.png"
            img_dest = img_dir / img_name
            img_dest.write_bytes(img_resp.content)
            # Rewrite reference in markdown
            markdown_content = markdown_content.replace(img_url, f"../images/{img_name}")
        except Exception:
            pass  # Skip failed image downloads

    # Slugify title for filename
    slug = re.sub(r"[^\w\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")[:80]
    if not slug:
        slug = "untitled"

    # Write markdown with frontmatter
    from datetime import date
    dest_path = vault_path / "raw" / "articles" / f"{slug}.md"
    frontmatter = f"---\ntitle: \"{title}\"\nurl: \"{url}\"\ndate_fetched: \"{date.today().isoformat()}\"\n---\n\n"
    dest_path.write_text(frontmatter + markdown_content, encoding="utf-8")

    rel_path = dest_path.relative_to(vault_path).as_posix()
    words = len(markdown_content.split())

    return {
        "source": url,
        "dest": rel_path,
        "title": title,
        "word_count": words,
    }


def run_ingest(paths: tuple[str, ...], url: bool = False, do_compile: bool = False) -> None:
    """Ingest one or more sources into the vault."""
    if not paths:
        raise click.ClickException("No sources provided. Usage: wiki-vault ingest <path> [<path> ...]")

    vault_path = _find_vault_root()
    results = []

    for source in paths:
        try:
            if url:
                meta = _ingest_url(vault_path, source)
            else:
                source_path = Path(source).resolve()
                if not source_path.exists():
                    click.echo(f"Warning: {source} not found, skipping.", err=True)
                    continue
                meta = _ingest_local_file(vault_path, source_path)

            # Update catalog and manifest
            update_catalog(vault_path, meta["dest"], meta["title"], meta["word_count"])
            update_manifest(vault_path, meta["dest"], meta["word_count"])
            append_log(vault_path, "ingest", meta["title"], {
                "Source": meta["source"],
                "Destination": meta["dest"],
                "Status": "pending-compile",
                "Word count": str(meta["word_count"]),
            })

            results.append(meta)
            click.echo(f"  Ingested: {meta['title']} -> {meta['dest']} ({meta['word_count']} words)")

        except Exception as e:
            click.echo(f"  Error ingesting {source}: {e}", err=True)

    if results:
        git_commit(vault_path, f"wiki-vault: ingest | {len(results)} source(s)")
        click.echo(f"\n{len(results)} source(s) ingested. Status: pending-compile")

    if do_compile and results:
        click.echo("\nRunning compile...")
        from wiki_vault.commands.compile import run_compile
        run_compile(batch=False)
