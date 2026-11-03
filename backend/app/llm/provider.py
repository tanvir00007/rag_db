from app.core.config_store import load_model_config, resolve_model_config
from app.core.schemas import ModelConfig
from app.llm.gemini import generate_gemini_sql_json, test_gemini_config
from app.llm.local_gguf import generate_local_sql_json


def generate_sql_json(
    user_message: str,
    schema_text: str,
    history: list[dict],
    repair_context: str | None = None,
    dialect: str = "MySQL",
) -> dict:
    config = load_model_config()
    assert config is not None
    if config.provider == "gemini":
        return generate_gemini_sql_json(config, user_message, schema_text, history, repair_context, dialect=dialect)
    return generate_local_sql_json(config, user_message, schema_text, history, repair_context, dialect=dialect)


def test_model_config(config: ModelConfig) -> None:
    config = resolve_model_config(config)
    if config.provider == "gemini":
        test_gemini_config(config)
        return
    if not config.model_path.strip():
        raise ValueError("Choose a local GGUF model path first.")
