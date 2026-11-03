from pathlib import Path

from app.core.schemas import DatabaseConfig
from app.db.database import dialect_name
from app.llm.prompt import build_sql_prompt
from database.postgres_schema import compile_postgres_schema


def test_postgres_config_and_prompt_dialect():
    config = DatabaseConfig(
        db_type="postgresql",
        host="127.0.0.1",
        port=55432,
        database="brac_microfinance_demo",
        username="ragdb",
        password="secret",
    )
    prompt = build_sql_prompt("monthly report", "Table members: member_id INTEGER", [], dialect=dialect_name(config))

    assert dialect_name(config) == "PostgreSQL"
    assert "safe read-only PostgreSQL SQL" in prompt
    assert "functions and date syntax valid for PostgreSQL" in prompt


def test_compiled_postgres_schema_removes_mysql_syntax():
    schema = compile_postgres_schema(Path(__file__).parents[1] / "database" / "schema_v1.sql")

    assert "ENGINE=InnoDB" not in schema
    assert "AUTO_INCREMENT" not in schema
    assert "UNSIGNED" not in schema
    assert "ENUM(" not in schema
    assert "TIMESTAMPTZ" in schema
    assert "CREATE INDEX ix_loan_portfolio" in schema
    assert "COMMENT ON TABLE members" in schema
