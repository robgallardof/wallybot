from wallybot.infrastructure.ai_worker_settings import load_ai_worker_settings


def test_native_settings_use_the_dedicated_runtime_file_and_loopback_port(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("WALLY_DATABASE_URL", raising=False)
    path = tmp_path / "analyst-url"
    path.write_text("postgresql+psycopg://wally_ai:synthetic@postgres:5432/wallybot")
    monkeypatch.setenv("WALLY_AI_DATABASE_URL_FILE", str(path))
    settings = load_ai_worker_settings()
    assert (
        settings.database_url.get_secret_value()
        == "postgresql+psycopg://wally_ai:synthetic@127.0.0.1:5433/wallybot"
    )
    assert "synthetic" not in repr(settings)


def test_explicit_native_database_setting_takes_priority(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(
        "WALLY_DATABASE_URL", "postgresql+psycopg://wally_ai:synthetic@localhost:5555/test"
    )
    settings = load_ai_worker_settings()
    assert "localhost:5555" in settings.database_url.get_secret_value()
