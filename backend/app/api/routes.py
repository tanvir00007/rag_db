from pathlib import Path
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.core.config_store import (
    load_database_config,
    public_db_config,
    public_model_config,
    resolve_model_config,
    save_model_config,
    save_database_config,
)
from app.core.schemas import (
    ChatRequest,
    ChatResponse,
    DatabaseActivateRequest,
    GoogleModelsRequest,
    ModelConfig,
    DatabaseConfig,
)
from app.core.settings import settings
from app.db.database import (
    create_database_engine,
    dialect_name,
    execute_query,
    introspect_schema,
    list_databases,
    schema_to_text,
    test_connection,
)
from app.llm.gemini import ModelProviderError, list_gemini_models
from app.llm.follow_up import follow_up_repair_context, follow_up_scope_issues
from app.llm.provider import generate_sql_json, test_model_config
from app.memory.store import append_turn, load_history
from app.reports.exporter import export_report
from app.sql_agent.validator import add_limit_if_missing, validate_read_only_sql

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/db/test")
def test_db(config: DatabaseConfig) -> dict:
    try:
        test_connection(config)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/db/save")
def save_db(config: DatabaseConfig) -> dict:
    try:
        test_connection(config)
        saved = save_database_config(config)
        return {"ok": True, "db_type": saved.db_type, "name": saved.name}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/db/active")
def active_db() -> dict:
    return {"config": public_db_config()}


@router.get("/db/databases")
def databases() -> dict:
    config = load_database_config()
    if not config:
        raise HTTPException(status_code=400, detail="No database connection is configured.")
    try:
        return {"databases": list_databases(config), "active_database": config.database}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not list accessible databases: {exc}") from exc


@router.post("/db/activate")
def activate_database(request: DatabaseActivateRequest) -> dict:
    current = load_database_config()
    if not current:
        raise HTTPException(status_code=400, detail="Save a database connection before selecting a database.")
    try:
        available = list_databases(current)
        if request.database not in available:
            raise HTTPException(status_code=404, detail="That database is not accessible with the saved connection.")
        candidate = current.model_copy(update={"database": request.database})
        test_connection(candidate)
        save_database_config(candidate)
        return {"ok": True, "database": request.database}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not activate database: {exc}") from exc


@router.get("/db/schema")
def get_schema() -> dict:
    config = load_database_config()
    if not config:
        raise HTTPException(status_code=400, detail="No database connection is configured.")
    engine = create_database_engine(config)
    try:
        return introspect_schema(engine, config.database, config.db_type).model_dump()
    finally:
        engine.dispose()


@router.post("/model/save")
def save_model(config: ModelConfig) -> dict:
    resolved = resolve_model_config(config)
    if resolved.provider == "gemini" and not resolved.gemini_api_key.strip():
        raise HTTPException(status_code=400, detail="Enter or save a Gemini API key first.")
    saved = save_model_config(config)
    return {"ok": True, "provider": saved.provider}


@router.get("/model/active")
def active_model() -> dict:
    return {"config": public_model_config().model_dump()}


@router.post("/model/test")
def test_model(config: ModelConfig) -> dict:
    try:
        test_model_config(config)
        return {"ok": True}
    except ModelProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/model/google/models")
def google_models(request: GoogleModelsRequest) -> dict:
    config = resolve_model_config(ModelConfig(provider="gemini", gemini_api_key=request.gemini_api_key))
    try:
        return {"models": list_gemini_models(config.gemini_api_key)}
    except ModelProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    config = load_database_config()
    if not config:
        raise HTTPException(status_code=400, detail="Configure a database first.")

    engine = create_database_engine(config)
    try:
        schema = introspect_schema(engine, config.database, config.db_type)
        dialect = dialect_name(config)
        schema_text = schema_to_text(schema, dialect)
        memory_namespace = f"{config.db_type}-{config.database}"
        history = load_history(request.conversation_id, namespace=memory_namespace)
        model_json, sql = _generate_scoped_sql(
            request.message,
            schema_text,
            history,
            request.preview_limit,
            dialect,
        )
        try:
            columns, rows = execute_query(engine, sql, request.preview_limit)
        except Exception as first_error:
            repair_context = (
                f"The previous SQL failed. Generate corrected {dialect} SQL only in JSON. "
                "Use table-qualified columns for joins. "
                f"Failed SQL: {sql}. {_safe_database_error(first_error)}"
            )
            model_json = generate_sql_json(request.message, schema_text, history, repair_context, dialect=dialect)
            raw_sql = str(model_json.get("sql", ""))
            sql = _prepare_sql(raw_sql, request.message, request.preview_limit)
            remaining_issues = follow_up_scope_issues(request.message, history, sql)
            if remaining_issues:
                raise ModelProviderError(
                    "I could not preserve the previous report scope in the repaired SQL. Please make the follow-up scope explicit.",
                    status_code=422,
                )
            columns, rows = execute_query(engine, sql, request.preview_limit)
        title = model_json.get("report_title") or "database_report"
        csv_url, excel_url = export_report(rows, title)
        answer = _compose_answer(request.message, rows, sql)
        append_turn(request.conversation_id, request.message, answer, sql, namespace=memory_namespace)
        return ChatResponse(
            answer=answer,
            sql=sql,
            columns=columns,
            rows=rows,
            csv_url=csv_url,
            excel_url=excel_url,
            report_title=title,
            database=config.database,
        )
    except ModelProviderError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        engine.dispose()


def _prepare_sql(raw_sql: str, message: str, limit: int) -> str:
    sql = validate_read_only_sql(raw_sql)
    sql = _clean_customer_count_followup(sql, message)
    return add_limit_if_missing(sql, limit)


def _generate_scoped_sql(
    message: str,
    schema_text: str,
    history: list[dict],
    preview_limit: int,
    dialect: str = "MySQL",
) -> tuple[dict, str]:
    model_json = generate_sql_json(message, schema_text, history, dialect=dialect)
    sql = _prepare_sql(str(model_json.get("sql", "")), message, preview_limit)
    issues = follow_up_scope_issues(message, history, sql)
    if not issues:
        return model_json, sql

    repair_context = follow_up_repair_context(message, history, issues)
    model_json = generate_sql_json(message, schema_text, history, repair_context, dialect=dialect)
    sql = _prepare_sql(str(model_json.get("sql", "")), message, preview_limit)
    remaining_issues = follow_up_scope_issues(message, history, sql)
    if remaining_issues:
        raise ModelProviderError(
            "I could not safely preserve the previous report scope. Please mention the date range and client cohort explicitly.",
            status_code=422,
        )
    return model_json, sql


def _clean_customer_count_followup(sql: str, message: str) -> str:
    lowered = message.lower()
    wants_customer_count = any(token in lowered for token in ["customer er count", "customer count", "client count"])
    rejects_sales = any(token in lowered for token in ["sales chai na", "sales na", "not sales", "no sales"])
    if not wants_customer_count:
        return sql

    cleaned = re.sub(
        r"COUNT\s*\(\s*(?:DISTINCT\s+)?client_id\s*\)",
        "COUNT(DISTINCT clients.client_id)",
        sql,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"COUNT\s*\(\s*(?:DISTINCT\s+)?customer_id\s*\)",
        "COUNT(DISTINCT clients.client_id)",
        cleaned,
        flags=re.IGNORECASE,
    )
    if rejects_sales:
        cleaned = re.sub(
            r",\s*SUM\s*\(\s*(?:sales\.)?total_amount\s*\)\s+AS\s+\w+",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
    return cleaned


def _compose_answer(message: str, rows: list[dict], sql: str) -> str:
    bangla_chars = any("\u0980" <= ch <= "\u09ff" for ch in message)
    if bangla_chars:
        return f"আমি query চালিয়েছি এবং {len(rows)}টি row preview করেছি। নিচে result preview ও download option আছে।"
    if any(token in message.lower() for token in ["dekhao", "koro", "dao", "er "]):
        return f"Query run kora hoyeche. {len(rows)} ta row preview dekhacchi, download option niche ache."
    return f"I ran the query and prepared a preview with {len(rows)} rows. Download options are available below."


def _safe_database_error(exc: Exception) -> str:
    """Return repair context without forwarding arbitrary driver messages to a cloud model."""
    original = getattr(exc, "orig", exc)
    args = getattr(original, "args", ())
    code = args[0] if args and isinstance(args[0], int) else None
    if code is not None:
        return f"The database rejected it with database error code {code}."
    return "The database rejected it. Re-check tables, columns, aliases, joins, and SQL syntax."


@router.get("/reports/{filename}")
def download_report(filename: str) -> FileResponse:
    path = Path(settings.exports_dir) / filename
    if not path.exists() or path.parent != settings.exports_dir:
        raise HTTPException(status_code=404, detail="Report not found.")
    return FileResponse(path)
