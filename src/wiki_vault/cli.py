"""CLI entry point for wiki-vault."""

import click

from wiki_vault import __version__


@click.group()
@click.version_option(version=__version__)
def cli():
    """Turn raw sources into structured, interlinked Obsidian wikis."""


@cli.command()
@click.argument("name")
def init(name):
    """Create a new wiki vault with the given NAME."""
    from wiki_vault.commands.init import run_init

    run_init(name)


@cli.command()
@click.argument("paths", nargs=-1)
@click.option("--url", is_flag=True, help="Treat paths as URLs to fetch.")
@click.option("--compile", "do_compile", is_flag=True, help="Run compile after ingest.")
def ingest(paths, url, do_compile):
    """Ingest one or more source files (or URLs with --url) into the vault."""
    from wiki_vault.commands.ingest import run_ingest

    run_ingest(paths, url=url, do_compile=do_compile)


@cli.command()
@click.option("--batch", is_flag=True, help="Skip interactive review (unattended mode).")
def compile(batch):
    """Compile pending sources into wiki pages."""
    from wiki_vault.commands.compile import run_compile

    run_compile(batch=batch)
