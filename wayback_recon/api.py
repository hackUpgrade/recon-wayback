"""Client for the Wayback Machine CDX API."""

from __future__ import annotations

import random
import re
import time

import httpx

CDX_API_URL = "https://web.archive.org/cdx/search/cdx"
DEFAULT_TIMEOUT = 60.0
DEFAULT_RETRIES = 3
_INITIAL_BACKOFF = 2.0
# The Wayback Machine is an overloaded public service; these are transient
# and usually succeed on a retry.
_RETRYABLE_STATUS = {503, 504}
_USER_AGENT = "wayback-recon/0.2.0 (passive OSINT reconnaissance; authorized use only)"

# A practical domain regex: one or more labels, each starting/ending
# with an alphanumeric character, with a TLD of 2+ letters.
_DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
    re.IGNORECASE,
)


class WaybackError(Exception):
    """Base error for every Wayback Machine interaction failure."""


class InvalidDomainError(WaybackError):
    """The supplied target is not a syntactically valid domain."""


class EmptyResponseError(WaybackError):
    """The CDX API returned no usable URLs for the target."""


class WaybackClient:
    """A thin, stateless wrapper around the Wayback CDX API."""

    def __init__(
        self,
        base_url: str = CDX_API_URL,
        timeout: float = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
    ) -> None:
        self.base_url = base_url
        self.timeout = timeout
        self.retries = retries

    def _validate_domain(self, domain: str) -> None:
        if not _DOMAIN_RE.fullmatch(domain):
            raise InvalidDomainError(
                f"Invalid domain {domain!r}. Expected something like 'example.com'."
            )

    def fetch_urls(self, domain: str, *, limit: int | None = None) -> list[str]:
        """Fetch archived URLs for *domain* from the CDX API.

        Transient failures (HTTP 503/504 and network timeouts) are retried
        up to ``self.retries`` extra times with exponential backoff, because
        the Wayback Machine is a busy public service that frequently succeeds
        on a retry.

        De-duplication happens client-side (see :mod:`wayback_recon.parser`);
        the server-side ``collapse`` option is intentionally not used because
        it is slow and frequently times out on the CDX side.

        Raises:
            InvalidDomainError: if the domain is syntactically invalid.
            EmptyResponseError: if no archived URLs were returned.
            WaybackError: on persistent network, timeout, or HTTP errors.
        """
        domain = domain.strip()
        self._validate_domain(domain)

        params: dict[str, str] = {
            "url": domain,
            "matchType": "domain",
            "output": "json",
            "fl": "original",
        }
        if limit and limit > 0:
            params["limit"] = str(limit)

        last_error: WaybackError | None = None
        for attempt in range(self.retries + 1):
            if attempt:
                _backoff(attempt)
            try:
                response = httpx.get(
                    self.base_url,
                    params=params,
                    timeout=self.timeout,
                    follow_redirects=True,
                    headers={"User-Agent": _USER_AGENT},
                )
            except httpx.TimeoutException as exc:
                last_error = WaybackError(f"Request timed out after {self.timeout:g}s.")
            except httpx.RequestError as exc:
                last_error = WaybackError(
                    f"Network error while contacting the Wayback Machine: {exc}"
                )
            else:
                if response.status_code == 200:
                    return _parse_records(response, domain)
                if response.status_code in _RETRYABLE_STATUS:
                    last_error = WaybackError(
                        f"The Wayback Machine is busy (HTTP {response.status_code})."
                    )
                else:
                    raise WaybackError(
                        f"The Wayback Machine responded with HTTP {response.status_code}."
                    )
            if attempt < self.retries:
                continue
            raise last_error or WaybackError("Unknown failure.")

        raise WaybackError("Unknown failure.")  # pragma: no cover


def _backoff(attempt: int) -> None:
    """Sleep with exponential backoff plus a little jitter before a retry."""
    time.sleep(_INITIAL_BACKOFF * 2 ** (attempt - 1) + random.uniform(0, 0.5))


def _parse_records(response: httpx.Response, domain: str) -> list[str]:
    """Extract distinct original URLs from a JSON CDX response."""
    try:
        records = response.json()
    except ValueError as exc:
        raise WaybackError("The Wayback Machine returned an invalid response.") from exc

    if len(records) <= 1:
        raise EmptyResponseError(f"No archived URLs found for '{domain}'.")

    urls = [
        row[0].strip()
        for row in records[1:]
        if isinstance(row, list) and row and isinstance(row[0], str)
    ]
    if not urls:
        raise EmptyResponseError(f"No archived URLs found for '{domain}'.")

    return urls