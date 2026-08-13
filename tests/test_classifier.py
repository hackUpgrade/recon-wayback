from wayback_recon.classifier import classify_url, classify_urls


def test_admin():
    assert classify_url("https://example.com/admin/") == "ADMIN"
    assert classify_url("https://example.com/wp-admin/setup") == "ADMIN"


def test_login():
    assert classify_url("https://example.com/login.php") == "LOGIN"
    assert classify_url("https://example.com/sign-in") == "LOGIN"


def test_api():
    assert classify_url("https://example.com/api/v1/users") == "API"
    assert classify_url("https://example.com/swagger/index.html") == "API"
    assert classify_url("https://example.com/rest/v2/items") == "API"


def test_api_does_not_match_restos():
    assert classify_url("https://example.com/2009/12/restos-de-navio.html") is None


def test_login():
    assert classify_url("https://example.com/login.php") == "LOGIN"
    assert classify_url("https://example.com/sign-in") == "LOGIN"
    assert classify_url("https://example.com/auth/login") == "LOGIN"


def test_login_does_not_match_author():
    assert classify_url("https://example.com/author/realidadeoculta/") is None


def test_staging():
    assert classify_url("https://staging.example.com/") == "STAGING"
    assert classify_url("https://example.com/uat") == "STAGING"


def test_staging_does_not_match_quatro():
    assert classify_url("https://example.com/odds/quatro_9402.html") is None
    assert classify_url("https://example.com/numero-quatro.html") is None
    assert classify_url("https://example.com/projeto-quatro/") is None


def test_env_file():
    assert classify_url("https://example.com/.env") == "ENV"
    assert classify_url("https://example.com/.env.production") == "ENV"


def test_sql_file():
    assert classify_url("https://example.com/backup/dump.sql") == "SQL"


def test_bak_file():
    assert classify_url("https://example.com/data.bak") == "BAK"


def test_archive_files():
    assert classify_url("https://example.com/site.zip") == "ARCHIVE"
    assert classify_url("https://example.com/archive.tar.gz") == "ARCHIVE"
    assert classify_url("https://example.com/export.tgz") == "ARCHIVE"


def test_backup_file_takes_priority():
    assert classify_url("https://example.com/backup.zip") == "BACKUP"


def test_javascript():
    assert classify_url("https://example.com/js/app.js?v=2") == "JAVASCRIPT"
    assert classify_url("https://example.com/admin/app.min.js") == "JAVASCRIPT"


def test_json_is_config_not_javascript():
    assert classify_url("https://example.com/data.json") == "CONFIG"


def test_config():
    assert classify_url("https://example.com/settings.yml") == "CONFIG"
    assert classify_url("https://example.com/application.ini") == "CONFIG"


def test_plain_urls_are_not_interesting():
    assert classify_url("https://example.com/") is None
    assert classify_url("https://example.com/about/team") is None
    assert classify_url("https://example.com/blog/post-1") is None


def test_domain_starting_with_test_is_not_dev():
    assert classify_url("http://testphp.vulnweb.com/") is None
    assert classify_url("https://test.example.com/blog") is None


def test_test_path_is_dev():
    assert classify_url("https://example.com/test") == "DEV"
    assert classify_url("https://example.com/test/page") == "DEV"


def test_classify_urls_groups_and_counts():
    urls = [
        "https://example.com/",
        "https://example.com/admin/",
        "https://example.com/api/v1/users",
        "https://example.com/admin/users",
        "https://example.com/about",
    ]
    groups = classify_urls(urls)
    assert groups["ADMIN"] == [
        "https://example.com/admin/",
        "https://example.com/admin/users",
    ]
    assert groups["API"] == ["https://example.com/api/v1/users"]
    assert "ADMIN" not in ("API",)
    assert sum(len(v) for v in groups.values()) == 3


def test_classify_urls_ignores_non_interesting():
    groups = classify_urls(["https://example.com/", "https://example.com/blog"])
    assert groups == {}