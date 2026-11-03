from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Local RAG DB Chatbot"
    data_dir: Path = Path(__file__).resolve().parents[3] / "data"
    configs_dir: Path = data_dir / "configs"
    exports_dir: Path = data_dir / "exports"
    memory_dir: Path = data_dir / "memory"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()

