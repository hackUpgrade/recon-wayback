"""Rendering of results to the terminal and export to JSON."""

from __future__ import annotations

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .classifier import CATEGORY_ORDER

CATEGORY_STYLES: dict[str, str] = {
    "ADMIN": "bright_red",
    "LOGIN": "bright_yellow",
    "API": "cyan",
    "DEV": "magenta",
    "STAGING": "bright_magenta",
    "BACKUP": "bright_blue",
    "BAK": "bright_blue",
    "ENV": "green",
    "SQL": "green",
    "ARCHIVE": "bright_blue",
    "JAVASCRIPT": "bright_cyan",
    "CONFIG": "yellow",
}


def print_summary(
    console: Console,
    domain: str,
    total: int,
    unique: int,
    interesting: int,
    *,
    pages_ok: int | None = None,
    pages_failed: int | None = None,
    links_extracted: int | None = None,
) -> None:
    """Render the summary panel with the scan totals."""
    table = Table(show_header=False, box=None)
    table.add_column(style="bold", min_width=16)
    table.add_column(style="white")
    table.add_row("[cyan]Target[/]", domain)
    table.add_row("[cyan]URLs found[/]", str(total))
    table.add_row("[cyan]Unique URLs[/]", str(unique))
    table.add_row("[cyan]Interesting URLs[/]", str(interesting))
    if pages_ok is not None:
        table.add_row("[cyan]Pages analysed[/]", str(pages_ok))
    if pages_failed:
        table.add_row("[cyan]Pages skipped[/]", str(pages_failed))
    if links_extracted is not None:
        table.add_row("[cyan]New links extracted[/]", str(links_extracted))

    panel = Panel(
        table,
        title="[bold blue]WAYBACK RECON[/]",
        border_style="blue",
        padding=(0, 1),
    )
    console.print(panel)


def print_interesting(console: Console, groups: dict[str, list[str]]) -> None:
    """Render URLs grouped by their interesting category."""
    if not groups:
        console.print("[yellow]No interesting URLs found.[/]")
        return

    for label in CATEGORY_ORDER:
        urls = groups.get(label)
        if not urls:
            continue
        style = CATEGORY_STYLES.get(label, "white")
        console.print(f"[bold {style}]{label}[/]")
        for url in urls:
            console.print(url, style=style)
        console.print()


def export_json(
    path: Path,
    domain: str,
    total: int,
    urls: list[str],
    groups: dict[str, list[str]],
    *,
    pages_ok: int | None = None,
    pages_failed: int | None = None,
    links_extracted: int | None = None,
) -> None:
    """Write the scan results to *path* as structured JSON."""
    payload = {
        "tool": "wayback-recon",
        "domain": domain,
        "total_urls": total,
        "unique_urls": len(urls),
        "interesting_urls": sum(len(items) for items in groups.values()),
        "categories": dict(groups),
        "urls": urls,
    }
    if pages_ok is not None:
        payload["pages_analysed"] = pages_ok
    if pages_failed:
        payload["pages_skipped"] = pages_failed
    if links_extracted is not None:
        payload["links_extracted"] = links_extracted
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")