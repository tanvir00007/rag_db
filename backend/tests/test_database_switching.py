from fastapi.testclient import TestClient

from app.api import routes
from app.core.schemas import DatabaseConfig
from app.core.settings import settings
from app.main import app
from app.memory.store import append_turn, load_history


def config(database: str = "sales") -> DatabaseConfig:
    return DatabaseConfig(
        host="127.0.0.1",
        database=database,
        username="demo",
        password="secret",
    )


def test_database_list_filters_and_reports_active(monkeypatch):
    monkeypatch.setattr(routes, "load_database_config", lambda: config())
    monkeypatch.setattr(routes, "list_databases", lambda _config: ["brac_microfinance_demo", "sales"])
    client = TestClient(app)

    response = client.get("/api/db/databases")

    assert response.status_code == 200
    assert response.json() == {
        "databases": ["brac_microfinance_demo", "sales"],
        "active_database": "sales",
    }
    client.close()


def test_activation_tests_before_saving_and_preserves_credentials(monkeypatch):
    saved = []
    tested = []
    monkeypatch.setattr(routes, "load_database_config", lambda: config())
    monkeypatch.setattr(routes, "list_databases", lambda _config: ["brac_microfinance_demo", "sales"])
    monkeypatch.setattr(routes, "test_connection", lambda candidate: tested.append(candidate))
    monkeypatch.setattr(routes, "save_database_config", lambda candidate: saved.append(candidate))
    client = TestClient(app)

    response = client.post("/api/db/activate", json={"database": "brac_microfinance_demo"})

    assert response.status_code == 200
    assert tested[0].database == "brac_microfinance_demo"
    assert saved[0].database == "brac_microfinance_demo"
    assert saved[0].password == "secret"
    client.close()


def test_failed_activation_does_not_save(monkeypatch):
    saved = []
    monkeypatch.setattr(routes, "load_database_config", lambda: config())
    monkeypatch.setattr(routes, "list_databases", lambda _config: ["brac_microfinance_demo", "sales"])
    monkeypatch.setattr(routes, "test_connection", lambda _candidate: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr(routes, "save_database_config", lambda candidate: saved.append(candidate))
    client = TestClient(app)

    response = client.post("/api/db/activate", json={"database": "brac_microfinance_demo"})

    assert response.status_code == 400
    assert saved == []
    client.close()


def test_memory_is_namespaced_by_database(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "memory_dir", tmp_path / "memory")
    append_turn("same-id", "sales question", "sales answer", "SELECT 1", namespace="sales")
    append_turn("same-id", "loan question", "loan answer", "SELECT 2", namespace="brac_microfinance_demo")

    assert load_history("same-id", namespace="sales")[0]["user"] == "sales question"
    assert load_history("same-id", namespace="brac_microfinance_demo")[0]["user"] == "loan question"
