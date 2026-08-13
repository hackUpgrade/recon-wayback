import httpx
import pytest

from wayback_recon import extractor
from wayback_recon.extractor import (
    extract_links,
    fetch_archived_page,
    harvest_links,
    looks_like_document,
)

HTML = """
<html>
<body>
  <a href="/admin/dashboard">Admin</a>
  <a href="https://sub.example.com/test">sub</a>
  <a href="https://external.org/x">external</a>
  <img src="/static/logo.png">
  <script src="/js/app.js?v=2"></script>
  <form action="/login.php">
  <a href="#top">fragment</a>
  <a href="mailto:x@y.com">mail</a>
  <a href="javascript:void(0)">js</a>
</body>
</html>
"""


def test_defines_document_urls():
    assert looks_like_document("https://example.com/")
    assert looks_like_document("https://example.com/about")
    assert looks_like_document("https://example.com/wp-login.php")
    assert looks_like_document("https://example.com/contato/")
    assert not looks_like_document("https://example.com/js/app.js")
    assert not looks_like_document("https://example.com/img/logo.png?v=1")
    assert not looks_like_document("https://example.com/backup.zip")
    assert not looks_like_document("https://example.com/data.json")


def test_extract_links_resolves_relative_and_filters():
    links = extract_links(HTML, "example.com", "http://example.com/")
    assert links == [
        "http://example.com/admin/dashboard",
        "https://sub.example.com/test",
        "http://example.com/static/logo.png",
        "http://example.com/js/app.js?v=2",
        "http://example.com/login.php",
    ]


def test_extract_links_ignores_other_domains():
    html = '<a href="https://other.org/a">x</a><a href="https://example.com/a">y</a>'
    assert extract_links(html, "example.com", "https://example.com/") == [
        "https://example.com/a"
    ]


def _no_sleep(*_args, **_kwargs):
    return None


def test_fetch_archived_retries_on_throttle(monkeypatch):
    calls = {"n": 0}

    def fake_get(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] <= 2:
            return httpx.Response(503)
        return httpx.Response(
            200,
            text="<html><body><a href='/x'>x</a></body></html>",
            headers={"content-type": "text/html"},
        )

    monkeypatch.setattr(extractor.httpx, "get", fake_get)
    monkeypatch.setattr(extractor, "_backoff", _no_sleep)

    html = fetch_archived_page("http://example.com/", retries=3)
    assert html is not None
    assert "link" in html or "href" in html
    assert calls["n"] == 3


def test_fetch_archived_gives_up(monkeypatch):
    def fake_get(*args, **kwargs):
        return httpx.Response(503)

    monkeypatch.setattr(extractor.httpx, "get", fake_get)
    monkeypatch.setattr(extractor, "_backoff", _no_sleep)

    assert fetch_archived_page("http://example.com/", retries=1) is None


def test_fetch_archived_skips_non_html(monkeypatch):
    def fake_get(*args, **kwargs):
        return httpx.Response(200, content=b"PK\x03\x04binary", headers={"content-type": "application/zip"})

    monkeypatch.setattr(extractor.httpx, "get", fake_get)

    assert fetch_archived_page("http://example.com/file.zip") is None


def test_harvest_links_counts_failures(monkeypatch):
    def fake_get(*args, **kwargs):
        url = args[0]
        if "missing" in url:
            return httpx.Response(503)
        return httpx.Response(
            200,
            text="<a href='/admin/'>a</a>",
            headers={"content-type": "text/html"},
        )

    monkeypatch.setattr(extractor.httpx, "get", fake_get)
    monkeypatch.setattr(extractor, "_backoff", _no_sleep)

    links, failed = harvest_links(
        ["http://example.com/", "http://example.com/missing"], "example.com", retries=1
    )
    assert failed == 1
    assert links == ["http://example.com/admin/"]