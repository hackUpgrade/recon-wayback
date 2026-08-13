"""Command-line interface for Wayback Recon."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from . import __version__
from .api import WaybackClient, WaybackError
from .classifier import classify_urls
from .extractor import harvest_links, looks_like_document
from .parser import normalize_urls
from .reporter import export_json, print_interesting, print_summary

app = typer.Typer(
    name="wayback-recon",
    help="Passive OSINT reconnaissance using the Wayback Machine CDX API.",
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)


@app.callback(invoke_without_command=True)
def _main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option("--version", help="Show the version and exit.", is_eager=True),
    ] = False,
) -> None:
    """Shared options for all commands."""
    if version:
        console.print(f"wayback-recon {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:  # pragma: no cover (help is shown by typer)
        raise typer.Exit()


@app.command()
def scan(
    domain: Annotated[
        str,
        typer.Argument(help="Target domain, e.g. example.com."),
    ],
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Export the results to a JSON file.",
        ),
    ] = None,
    interesting_only: Annotated[
        bool,
        typer.Option(
            "--interesting",
            help="Show only URLs classified as interesting (skip the summary).",
        ),
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit",
            help="Stop after this many archived URLs (default: no limit).",
        ),
    ] = None,
    timeout: Annotated[
        float,
        typer.Option("--timeout", help="Request timeout in seconds."),
    ] = 60.0,
    retries: Annotated[
        int,
        typer.Option(
            "--retries",
            help="Extra attempts on transient failures (503/504/timeout).",
        ),
    ] = 3,
    extract_links: Annotated[
        bool,
        typer.Option(
            "--extract-links",
            help="Also fetch archived page copies and harvest the links inside them.",
        ),
    ] = False,
    max_pages: Annotated[
        int,
        typer.Option(
            "--max-pages",
            help="Archived pages to fetch when --extract-links is used.",
        ),
    ] = 20,
) -> None:
    """Scan *domain* for historical URLs archived by the Wayback Machine."""
    client = WaybackClient(timeout=timeout, retries=retries)

    try:
        with console.status(f"Querying the Wayback Machine for {domain}..."):
            raw_urls = client.fetch_urls(domain, limit=limit)
    except WaybackError as exc:
        err_console.print(f"[bold red]Error:[/] {exc}")
        raise typer.Exit(code=1) from exc

    urls = normalize_urls(raw_urls)

    pages_ok: int | None = None
    pages_failed: int | None = None
    links_extracted: int | None = None
    if extract_links:
        candidates = [u for u in urls if looks_like_document(u)][:max_pages]
        if candidates:
            with console.status(
                f"Extracting links from {len(candidates)} archived pages..."
            ):
                raw_links, pages_failed = harvest_links(
                    candidates, domain, timeout=timeout, retries=retries
                )
            pages_ok = len(candidates) - pages_failed
            merged = normalize_urls([*urls, *raw_links])
            links_extracted = len(merged) - len(urls)
            urls = merged
        else:
            pages_ok = 0
            pages_failed = 0

    groups = classify_urls(urls)
    interesting_count = sum(len(items) for items in groups.values())

    if not interesting_only:
        print_summary(
            console,
            domain,
            len(raw_urls),
            len(urls),
            interesting_count,
            pages_ok=pages_ok,
            pages_failed=pages_failed,
            links_extracted=links_extracted,
        )

    print_interesting(console, groups)

    if output is not None:
        export_json(
            output,
            domain,
            len(raw_urls),
            urls,
            groups,
            pages_ok=pages_ok,
            pages_failed=pages_failed,
            links_extracted=links_extracted,
        )
        console.print(f"[green]Results saved to[/] [bold]{output}[/]")


if __name__ == "__main__":
    app()