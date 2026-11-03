from collections.abc import Iterable
from typing import Any
from urllib.parse import quote_plus

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from app.core.schemas import ColumnInfo, DatabaseConfig, SchemaSnapshot, TableInfo


SYSTEM_DATABASES = {
    "information_schema",
    "mysql",
    "performance_schema",
    "sys",
    "postgres",
    "template0",
    "template1",
}


def create_database_engine(config: DatabaseConfig, database: str | None = None) -> Engine:
    password = quote_plus(config.password)
    username = quote_plus(config.username)
    selected_database = quote_plus(database or config.database)
    if config.db_type == "postgresql":
        ssl_args = "?sslmode=require" if config.ssl else ""
        url = f"postgresql+psycopg://{username}:{password}@{config.host}:{config.port}/{selected_database}{ssl_args}"
    else:
        ssl_args = "?ssl=true" if config.ssl else ""
        url = f"mysql+pymysql://{username}:{password}@{config.host}:{config.port}/{selected_database}{ssl_args}"
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800)


def test_connection(config: DatabaseConfig) -> bool:
    engine = create_database_engine(config)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    finally:
        engine.dispose()


def list_databases(config: DatabaseConfig) -> list[str]:
    engine = create_database_engine(config)
    try:
        with engine.connect() as conn:
            if config.db_type == "postgresql":
                result = conn.execute(text("SELECT datname FROM pg_database WHERE datallowconn AND NOT datistemplate"))
            else:
                result = conn.execute(text("SHOW DATABASES"))
            names = [str(row[0]) for row in result]
        return sorted(name for name in names if name.lower() not in SYSTEM_DATABASES)
    finally:
        engine.dispose()


def introspect_schema(engine: Engine, database: str, db_type: str) -> SchemaSnapshot:
    inspector = inspect(engine)
    schema_name = "public" if db_type == "postgresql" else None
    objects = [(name, "table") for name in inspector.get_table_names(schema=schema_name)]
    objects.extend((name, "view") for name in inspector.get_view_names(schema=schema_name))
    tables: list[TableInfo] = []
    for table_name, object_type in objects:
        pk_cols = set(
            (inspector.get_pk_constraint(table_name, schema=schema_name).get("constrained_columns") or [])
            if object_type == "table"
            else []
        )
        fk_map: dict[str, str] = {}
        if object_type == "table":
            for fk in inspector.get_foreign_keys(table_name, schema=schema_name):
                referred_table = fk.get("referred_table")
                referred_cols = fk.get("referred_columns") or []
                for col, ref_col in zip(fk.get("constrained_columns") or [], referred_cols, strict=False):
                    fk_map[col] = f"{referred_table}.{ref_col}"
        columns = [
            ColumnInfo(
                name=col["name"],
                type=str(col["type"]),
                nullable=bool(col.get("nullable", True)),
                primary_key=col["name"] in pk_cols,
                foreign_key=fk_map.get(col["name"]),
                comment=col.get("comment"),
            )
            for col in inspector.get_columns(table_name, schema=schema_name)
        ]
        table_comment = None
        if object_type == "table":
            try:
                table_comment = inspector.get_table_comment(table_name, schema=schema_name).get("text")
            except NotImplementedError:
                pass
        tables.append(TableInfo(name=table_name, columns=columns, object_type=object_type, comment=table_comment))
    return SchemaSnapshot(database=database, tables=tables)


def execute_query(engine: Engine, sql: str, limit: int = 100) -> tuple[list[str], list[dict[str, Any]]]:
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        columns = list(result.keys())
        rows = [dict(row._mapping) for row in result.fetchmany(limit)]
    return columns, rows


def schema_to_text(schema: SchemaSnapshot, dialect: str, max_tables: int = 80) -> str:
    lines: list[str] = [f"Database: {schema.database}", f"SQL dialect: {dialect}"]
    for table in schema.tables[:max_tables]:
        column_bits: Iterable[str] = (
            f"{col.name} {col.type}"
            + (" PK" if col.primary_key else "")
            + (f" FK->{col.foreign_key}" if col.foreign_key else "")
            + (f" [{col.comment}]" if col.comment else "")
            for col in table.columns
        )
        label = "View" if table.object_type == "view" else "Table"
        description = f" -- {table.comment}" if table.comment else ""
        lines.append(f"{label} {table.name}{description}: " + ", ".join(column_bits))
    return "\n".join(lines)


def dialect_name(config: DatabaseConfig) -> str:
    return "PostgreSQL" if config.db_type == "postgresql" else "MySQL"
