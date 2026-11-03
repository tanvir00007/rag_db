import json
from pathlib import Path

from app.core.schemas import DatabaseConfig, ModelConfig, MySQLConfig, PublicModelConfig, SavedDBConfig, SavedModelConfig
from app.core.settings import settings
from app.security.crypto import decrypt_text, encrypt_text


def _db_config_path() -> Path:
    settings.configs_dir.mkdir(parents=True, exist_ok=True)
    return settings.configs_dir / "database.json"


def _model_config_path() -> Path:
    settings.configs_dir.mkdir(parents=True, exist_ok=True)
    return settings.configs_dir / "model.json"


def save_database_config(config: DatabaseConfig) -> SavedDBConfig:
    existing = load_database_config()
    password = config.password or (existing.password if existing else "")
    saved = SavedDBConfig(
        db_type=config.db_type,
        name=config.name,
        host=config.host,
        port=config.port,
        database=config.database,
        username=config.username,
        password_encrypted=encrypt_text(password),
        ssl=config.ssl,
    )
    _db_config_path().write_text(saved.model_dump_json(indent=2), encoding="utf-8")
    return saved


def load_database_config() -> DatabaseConfig | None:
    path = _db_config_path()
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    saved = SavedDBConfig(**raw)
    return DatabaseConfig(
        db_type=saved.db_type,
        name=saved.name,
        host=saved.host,
        port=saved.port,
        database=saved.database,
        username=saved.username,
        password=decrypt_text(saved.password_encrypted),
        ssl=saved.ssl,
    )


def public_db_config() -> dict | None:
    config = load_database_config()
    if not config:
        return None
    data = config.model_dump()
    data["password"] = ""
    return data


def save_mysql_config(config: MySQLConfig) -> SavedDBConfig:
    """Compatibility wrapper for older callers and setup tooling."""
    return save_database_config(config)


def load_mysql_config() -> MySQLConfig | None:
    """Load only a MySQL configuration for legacy MySQL setup tooling."""
    config = load_database_config()
    if not config or config.db_type != "mysql":
        return None
    return MySQLConfig(**config.model_dump())


def save_model_config(config: ModelConfig) -> ModelConfig:
    existing = load_model_config(create_default=False)
    api_key = config.gemini_api_key or (existing.gemini_api_key if existing else "")
    saved = SavedModelConfig(
        provider=config.provider,
        model_path=config.model_path,
        context_window=config.context_window,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        gemini_model=config.gemini_model,
        gemini_api_key_encrypted=encrypt_text(api_key) if api_key else "",
    )
    _model_config_path().write_text(saved.model_dump_json(indent=2), encoding="utf-8")
    return ModelConfig(**config.model_dump(exclude={"gemini_api_key"}), gemini_api_key=api_key)


def load_model_config(create_default: bool = True) -> ModelConfig | None:
    path = _model_config_path()
    if not path.exists():
        if not create_default:
            return None
        config = ModelConfig()
        save_model_config(config)
        return config
    raw = json.loads(path.read_text(encoding="utf-8"))
    # Older versions stored the public llama.cpp fields directly. SavedModelConfig
    # supplies the new Gemini defaults, so those files continue to load unchanged.
    saved = SavedModelConfig(**raw)
    api_key = decrypt_text(saved.gemini_api_key_encrypted) if saved.gemini_api_key_encrypted else ""
    return ModelConfig(
        provider=saved.provider,
        model_path=saved.model_path,
        context_window=saved.context_window,
        temperature=saved.temperature,
        max_tokens=saved.max_tokens,
        gemini_model=saved.gemini_model,
        gemini_api_key=api_key,
    )


def public_model_config() -> PublicModelConfig:
    config = load_model_config()
    assert config is not None
    return PublicModelConfig(
        provider=config.provider,
        model_path=config.model_path,
        context_window=config.context_window,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        gemini_model=config.gemini_model,
        api_key_configured=bool(config.gemini_api_key),
    )


def resolve_model_config(config: ModelConfig) -> ModelConfig:
    if config.gemini_api_key:
        return config
    saved = load_model_config(create_default=False)
    if saved and saved.gemini_api_key:
        return config.model_copy(update={"gemini_api_key": saved.gemini_api_key})
    return config
