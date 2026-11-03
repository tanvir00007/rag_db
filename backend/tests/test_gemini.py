import json
from types import SimpleNamespace

import pytest

from app.core.schemas import ModelConfig
from app.llm import gemini


class FakeInteractions:
    def __init__(self):
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(
            output_text=json.dumps(
                {"sql": "SELECT COUNT(*) FROM clients", "answer_language": "english", "report_title": "clients"}
            )
        )


class FakeClient:
    def __init__(self, models=None):
        self.interactions = FakeInteractions()
        self.models = SimpleNamespace(list=lambda: models or [])


def test_structured_generation_enforces_cloud_payload_boundary(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(gemini, "_create_client", lambda _key: client)
    config = ModelConfig(provider="gemini", gemini_api_key="api-secret")
    history = [
        {
            "user": "count clients",
            "assistant": "done",
            "sql": "SELECT COUNT(*) FROM clients",
            "password": "db-password",
            "rows": [{"email": "private@example.com"}],
        }
    ]

    result = gemini.generate_gemini_sql_json(
        config,
        "count clients",
        "Table clients: client_id INT PK",
        history,
    )

    assert result["sql"] == "SELECT COUNT(*) FROM clients"
    request = client.interactions.requests[0]
    prompt = request["input"]
    assert request["store"] is False
    assert request["generation_config"] == {"temperature": 0.2, "max_output_tokens": 768}
    assert request["response_format"]["mime_type"] == "application/json"
    assert "db-password" not in prompt
    assert "private@example.com" not in prompt
    assert "api-secret" not in prompt
    assert "Table clients" in prompt
    assert "SELECT COUNT(*) FROM clients" in prompt


def test_lists_only_text_generation_models(monkeypatch):
    models = [
        SimpleNamespace(name="models/gemini-3.6-flash", supported_actions=["generateContent"]),
        SimpleNamespace(name="models/gemini-embedding", supported_actions=["embedContent"]),
        SimpleNamespace(name="models/gemini-3.1-flash-image", supported_actions=["generateContent"]),
    ]
    monkeypatch.setattr(gemini, "_create_client", lambda _key: FakeClient(models))

    assert gemini.list_gemini_models("key") == ["gemini-3.6-flash"]


@pytest.mark.parametrize(
    ("code", "expected_status"),
    [(403, 401), (404, 400), (429, 429), (504, 504), (500, 502)],
)
def test_maps_provider_errors_without_leaking_details(code, expected_status):
    error = RuntimeError("secret provider response")
    error.code = code

    public = gemini._public_gemini_error(error)

    assert public.status_code == expected_status
    assert "secret provider response" not in str(public)
