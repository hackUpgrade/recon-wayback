"""Normalization and de-duplication of raw CDX API results."""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

_DEFAULT_PORTS = {"http": 80, "https": 443}

_SCHEME_RE = re.compile(r"(?i)^(https?)://")


def normalize_urls(urls: list[str]) -> list[str]:
    """Normalize and de-duplicate raw URLs.

    * Blank entries are skipped.
    * URL-less entries are treated as ``https://`` URLs.
    * Schemes and hostnames are lowercased.
    * Default ports (:80 / :443) are removed.
    * Paths are kept but empty paths become ``/``.
    * Fragments are dropped; query strings are kept.
    * The result is sorted alphabetically for deterministic output.
    """
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        normalized = _normalize(url)
        if normalized is not None and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    result.sort()
    return result


def _normalize(url: str) -> str | None:
    """Return a canonical form of *url*, or ``None`` if it cannot be parsed."""
    cleaned = url.strip()
    if not cleaned:
        return None
    if not _SCHEME_RE.match(cleaned):
        cleaned = "https://" + cleaned

    parsed = urlparse(cleaned)
    if not parsed.hostname or any(ch.isspace() for ch in parsed.hostname):
        return None

    scheme = parsed.scheme.lower()
    hostname = parsed.hostname.lower()

    if parsed.port and parsed.port == _DEFAULT_PORTS.get(scheme):
        netloc = hostname
    elif parsed.port:
        netloc = f"{hostname}:{parsed.port}"
    else:
        netloc = hostname

    return urlunparse((scheme, netloc, parsed.path or "/", "", parsed.query, ""))