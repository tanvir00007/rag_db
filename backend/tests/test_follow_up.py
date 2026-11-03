from app.llm.follow_up import follow_up_guidance, follow_up_scope_issues, scope_anchor_sql
from app.llm.prompt import build_sql_prompt


PREVIOUS_SQL = """SELECT clients.client_name, SUM(sales.total_amount) AS total_sales
FROM sales JOIN clients ON sales.client_id = clients.client_id
WHERE YEAR(sales.sale_date) = 2026 AND MONTH(sales.sale_date) = 5
GROUP BY clients.client_id, clients.client_name
ORDER BY total_sales DESC LIMIT 10"""

CORRECT_DRILL_DOWN_SQL = """WITH top_clients AS (
  SELECT sales.client_id, SUM(sales.total_amount) AS total_sales
  FROM sales
  WHERE YEAR(sales.sale_date) = 2026 AND MONTH(sales.sale_date) = 5
  GROUP BY sales.client_id
  ORDER BY total_sales DESC
  LIMIT 10
)
SELECT clients.client_name, sales.sale_id, sales.sale_date, sales.total_amount
FROM sales
JOIN top_clients ON sales.client_id = top_clients.client_id
JOIN clients ON sales.client_id = clients.client_id
WHERE YEAR(sales.sale_date) = 2026 AND MONTH(sales.sale_date) = 5
ORDER BY clients.client_name, sales.sale_date DESC LIMIT 100"""


def _history():
    return [
        {
            "user": "top 10 client er may 2026 er sales koto",
            "assistant": "done",
            "sql": PREVIOUS_SQL,
        }
    ]


def test_detects_dropped_time_and_ranked_client_scope():
    candidate = """SELECT clients.client_name, sales.sale_id, sales.sale_date, sales.total_amount
FROM sales JOIN clients ON sales.client_id = clients.client_id
ORDER BY clients.client_name, sales.sale_date DESC LIMIT 100"""

    issues = follow_up_scope_issues("client wise transactions gula dekhaw", _history(), candidate)

    assert any("year filter (2026)" in issue for issue in issues)
    assert any("month filter (5)" in issue for issue in issues)
    assert any("top-10 cohort" in issue for issue in issues)


def test_accepts_scoped_transaction_drill_down():
    assert follow_up_scope_issues(
        "client wise transactions gula dekhaw",
        _history(),
        CORRECT_DRILL_DOWN_SQL,
    ) == []


def test_explicit_all_clients_resets_previous_scope():
    assert follow_up_scope_issues(
        "show all client transactions",
        _history(),
        "SELECT * FROM sales LIMIT 100",
    ) == []


def test_prompt_marks_ambiguous_transaction_request_as_drill_down():
    guidance = follow_up_guidance("client wise transactions gula dekhaw", _history())
    prompt = build_sql_prompt(
        "client wise transactions gula dekhaw",
        "Table sales: sale_id INT, client_id INT, sale_date DATE",
        _history(),
    )

    assert "drill-down" in guidance
    assert "not a new all-data report" in prompt
    assert "SELECT clients.client_name" in prompt
    assert "ORDER BY total_sales DESC LIMIT 10" in prompt


def test_uses_older_scoped_report_when_latest_turn_is_an_unscoped_bad_drill_down():
    history = _history() + [
        {
            "user": "client wise transactions gula dekhaw",
            "assistant": "done",
            "sql": "SELECT clients.client_name, sales.sale_id FROM sales JOIN clients ON sales.client_id = clients.client_id LIMIT 100",
        }
    ]

    issues = follow_up_scope_issues(
        "individual transactions dekhao",
        history,
        "SELECT * FROM sales LIMIT 100",
    )

    assert scope_anchor_sql(history) == PREVIOUS_SQL
    assert any("top-10 cohort" in issue for issue in issues)
    assert any("month filter (5)" in issue for issue in issues)
