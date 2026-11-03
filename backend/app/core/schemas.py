from typing import Any, Literal

from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    db_type: Literal["mysql", "postgresql"] = "mysql"
    name: str = Field(default="default")
    host: str
    port: int = 3306
    database: str
    username: str
    password: str
    ssl: bool = False


class SavedDBConfig(BaseModel):
    db_type: Literal["mysql", "postgresql"] = "mysql"
    name: str = "default"
    host: str
    port: int = 3306
    database: str
    username: str
    password_encrypted: str
    ssl: bool = False


class MySQLConfig(DatabaseConfig):
    db_type: Literal["mysql"] = "mysql"


class ModelConfig(BaseModel):
    provider: Literal["llama_cpp", "gemini"] = "llama_cpp"
    model_path: str = ""
    context_window: int = Field(default=4096, ge=512, le=131072)
    temperature: float = Field(default=0.2, ge=0, le=2)
    max_tokens: int = Field(default=768, ge=64, le=65536)
    gemini_model: str = "gemini-3.6-flash"
    gemini_api_key: str = ""

    def __repr_args__(self):
        return [(name, value) for name, value in super().__repr_args__() if name != "gemini_api_key"]


class SavedModelConfig(BaseModel):
    provider: Literal["llama_cpp", "gemini"] = "llama_cpp"
    model_path: str = ""
    context_window: int = 4096
    temperature: float = 0.2
    max_tokens: int = 768
    gemini_model: str = "gemini-3.6-flash"
    gemini_api_key_encrypted: str = ""


class PublicModelConfig(BaseModel):
    provider: Literal["llama_cpp", "gemini"] = "llama_cpp"
    model_path: str = ""
    context_window: int = 4096
    temperature: float = 0.2
    max_tokens: int = 768
    gemini_model: str = "gemini-3.6-flash"
    gemini_api_key: str = ""
    api_key_configured: bool = False


class GoogleModelsRequest(BaseModel):
    gemini_api_key: str = ""

    def __repr_args__(self):
        return [(name, value) for name, value in super().__repr_args__() if name != "gemini_api_key"]


class SQLGeneration(BaseModel):
    sql: str
    answer_language: str = "english"
    report_title: str = "database_report"


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool
    primary_key: bool = False
    foreign_key: str | None = None
    comment: str | None = None


class TableInfo(BaseModel):
    name: str
    columns: list[ColumnInfo]
    object_type: Literal["table", "view"] = "table"
    comment: str | None = None


class SchemaSnapshot(BaseModel):
    database: str
    tables: list[TableInfo]


class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "default"
    preview_limit: int = 100


class ChatResponse(BaseModel):
    answer: str
    sql: str | None = None
    columns: list[str] = []
    rows: list[dict[str, Any]] = []
    csv_url: str | None = None
    excel_url: str | None = None
    report_title: str | None = None
    database: str


class DatabaseActivateRequest(BaseModel):
    database: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_$]+$")
