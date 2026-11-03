from __future__ import annotations

import re
from pathlib import Path


def compile_postgres_schema(mysql_schema_path: Path) -> str:
    """Compile the versioned MariaDB DDL into equivalent PostgreSQL DDL."""
    source = mysql_schema_path.read_text(encoding="utf-8")
    output: list[str] = ["SET TIME ZONE 'UTC';"]
    indexes: list[str] = []
    comments: list[str] = []
    current_table = ""

    for raw_line in source.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("SET NAMES") or stripped.startswith("SET time_zone"):
            continue
        table_match = re.match(r"CREATE TABLE\s+(\w+)", stripped, re.IGNORECASE)
        if table_match:
            current_table = table_match.group(1)

        index_match = re.match(r"INDEX\s+(\w+)\s*\((.+)\),?$", stripped, re.IGNORECASE)
        if index_match:
            indexes.append(f"CREATE INDEX {index_match.group(1)} ON {current_table} ({index_match.group(2)});")
            continue

        column_comment = re.search(r"\bCOMMENT\s+'([^']*)'", raw_line, re.IGNORECASE)
        if column_comment and not stripped.startswith(") ENGINE"):
            column_match = re.match(r"\s*(\w+)\s+", raw_line)
            if column_match and current_table:
                comment = column_comment.group(1).replace("'", "''")
                comments.append(f"COMMENT ON COLUMN {current_table}.{column_match.group(1)} IS '{comment}';")

        engine_match = re.match(r"\)\s+ENGINE=\w+(?:\s+COMMENT='([^']*)')?;?", stripped, re.IGNORECASE)
        if engine_match:
            if output and output[-1].rstrip().endswith(","):
                output[-1] = output[-1].rstrip()[:-1]
            output.append(");")
            if engine_match.group(1):
                comment = engine_match.group(1).replace("'", "''")
                comments.append(f"COMMENT ON TABLE {current_table} IS '{comment}';")
            continue

        line = raw_line
        line = re.sub(r"\bENUM\s*\([^)]*\)", "VARCHAR(40)", line, flags=re.IGNORECASE)
        line = re.sub(r"\bTINYINT\s+UNSIGNED\b", "SMALLINT", line, flags=re.IGNORECASE)
        line = re.sub(r"\bSMALLINT\s+UNSIGNED\b", "INTEGER", line, flags=re.IGNORECASE)
        line = re.sub(r"\bBIGINT\s+UNSIGNED\b", "BIGINT", line, flags=re.IGNORECASE)
        line = re.sub(r"\bINT\s+UNSIGNED\b", "INTEGER", line, flags=re.IGNORECASE)
        line = re.sub(r"\bDATETIME\s*\(6\)", "TIMESTAMPTZ", line, flags=re.IGNORECASE)
        line = re.sub(r"\bAUTO_INCREMENT\b", "", line, flags=re.IGNORECASE)
        line = re.sub(r"\s+COMMENT\s+'[^']*'", "", line, flags=re.IGNORECASE)
        line = re.sub(r"UNIQUE\s+KEY\s+(\w+)\s*", r"CONSTRAINT \1 UNIQUE ", line, flags=re.IGNORECASE)
        output.append(line.rstrip())

    return "\n".join(output + indexes + comments) + "\n"
