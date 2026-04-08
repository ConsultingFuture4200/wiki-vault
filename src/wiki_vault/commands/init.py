"""wiki-vault init command — scaffold a new vault."""

import json
from pathlib import Path

import click

from wiki_vault.templates.claude_md import generate_claude_md
from wiki_vault.utils.config import generate_config
from wiki_vault.utils.git import git_commit, git_init
from wiki_vault.utils.log import append_log

# All directories to create
DIRECTORIES = [
    "raw/articles",
    "raw/papers",
    "raw/repos",
    "raw/datasets",
    "raw/images",
    "wiki/concepts",
    "wiki/topics",
    "wiki/entities",
    "output/reports",
    "output/slides",
    "output/charts",
    "_system/prompts",
]

# Placeholder files with initial content
PLACEHOLDERS = {
    "wiki/index.md": (
        "---\ntitle: Index\ntype: index\n---\n\n"
        "# Index\n\n"
        "| Article | Type | Summary |\n"
        "|---------|------|---------|\n"
    ),
    "wiki/glossary.md": (
        "---\ntitle: Glossary\ntype: glossary\n---\n\n"
        "# Glossary\n\n"
        "_Terms are added automatically during compilation._\n"
    ),
    "_system/catalog.md": (
        "# Source Catalog\n\n"
        "| Source | Title | Ingested | Status | Words |\n"
        "|--------|-------|----------|--------|-------|\n"
    ),
    "_system/log.md": "# Operations Log\n",
    "_system/health.md": (
        "# Vault Health\n\n"
        "_Run `wiki-vault lint` to populate this report._\n"
    ),
    "_system/manifest.json": "{}",
}

PROMPT_STUBS = {
    "_system/prompts/compile.md": "# Compile Prompt\n\n_TODO: Generated during first compile._\n",
    "_system/prompts/query.md": "# Query Prompt\n\n_TODO: Phase 2._\n",
    "_system/prompts/lint.md": "# Lint Prompt\n\n_TODO: Phase 2._\n",
    "_system/prompts/render.md": "# Render Prompt\n\n_TODO: Phase 3._\n",
}

OBSIDIAN_APP_JSON = {
    "attachmentFolderPath": "raw/images/",
}


def scaffold_vault(base_path: Path, name: str) -> None:
    """Create all vault directories and placeholder files."""
    base_path.mkdir(parents=True, exist_ok=True)

    # Create directories
    for d in DIRECTORIES:
        (base_path / d).mkdir(parents=True, exist_ok=True)

    # Create placeholder files (don't overwrite if they exist)
    for filepath, content in {**PLACEHOLDERS, **PROMPT_STUBS}.items():
        p = base_path / filepath
        if not p.exists():
            p.write_text(content, encoding="utf-8")

    # .obsidian config
    obsidian_dir = base_path / ".obsidian"
    obsidian_dir.mkdir(exist_ok=True)
    app_json = obsidian_dir / "app.json"
    if not app_json.exists():
        app_json.write_text(json.dumps(OBSIDIAN_APP_JSON, indent=2) + "\n", encoding="utf-8")

    # CLAUDE.md
    claude_md = base_path / "CLAUDE.md"
    if not claude_md.exists():
        claude_md.write_text(generate_claude_md(name), encoding="utf-8")

    # config.yaml
    config_path = base_path / "_system" / "config.yaml"
    if not config_path.exists():
        generate_config(base_path, name)


def run_init(name: str) -> None:
    """Create a new wiki vault with the given name."""
    vault_path = Path.cwd() / name
    if vault_path.exists() and any(vault_path.iterdir()):
        click.echo(f"Error: Directory '{name}' already exists and is not empty.", err=True)
        raise SystemExit(1)

    click.echo(f"Creating wiki vault: {name}")
    scaffold_vault(vault_path, name)

    # Git init + first commit
    git_init(vault_path)
    git_commit(vault_path, f"wiki-vault: init | {name}")

    # Log the init operation
    append_log(vault_path, "init", name, {
        "Status": "created",
        "Directories": str(len(DIRECTORIES)),
        "Placeholder files": str(len(PLACEHOLDERS) + len(PROMPT_STUBS)),
    })

    click.echo(f"Vault created at: {vault_path}")
    click.echo(f"  {len(DIRECTORIES)} directories")
    click.echo(f"  {len(PLACEHOLDERS) + len(PROMPT_STUBS)} placeholder files")
    click.echo(f"  CLAUDE.md, config.yaml, .obsidian/app.json")
    click.echo(f"  Git repo initialized with first commit")
    click.echo(f"\nNext: cd {name} && wiki-vault ingest <source-file>")
