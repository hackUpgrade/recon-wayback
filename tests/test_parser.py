from wayback_recon.parser import normalize_urls


def test_removes_duplicates():
    assert normalize_urls(["https://a.com/x", "https://a.com/x"]) == ["https://a.com/x"]


def test_trims_whitespace():
    assert normalize_urls(["  https://a.com/x  "]) == ["https://a.com/x"]


def test_adds_scheme_when_missing():
    urls = normalize_urls(["example.com/a", "example.com/b"])
    assert urls == [
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_lowercases_hostname():
    assert normalize_urls(["HTTPS://Example.COM/Path"]) == ["https://example.com/Path"]


def test_removes_default_ports():
    urls = normalize_urls(["https://example.com:443/x", "http://example.com:80/y"])
    assert urls == ["http://example.com/y", "https://example.com/x"]


def test_keeps_non_default_port():
    assert normalize_urls(["http://example.com:8080/x"]) == ["http://example.com:8080/x"]


def test_empty_path_becomes_root():
    assert normalize_urls(["https://example.com"]) == ["https://example.com/"]


def test_drops_fragment_keeps_query():
    assert normalize_urls(["https://example.com/a?b=1#top"]) == ["https://example.com/a?b=1"]


def test_skips_blank_entries():
    assert normalize_urls(["", "   ", "https://x.com/y"]) == ["https://x.com/y"]


def test_skips_unparseable_entries():
    assert normalize_urls(["not a url at all!!"]) == []


def test_sorts_output():
    assert normalize_urls(["https://b.com", "https://a.com", "https://a.com"]) == [
        "https://a.com/",
        "https://b.com/",
    ]