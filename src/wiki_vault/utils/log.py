"""Append-only log writer for wiki-vault operations."""

from datetime import date
from pathlib import Path


def append_log(vault_path: Path, operation: str, title: str, details: dict) -> None:
    """Append a formatted entry to _system/log.md.

    Format: ## [YYYY-MM-DD] <operation> | <title>
    """
    log_path = vault_path / "_system" / "log.md"
    lines = [f"\n## [{date.today().isoformat()}] {operation} | {title}\n"]
    for key, value in details.items():
        lines.append(f"- {key}: {value}\n")
    lines.append("\n")

    with open(log_path, "a", encoding="utf-8") as f:
        f.writelines(lines)
