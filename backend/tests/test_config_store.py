import json

from app.core import config_store
from app.core.schemas import DatabaseConfig, ModelConfig
from app.core.settings import settings


def _use_temp_config_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "configs_dir", tmp_path / "configs")


def test_loads_legacy_llama_config(monkeypatch, tmp_path):
    _use_temp_config_dir(monkeypatch, tmp_path)
    path = config_store._model_config_path()
    path.write_text(
        json.dumps(
            {
                "provider": "llama_cpp",
                "model_path": "C:/models/local.gguf",
                "context_window": 8192,
                "temperature": 0.1,
                "max_tokens": 512,
            }
        ),
        encoding="utf-8",
    )

    loaded = config_store.load_model_config()

    assert loaded is not None
    assert loaded.provider == "llama_cpp"
    assert loaded.model_path == "C:/models/local.gguf"
    assert loaded.gemini_model == "gemini-3.6-flash"
    assert loaded.gemini_api_key == ""


def test_encrypts_and_redacts_gemini_key(monkeypatch, tmp_path):
    _use_temp_config_dir(monkeypatch, tmp_path)
    secret = "gemini-secret-key"

    config_store.save_model_config(
        ModelConfig(provider="gemini", gemini_api_key=secret, gemini_model="gemini-3.6-flash")
    )

    raw = config_store._model_config_path().read_text(encoding="utf-8")
    public = config_store.public_model_config()
    assert secret not in raw
    assert "gemini_api_key_encrypted" in raw
    assert public.gemini_api_key == ""
    assert public.api_key_configured is True
    assert config_store.load_model_config().gemini_api_key == secret


def test_blank_key_preserves_saved_key(monkeypatch, tmp_path):
    _use_temp_config_dir(monkeypatch, tmp_path)
    config_store.save_model_config(ModelConfig(provider="gemini", gemini_api_key="first-secret"))

    config_store.save_model_config(
        ModelConfig(provider="gemini", gemini_api_key="", gemini_model="gemini-3.5-flash-lite")
    )

    loaded = config_store.load_model_config()
    assert loaded is not None
    assert loaded.gemini_api_key == "first-secret"
    assert loaded.gemini_model == "gemini-3.5-flash-lite"


def test_postgres_config_encrypts_password_and_preserves_blank_update(monkeypatch, tmp_path):
    _use_temp_config_dir(monkeypatch, tmp_path)
    original = DatabaseConfig(
        db_type="postgresql",
        host="127.0.0.1",
        port=55432,
        database="brac_microfinance_demo",
        username="ragdb",
        password="postgres-secret",
    )
    config_store.save_database_config(original)
    config_store.save_database_config(original.model_copy(update={"password": "", "name": "docker-postgresql"}))

    raw = config_store._db_config_path().read_text(encoding="utf-8")
    loaded = config_store.load_database_config()
    public = config_store.public_db_config()

    assert "postgres-secret" not in raw
    assert loaded is not None and loaded.db_type == "postgresql"
    assert loaded.password == "postgres-secret"
    assert public is not None and public["password"] == ""
