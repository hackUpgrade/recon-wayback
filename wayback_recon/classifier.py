"""Classification of URLs into interesting attack-surface categories.

Each URL is assigned to **at most one** category: rules are evaluated in
priority order and the first match wins. Highly specific file-extension
rules (e.g. ``.env``, ``.sql``, ``.js``) come first, followed by path and
keyword rules (admin, login, api, ...).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlparse


@dataclass(frozen=True)
class CategoryRule:
    """A category and the markers that identify it.

    A URL is matched against the rule in this order:

    * ``substrings`` match anywhere in the (lowercased) URL;
    * ``patterns`` are regular expressions searched over the whole URL
      (case-insensitive) -- useful when a marker needs a boundary, e.g.
      ``/test`` should not match ``testphp.vulnweb.com``;
    * ``extensions`` must be the file extension at the end of the path,
      so ``.js`` matches ``app.js`` but not ``data.json``.
    """

    label: str
    substrings: tuple[str, ...] = ()
    patterns: tuple[str, ...] = ()
    extensions: tuple[str, ...] = ()

    def matches(self, url: str) -> bool:
        lowered = url.lower()
        if any(marker in lowered for marker in self.substrings):
            return True
        if any(pat.search(lowered) for pat in _compile_patterns(self.patterns)):
            return True
        path = urlparse(url).path.lower()
        return any(re.search(rf"\.{re.escape(ext)}$", path) for ext in self.extensions)


@lru_cache(maxsize=None)
def _compile_patterns(patterns: tuple[str, ...]) -> tuple[re.Pattern[str], ...]:
    return tuple(re.compile(pattern) for pattern in patterns)


RULES: tuple[CategoryRule, ...] = (
    CategoryRule("ENV", substrings=(".env",)),
    CategoryRule("SQL", extensions=("sql",)),
    CategoryRule("BACKUP", substrings=("backup", "dump", "snapshot")),
    CategoryRule("BAK", extensions=("bak", "old", "old1", "orig", "swp")),
    CategoryRule(
        "ARCHIVE",
        extensions=("zip", "tar", "tar.gz", "tgz", "gz", "rar", "7z", "bz2", "zst"),
    ),
    CategoryRule("JAVASCRIPT", extensions=("js",)),
    CategoryRule(
        "API",
        substrings=(
            "/api",
            "/graphql",
            "/swagger",
            "/openapi",
            "/v1/",
            "/v2/",
            "/v3/",
            "/v4/",
        ),
        patterns=(
            r"/rest(?:/|$|[?#])",
            r"/restful(?:/|$|[?#])",
            r"/rest-api(?:/|$|[?#])",
        ),
    ),
    CategoryRule(
        "ADMIN",
        substrings=("admin", "administrator", "dashboard", "/panel", "wp-admin", "/manage"),
    ),
    CategoryRule(
        "LOGIN",
        substrings=("login", "signin", "sign-in", "authenticate", "oauth"),
        patterns=(r"/auth(?:/|$|[?#])",),
    ),
    CategoryRule(
        "DEV",
        substrings=("dev.", "localhost", "/internal", "/debug", "/sandbox"),
        patterns=(r"/dev(?:/|$)", r"/test(?:/|$|[?#])", r"/tests(?:/|$)"),
    ),
    CategoryRule(
        "STAGING",
        substrings=("staging", "stage.", "/stage", "preprod", "pre-prod", "/beta"),
        patterns=(r"(?:[/.]|^)uat(?:[/.]|$)",),
    ),
    CategoryRule(
        "CONFIG",
        substrings=("config", "settings"),
        extensions=("yml", "yaml", "ini", "toml", "properties", "xml", "conf", "cfg", "json"),
    ),
)

CATEGORY_ORDER: tuple[str, ...] = tuple(rule.label for rule in RULES)


def classify_url(url: str) -> str | None:
    """Return the category label for *url*, or ``None`` if it is not interesting."""
    for rule in RULES:
        if rule.matches(url):
            return rule.label
    return None


def classify_urls(urls: list[str]) -> dict[str, list[str]]:
    """Group *urls* by their first matching interesting category.

    URLs that match no rule are excluded from the returned mapping.
    """
    grouped: dict[str, list[str]] = {}
    for url in urls:
        label = classify_url(url)
        if label is not None:
            grouped.setdefault(label, []).append(url)
    return grouped