import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.settings import settings


def _conversation_path(conversation_id: str, namespace: str = "default") -> Path:
    safe_id = "".join(ch for ch in conversation_id if ch.isalnum() or ch in ("-", "_")) or "default"
    safe_namespace = "".join(ch for ch in namespace if ch.isalnum() or ch in ("-", "_")) or "default"
    settings.memory_dir.mkdir(parents=True, exist_ok=True)
    namespace_dir = settings.memory_dir / safe_namespace
    namespace_dir.mkdir(parents=True, exist_ok=True)
    return namespace_dir / f"{safe_id}.json"


def load_history(conversation_id: str, max_turns: int = 8, namespace: str = "default") -> list[dict]:
    path = _conversation_path(conversation_id, namespace)
    if not path.exists():
        return []
    history = json.loads(path.read_text(encoding="utf-8"))
    return history[-max_turns:]


def append_turn(
    conversation_id: str,
    user_message: str,
    assistant_answer: str,
    sql: str | None,
    namespace: str = "default",
) -> None:
    path = _conversation_path(conversation_id, namespace)
    history = load_history(conversation_id, max_turns=100, namespace=namespace)
    history.append(
        {
            "at": datetime.now(timezone.utc).isoformat(),
            "user": user_message,
            "assistant": assistant_answer,
            "sql": sql,
        }
    )
    path.write_text(json.dumps(history, indent=2, ensure_ascii=False), encoding="utf-8")
