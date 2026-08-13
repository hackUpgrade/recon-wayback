import httpx
import pytest

from wayback_recon import api
from wayback_recon.api import (
    EmptyResponseError,
    InvalidDomainError,
    WaybackClient,
    WaybackError,
)

GOOD = {"json": [["original"], ["http://example.com/"], ["http://example.com/admin/"]]}


def _response(status: int = 200, payload: object = GOOD["json"]):
    return httpx.Response(status, json=payload)


def _no_sleep(*_args, **_kwargs):
    return None


def test_fetch_returns_urls(monkeypatch):
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(kwargs)
        return _response()

    monkeypatch.setattr(api.httpx, "get", fake_get)
    monkeypatch.setattr(api.time, "sleep", _no_sleep)

    assert WaybackClient().fetch_urls("example.com") == [
        "http://example.com/",
        "http://example.com/admin/",
    ]


def test_requests_domain_match_and_ua(monkeypatch):
    captured = {}

    def fake_get(*args, **kwargs):
        captured.update(kwargs)
        return _response()

    monkeypatch.setattr(api.httpx, "get", fake_get)

    WaybackClient().fetch_urls("example.com")
    params = captured["params"]
    assert params["url"] == "example.com"
    assert params["matchType"] == "domain"
    assert "collapse" not in params
    assert "wayback-recon" in captured["headers"]["User-Agent"]


def test_retries_on_503_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_get(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] <= 2:
            return _response(503)
        return _response()

    monkeypatch.setattr(api.httpx, "get", fake_get)
    monkeypatch.setattr(api.time, "sleep", _no_sleep)

    urls = WaybackClient(retries=3).fetch_urls("example.com")
    assert urls == ["http://example.com/", "http://example.com/admin/"]
    assert calls["n"] == 3


def test_retries_on_timeout_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_get(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] <= 1:
            raise httpx.TimeoutException("too slow")
        return _response()

    monkeypatch.setattr(api.httpx, "get", fake_get)
    monkeypatch.setattr(api.time, "sleep", _no_sleep)

    urls = WaybackClient(retries=3).fetch_urls("example.com")
    assert urls == ["http://example.com/", "http://example.com/admin/"]
    assert calls["n"] == 2


def test_gives_up_after_max_retries(monkeypatch):
    calls = {"n": 0}

    def fake_get(*args, **kwargs):
        calls["n"] += 1
        raise httpx.TimeoutException("too slow")

    monkeypatch.setattr(api.httpx, "get", fake_get)
    monkeypatch.setattr(api.time, "sleep", _no_sleep)

    with pytest.raises(WaybackError, match="timed out"):
        WaybackClient(retries=2).fetch_urls("example.com")
    assert calls["n"] == 3


def test_gives_up_on_retryable_status(monkeypatch):
    calls = {"n": 0}

    def fake_get(*args, **kwargs):
        calls["n"] += 1
        return _response(504)

    monkeypatch.setattr(api.httpx, "get", fake_get)
    monkeypatch.setattr(api.time, "sleep", _no_sleep)

    with pytest.raises(WaybackError, match="busy"):
        WaybackClient(retries=1).fetch_urls("example.com")
    assert calls["n"] == 2


def test_non_retryable_status_raises_immediately(monkeypatch):
    def fake_get(*args, **kwargs):
        return _response(401)

    monkeypatch.setattr(api.httpx, "get", fake_get)

    with pytest.raises(WaybackError, match="HTTP 401"):
        WaybackClient(retries=3).fetch_urls("example.com")


def test_empty_response_raises(monkeypatch):
    def fake_get(*args, **kwargs):
        return _response(200, payload=[["original"]])

    monkeypatch.setattr(api.httpx, "get", fake_get)

    with pytest.raises(EmptyResponseError, match="No archived URLs"):
        WaybackClient().fetch_urls("example.com")


def test_invalid_domain_raises_without_network(monkeypatch):
    def fake_get(*args, **kwargs):
        raise AssertionError("network should not be contacted")

    monkeypatch.setattr(api.httpx, "get", fake_get)

    with pytest.raises(InvalidDomainError, match="Invalid domain"):
        WaybackClient().fetch_urls("bad_domain!")