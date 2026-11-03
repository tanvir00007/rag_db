import json

from app.llm.follow_up import follow_up_guidance


SYSTEM_PROMPT = """You are a database analyst chatbot.
You answer Bangla, English, Banglish, and mixed Bangla-English.
Generate only safe read-only {dialect} SQL. Use functions and date syntax valid for {dialect}.
When a query joins tables, always qualify column names with table names.
For follow-up requests, preserve prior date, entity, and ranked/top-N scope unless the latest message explicitly changes it.
The latest message overrides only the metrics, grouping, or filters it explicitly changes.
When the user asks for transactions/details after an aggregate report, drill into the previous result cohort rather than all rows.
If the user asks for customer count, use COUNT(DISTINCT customer/client id), not sales amount.
If the user says they do not want sales, do not include SUM(total_amount).
Return an object with keys: sql, answer_language, report_title.
Do not include markdown."""


def model_safe_history(history: list[dict], max_turns: int = 8) -> list[dict[str, str | None]]:
    """Keep only conversation fields intentionally allowed to reach a model provider."""
    safe: list[dict[str, str | None]] = []
    for turn in history[-max_turns:]:
        safe.append(
            {
                "user": _bounded_text(turn.get("user")),
                "assistant": _bounded_text(turn.get("assistant")),
                "sql": _bounded_text(turn.get("sql")),
            }
        )
    return safe


def build_sql_prompt(
    user_message: str,
    schema_text: str,
    history: list[dict],
    repair_context: str | None = None,
    dialect: str = "MySQL",
) -> str:
    safe_history = model_safe_history(history)
    guidance = follow_up_guidance(user_message, history)
    return f"""{SYSTEM_PROMPT.format(dialect=dialect)}

Schema metadata:
{schema_text}

Recent conversation:
{json.dumps(safe_history, ensure_ascii=False)}

{guidance}

User request:
{user_message}

{f"SQL repair context:\n{repair_context}" if repair_context else ""}

JSON:"""


def _bounded_text(value: object, limit: int = 4000) -> str | None:
    if value is None:
        return None
    return str(value)[:limit]
