import json
from functools import lru_cache

from app.core.schemas import ModelConfig
from app.llm.prompt import build_sql_prompt


@lru_cache(maxsize=2)
def _load_llama(model_path: str, context_window: int):
    try:
        from llama_cpp import Llama
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "llama-cpp-python is not installed. Install backend/requirements-llm.txt or a Windows wheel for your GGUF runtime."
        ) from exc

    return Llama(model_path=model_path, n_ctx=context_window, verbose=False)


def _extract_json(text: str) -> dict:
    start = text.find("{")
    if start == -1:
        raise ValueError("The model did not return JSON.")
    decoder = json.JSONDecoder()
    try:
        parsed, _ = decoder.raw_decode(text[start:])
    except json.JSONDecodeError as exc:
        preview = text.strip().replace("\n", " ")[:240]
        raise ValueError(f"The model returned malformed JSON: {preview}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("The model JSON response must be an object.")
    return parsed


def generate_local_sql_json(
    config: ModelConfig,
    user_message: str,
    schema_text: str,
    history: list[dict],
    repair_context: str | None = None,
    dialect: str = "MySQL",
) -> dict:
    if not config.model_path:
        raise RuntimeError("No local GGUF model path is configured yet.")

    llm = _load_llama(config.model_path, config.context_window)
    prompt = build_sql_prompt(user_message, schema_text, history, repair_context, dialect=dialect)
    output = llm(
        prompt,
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        stop=["\n\nUser:", "</s>"],
    )
    text = output["choices"][0]["text"]
    return _extract_json(text)
