from collections.abc import Iterable
from typing import Any
from urllib.parse import quote_plus

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

from app.core.schemas import ColumnInfo, MySQLConfig, SchemaSnapshot, TableInfo


SYSTEM_DATABASES = {"information_schema", "mysql", "performance_schema", "sys"}


def create_mysql_engine(config: MySQLConfig) -> Engine:
    password = quote_plus(config.password)
    username = quote_plus(config.username)
    ssl_args = "?ssl=true" if config.ssl else ""
    url = f"mysql+pymysql://{username}:{password}@{config.host}:{config.port}/{config.database}{ssl_args}"
    return create_engine(url, pool_pre_ping=True, pool_recycle=1800)


def test_connection(config: MySQLConfig) -> bool:
    engine = create_mysql_engine(config)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    engine.dispose()
    return True


def list_databases(config: MySQLConfig) -> list[str]:
    """Return databases visible to the saved user, excluding MariaDB system schemas."""
    engine = create_mysql_engine(config)
    try:
        with engine.connect() as conn:
            names = [str(row[0]) for row in conn.execute(text("SHOW DATABASES"))]
        return sorted(name for name in names if name.lower() not in SYSTEM_DATABASES)
    finally:
        engine.dispose()


def introspect_schema(engine: Engine, database: str) -> SchemaSnapshot:
    inspector = inspect(engine)
    tables: list[TableInfo] = []
    objects = [(name, "table") for name in inspector.get_table_names()]
    objects.extend((name, "view") for name in inspector.get_view_names())
    for table_name, object_type in objects:
        pk_cols = set(inspector.get_pk_constraint(table_name).get("constrained_columns") or [])
        fk_map: dict[str, str] = {}
        for fk in inspector.get_foreign_keys(table_name):
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
            for col in inspector.get_columns(table_name)
        ]
        table_comment = None
        if object_type == "table":
            try:
                table_comment = inspector.get_table_comment(table_name).get("text")
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


def schema_to_text(schema: SchemaSnapshot, max_tables: int = 60) -> str:
    lines: list[str] = [f"Database: {schema.database}"]
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
