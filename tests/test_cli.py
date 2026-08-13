import json
from pathlib import Path

from typer.testing import CliRunner

from wayback_recon.api import EmptyResponseError
from wayback_recon.cli import app

runner = CliRunner()

FAKE_URLS = [
    "http://example.com/",
    "http://example.com/admin/",
    "http://example.com/admin/",
    "http://example.com/api/v1/users",
    "http://example.com/app.js",
    "http://example.com/blog",
]


def _fake_fetch(self, domain, *, limit=None):
    return FAKE_URLS


def test_scan_prints_summary_and_interesting(monkeypatch, tmp_path):
    monkeypatch.setattr("wayback_recon.cli.WaybackClient.fetch_urls", _fake_fetch)
    out = tmp_path / "results.json"

    result = runner.invoke(app, ["scan", "example.com", "-o", str(out)])

    assert result.exit_code == 0
    assert "WAYBACK RECON" in result.stdout
    assert "example.com" in result.stdout
    assert "URLs found" in result.stdout
    assert "ADMIN" in result.stdout
    assert "http://example.com/admin/" in result.stdout
    assert "API" in result.stdout
    assert "http://example.com/api/v1/users" in result.stdout


def test_scan_exports_json(monkeypatch, tmp_path):
    monkeypatch.setattr("wayback_recon.cli.WaybackClient.fetch_urls", _fake_fetch)
    out = tmp_path / "results.json"

    result = runner.invoke(app, ["scan", "example.com", "-o", str(out)])

    assert result.exit_code == 0
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["tool"] == "wayback-recon"
    assert payload["domain"] == "example.com"
    assert payload["total_urls"] == 6
    assert payload["unique_urls"] == 5
    assert payload["interesting_urls"] == 3
    assert "urls" in payload and len(payload["urls"]) == 5
    assert payload["categories"]["ADMIN"] == ["http://example.com/admin/"]


def test_interesting_only_skips_summary(monkeypatch):
    monkeypatch.setattr("wayback_recon.cli.WaybackClient.fetch_urls", _fake_fetch)

    result = runner.invoke(app, ["scan", "example.com", "--interesting"])

    assert result.exit_code == 0
    assert "WAYBACK RECON" not in result.stdout
    assert "ADMIN" in result.stdout
    assert "JAVASCRIPT" in result.stdout


def test_invalid_domain_fails_without_network():
    result = runner.invoke(app, ["scan", "bad_domain!"])
    assert result.exit_code == 1


def test_empty_response_is_handled(monkeypatch):
    def _empty(self, domain, *, limit=None):
        raise EmptyResponseError(f"No archived URLs found for '{domain}'.")

    monkeypatch.setattr("wayback_recon.cli.WaybackClient.fetch_urls", _empty)
    result = runner.invoke(app, ["scan", "example.com"])
    assert result.exit_code == 1


def test_extract_links_merges_and_reports(monkeypatch, tmp_path):
    monkeypatch.setattr("wayback_recon.cli.WaybackClient.fetch_urls", _fake_fetch)

    def _harvest(originals, domain, *, timeout, retries):
        return ["http://example.com/wp-login.php", "http://example.com/"], 1

    monkeypatch.setattr("wayback_recon.cli.harvest_links", _harvest)
    out = tmp_path / "with-extract.json"

    result = runner.invoke(
        app, ["scan", "example.com", "--extract-links", "-o", str(out)]
    )

    assert result.exit_code == 0
    assert "Pages analysed" in result.stdout
    assert "Pages skipped" in result.stdout
    assert "New links extracted" in result.stdout
    assert "wp-login.php" in result.stdout  # LOGIN now in the interesting section

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["links_extracted"] == 1
    assert payload["pages_analysed"] == 3
    assert payload["pages_skipped"] == 1
    assert "http://example.com/wp-login.php" in payload["urls"]