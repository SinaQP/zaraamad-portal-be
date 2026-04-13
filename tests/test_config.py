from app.common.config import DEFAULT_DATABASE_URL, Settings


def test_get_settings_uses_database_url_env(monkeypatch):
    database_url = (
        "mssql+pyodbc://portal_app:secret@localhost:1433/zaraamad_portal"
        "?driver=ODBC+Driver+18+for+SQL+Server&Encrypt=yes"
    )
    settings = Settings(
        _env_file=None,
        database_url=database_url,
    )

    assert settings.database_url == database_url


def test_get_settings_keeps_sqlserver_url_separate_from_default_database(monkeypatch):
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/zaraamad_portal",
        sqlserver_url=(
            "mssql+pyodbc://sa:password@192.168.174.5:1441/Zaramad-Online"
            "?driver=ODBC+Driver+18+for+SQL+Server"
            "&Encrypt=yes"
            "&TrustServerCertificate=yes"
            "&Connection+Timeout=30"
        ),
    )

    assert settings.database_url == (
        "postgresql+psycopg://postgres:postgres@localhost:5432/zaraamad_portal"
    )
    assert settings.sqlserver_url == (
        "mssql+pyodbc://sa:password@192.168.174.5:1441/Zaramad-Online"
        "?driver=ODBC+Driver+18+for+SQL+Server"
        "&Encrypt=yes"
        "&TrustServerCertificate=yes"
        "&Connection+Timeout=30"
    )


def test_get_settings_keeps_default_database_url(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SQLSERVER_URL", raising=False)
    monkeypatch.delenv("CENTRAL_DATABASE_URL", raising=False)

    settings = Settings(_env_file=None)

    assert settings.database_url == DEFAULT_DATABASE_URL
