from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key: str = ""
    judge_model: str = "gpt-4o"
    extraction_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    retrieval_top_k: int = 5
    retrieval_min_similarity: float = 0.30
    sqlite_path: str = "./data/northwind.db"
    chroma_path: str = "./data/chroma"
    policies_dir: str = "./policies"
    submissions_dir: str = "./submissions"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def ensure_data_dirs(settings: Settings) -> None:
    Path("data").mkdir(parents=True, exist_ok=True)
    Path(settings.chroma_path).mkdir(parents=True, exist_ok=True)
