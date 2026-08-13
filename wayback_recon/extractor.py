"""Extraction of outlinks from archived page copies.

The Wayback Machine stores a raw copy of every page it captured. By asking the
replay service for the raw archived content (the ``id_`` variant, which leaves
the original URLs untouched) we can harvest the links that exist *inside* the
pages. This discovers routes and subdomains that were referenced by the target
but never captured as URLs themselves.
"""

from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from .api import DEFAULT_RETRIES, DEFAULT_TIMEOUT, _USER_AGENT, _backoff

# Status codes that usually mean "the Wayback service is busy / throttling us".
_THROTTLE_STATUS = {403, 503, 504}

_LINKABLE_ATTRS = ("href", "src", "action")
_SKIPPED_SCHEMES = ("mailto:", "tel:", "data:", "javascript:", "about:", "#")

# Known non-document extensions: if a URL's path ends in one of these, fetching
# its archived copy is unlikely to yield any useful links.
_ASSET_EXTS = {
    "7z", "avi", "bak", "bmp", "bz2", "cfg", "conf", "csv", "doc", "docx", "eot",
    "env", "gif", "gz", "ico", "ini", "jpeg", "jpg", "json", "js", "m4v", "mkv",
    "mov", "mp3", "mp4", "ogg", "otf", "pdf", "png", "ppt", "pptx", "rar", "sql",
    "svg", "swf", "tar", "tiff", "toml", "ttf", "webm", "webp", "woff", "woff2",
    "xls", "xlsx", "xml", "xz", "yaml", "yml", "zip", "zst",
}


class _LinkParser(HTMLParser):
    """Collect the href/src/action attributes of an HTML document."""

    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if key in _LINKABLE_ATTRS and value and value.strip():
                self.links.append(value.strip())


def looks_like_document(url: str) -> bool:
    """Return True when *url* points to a page likely to contain links."""
    path = urlparse(url).path.rstrip("/")
    last = path.rsplit("/", 1)[-1]
    ext = last.rsplit(".", 1)[-1].lower() if "." in last else ""
    return ext not in _ASSET_EXTS


def extract_links(html: str, domain: str, base_url: str) -> list[str]:
    """Return absolute URLs referenced by ``html`` that belong to *domain* or a subdomain.

    Relative links are resolved against *base_url* (the original page URL).
    External links, fragments, and ``mailto:``/``javascript:``/``data:`` URLs are ignored.
    """
    parser = _LinkParser()
    parser.feed(html)

    extracted: list[str] = []
    for raw in parser.links:
        lower = raw.lower()
        if raw.startswith("#") or any(lower.startswith(s) for s in _SKIPPED_SCHEMES):
            continue
        absolute = urljoin(base_url, raw)
        host = urlparse(absolute).hostname
        if host and (host.lower() == domain.lower() or host.lower().endswith("." + domain.lower())):
            extracted.append(absolute)
    return extracted


def fetch_archived_page(
    original_url: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> str | None:
    """Fetch the raw archived copy of *original_url*.

    Returns the page HTML, or ``None`` if every attempt failed or the archived
    content is not HTML. Transient Wayback failures (403/503/504/timeouts) are
    retried with exponential backoff.
    """
    replay_url = f"https://web.archive.org/web/2id_/{original_url}"

    for attempt in range(retries + 1):
        if attempt:
            _backoff(attempt)
        try:
            response = httpx.get(
                replay_url,
                timeout=timeout,
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            )
        except httpx.RequestError:
            continue
        if response.status_code == 200:
            content_type = response.headers.get("content-type", "")
            if not content_type or "text/html" in content_type:
                return response.text
            return None
        if response.status_code not in _THROTTLE_STATUS:
            return None
    return None


def harvest_links(
    originals: list[str],
    domain: str,
    *,
    timeout: float = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
) -> tuple[list[str], int]:
    """Fetch the archived copies of *originals* and harvest their outlinks.

    Returns ``(all_extracted_links, failed_pages)`` where *failed_pages* counts
    the pages whose archived copy could not be retrieved.
    """
    all_links: list[str] = []
    failed = 0
    for original in originals:
        html = fetch_archived_page(original, timeout=timeout, retries=retries)
        if html is None:
            failed += 1
            continue
        all_links.extend(extract_links(html, domain, original))
    return all_links, failed