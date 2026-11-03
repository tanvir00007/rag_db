import re


DRILL_DOWN_TOKENS = (
    "transaction",
    "transactions",
    "detail",
    "details",
    "individual",
    "invoice",
    "invoices",
    "line item",
    "records",
)

SCOPE_RESET_TOKENS = (
    "all client",
    "all customer",
    "all transaction",
    "all data",
    "every client",
    "every customer",
    "shob client",
    "sob client",
)


def needs_previous_scope(message: str, history: list[dict]) -> bool:
    lowered = message.lower()
    return (
        bool(scope_anchor_sql(history))
        and any(token in lowered for token in DRILL_DOWN_TOKENS)
        and not any(token in lowered for token in SCOPE_RESET_TOKENS)
    )


def follow_up_guidance(message: str, history: list[dict]) -> str:
    if not needs_previous_scope(message, history):
        return ""
    anchor_sql = scope_anchor_sql(history)
    return f"""Important follow-up interpretation:
This request is a drill-down of the latest meaningful scoped result, not a new all-data report.
Preserve the previous date/time filters, entity filters, and ranked/top-N cohort unless the user explicitly changes them.
When changing an aggregate result into transaction/detail rows, reproduce the previous cohort as a CTE or derived subquery and join the detail rows to it.
Do not return transactions for entities outside the previous result scope.
If a later unscoped detail query conflicts with this scope, ignore that query and use this scope anchor SQL:
{anchor_sql}"""


def follow_up_scope_issues(message: str, history: list[dict], candidate_sql: str) -> list[str]:
    if not needs_previous_scope(message, history):
        return []
    previous_sql = scope_anchor_sql(history)
    if not previous_sql:
        return []

    issues: list[str] = []
    previous_years = re.findall(r"\bYEAR\s*\([^)]*\)\s*=\s*(\d{4})", previous_sql, re.IGNORECASE)
    previous_years.extend(
        re.findall(r"\bEXTRACT\s*\(\s*YEAR\s+FROM[^)]*\)\s*=\s*(\d{4})", previous_sql, re.IGNORECASE)
    )
    previous_months = re.findall(r"\bMONTH\s*\([^)]*\)\s*=\s*(\d{1,2})", previous_sql, re.IGNORECASE)
    previous_dates = re.findall(r"'((?:19|20)\d{2}-\d{2}-\d{2})'", previous_sql)

    for year in previous_years:
        if year not in candidate_sql:
            issues.append(f"preserve the previous year filter ({year})")
    for month in previous_months:
        if not _contains_month_scope(candidate_sql, int(month), previous_years):
            issues.append(f"preserve the previous month filter ({int(month)})")
    for date in previous_dates:
        if date not in candidate_sql:
            issues.append(f"preserve the previous date boundary ({date})")

    previous_limit = _ranked_cohort_limit(previous_sql)
    if previous_limit is not None and not _contains_ranked_cohort(candidate_sql, previous_limit):
        issues.append(
            f"restrict detail rows to the previous ranked top-{previous_limit} cohort using an aggregate CTE or derived subquery"
        )
    return issues


def follow_up_repair_context(message: str, history: list[dict], issues: list[str]) -> str:
    previous_sql = scope_anchor_sql(history)
    requirements = "; ".join(issues)
    return (
        "The candidate SQL lost required follow-up context. Regenerate it as a scoped drill-down. "
        f"Requirements: {requirements}. Previous SQL: {previous_sql}. "
        "Use a CTE or derived subquery when necessary; return one safe read-only query in the active SQL dialect."
    )


def scope_anchor_sql(history: list[dict]) -> str:
    """Find the latest query that defines a reusable filter or ranked cohort."""
    for turn in reversed(history):
        sql = str(turn.get("sql") or "")
        if not sql:
            continue
        if _ranked_cohort_limit(sql) is not None or re.search(r"\bWHERE\b", sql, re.IGNORECASE):
            return sql
    return ""


def _ranked_cohort_limit(sql: str) -> int | None:
    has_aggregate = bool(re.search(r"\b(SUM|COUNT|AVG|MIN|MAX)\s*\(", sql, re.IGNORECASE))
    has_grouping = bool(re.search(r"\bGROUP\s+BY\b", sql, re.IGNORECASE))
    has_ranking = bool(re.search(r"\bORDER\s+BY\b", sql, re.IGNORECASE))
    limits = re.findall(r"\bLIMIT\s+(\d+)\b", sql, re.IGNORECASE)
    if has_aggregate and has_grouping and has_ranking and limits:
        return int(limits[-1])
    return None


def _contains_ranked_cohort(sql: str, limit: int) -> bool:
    return (
        bool(re.search(r"\b(SUM|COUNT|AVG|MIN|MAX)\s*\(", sql, re.IGNORECASE))
        and bool(re.search(r"\bGROUP\s+BY\b", sql, re.IGNORECASE))
        and bool(re.search(rf"\bLIMIT\s+{limit}\b", sql, re.IGNORECASE))
        and (bool(re.search(r"\bWITH\b", sql, re.IGNORECASE)) or sql.upper().count("SELECT") >= 2)
    )


def _contains_month_scope(sql: str, month: int, years: list[str]) -> bool:
    function_filter = bool(
        re.search(rf"\bMONTH\s*\([^)]*\)\s*=\s*0?{month}\b", sql, re.IGNORECASE)
        or re.search(rf"\bEXTRACT\s*\(\s*MONTH\s+FROM[^)]*\)\s*=\s*0?{month}\b", sql, re.IGNORECASE)
    )
    date_prefixes = [f"{year}-{month:02d}" for year in years]
    return function_filter or any(prefix in sql for prefix in date_prefixes)
