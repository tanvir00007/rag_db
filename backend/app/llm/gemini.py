from collections.abc import Iterable
from typing import Any

from app.core.schemas import ModelConfig, SQLGeneration
from app.llm.prompt import build_sql_prompt


DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"


class ModelProviderError(RuntimeError):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def generate_gemini_sql_json(
    config: ModelConfig,
    user_message: str,
    schema_text: str,
    history: list[dict],
    repair_context: str | None = None,
    dialect: str = "MySQL",
) -> dict:
    _require_gemini_config(config)
    prompt = build_sql_prompt(user_message, schema_text, history, repair_context, dialect=dialect)
    generation = _request_structured_generation(config, prompt)
    return generation.model_dump()


def test_gemini_config(config: ModelConfig, dialect: str = "PostgreSQL") -> None:
    _require_gemini_config(config)
    prompt = f"Return SELECT 1 as safe read-only {dialect} SQL with a short report title."
    _request_structured_generation(config, prompt)


def list_gemini_models(api_key: str) -> list[str]:
    if not api_key.strip():
        raise ModelProviderError("Enter or save a Gemini API key first.", status_code=400)
    try:
        client = _create_client(api_key)
        models = client.models.list()
        names = sorted({_model_name(model) for model in models if _is_text_generation_model(model)})
        if DEFAULT_GEMINI_MODEL not in names:
            names.insert(0, DEFAULT_GEMINI_MODEL)
        return names
    except ModelProviderError:
        raise
    except Exception as exc:
        raise _public_gemini_error(exc) from exc


def _request_structured_generation(config: ModelConfig, prompt: str) -> SQLGeneration:
    try:
        client = _create_client(config.gemini_api_key)
        interaction = client.interactions.create(
            model=config.gemini_model,
            input=prompt,
            store=False,
            generation_config={
                "temperature": config.temperature,
                "max_output_tokens": config.max_tokens,
            },
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": SQLGeneration.model_json_schema(),
            },
        )
        return SQLGeneration.model_validate_json(interaction.output_text)
    except ModelProviderError:
        raise
    except Exception as exc:
        raise _public_gemini_error(exc) from exc


def _create_client(api_key: str):
    try:
        from google import genai
    except ModuleNotFoundError as exc:
        raise ModelProviderError(
            "google-genai is not installed. Install backend/requirements.txt before using Gemini."
        ) from exc
    return genai.Client(api_key=api_key, http_options={"timeout": 60_000})


def _require_gemini_config(config: ModelConfig) -> None:
    if not config.gemini_api_key.strip():
        raise ModelProviderError("Enter or save a Gemini API key first.", status_code=400)
    if not config.gemini_model.strip():
        raise ModelProviderError("Choose a Gemini model first.", status_code=400)


def _model_name(model: Any) -> str:
    return str(getattr(model, "name", "")).removeprefix("models/")


def _is_text_generation_model(model: Any) -> bool:
    name = _model_name(model).lower()
    actions: Iterable[str] = getattr(model, "supported_actions", None) or []
    excluded = ("embedding", "image", "live", "tts", "veo")
    return (
        name.startswith("gemini-")
        and "generateContent" in actions
        and not any(token in name for token in excluded)
    )


def _public_gemini_error(exc: Exception) -> ModelProviderError:
    code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if code in (401, 403):
        return ModelProviderError("The Gemini API key is invalid or not permitted to use this API.", 401)
    if code == 404:
        return ModelProviderError("The selected Gemini model is unavailable for this API key.", 400)
    if code == 429:
        return ModelProviderError("Gemini quota or rate limit exceeded. Try again later or review billing.", 429)
    if code in (408, 504) or isinstance(exc, TimeoutError):
        return ModelProviderError("Gemini did not respond before the request timed out.", 504)
    if code == 400:
        return ModelProviderError("Gemini rejected the request. Check the selected model and settings.", 400)
    return ModelProviderError("Gemini is unavailable right now. Check the connection and try again.", 502)
