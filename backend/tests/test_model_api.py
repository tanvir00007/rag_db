from fastapi.testclient import TestClient

from app.api import routes
from app.core.settings import settings
from app.main import app
from tests.test_follow_up import CORRECT_DRILL_DOWN_SQL, PREVIOUS_SQL


def test_model_configuration_endpoints(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "configs_dir", tmp_path / "configs")
    monkeypatch.setattr(routes, "test_model_config", lambda _config: None)
    monkeypatch.setattr(routes, "list_gemini_models", lambda key: ["gemini-3.6-flash"] if key else [])
    client = TestClient(app)

    save_response = client.post(
        "/api/model/save",
        json={
            "provider": "gemini",
            "gemini_api_key": "api-secret",
            "gemini_model": "gemini-3.6-flash",
            "model_path": "",
            "context_window": 4096,
            "temperature": 0.2,
            "max_tokens": 768,
        },
    )
    assert save_response.status_code == 200
    assert save_response.json()["provider"] == "gemini"

    active = client.get("/api/model/active").json()["config"]
    assert active["provider"] == "gemini"
    assert active["api_key_configured"] is True
    assert active["gemini_api_key"] == ""
    assert "api-secret" not in str(active)

    test_response = client.post(
        "/api/model/test",
        json={"provider": "gemini", "gemini_api_key": "", "gemini_model": "gemini-3.6-flash"},
    )
    assert test_response.status_code == 200

    models_response = client.post("/api/model/google/models", json={"gemini_api_key": ""})
    assert models_response.status_code == 200
    assert models_response.json() == {"models": ["gemini-3.6-flash"]}
    client.close()


def test_safe_database_error_excludes_driver_message():
    original = RuntimeError(1054, "Unknown column private_customer_name")
    wrapper = RuntimeError("query failed")
    wrapper.orig = original

    result = routes._safe_database_error(wrapper)

    assert result == "The database rejected it with database error code 1054."
    assert "private_customer_name" not in result


def test_semantic_scope_loss_triggers_regeneration(monkeypatch):
    calls = []
    generated = iter(
        [
            {
                "sql": "SELECT clients.client_name, sales.sale_id FROM sales JOIN clients ON sales.client_id = clients.client_id",
                "report_title": "all_transactions",
            },
            {"sql": CORRECT_DRILL_DOWN_SQL, "report_title": "top_client_transactions"},
        ]
    )

    def fake_generate(message, schema_text, history, repair_context=None, dialect="MySQL"):
        calls.append(repair_context)
        return next(generated)

    monkeypatch.setattr(routes, "generate_sql_json", fake_generate)
    history = [{"user": "top clients", "assistant": "done", "sql": PREVIOUS_SQL}]

    model_json, sql = routes._generate_scoped_sql(
        "client wise transactions gula dekhaw",
        "schema",
        history,
        100,
    )

    assert model_json["report_title"] == "top_client_transactions"
    assert "WITH top_clients" in sql
    assert calls[0] is None
    assert "lost required follow-up context" in calls[1]
