"""Git utilities for wiki-vault: init and auto-commit."""

import subprocess
from pathlib import Path

GITIGNORE_CONTENT = """\
# Obsidian
.obsidian/workspace.json
.obsidian/workspace-mobile.json

# Python
*.pyc
__pycache__/
*.egg-info/
dist/
build/

# OS
.DS_Store
Thumbs.db
"""


def git_init(path: Path) -> bool:
    """Initialize a git repo at path with a .gitignore. Returns True on success."""
    path = Path(path)
    result = subprocess.run(
        ["git", "init"],
        cwd=path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        click_echo_error(f"git init failed: {result.stderr}")
        return False

    gitignore = path / ".gitignore"
    if not gitignore.exists():
        gitignore.write_text(GITIGNORE_CONTENT)

    return True


def git_commit(path: Path, message: str) -> bool:
    """Stage all changes and commit. Returns True if a commit was created, False if nothing to commit."""
    path = Path(path)

    # Stage all changes
    subprocess.run(["git", "add", "-A"], cwd=path, capture_output=True, text=True)

    # Check if there's anything to commit
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=path,
        capture_output=True,
        text=True,
    )
    if not status.stdout.strip():
        return False

    result = subprocess.run(
        ["git", "commit", "-m", message],
        cwd=path,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def click_echo_error(msg: str):
    """Print error message using click if available, else print."""
    try:
        import click
        click.echo(f"Error: {msg}", err=True)
    except ImportError:
        print(f"Error: {msg}")
