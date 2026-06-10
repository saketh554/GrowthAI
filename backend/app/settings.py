from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    judge_model: str = "gpt-4o"
    extraction_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    openai_timeout_seconds: float = 30.0
    openai_max_retries: int = 2
    retrieval_top_k: int = 5
    retrieval_min_similarity: float = 0.30
    upload_max_file_size_mb: int = 15
    upload_allowed_extensions: str = ".pdf,.png,.jpg,.jpeg,.txt"
    sqlite_path: str = "./data/northwind.db"
    chroma_path: str = "./data/chroma"
    policies_dir: str = "./data/policies"
    submissions_dir: str = "./data/submissions"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def ensure_data_dirs(settings: Settings) -> None:
    Path("data").mkdir(parents=True, exist_ok=True)
    Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
