import re


FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|drop|alter|truncate|create|replace|grant|revoke|merge|call|exec|execute|load|outfile)\b",
    re.IGNORECASE,
)


def validate_read_only_sql(sql: str) -> str:
    cleaned = sql.strip().rstrip(";")
    if not cleaned:
        raise ValueError("No SQL was generated.")
    if ";" in cleaned:
        raise ValueError("Only one SQL statement is allowed.")
    if FORBIDDEN_SQL.search(cleaned):
        raise ValueError("Only read-only SELECT/WITH queries are allowed.")
    if not re.match(r"^\s*(select|with)\b", cleaned, re.IGNORECASE):
        raise ValueError("Query must start with SELECT or WITH.")
    return cleaned


def add_limit_if_missing(sql: str, limit: int) -> str:
    if re.search(r"\blimit\s+\d+\b", sql, re.IGNORECASE):
        return sql
    return f"{sql} LIMIT {limit}"

