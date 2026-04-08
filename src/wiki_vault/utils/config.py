"""Config generation for wiki-vault."""

from datetime import date
from pathlib import Path

import yaml

DEFAULT_CONFIG = {
    "vault": {
        "name": "",
        "created": "",
    },
    "compile": {
        "model": "claude-sonnet-4-20250514",
        "max_article_length": 3000,
        "auto_glossary": True,
        "interactive": True,
    },
    "lint": {
        "staleness_threshold_days": 90,
        "min_article_length": 200,
        "require_sources": True,
    },
    "search": {
        "engine": "builtin",
        "index_fallback": True,
    },
    "render": {
        "marp_theme": "default",
        "chart_style": "seaborn",
        "chart_dpi": 150,
    },
    "paths": {
        "raw": "raw/",
        "wiki": "wiki/",
        "output": "output/",
        "system": "_system/",
    },
}


def generate_config(vault_path: Path, name: str) -> None:
    """Write _system/config.yaml with vault name and creation date."""
    config = DEFAULT_CONFIG.copy()
    config["vault"] = {
        "name": name,
        "created": date.today().isoformat(),
    }
    config_path = vault_path / "_system" / "config.yaml"
    config_path.write_text(yaml.dump(config, default_flow_style=False, sort_keys=False))
